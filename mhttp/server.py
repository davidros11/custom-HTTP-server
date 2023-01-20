import select
import socket
import traceback
from typing import Callable
from concurrent.futures import ThreadPoolExecutor
import ssl
from utils import BufferedSocket
from mhttp import ServerSocketWrapper
from mhttp.helpers import HttpError
from mhttp.constants import header_keys, status_codes, content_types
from mhttp.session import SessionManager
from mhttp import HttpContext, HttpResponse, HttpRequest
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
        :param handler: a callable object that takes an HttpContext and returns an appropriate HttpResponse object.
        :param logger: callable object for logging errors
        """
        self.sessions = SessionManager(20*60)
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

    def error_resp(self, code: int, protocol: str, error: Exception = None):
        msg = None
        if error and error.args:
            msg = str(error.args[0])
        resp = HttpResponse(msg, code)
        resp.protocol = protocol
        self.add_server_name(resp)
        return resp

    def handle_request(self, request: HttpRequest) -> HttpResponse:
        session_key = request.cookies.get('Session')
        if not session_key:
            session = dict()
        else:
            session = self.sessions.get_session(session_key)
            session = session if session is not None else dict()
        context = HttpContext(request, session)
        response: HttpResponse = self.handler(context)
        if not context.session:
            self.sessions.delete_session(session_key)
        elif session_key is None or session_key not in self.sessions:
            session_key = self.sessions.add_session(context.session)
            response.add_cookie('Session', session_key, http_only=True)
        return response

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
                finally:
                    response.delete()
                if not response.keep_connection:
                    break

    def _handle_http11_client(self, sock: socket.socket):
        self.handle_client(sock,  HTTP1_1)

    def run(self, ip='0.0.0.0', http_port=5400, https_port=5401, certs=None):
        """
        Runs the server.
        :param ip: The IP Address the server will answer to
        :param http_port: port for HTTP connections
        :param https_port: port for HTTPS  connections
        :param certs: a tuple containing the certificate file path, and private key path respectively.
        """
        executor = ThreadPoolExecutor()
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind((ip, http_port))
        listener.listen(8)
        sockets = [listener]
        if certs:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.set_alpn_protocols(['http/1.1'])
            context.load_cert_chain(certs[0], certs[1])
            tls_listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            tls_listener.bind((ip, https_port))
            tls_listener.listen(8)
            sockets.append(context.wrap_socket(tls_listener))
        while True:
            readable, _, _ = select.select(sockets, [], [])
            for sock in readable:
                try:
                    conn, addr = sock.accept()
                    conn.setblocking(True)
                    executor.submit(self._handle_http11_client, conn)
                except ssl.SSLError as e:
                    print(e)

