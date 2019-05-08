from tapiriik.settings import USER_DATA_FILES
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

import os.path

@csrf_exempt
def save_content(req, file_id):
    zip_filename = "{}.zip".format(file_id)
    file_path = os.path.join(USER_DATA_FILES, zip_filename)

    if req.method == "POST":
        with open(file_path, 'wb+') as destination:
            for chunk in req.FILES['file'].chunks():
                destination.write(chunk)
        return HttpResponse(status=200)
    elif req.method == "GET":
        if os.path.isfile(file_path):
            zip_file = open(file_path, 'rb')
            resp = HttpResponse(zip_file, content_type='application/force-download')
            resp['Content-Disposition'] = 'attachment; filename={}'.format(zip_filename)
            return resp
            
    return HttpResponse(status=404)
    