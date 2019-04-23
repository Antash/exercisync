# Local export module for
# (c) 2018 Anton Ashmarin, aashmarin@gmail.com
from tapiriik.services.service_base import ServiceAuthenticationType, ServiceBase
from tapiriik.services.tcx import TCXIO
from tapiriik.settings import USER_DATA_FILES
from tapiriik.services.interchange import ActivityType
from tapiriik.web.email import generate_message_from_template, send_email

import os
import logging
import requests
import shutil
import zipfile
import uuid

# Make settings work (to send email)
os.environ["DJANGO_SETTINGS_MODULE"] = "tapiriik.settings"

logger = logging.getLogger(__name__)

class LocalExporterService(ServiceBase):
    ID = "localexporter"
    DisplayName = "Local Export"
    DisplayAbbreviation = "LE"

    AuthenticationType = ServiceAuthenticationType.UsernamePassword
    RequiresExtendedAuthorizationDetails = True

    SupportsHR = SupportsCalories = SupportsCadence = SupportsTemp = SupportsPower = True

    SupportedActivities = [
        ActivityType.Running,
        ActivityType.Cycling,
        ActivityType.Other
    ]

    def _download_image(self, image_url, file_name):
        with open(file_name, 'wb') as handle:
            response = requests.get(image_url, stream=True)
            if not response.ok:
                logger.debug("Error downloading file {}: {}".format(image_url, response))
            for block in response.iter_content(1024):
                if not block:
                    break
                handle.write(block)

    def Authorize(self, username, password):
        if not os.path.exists(USER_DATA_FILES):
            os.mkdir(USER_DATA_FILES)
        user_folder = os.path.join(USER_DATA_FILES, username)
        if os.path.exists(user_folder):
            shutil.rmtree(user_folder, ignore_errors=True)
        os.mkdir(user_folder)
        return (username, {}, {"Email" : username, "Password": password})

    def DownloadActivityList(self, serviceRecord, exhaustive=False):
        # Not supported
        return [], []

    def DownloadActivity(self, serviceRecord, activity):
        # Not supported
        pass

    def SynchronizationComplete(self, serviceRecord):
        user_folder = os.path.join(USER_DATA_FILES, serviceRecord.ExternalID)
        user_hash = uuid.uuid4().hex
        zipf_name = os.path.join(USER_DATA_FILES, user_hash)
        shutil.make_archive(zipf_name, 'zip', user_folder)
        # Not need raw data anymore
        self.DeleteCachedData(serviceRecord)

        context = {
            "url": "https://exercisync.com/download/{}".format(user_hash)
        }
        message, plaintext_message = generate_message_from_template("email/data_download.html", context)
        send_email(serviceRecord.ExternalID, "Your Aerobia files", message, plaintext_message=plaintext_message)

    def DeleteCachedData(self, serviceRecord):
        user_folder = os.path.join(USER_DATA_FILES, serviceRecord.ExternalID)
        if os.path.exists(user_folder):
            shutil.rmtree(user_folder, ignore_errors=True)

    def DeleteActivity(self, serviceRecord, uploadId):
        # Not supported
        pass

    def UploadActivity(self, serviceRecord, activity):
        tcx_data = None

        # Patch tcx with notes
        if not activity.NotesExt and activity.Notes:
            tcx_data = TCXIO.Dump(activity)
        elif "tcx" in activity.PrerenderedFormats:
            tcx_data = activity.PrerenderedFormats["tcx"]
        else:
            tcx_data = TCXIO.Dump(activity)

        name_base = os.path.join(USER_DATA_FILES, serviceRecord.ExternalID)
        if not os.path.exists(name_base):
            os.mkdir(name_base)

        day_name_chunk = activity.StartTime.strftime("%Y-%m-%d")
        filename_base = "{}_{}".format(day_name_chunk, activity.Type)
        if activity.Name:
            filename_base = "{}_{}_{}".format(day_name_chunk, activity.Type, activity.Name)
        
        name_base = os.path.join(name_base, filename_base)

        ext = ".tcx"
        file_exists = 1
        while os.path.exists(name_base + ext):
            ext = "_{}.tcx".format(file_exists)
            file_exists = file_exists + 1
        tcx_file_name = name_base + ext
        
        if tcx_data:
            with open(tcx_file_name, 'w') as file:
                file.write(tcx_data)

        if activity.NotesExt or len(activity.PhotoUrls):
            ext = ""
            folders_exists = 1
            while os.path.exists(name_base + ext):
                ext = "_{}".format(folders_exists)
                folders_exists = folders_exists + 1
            folder_base = name_base + ext
            os.mkdir(folder_base)

            for url_data in activity.PhotoUrls:
                img_file_name = "{}.jpg".format(url_data["id"])
                img_file = os.path.join(folder_base, img_file_name)
                if activity.NotesExt:
                    activity.NotesExt = activity.NotesExt.replace(url_data["url"], os.path.join(".", img_file_name))
                self._download_image(url_data["url"], img_file)

            if activity.NotesExt:
                report_file_name = "{}.html".format(filename_base)
                note_file = os.path.join(folder_base, "index.html")
                with open(note_file, 'w') as file:
                    file.write(activity.NotesExt)

        return serviceRecord.ExternalID + activity.UID

    def RevokeAuthorization(self, serviceRecord):
        # nothing to do here...
        pass