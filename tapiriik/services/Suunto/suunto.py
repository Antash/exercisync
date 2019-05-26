# Synchronization module for suunto
# (c) 2018 Anton Ashmarin, aashmarin@gmail.com
from tapiriik.settings import WEB_ROOT, SUUNTO_CLIENT_SECRET, SUUNTO_CLIENT_ID
from tapiriik.services.service_base import ServiceAuthenticationType, ServiceBase
from tapiriik.services.service_record import ServiceRecord
from tapiriik.services.api import APIException, UserException, UserExceptionType
from tapiriik.database import db

from django.core.urlresolvers import reverse
from urllib.parse import urlencode

import requests
import time

class SuuntoService(ServiceBase):
    ID = "suunto"
    DisplayName = "Suunto"
    DisplayAbbreviation = "SU"
    AuthenticationType = ServiceAuthenticationType.OAuth
    AuthenticationNoFrame = True # form not fit in the small frame

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

        params = {
            "since": int((time.time() - 40000) * 1000),
            "until": int(time.time() * 1000)
        }
        res = self._requestWithAuth(lambda session: session.get(self._api_endpoint + "workouts", params=params), serviceRecord)
        data = res.json()
        return activities, exclusions

    def DownloadActivity(self, serviceRecord, activity):
        pass

    def UploadActivity(self, serviceRecord, activity):
        pass

    def DeleteCachedData(self, serviceRecord):
        pass  # No cached data...
