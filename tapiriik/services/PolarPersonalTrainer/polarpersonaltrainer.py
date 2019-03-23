# Synchronization module for polarpersonaltrainer.com
# (c) 2018 Anton Ashmarin, aashmarin@gmail.com
from tapiriik.services.service_base import ServiceAuthenticationType, ServiceBase
from tapiriik.services.api import APIException, UserException, UserExceptionType
from tapiriik.services.interchange import UploadedActivity, ActivityType, ActivityStatistic, ActivityStatisticUnit
from tapiriik.services.tcx import TCXIO
from tapiriik.services.sessioncache import SessionCache
from tapiriik.services.PolarPersonalTrainer.pptToTcx import convert

from datetime import date, datetime, timedelta
from django.core.urlresolvers import reverse
from bs4 import BeautifulSoup

import logging
import pytz
import requests

logger = logging.getLogger(__name__)

class PolarPersonalTrainerService(ServiceBase):
    ID = "polarpersonaltrainer"
    DisplayName = "Polar Personal Trainer"
    DisplayAbbreviation = "PPT"
    AuthenticationType = ServiceAuthenticationType.UsernamePassword
    RequiresExtendedAuthorizationDetails = True

    # Will be retired by the end of 2019. Only need to transfer data to another services.
    ReceivesActivities = False 

    _sessionCache = SessionCache("polarpersonaltrainer", lifetime=timedelta(minutes=30), freshen_on_get=False)

    # PPT - common
    # due to we can actually put any sport name in PPT detect some wery common as well as types I personally have
    # cycling # means different bike presets, hope 4 will cover most cases
    _reverseActivityMappings = {
        "cycling" : ActivityType.Cycling,
        "cycling 2" : ActivityType.Cycling,
        "cycling 3" : ActivityType.Cycling,
        "cycling 4" : ActivityType.Cycling,
        "road biking" : ActivityType.Cycling,
        "running" : ActivityType.Running,
        "indoor running" : ActivityType.Running,
        "mtb" : ActivityType.MountainBiking,
        "mountain biking" : ActivityType.MountainBiking,
        "walking" : ActivityType.Walking,
        "skiing" : ActivityType.CrossCountrySkiing,
        "swimming" : ActivityType.Swimming,
        "ows" : ActivityType.Swimming,
        "other sport": ActivityType.Other
    }

    def _get_session(self, record=None, username=None, password=None, skip_cache=False):
        from tapiriik.auth.credential_storage import CredentialStore
        cached = self._sessionCache.Get(record.ExternalID if record else username)
        if cached and not skip_cache:
            logger.debug("Using cached credential")
            return cached
        if record:
            #  longing for C style overloads...
            password = CredentialStore.Decrypt(record.ExtendedAuthorization["Password"])
            username = CredentialStore.Decrypt(record.ExtendedAuthorization["Email"])

        session = requests.Session()

        data = {
            "username": username,
            "password": password
        }
        params = {
            "response_type": "code",
            "client_id": "ppt_client_id",
            "redirect_uri": "https://polarpersonaltrainer.com/oauth.ftl",
            "scope": "POLAR_SSO"
        }

        preResp = session.get("https://auth.polar.com/oauth/authorize", params=params)
        if preResp.status_code != 200:
            raise APIException("SSO prestart error {} {}".format(preResp.status_code, preResp.text))

        # Extract csrf token
        bs = BeautifulSoup(preResp.text, "html.parser")
        csrftoken = bs.find("input", {"name": "_csrf"})["value"]
        data.update({"_csrf" : csrftoken})
        ssoResp = session.post("https://auth.polar.com/login", data=data)
        if ssoResp.status_code != 200 or "temporarily unavailable" in ssoResp.text:
            raise APIException("SSO error {} {}".format(ssoResp.status_code, ssoResp.text))
        
        if "error" in ssoResp.url:
            raise APIException("Login exception {}".format(ssoResp.url), user_exception=UserException(UserExceptionType.Authorization))

        # Finish auth process passing timezone
        session.get(ssoResp.url, params={"userTimezone": "-180"})

        session.get("https://polarpersonaltrainer.com/user/index.ftl")

        self._sessionCache.Set(record.ExternalID if record else username, session)

        return session

    def Authorize(self, username, password):
        from tapiriik.auth.credential_storage import CredentialStore
        self._get_session(username=username, password=password, skip_cache=True)

        return (username, {}, {"Email": CredentialStore.Encrypt(username), "Password": CredentialStore.Encrypt(password)})

    def DownloadActivityList(self, serviceRecord, exhaustive=False):
        #TODO find out polar session timeout
        session = self._get_session(serviceRecord)

        activities = []
        exclusions = []

        date_format = "{d.day}.{d.month}.{d.year}"
        end_date = datetime.now() + timedelta(days=1.5)
        start_date = date(1961, 4, 12) if exhaustive else end_date - timedelta(days=60)
        params = {
            "startDate": date_format.format(d=start_date),
            "endDate": date_format.format(d=end_date)
        }
        res = session.get("https://polarpersonaltrainer.com/user/calendar/inc/listview.ftl", params=params)

        bs = BeautifulSoup(res.text, "html.parser")
        for activity_row in bs.select("tr[class^=listRow]"):

            data_cells = activity_row.findAll("td")
            info_cell = 0
            date_cell = 4
            time_cell = 3
            result_type_cell = 5
            sport_type_cell = 6
            type_data = data_cells[info_cell].find("input", {"name": "calendarItemTypes"})
            # Skip fitness data whatever 
            if type_data["value"] == "OptimizedExercise":
                activity = UploadedActivity()

                id = data_cells[info_cell].find("input", {"name": "calendarItem"})["value"]
                name = data_cells[info_cell].find("input", {"name": "calendarItemName"})["value"]
                activity.ExternalID = id
                activity.Name = name

                time_text = "{} {}".format(data_cells[date_cell].contents[0], data_cells[time_cell].contents[0])
                activity.StartTime = pytz.utc.localize(datetime.strptime(time_text, "%d.%m.%Y %H:%M"))

                result_type_text = data_cells[result_type_cell].contents[0]
                if "Strength Training Result" in result_type_text:
                    activity.Type = ActivityType.StrengthTraining
                    # This type of activity always stationary
                    activity.Stationary = True
                else:
                    type_text = data_cells[sport_type_cell].contents[0]
                    activity.Type = self._reverseActivityMappings.get(type_text.lower(), ActivityType.Other)
                
                logger.debug("\tActivity s/t {}: {}".format(activity.StartTime, activity.Type))
                activity.CalculateUID()
                activities.append(activity)

        return activities, exclusions

    def DownloadActivity(self, serviceRecord, activity):
        session = self._get_session(serviceRecord)

        url = "https://www.polarpersonaltrainer.com/user/calendar/"
        gpxUrl = "index.gpx"
        xmlUrl = "index.jxml"

        gpx_data = {
            ".action": "gpx",
            "items.0.item": activity.ExternalID,
            "items.0.itemType": "OptimizedExercise"
        }

        xml_data = {
            ".action": "export", 
            "items.0.item": activity.ExternalID,
            "items.0.itemType": "OptimizedExercise",
            ".filename": "training.xml"
        }

        xmlResp = session.post(url + xmlUrl, data=xml_data)
        xmlText = xmlResp.text
        gpxResp = session.post(url + gpxUrl, data=gpx_data)
        if gpxResp.status_code == 401:
            logger.debug("Problem completing request. Unauthorized. Activity extId = {}".format(activity.ExternalID))
            raise APIException("Unknown authorization problem during request", user_exception=UserException(UserExceptionType.DownloadError))
        
        gpxText = gpxResp.text
        activity.GPS = not ("The items you are exporting contain no GPS data" in gpxText)

        tcxData = convert(xmlText, activity.StartTime, gpxText if activity.GPS else None)
        activity = TCXIO.Parse(tcxData, activity)

        return activity

    def RevokeAuthorization(self, serviceRecord):
        # nothing to do here...
        pass

    def DeleteCachedData(self, serviceRecord):
        # Nothing to delete
        pass

    def DeleteActivity(self, serviceRecord, uploadId):
        # Not supported
        pass

    def UploadActivity(self, serviceRecord, activity):
        # Not supported
        pass
