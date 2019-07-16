# Synchronization module for aerobia.ru
# (c) 2018 Anton Ashmarin, aashmarin@gmail.com
from tapiriik.database import db
from tapiriik.services.service_base import ServiceAuthenticationType, ServiceBase
from tapiriik.services.service_record import ServiceRecord
from tapiriik.services.interchange import UploadedActivity, ActivityType, ActivityStatistic, ActivityStatisticUnit, Waypoint, Location, Lap
from tapiriik.services.api import APIException, UserException, UserExceptionType, APIExcludeActivity
from tapiriik.services.tcx import TCXIO
from tapiriik.services.sessioncache import SessionCache

from lxml import etree
from bs4 import BeautifulSoup

import requests
import logging
import re
import os
import pytz
import time

from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class AerobiaService(ServiceBase):
    ID = "aerobia"
    DisplayName = "Aerobia"
    DisplayAbbreviation = "ARB"
    AuthenticationType = ServiceAuthenticationType.UsernamePassword
    RequiresExtendedAuthorizationDetails = True
    UserProfileURL = "https://www.old15.aerobia.ru/users/{0}"
    UserActivityURL = "https://www.old15.aerobia.ru/users/{0}/workouts/{1}"
    
    Configurable = True
    ConfigurationDefaults = {}

    # notes longer than this number by default considered as reports and being saved separatelly
    REPORT_MIN_LIMIT = 1000

    # common -> aerobia (garmin tcx sport names)
    # todo may better to include this into tcxio logic instead
    _activityMappings = {
        ActivityType.Running : "Running",
        ActivityType.Cycling : "Biking",
        ActivityType.MountainBiking : "Mountain biking",
        ActivityType.Walking : "Walking",
        ActivityType.Hiking : "Hiking",
        ActivityType.DownhillSkiing : "Skiing downhill",
        ActivityType.CrossCountrySkiing : "Cross country skiing",
        ActivityType.Snowboarding : "Snowboard",
        ActivityType.Skating : "Skating",
        ActivityType.Swimming : "Swimming",
        #ActivityType.Wheelchair : "Wheelchair",
        ActivityType.Rowing : "Rowing",
        ActivityType.Elliptical : "Ellips",
        ActivityType.Gym : "Gym",
        ActivityType.Climbing : "Rock climbing",
        ActivityType.RollerSkiing : "Roller skiing",
        ActivityType.StrengthTraining : "Ofp",
        ActivityType.Other : "Sport",
        ActivityType.RollerSkating : "Roller Skating",
        ActivityType.Report : "Report"
    }

    # aerobia -> common
    _reverseActivityMappings = {
        1 : ActivityType.Cycling,
        2 : ActivityType.Running,
        56 : ActivityType.MountainBiking,
        19 : ActivityType.Walking,
        43 : ActivityType.Hiking,
        9 : ActivityType.DownhillSkiing,
        3 : ActivityType.CrossCountrySkiing,
        46 : ActivityType.Skating,
        21 : ActivityType.Swimming,
        13 : ActivityType.Rowing,
        74 : ActivityType.Elliptical,
        54 : ActivityType.Gym,
        63 : ActivityType.Climbing,
        72 : ActivityType.StrengthTraining,

        6 : ActivityType.Cycling, #cycling transport
        22 : ActivityType.Cycling, #indoor cycling
        73 : ActivityType.Gym, #stretching
        76 : ActivityType.Gym, #trx
        83 : ActivityType.CrossCountrySkiing, #classic skiing
        65 : ActivityType.Other, #triathlon
        51 : ActivityType.Other, #beach volleyball
        53 : ActivityType.Other, #basketball
        55 : ActivityType.RollerSkating, #roller sport
        77 : ActivityType.Running, #tredmill
        66 : ActivityType.Other, #roller skiing
        7 : ActivityType.RollerSkating, #rollers
        58 : ActivityType.Other, #nordic walking
        10 : ActivityType.Other, #snowboarding
        16 : ActivityType.Other, #walking sport
        18 : ActivityType.Other, #orienting
        38 : ActivityType.Other, #OTHER
        61 : ActivityType.Other, #WATER AEROBICS
        79 : ActivityType.Other, #ACROBATICS
        23 : ActivityType.Gym, #AEROBICS
        26 : ActivityType.Other, #BOX
        84 : ActivityType.Cycling, #CYCLOCROSS
        24 : ActivityType.Other, #BADMINTON
        52 : ActivityType.Other, #VOLLEYBALL
        50 : ActivityType.Other, #MARTIAL ARTS
        49 : ActivityType.Other, #HANDBALL
        48 : ActivityType.Gym, #GYMNASTICS
        4 : ActivityType.Other, #GOLF
        36 : ActivityType.Other, #SCUBA DIVING
        85 : ActivityType.Other, #DUATHLON
        69 : ActivityType.Other, #DELTAPLAN
        47 : ActivityType.Yoga, #YOGA
        45 : ActivityType.Other, #KITEBOARDING
        80 : ActivityType.Other, #KERLING
        62 : ActivityType.Other, #HORSE RIDING
        71 : ActivityType.Crossfit, #СROSSFIT
        64 : ActivityType.Other, #CIRCLE WORKOUT
        78 : ActivityType.Other, #MOTORSPORT
        44 : ActivityType.Other, #ММА
        70 : ActivityType.Other, #PARAPLANE
        35 : ActivityType.Gym, #PILATES
        20 : ActivityType.Other, #POLO
        33 : ActivityType.Other, #RUGBY
        60 : ActivityType.Other, #FISHING
        67 : ActivityType.Other, #SCOOTER
        15 : ActivityType.Other, #WINDSURFING
        42 : ActivityType.Other, #SQUASH
        41 : ActivityType.Other, #SKATEBOARD
        75 : ActivityType.Stepper, #STEPPER
        29 : ActivityType.Other, #DANCING
        40 : ActivityType.Other, #TENNIS
        37 : ActivityType.Other, #TABLE TENNIS
        81 : ActivityType.Other, #OUTDOOR FITNESS
        31 : ActivityType.Soccer, #FOOTBALL
        59 : ActivityType.Other, #FENCING
        39 : ActivityType.Other, #FIGURE SKATING
        34 : ActivityType.Other, #HOCKEY
        82 : ActivityType.Other, #CHESS

        68 : ActivityType.Other
    }

    SupportedActivities = list(_activityMappings.keys())

    SupportsHR = SupportsCadence = True

    SupportsActivityDeletion = True

    _sessionCache = SessionCache("aerobia", lifetime=timedelta(minutes=120), freshen_on_get=False)
    _obligatory_headers = {
        # Without user-agent patch aerobia requests doesn't work
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64; Trident/7.0; rv:11.0) like Gecko"
    }

    _urlRoot = "https://old15.aerobia.ru/"
    _apiRoot = "https://old15.aerobia.ru/api/"
    _loginUrlRoot = _apiRoot + "sign_in"
    _workoutsUrl = _apiRoot + "workouts"
    _workoutUrlJson = _apiRoot + "workouts/{id}.json"
    _workoutUrl = _urlRoot + "workouts/{id}"
    _uploadsUrl = _apiRoot + "uploads.json"
    _postsUrl = _apiRoot + "my/posts"
    _postUrlJson = _apiRoot + "posts/{id}.json"

    def _get_session(self, record=None, username=None, skip_cache=False):
        if not skip_cache:
            cached = self._sessionCache.Get(record.ExternalID if record else username)
            if cached:
                logger.debug("Using cached credential")
                return cached

        session = requests.Session()
        session.headers.update(self._obligatory_headers)

        return session

    def _get_auth_data(self, record=None, username=None, password=None):
        from tapiriik.auth.credential_storage import CredentialStore

        if record:
            #  longing for C style overloads...
            password = CredentialStore.Decrypt(record.ExtendedAuthorization["Password"])
            username = CredentialStore.Decrypt(record.ExtendedAuthorization["Email"])

        session = self._get_session(record, username, skip_cache=True)
        request_parameters = {"user[email]": username, "user[password]": password}
        res = session.post(self._loginUrlRoot, data=request_parameters)

        if res.status_code != 200:
            raise APIException("Login exception {} - {}".format(res.status_code, res.text), user_exception=UserException(UserExceptionType.Authorization))

        res_xml = etree.fromstring(res.text.encode('utf-8'))

        info = res_xml.find("info")
        if info.get("status") != "ok":
            raise APIException(info.get("description"), user_exception=UserException(UserExceptionType.Authorization))

        user_id = int(res_xml.find("user/id").get("value"))
        user_token = res_xml.find("user/authentication_token").get("value")

        # Not really need to cache sessions for aerobia
        #self._sessionCache.Set(record.ExternalID if record else username, session)

        return user_id, user_token

    def _safe_call(self, serviceRecord, method, endpoint, params={}, files=None, retry_count=3):
        resp = None
        for i in range(0, retry_count):
            try:
                session = self._get_session(serviceRecord)
                if method == "get":
                    resp = session.get(endpoint, params=self._with_auth(serviceRecord, params))
                elif method == "post":
                    resp = session.post(endpoint, data=self._with_auth(serviceRecord, params), files=files)
                else:
                    raise APIException("Unsupported method: {}".format(method), user_exception=UserException(UserExceptionType.Other))

                if resp.status_code == 200:
                    # For some reason aerobia api always return 200 instead of 401
                    if "/users/sign_up" not in resp.text and "неверный ключ аутентификации" not in resp.text.lower():
                        break
                # most likely token or session expired.
                self._refresh_token(serviceRecord)
            except (requests.exceptions.ConnectionError, requests.exceptions.ConnectTimeout) as ex:
                # Aerobia sometimes answer like
                # "Remote end closed connection without response"
                # "Failed to establish a new connection: [WinError 10060]"
                # wait a bit and retry
                time.sleep(.2)
        if resp is None:
            raise APIException("Connectivity issues")
        return resp

    def _refresh_token(self, record):
        logger.info("refreshing auth token")
        user_id, user_token = self._get_auth_data(record=record)
        auth_datails = {"OAuthToken": user_token}
        record.Authorization.update(auth_datails)
        db.connections.update({"_id": record._id}, {"$set": {"Authorization": auth_datails}})

    def _should_load_media_only(self, serviceRecord):
        return serviceRecord.Config["export"]["upload_media_content"] if "export" in serviceRecord.Config else False

    def _get_min_report_length(self, serviceRecord):
        return serviceRecord.Config["export"]["min_report_length"] if "export" in serviceRecord.Config else self.REPORT_MIN_LIMIT

    def _with_auth(self, record, params={}):
        params.update({"authentication_token": record.Authorization["OAuthToken"]})
        return params

    def Authorize(self, username, password):
        from tapiriik.auth.credential_storage import CredentialStore
        user_id, user_token = self._get_auth_data(username=username, password=password)

        secret = {
            "Email": CredentialStore.Encrypt(username), 
            "Password": CredentialStore.Encrypt(password)
            }
        authorizationData = {"OAuthToken": user_token}
        
        return (user_id, authorizationData, secret)

    def DownloadActivityList(self, serviceRecord, exhaustive=False):
        activities = []
        exclusions = []

        total_pages = None
        page = 1
        while True:
            diary_xml = self._get_diary_xml(serviceRecord, self._workoutsUrl, page)

            for workout_info in diary_xml.findall("workouts/r"):
                activity = self._create_activity(workout_info)
                activities.append(activity)

            if total_pages is None:
                pagination = diary_xml.find("pagination")
                # New accounts have no data pages initially
                total_pages_str = pagination.get("total_pages") if pagination is not None else None
                total_pages = int(total_pages_str) if total_pages_str else 1
            page += 1

            if not exhaustive or page > total_pages:
                break

        page = 1
        has_more = True
        while has_more:
            feed_xml = self._get_diary_xml(serviceRecord, self._postsUrl, page)

            for post_info in feed_xml.findall("posts/r"):
                activity = self._create_post(post_info)
                activities.append(activity)

            pagination = feed_xml.find("pagination")
            has_more = pagination.get("more") == "true" if pagination is not None else False
            page += 1

            if not exhaustive:
                break

        return activities, exclusions

    def _get_diary_xml(self, serviceRecord, endpoint, page=1):
        diary_data = self._safe_call(serviceRecord, "get", endpoint, {"page": page})
        diary_xml = etree.fromstring(diary_data.text.encode('utf-8'))

        info = diary_xml.find("info")
        if info.get("status") != "ok":
            raise APIException(info.get("description"), user_exception=UserException(UserExceptionType.DownloadError))

        return diary_xml

    def _create_post(self, data):
        post = UploadedActivity()
        post.Type = ActivityType.Report
        post.Stationary = True

        post_xml = data.find("post")

        post.Name = post_xml.get("title")
        post.NotesExt = post_xml.get("formatted_body")
        post.StartTime = pytz.utc.localize(datetime.strptime(post_xml.get("created_at"), "%Y-%m-%dT%H:%M:%SZ"))
        #need to set EndTime for consistency
        post.EndTime = post.StartTime

        post.ServiceData = {"ActivityID": post_xml.get("id")}

        if int(post_xml.get("photos_count")) > 0:
            for photo_xml in data.findall("photos/photo"):
                post.PhotoUrls.append({"id": photo_xml.get("id"), "url": photo_xml.get("image_original")})

        logger.debug("\tPost s/t {}: {}".format(post.StartTime, post.Type))
        post.CalculateUID()
        return post

    def _create_activity(self, data):
        activity = UploadedActivity()
        activity.Name = data.get("name")
        activity.StartTime = pytz.utc.localize(datetime.strptime(data.get("start_at"), "%Y-%m-%dT%H:%M:%SZ"))
        activity.EndTime = activity.StartTime + timedelta(0, float(data.get("duration")))
        sport_id = data.get("sport_id")
        activity.Type = self._reverseActivityMappings.get(int(sport_id), ActivityType.Other) if sport_id else ActivityType.Other

        distance = data.get("distance")
        activity.Stats.Distance = ActivityStatistic(ActivityStatisticUnit.Kilometers, value=float(distance) if distance else None)
        activity.Stats.MovingTime = ActivityStatistic(ActivityStatisticUnit.Seconds, value=float(data.get("total_time_in_seconds")))
        avg_speed = data.get("average_speed")
        max_speed = data.get("max_speed")
        activity.Stats.Speed = ActivityStatistic(ActivityStatisticUnit.KilometersPerHour, avg=float(avg_speed) if avg_speed else None, max=float(max_speed) if max_speed else None)
        avg_hr = data.get("average_heart_rate")
        max_hr = data.get("maximum_heart_rate")
        activity.Stats.HR.update(ActivityStatistic(ActivityStatisticUnit.BeatsPerMinute, avg=float(avg_hr) if avg_hr else None, max=float(max_hr) if max_hr else None))
        calories = data.get("calories")
        activity.Stats.Energy = ActivityStatistic(ActivityStatisticUnit.Kilocalories, value=int(calories) if calories else None)

        activity.ServiceData = {"ActivityID": data.get("id")}

        logger.debug("\tActivity s/t {}: {}".format(activity.StartTime, activity.Type))
        activity.CalculateUID()
        return activity

    def DownloadActivity(self, serviceRecord, activity):
        activity_id = activity.ServiceData["ActivityID"]

        load_media_only = self._should_load_media_only(serviceRecord)
        min_report_length = self._get_min_report_length(serviceRecord)

        # reports already contains all data
        if activity.Type == ActivityType.Report:
            # ignore short posts without photos
            if not len(activity.PhotoUrls) and len(activity.NotesExt) < min_report_length:
                activity.Ignore = True
            return activity

        # Obtain more information about activity
        res = self._safe_call(serviceRecord, "get", self._workoutUrlJson.format(id=activity_id))
        activity_data = res.json()
        
        if "photos" not in activity_data["post"] and load_media_only:
            # Ignore activities without media
            activity.Ignore = True
            return activity

        tcx_data = self._safe_call(serviceRecord, "get", "{}export/workouts/{}/tcx".format(self._urlRoot, activity_id))
        try:
            activity_ex = TCXIO.Parse(tcx_data.text.encode('utf-8'), activity)
        except:
            logger.debug("Unable to parse activity tcx: data corrupted")
            raise APIException("Unable to parse activity tcx: data corrupted")

        activity_ex.Name = activity_data["name"] if "name" in activity_data else ""

        if "photos" in activity_data["post"]:
            for img_info in activity_data["post"]["photos"]:
                activity_ex.PhotoUrls.append({"id": img_info["id"], "url": img_info["original"]})
        # Notes comes as html. Hardly any other service will support this so needs to extract text data
        if "body" in activity_data["post"]:
            post_html = activity_data["post"]["body"]
            soup = BeautifulSoup(post_html)
            # Notes also contains styles, get rid of them
            for style in soup("style"):
                style.decompose()
            activity_ex.Notes = soup.getText()
            # all notes with photos considered as reports
            if len(activity_ex.Notes) < min_report_length:
                if len(activity_ex.PhotoUrls):
                    activity_ex.NotesExt = soup.prettify()
                elif load_media_only:
                    # ignore activities with a very short notes
                    activity_ex.Ignore = True

        # Dirty hack to patch users inventory even if they use aerobia mobile app to record activities
        # Still need to sync with some service though.
        # TODO should driven by setting
        #extra_data = {}
        #self._put_default_inventory(activity, serviceRecord, extra_data)
        #if extra_data:
        #    self._patch_activity(serviceRecord, extra_data, activity_id)

        return activity_ex

    def UploadActivity(self, serviceRecord, activity):
        tcx_data = None
        # If some service provides ready-to-use tcx data why not to use it?
        if "tcx" in activity.PrerenderedFormats:
            tcx_data = activity.PrerenderedFormats["tcx"]
            # Set aerobia-understandable sport name
            tcx_data = re.sub(r'(Sport=\")[\w\s]+(\">)', r'\1{}\2'.format(self._activityMappings[activity.Type]), tcx_data) if tcx_data else None
        if not tcx_data:
            tcx_data =  TCXIO.Dump(activity, self._activityMappings[activity.Type])
        
        # Aerobia support activity names not longer than 60 characters
        activity_name = activity.Name[:60] if activity.Name else None

        data = {"name": activity_name,
                "description": activity.Notes}
        files = {"file": ("tap-sync-{}-{}.tcx".format(os.getpid(), activity.UID), tcx_data)}
        res = self._safe_call(serviceRecord, "post", self._uploadsUrl, data, files)
        res_obj = res.json()
        uploaded_id = res_obj["workouts"][0]["id"]

        if "error" in res_obj:
            raise APIException(res_obj["error"], user_exception=UserException(UserExceptionType.UploadError))
        
        extra_data = {}
        if activity_name:
            extra_data.update({"workout[name]": activity_name})
        
        self._put_default_inventory(activity, serviceRecord, extra_data)

        # Post extra data to newly uploaded activity
        if extra_data:
            self._patch_activity(serviceRecord, extra_data, uploaded_id)

        # return just uploaded activity id
        return uploaded_id

    def _put_default_inventory(self, activity, serviceRecord, data):
        rules = serviceRecord.Config["gearRules"] if "gearRules" in serviceRecord.Config else None
        if rules is None:
            return
        inventory = []
        for rule in rules:
            if "sport" in rule and "gear" in rule:
                if activity.Type == rule["sport"]:
                    inventory += rule["gear"]
        if len(inventory):
            data.update({"workout[inventory_ids][]": inventory})

    def _patch_activity(self, serviceRecord, data, activity_id):
        data.update({"_method": "put"})
        try:
            self._safe_call(serviceRecord, "post", self._workoutUrl.format(id=activity_id), data)
        except Exception as e:
            # do nothing but logging - anything critical happened to interrupt process
            logger.debug("Unable to patch activity: " + e)

    def UserUploadedActivityURL(self, uploadId):
        raise NotImplementedError
        # TODO need to include user id
        #return self.UserActivityURL.format(userId, uploadId)

    def DeleteActivity(self, serviceRecord, uploadId):
        delete_parameters = {"_method" : "delete"}
        self._safe_call(serviceRecord, "post", "{}workouts/{}".format(self._urlRoot, uploadId), delete_parameters)

    def DeleteCachedData(self, serviceRecord):
        pass  # No cached data...

    def RevokeAuthorization(self, serviceRecord):
        # nothing to do here...
        pass
