import os
from mhttp import HttpRequest, HttpResponse, HttpContext, file_response, HttpServer
from mhttp.constants import content_types


def test(context: HttpContext):
    request = context.request
    if request.method == 'POST':
        return post_test(context)
    elif request.method == 'GET':
        return get_test(context)


def post_test(context: HttpContext):
    if not context.session:
        context.session['user'] = 'bob'
    else:
        print('you are', context.session['user'])
    request = context.request
    t = request.content_type
    if not t:
        t = content_types.OCTET_STREAM
    if t.startswith(content_types.MULTIPART_FORM):
        a = request.files_list
        for file in a:
            file.copy_to(os.path.join('stuff', file.filename))
        b = request.form
        for field in b:
            print(field)
    elif t.startswith(content_types.JSON):
        print(request.json)
    elif t.startswith(content_types.URL_FORM):
        for field in request.form:
            print(field)
    else:
        print(request.body.data)
    resp = HttpResponse()
    resp.keep_connection = request.keep_connection
    return resp


def get_test(context: HttpContext):
    return file_response('file.txt', attachment=False)


def main():
    server = HttpServer(test)
    server.run(certs=(os.path.join('certs', 'rosenbdc.crt'), os.path.join('certs', 'rosenbdc.key')))


if __name__ == '__main__':
    main()
