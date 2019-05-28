# Synchronization module for suunto
# (c) 2018 Anton Ashmarin, aashmarin@gmail.com
from tapiriik.settings import WEB_ROOT, SUUNTO_CLIENT_SECRET, SUUNTO_CLIENT_ID
from tapiriik.services.service_base import ServiceAuthenticationType, ServiceBase
from tapiriik.services.service_record import ServiceRecord
from tapiriik.services.api import APIException, UserException, UserExceptionType
from tapiriik.services.interchange import UploadedActivity, ActivityType
from tapiriik.database import db
from tapiriik.services.fit import FITIO

from django.core.urlresolvers import reverse
from urllib.parse import urlencode
from datetime import date, datetime

import logging
import requests
import time

logger = logging.getLogger(__name__)

class SuuntoService(ServiceBase):
    ID = "suunto"
    DisplayName = "Suunto"
    DisplayAbbreviation = "SU"
    AuthenticationType = ServiceAuthenticationType.OAuth
    AuthenticationNoFrame = True # form not fit in the small frame
    #TODO activity hook
    #PartialSyncRequiresTrigger = True

    ReceivesActivities = False 

    _activity_type_mappings = {
        ActivityType.Cycling: 3,
        ActivityType.MountainBiking: 10,
        ActivityType.Hiking: 11,
        ActivityType.Running: 1,
        ActivityType.Walking: 0,
        ActivityType.Snowboarding: 30,
        ActivityType.Skating: "IceSkate",
        ActivityType.CrossCountrySkiing: 3,
        ActivityType.DownhillSkiing: "AlpineSki",
        ActivityType.Swimming: 21,
        ActivityType.Gym: 23,
        ActivityType.Rowing: "Rowing",
        ActivityType.RollerSkiing: "RollerSki",
        ActivityType.StrengthTraining: "WeightTraining",
        ActivityType.Climbing: "RockClimbing",
        ActivityType.Wheelchair: "Wheelchair",
        ActivityType.Other: 4,
    }

    SupportedActivities = list(_activity_type_mappings.keys())

    _auth_api_endpoint = "https://cloudapi-oauth.suunto.com/"
    _api_endpoint = "https://cloudapi.suunto.com/v2/"

    def _getRedirectUri(self):
        return WEB_ROOT + reverse("oauth_return", kwargs={"service": "suunto"})

    def _requestWithAuth(self, reqLambda, serviceRecord):
        session = requests.Session()

        if time.time() > serviceRecord.Authorization.get("AccessTokenExpiresIn", 0) - 60:
            # Expired access token.
            refreshToken = serviceRecord.Authorization.get("RefreshToken")
            post_data = {
                'grant_type': 'refresh_token',
                'refresh_token': refreshToken,
                'redirect_uri': self._getRedirectUri()
            }
            res = requests.post(self._auth_api_endpoint + "oauth/token", auth=(SUUNTO_CLIENT_ID, ''), data=post_data)
            if res.status_code != 200:
                raise APIException("No authorization to refresh token", block=True, user_exception=UserException(UserExceptionType.Authorization, intervention_required=True))
            data = res.json()
            authorizationData = {
                "AccessToken": data["access_token"],
                "AccessTokenExpiresIn": int(time.time()) + data["expires_in"],
                "RefreshToken": data["refresh_token"]
            }
            serviceRecord.Authorization.update(authorizationData)
            db.connections.update({"_id": serviceRecord._id}, {"$set": {"Authorization": authorizationData}})

        session.headers.update({
            "Authorization": "Bearer {}".format(serviceRecord.Authorization["AccessToken"]),
            "Ocp-Apim-Subscription-Key": SUUNTO_CLIENT_SECRET
            })
        return reqLambda(session)

    def _create_activity(self, data):
        activity = UploadedActivity()
        activity.ServiceData = {"ActivityID": data["workoutKey"]}
        return True, activity

    def WebInit(self):
        params = {
            'response_type': 'code',
            'client_id': SUUNTO_CLIENT_ID,
            'redirect_uri': self._getRedirectUri()
        }
        self.UserAuthorizationURL = self._auth_api_endpoint + "oauth/authorize?" + urlencode(params)

    def RetrieveAuthorizationToken(self, req, level):
        auth_code = req.GET.get("code")
        post_data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': self._getRedirectUri()
        }
        res = requests.post(self._auth_api_endpoint + "oauth/token", auth=(SUUNTO_CLIENT_ID, ''), data=post_data)

        if res.status_code != 200:
            raise APIException(res.text, user_exception=UserException(UserExceptionType.Authorization))
        
        data = res.json()

        authorizationData = {
            "AccessToken": data["access_token"],
            "AccessTokenExpiresIn": int(time.time()) + data["expires_in"],
            "RefreshToken": data["refresh_token"]
        }
        
        return (data["user"], authorizationData)

    def RevokeAuthorization(self, serviceRecord):
        params = {
            'client_id': SUUNTO_CLIENT_ID
        }
        res = self._requestWithAuth(lambda session: session.get(self._auth_api_endpoint + "oauth/deauthorize", params=params), serviceRecord)
        if res.status_code != 200:
            raise APIException("Error deauthorizing suunto app.", user_exception=UserException(UserExceptionType.Authorization))

    def DownloadActivityList(self, serviceRecord, exhaustive=False):
        activities = []
        exclusions = []

        since_epoch = int(datetime.datetime.utcfromtimestamp(0) if exhaustive else (time.time() - 60*60*24) * 1000)
        until_epoch = int(time.time() * 1000)

        while True:
            params = {
                "since": since_epoch,
                "until": until_epoch
            }
            res = self._requestWithAuth(lambda session: session.get(self._api_endpoint + "workouts", params=params), serviceRecord)

            if res.status_code != 200:
                raise APIException("Error during activitieslist fetch.", user_exception=UserException(UserExceptionType.ListingError))

            data = res.json()
            if data["error"]:
                raise APIException(data["error"], user_exception=UserException(UserExceptionType.ListingError))
            for activity_metadata in data["payload"]:
                compatible, activity = self._create_activity(activity_metadata)
                if compatible:
                    activities.append(activity)
                else:
                    exclusions.append(activity)
            
            since_epoch = data["metadata"]["until"]
            if not exhaustive or data["metadata"]["workoutcount"] == "0":
                break

        return activities, exclusions

    def DownloadActivity(self, serviceRecord, activity):
        res = self._requestWithAuth(lambda session: session.get(self._api_endpoint + "workout/exportFit/{}".format(activity.ServiceData["ActivityID"])), serviceRecord)
        activity
        pass

    def UploadActivity(self, serviceRecord, activity):
        # Not supported
        pass

    def DeleteCachedData(self, serviceRecord):
        pass  # No cached data...
