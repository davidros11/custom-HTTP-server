import io
import socket
import traceback
from typing import Callable
from utils import BufferedSocket
from mhttp import ServerSocketWrapper
from concurrent.futures import ThreadPoolExecutor
from mhttp.messages import HttpResponse, HttpRequest
from mhttp.helpers import HttpError
from mhttp.constants import header_keys, status_codes, content_types
HTTP1_1 = 'HTTP/1.1'
HTTP2 = 'HTTP/2'


def default_logger(error: Exception):
    print(error)
    print(error.args)
    traceback.print_exc()


class HttpServer:
    server_name = 'myserver'

    def __init__(self, handler: Callable, logger: Callable = None):
        """
        Initializes an HttpServer instance
        :param handler: a callable object that takes an HttpRequest and returns an HttpResponse
        :param logger: callable object for logging errors
        """
        if callable(handler):
            self.handler: Callable[[HttpRequest], HttpResponse] = handler
        else:
            raise ValueError("handler must be a callable object")
        if callable(logger):
            self.log_error = logger
        else:
            self.log_error = default_logger

    def add_server_name(self, resp: HttpResponse):
        if self.server_name:
            resp.headers[header_keys.SERVER] = self.server_name

    def error_resp(self, code: int, protocol: str, error: Exception):
        msg = None
        if error and error.args:
            msg = str(error.args[0])
        resp = HttpResponse(msg, code)
        resp.protocol = protocol
        self.add_server_name(resp)
        return resp

    def handle_request(self, request: HttpRequest) -> HttpResponse:
        return self.handler(request)

    def handle_client(self, sock: socket.socket, protocol):
        with BufferedSocket(sock) as sock:
            ssw = ServerSocketWrapper(sock)
            while True:
                try:
                    request = ssw.get_request()
                except HttpError as e:
                    ssw.send_response(self.error_resp(e.code, protocol, e))
                    break
                except OSError:
                    self.log_error(e)
                    break
                except Exception as e:
                    self.log_error(e)
                    ssw.send_response(self.error_resp(status_codes.INTERNAL_SERVER_ERROR, protocol))
                    break
                try:
                    response = self.handle_request(request)
                    response.protocol = request.protocol
                    self.add_server_name(response)
                except HttpError as e:
                    ssw.send_response(self.error_resp(e.code, protocol, e))
                    break
                except Exception as e:
                    self.log_error(e)
                    ssw.send_response(self.error_resp(status_codes.INTERNAL_SERVER_ERROR, protocol))
                    break
                finally:
                    request.delete()
                try:
                    ssw.send_response(response)
                except Exception as e:
                    self.log_error(e)
                    break
                if not response.keep_connection:
                    break

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