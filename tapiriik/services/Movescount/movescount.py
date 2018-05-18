# Synchronization module for movescount.com
# (c) 2018 Anton Ashmarin, aashmarin@gmail.com
from tapiriik.settings import WEB_ROOT, MOVESCOUNT_APP_KEY
from tapiriik.services.service_base import ServiceAuthenticationType, ServiceBase
from tapiriik.services.service_record import ServiceRecord
from tapiriik.services.api import APIException, UserException, UserExceptionType

from django.core.urlresolvers import reverse
from urllib.parse import urlencode

import requests

class MovescountService(ServiceBase):
    ID = "movescount"
    DisplayName = "Movescount"
    DisplayAbbreviation = "MC"
    AuthenticationType = ServiceAuthenticationType.OAuth
    AuthenticationNoFrame = True # form not fit in the small frame

    _api_endpoint = "https://partner-rest.movescount.com"
    _ui_url = "https://partner-ui.movescount.com"

    def _with_auth(self, serviceRecord):
        pass

    def WebInit(self):
        params = {'client_id': MOVESCOUNT_APP_KEY,
                  'redirect_uri': WEB_ROOT + reverse("oauth_return", kwargs={"service": "movescount"})}
        self.UserAuthorizationURL = self._ui_url +"/auth?" + urlencode(params)

    def RetrieveAuthorizationToken(self, req, level):
        error = req.GET.get("error", False)
        if error:
            raise APIException(error, user_exception=UserException(UserExceptionType.Authorization))

        email = req.GET.get("email")
        user_key = req.GET.get("userkey")
        
        authorizationData = {"OAuthToken": user_key}
        
        return (email, authorizationData)

    def RevokeAuthorization(self, serviceRecord):
        #res = requests.delete(self._api_endpoint +
        #    "/members/private/applications/appkey?appkey={}&userkey={}".format(MOVESCOUNT_APP_KEY, serviceRecord.Authorization["OAuthToken"]))
        pass # Not used.

    def DeleteCachedData(self, serviceRecord):
        pass  # No cached data...
