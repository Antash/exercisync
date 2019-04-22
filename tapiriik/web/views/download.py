from tapiriik.settings import USER_DATA_FILES
from django.http import HttpResponse
import os.path

def save_content(req, file_id):
    
    zip_filename = "{}.zip".format(file_id)

    file_path = USER_DATA_FILES + zip_filename
    if os.path.isfile(file_path):
        zip_file = open(file_path, 'rb')
        resp = HttpResponse(zip_file, content_type='application/force-download')
        resp['Content-Disposition'] = 'attachment; filename={}'.format(zip_filename)
    else:
        return HttpResponse(status=404)

    return resp