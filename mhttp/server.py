import io
import os.path
import socket
from utils import BufferedSocket
from mhttp import ServerSocketWrapper
from concurrent.futures import ThreadPoolExecutor
from mhttp.messages import HttpResponse, HttpRequest
from mhttp.helpers import HttpError
from mhttp.constants import header_keys, status_codes, content_types
HTTP1_1 = 'HTTP/1.1'
HTTP2 = 'HTTP/2'


def default_logger(error: Exception):
    print(error.args)


class HttpServer:
    server_name = "wgwgqwgqg"

    def handle_request_test(self, request: HttpRequest):
        t = request.content_type
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
        resp = HttpResponse(200, HTTP1_1)
        resp.headers[header_keys.SERVER] = self.server_name
        resp.keep_connection = request.keep_connection
        return resp

    def __init__(self, handler=None, logger=None):
        if callable(handler):
            self.handle_request = handler
        else:
            self.handle_request = self.handle_request_test
        if callable(logger):
            self.log_error = logger
        else:
            self.log_error = default_logger

    def error_resp(self, code: int, protocol: str, error: Exception = None):
        msg = None
        if error and error.args:
            msg = str(error.args[0])
        resp = HttpResponse(code, protocol)
        resp.headers[header_keys.SERVER] = self.server_name
        msg = msg.encode()
        if msg:
            resp.set_body(io.BytesIO(msg), len(msg))
        return resp

    def handle_client(self, sock: socket.socket, protocol):
        with BufferedSocket(sock) as sock:
            ssw = ServerSocketWrapper(sock)
            while True:
                try:
                    request = ssw.get_request()
                except TimeoutError:
                    ssw.send_response(self.error_resp(status_codes.REQUEST_TIMEOUT, protocol))
                    return
                except HttpError as e:
                    ssw.send_response(self.error_resp(e.code, protocol, e))
                    return
                except OSError:
                    self.log_error(e)
                    return
                except Exception as e:
                    self.log_error(e)
                    ssw.send_response(self.error_resp(status_codes.INTERNAL_SERVER_ERROR, protocol))
                    return
                try:
                    response = self.handle_request(request)
                except TimeoutError:
                    ssw.send_response(self.error_resp(status_codes.REQUEST_TIMEOUT, protocol))
                except HttpError as e:
                    ssw.send_response(self.error_resp(e.code, protocol, e))
                except OSError as e:
                    self.log_error(e)
                except Exception as e:
                    self.log_error(e)
                    ssw.send_response(self.error_resp(status_codes.INTERNAL_SERVER_ERROR, protocol))
                try:
                    ssw.send_response(response)
                except Exception as e:
                    self.log_error(e)
                    return
                if not response.keep_connection:
                    return

    def handle_http_client(self, sock: socket.socket):
        self.handle_client(sock,  HTTP1_1)

    def handle_https_client(self, sock: socket.socket):
        pass

    def run(self):
        executor = ThreadPoolExecutor(max_workers=20)
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(('0.0.0.0', 5400))
        listener.listen(8)
        while True:
            conn, addr = listener.accept()
            executor.submit(self.handle_http_client, conn)


def main():
    server = HttpServer()
    server.run()


if __name__ == '__main__':
    main()
