import os
from mhttp import HttpRequest, HttpResponse, HttpContext, file_response, HttpServer
from mhttp.constants import content_types, status_codes


def test(context: HttpContext):
    request = context.request
    route = request.route
    method = request.method
    print(route, method)
    if route == '/login':
        if method != 'POST':
            return HttpResponse(code=status_codes.METHOD_NOT_ALLOWED)
        if route.endswith('login'):
            return login_test(context)
    elif route == '/logout':
        return logout(context)
    elif route == '/':
        if method == 'GET':
            return get_test(context)
        elif method == 'POST':
            return post_test(context)
        return HttpResponse(code=status_codes.METHOD_NOT_ALLOWED)
    return HttpResponse(code=status_codes.NOT_FOUND)




def login_test(context: HttpContext):
    login = context.request.json
    user = 'UserName'
    pw = 'Password'
    if login is None or user not in login or pw not in login:
        return HttpResponse("Invalid login credentials", status_codes.BAD_REQUEST)
    if login[user] == 'bob' and login[pw] == 'password':
        context.session['userID'] = 'bob123'
        print(f"bob123 has logged in")
        return HttpResponse(f"Welcome, {login[user]}!")
    else:
        return HttpResponse(code=status_codes.UNAUTHORIZED)


def logout(context: HttpContext):
    context.session = None
    return HttpResponse(code=200)


def post_test(context: HttpContext):
    if not context.session:
        return HttpResponse(code=status_codes.UNAUTHORIZED)
    request = context.request
    t = request.content_type
    if not t:
        t = content_types.OCTET_STREAM
    folder = os.path.join('stuff', context.session['userID'])
    if not os.path.isdir(folder):
        os.mkdir(folder)
    if t.startswith(content_types.MULTIPART_FORM):
        a = request.files_list
        for file in a:
            file.copy_to(os.path.join(folder, file.filename))
        if a:
            print(f"{context.session['userID']} has uploaded some files")
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
    server.run()


if __name__ == '__main__':
    main()
