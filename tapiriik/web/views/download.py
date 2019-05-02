from tapiriik.settings import USER_DATA_FILES
from django.http import HttpResponse
import os.path

def save_content(req, file_id):
    zip_filename = "{}.zip".format(file_id)
    file_path = os.path.join(USER_DATA_FILES, zip_filename)

    if req.method == "POST":
        form = UploadFileForm(req.POST, request.FILES)
        if form.is_valid():
            handle_uploaded_file(request.FILES['file'])
            return HttpResponse(status=200)
    elif req.method == "GET":
        if os.path.isfile(file_path):
            zip_file = open(file_path, 'rb')
            resp = HttpResponse(zip_file, content_type='application/force-download')
            resp['Content-Disposition'] = 'attachment; filename={}'.format(zip_filename)
            return resp
            
    return HttpResponse(status=404)
    