import io
import socket
from mhttp.constants import status_codes, header_keys, content_types
from mhttp.messages import HttpRequest, HttpResponse, HttpError
from mhttp.files import TempFileFactory
import time
import pprint
from utils import BufferedSocket
from typing import IO
from abc import ABC


methods = {"GET", "POST", "HEAD", "PUT", "DELETE", "TRACE", "PATCH", "OPTIONS", "CONNECT"}


def split_two(string: str, splitter: str):
    sp = string.split(splitter, maxsplit=1)
    if len(sp) != 2:
        raise HttpError(status_codes.BAD_REQUEST, "header format invalid")
    return sp[0].strip(), sp[1].strip()


def check_content_headers(headers, max_content_length):
    """
    Check content headers to determine if there's a response body. If there is a response body,
    but something is wrong with the headers, an HttpError is thrown
    :param headers: header dictionary
    :param max_content_length: maximum length in bytes of body
    :return:
    """
    transfer = headers.get(header_keys.TRANSFER_ENCODING)
    try:
        length = headers.get(header_keys.CONTENT_LENGTH)
        length = int(length) if length else 0
    except ValueError:
        raise HttpError(status_codes.LENGTH_REQUIRED, "Content length value invalid")
    if length < 0:
        raise HttpError(status_codes.LENGTH_REQUIRED, "Content length value invalid")
    if length > max_content_length:
        raise HttpError(status_codes.PAYLOAD_TOO_LARGE, f"Content length too big. Max is {max_content_length} bytes")
    content_type = headers.get(header_keys.CONTENT_TYPE)
    encoding = headers.get(header_keys.CONTENT_ENCODING)
    if transfer != 'chunked' and not length:
        return None
    if not content_type:
        content_type = content_types.OCTET_STREAM
    if transfer == 'chunked':
        return content_type, 0, encoding
    return content_type, length, encoding


class HttpSocketWrapper(ABC):

    def __init__(self, sock: BufferedSocket):
        self.__socket = sock
        self.request_timeout = 100
        self.max_content_length = 30000000
        self.max_body_ram = 128000
        self.max_headers_size = 32000
        self.__buffer = bytes()
        self.__bytes_read = 1024
        self._remaining_time = self.request_timeout
        self._remaining_size = self.max_content_length
        self._remaining_header_size = self.max_headers_size

    def reset_timers(self):
        self._remaining_time = self.request_timeout
        self._remaining_size = self.max_content_length
        self._remaining_header_size = self.max_headers_size

    def __read_from_socket(self, bytes_to_read: int) -> bytes:
        return self.__read_stuff(self.__socket.read, bytes_to_read)

    def read_line(self, limit) -> bytes:
        return self.__read_stuff(self.__socket.read_line, limit)

    def __read_stuff(self, reader, limit):
        start = time.perf_counter()
        try:
            received = reader(limit)
        except TimeoutError:
            raise HttpError(status_codes.REQUEST_TIMEOUT)
        if received is None:
            received = b''
        end = time.perf_counter()
        self._remaining_time -= (end - start)
        if self._remaining_time < 0:
            raise HttpError(status_codes.REQUEST_TIMEOUT)
        return received

    def _get_headers_strings(self):
        self.reset_timers()
        line = self.read_line(self._remaining_header_size).decode()
        header_strings = []
        while line:
            header_strings.append(line)
            line = self.read_line(self._remaining_header_size).decode()
        return header_strings

    def __read_body_chunked(self, accumulator, trailer_keys):
        while True:
            limit = len(str(self._remaining_size))
            length = int(self.read_line(limit), 16)
            self._remaining_size -= length
            if not self._remaining_size:
                raise HttpError(status_codes.PAYLOAD_TOO_LARGE, "Request too big")
            if length == 0:
                if trailer_keys:
                    return dict(split_two(a, ':') for a in self._get_headers_strings())
                try:
                    self.read_line(2)
                except ValueError:
                    pass
                return None
            self.__read_chunk(accumulator, length)

    def __read_chunk(self, factory: TempFileFactory, length: int):
        while length > 0:
            received = self.__read_from_socket(min(self.__bytes_read, length))
            factory.append_to_file(received)
            length -= len(received)

    def _read_body(self, headers):
        content_headers = check_content_headers(headers, self.max_content_length)
        if not content_headers:
            return None
        content_type, length, encoding = content_headers
        body_factory = TempFileFactory(self.max_body_ram, encoding)
        trailer_keys = headers.get(header_keys.TRAILER)
        if length:
            self.__read_chunk(body_factory, length)
        else:
            trailer = self.__read_body_chunked(body_factory, trailer_keys)
            if trailer:
                headers.update(trailer)
        self.reset_timers()
        file = body_factory.get_file()
        body_factory.clear()
        return file

    def fileno(self):
        return self.__socket.fileno()

    def _send(self, stuff: IO):
        while True:
            to_send = stuff.read(1024)
            if not to_send:
                return
            self.__socket.send(to_send)

    def _send_chunked(self, stream: IO, chunk_size: int):
        while True:
            read = stream.read(chunk_size)
            length = len(read)
            len_hex = hex(length)[2:].encode()
            self.__socket.send(len_hex + b'\r\n')
            self.__socket.send(read + b'\r\n')
            if length == 0:
                return


class ServerSocketWrapper(HttpSocketWrapper):
    def get_request(self) -> HttpRequest:
        header_strings = self._get_headers_strings()
        a = header_strings[0].split(' ')
        if len(a) != 3:
            raise HttpError(status_codes.BAD_REQUEST, "First line invalid. Should be {Method} {route} {protocol}")
        method, url, protocol = a
        x = url.split('?', 1)
        route = x[0]
        args = dict()
        headers = dict()
        cookies = dict()
        if len(x) == 2:
            args = dict(split_two(item, '=') for item in x[1].split("&"))
        if method not in methods:
            raise ValueError(status_codes.BAD_REQUEST, "Method name invalid")
        for line in header_strings[1:]:
            title, content = split_two(line, ':')
            if title == "Cookie":
                a = dict(split_two(item, '=') for item in content.split(";"))
                cookies.update(a)
            else:
                headers[title] = content
        body = self._read_body(headers)
        return HttpRequest(protocol, route, method, args, headers, cookies, body)

    def send_response(self, response: HttpResponse):
        header_string = response.get_header_string()
        with io.BytesIO(header_string) as header_stream:
            self._send(header_stream)
        if not response.body:
            return
        if response.is_chunked:
            self._send_chunked(response.body, response.chunk_size)
        else:
            self._send(response.body)


class ClientSocketWrapper(HttpSocketWrapper):
    pass


def main():
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('0.0.0.0', 5400))
            s.listen()
            conn, addr = s.accept()
            sock = BufferedSocket(conn)
            abo = ServerSocketWrapper(sock)
            req = abo.get_request()
            print(req.files_list[0].open_stream().read().decode())
            code = 200
            protocol = req.protocol
            headers = {
                'Server': 'pswfiwp',
                'Connection': 'Close',
                'Content-Type': content_types.JSON,
                'Content-Disposition': 'inline; filename=ex.json'
            }
            pprint.pprint(vars(req))
            response = HttpResponse(code, protocol)
            response.headers.update(headers)
            json = io.BytesIO('{"aaa": "500"}'.encode())
            response.set_body_chunked(json)
            with response.body:
                abo.send_response(response)
            req.delete()
            conn.close()
            s.close()


if __name__ == '__main__':
    main()
