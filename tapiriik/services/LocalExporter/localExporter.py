# Local export module for exercisync
# (c) 2018 Anton Ashmarin, aashmarin@gmail.com
from tapiriik.services.service_base import ServiceAuthenticationType, ServiceBase
from tapiriik.services.api import APIException, UserException, UserExceptionType
from tapiriik.services.tcx import TCXIO
from tapiriik.settings import USER_DATA_FILES, WEB_ROOT, PRIMARY_HOST_NAME
from tapiriik.services.interchange import ActivityType
from tapiriik.web.email import generate_message_from_template, send_email
from tapiriik.database import db

import socket
import django.utils.text
import os
import logging
import requests
import shutil
import zipfile
import uuid
import django
import re

# Make settings work (to send email)
os.environ["DJANGO_SETTINGS_MODULE"] = "tapiriik.settings"
django.setup()

logger = logging.getLogger(__name__)

class LocalExporterService(ServiceBase):
    ID = "localexporter"
    DisplayName = "Local Export"
    DisplayAbbreviation = "LE"

    AuthenticationType = ServiceAuthenticationType.UsernamePassword

    SupportsHR = SupportsCalories = SupportsCadence = SupportsTemp = SupportsPower = True

    SupportedActivities = [
        ActivityType.Running,
        ActivityType.Cycling,
        ActivityType.MountainBiking,
        ActivityType.Walking,
        ActivityType.Hiking,
        ActivityType.DownhillSkiing,
        ActivityType.CrossCountrySkiing,
        ActivityType.Snowboarding,
        ActivityType.Skating,
        ActivityType.Swimming,
        ActivityType.Wheelchair,
        ActivityType.Rowing,
        ActivityType.Elliptical,
        ActivityType.Gym,
        ActivityType.Climbing,
        ActivityType.RollerSkiing,
        ActivityType.StrengthTraining,
        ActivityType.Other,
        ActivityType.Report
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

    def _ensure_user_root_exists(self, username):
        if not os.path.exists(USER_DATA_FILES):
            os.mkdir(USER_DATA_FILES)
        root = os.path.join(USER_DATA_FILES, username)
        if not os.path.exists(root):
            os.mkdir(root)
        posts_root = os.path.join(root, "Posts")
        if not os.path.exists(posts_root):
            os.mkdir(posts_root)

    def Authorize(self, username, password):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", username):
            raise APIException("Not a email address. Please, enter your email.", user_exception=UserException(UserExceptionType.NotAValidEmail))
        if username != password:
            raise APIException("Inputs doesn't match. Please enter same email in both inputs.", user_exception=UserException(UserExceptionType.EmailsDoNotMatch))

        self._ensure_user_root_exists(username)
        return (username, {})

    def DownloadActivityList(self, serviceRecord, exhaustive=False):
        self._ensure_user_root_exists(serviceRecord.ExternalID)
        return [], []

    def DownloadActivity(self, serviceRecord, activity):
        # Not supported
        pass

    def SynchronizationComplete(self, serviceRecord):
        root = os.path.join(USER_DATA_FILES, serviceRecord.ExternalID)
        if not os.path.exists(root):
            return

        posts_root = os.path.join(posts_root, "Posts")
        # No new files downloaded, skip sending email
        if len(os.listdir(root)) <= 1 and len(os.listdir(posts_root)) <= 0:
            return

        user_folder = os.path.join(USER_DATA_FILES, serviceRecord.ExternalID)
        user_hash = uuid.uuid4().hex
        zipf_name = os.path.join(USER_DATA_FILES, user_hash)
        shutil.make_archive(zipf_name, 'zip', user_folder)

        # To reduce disk usage delete all data except the result archive
        # but keep root structure cause user is not yed disconnected
        shutil.rmtree(user_folder, ignore_errors=True)
        self._ensure_user_root_exists(serviceRecord.ExternalID)

        file_url = "{}/download/{}".format(WEB_ROOT, user_hash)

        host = socket.gethostname()
        if PRIMARY_HOST_NAME != host:
            # send zip archive to the http server node
            with open(zipf_name + ".zip", 'rb') as fileHandler:
                file = {'file': (zipf_name, fileHandler)}
                resp = requests.post(file_url, files=file)
            if resp.status_code != 200:
                logger.debug("Error uploading user file to primary host. (user: {}, file: {}".format(serviceRecord.ExternalID, zipf_name))
                raise APIException("Error uploading user file.", user_exception=UserException(UserExceptionType.Other))

        context = {
            "url": file_url
        }
        message, plaintext_message = generate_message_from_template("email/data_download.html", context)
        send_email(serviceRecord.ExternalID, "Your Aerobia files", message, plaintext_message=plaintext_message)

    def DeleteCachedData(self, serviceRecord):
        # No need to delete
        pass

    def DeleteActivity(self, serviceRecord, uploadId):
        # Not supported
        pass

    def UploadActivity(self, serviceRecord, activity):
        tcx_data = None
        # Patch tcx with notes
        if activity.Type != ActivityType.Report:
            if not activity.NotesExt and activity.Notes:
                tcx_data = TCXIO.Dump(activity)
            elif "tcx" in activity.PrerenderedFormats:
                tcx_data = activity.PrerenderedFormats["tcx"]
            else:
                tcx_data = TCXIO.Dump(activity)

        folder_base = os.path.join(USER_DATA_FILES, serviceRecord.ExternalID)

        # store reports in the separate folder
        if activity.Type == ActivityType.Report:
            folder_base = os.path.join(folder_base, "Posts")

        day_name_chunk = activity.StartTime.strftime("%Y-%m-%d")
        filename_base = "{}_{}".format(day_name_chunk, activity.Type)
        if activity.Name:
            if activity.Type == ActivityType.Report:
                filename_base = "{}_{}".format(day_name_chunk, activity.Name)
            else:
                filename_base = "{}_{}_{}".format(day_name_chunk, activity.Type, activity.Name)
        
        filename_base = django.utils.text.get_valid_filename(filename_base)
        name_base = os.path.join(folder_base, filename_base)
        
        if tcx_data:
            ext = ".tcx"
            file_exists = 1
            while os.path.exists(name_base + ext):
                ext = "_{}.tcx".format(file_exists)
                file_exists = file_exists + 1
            tcx_file_name = name_base + ext

            with open(tcx_file_name, 'w', encoding="utf-8") as file:
                file.write(tcx_data)

        if activity.NotesExt or len(activity.PhotoUrls):
            # Create subfolder only when need to save multiple files
            if tcx_data or len(activity.PhotoUrls):
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
                note_file = os.path.join(folder_base, report_file_name)
                with open(note_file, 'w', encoding="utf-8") as file:
                    file.write(activity.NotesExt)

        return serviceRecord.ExternalID + activity.UID

    def RevokeAuthorization(self, serviceRecord):
        # Remove all user content
        user_folder = os.path.join(USER_DATA_FILES, serviceRecord.ExternalID)
        if os.path.exists(user_folder):
            shutil.rmtree(user_folder, ignore_errors=True)
