# Local export module for
# (c) 2018 Anton Ashmarin, aashmarin@gmail.com
from tapiriik.services.service_base import ServiceAuthenticationType, ServiceBase

import logging

logger = logging.getLogger(__name__)

class LocalExporterService(ServiceBase):
    ID = "localexporter"
    DisplayName = "Local Export"
    DisplayAbbreviation = "LE"

    AuthenticationType = ServiceAuthenticationType.UsernamePassword

    SupportsHR = SupportsCalories = SupportsCadence = SupportsTemp = SupportsPower = True

    def Authorize(self, username, password):
        #TODO set up user working temp folder
        return (username, {}, {"email" : username, "password": password})

    def DownloadActivityList(self, serviceRecord, exhaustive=False):
        # Not supported
        return []

    def DownloadActivity(self, serviceRecord, activity):
        # Not supported
        pass

    def SynchronizationComplete(self, serviceRecord):
        #TODO 
        # 1. generate link hash
        # 2. zip user files to USER_DATA_FILES/<hash>.zip
        # 3. send email with a download link to user
        pass

    def DeleteCachedData(self, serviceRecord):
        #TODO delete all user data folders
        pass

    def DeleteActivity(self, serviceRecord, uploadId):
        # Not supported
        pass

    def UploadActivity(self, serviceRecord, activity):
        #TODO store file to the user folder
        pass

    def RevokeAuthorization(self, serviceRecord):
        # nothing to do here...
        pass