import datetime
import io
import mimetypes
import os
from io import BufferedIOBase
from wsgiref.handlers import format_date_time
from typing import Optional, List, Dict, Union, BinaryIO
from functools import cached_property
from utils.mcollections.mydicts import CaseInsensitiveDict
from utils.mcollections import ReadOnlyDict
from utils import myjson
from mhttp.constants import status_codes, header_keys, content_types
from mhttp.helpers import is_text, get_header_param, HttpError
from mhttp.form import FormReader, parse_form, FormFile, CopiedFile
from mhttp.files import TempFile


class HttpCookie:

    def __init__(self, name: str, value: str,
                 path='/', expire_date: datetime.datetime = None, max_age=None, http_only=False,
                 secure=False, same_site='Lax', domain=None):
        if not secure and same_site == 'None':
            raise ValueError("Cookies with same site None must be Secure.")
        if same_site not in {'Lax', 'Strict', 'None'}:
            raise ValueError("same_site must be 'Lax','Strict', or 'None'")
        self.name = name
        self.max_age = max_age
        self.value = value
        self.path = path
        if expire_date:
            self.expire_date = expire_date.timestamp()
        else:
            self.expire_date = None
        self.http_only = http_only
        self.secure = secure
        self.same_site = same_site
        self.domain = domain

    def __str__(self):
        strings = [f'{self.name}={self.value}']
        if self.path and self.path != '/':
            strings.append(f'path={self.path}')
        if self.max_age:
            strings.append(f'max-age={self.max_age}')
        if self.http_only:
            strings.append('HttpOnly')
        if self.secure:
            strings.append('Secure')
        strings.append(f'SameSite={self.same_site}')
        if self.domain:
            strings.append(f'Domain={self.domain}')
        if self.expire_date:
            strings.append(f'Expires={format_date_time(self.expire_date)}')
        return '; '.join(strings)


class HttpRequest:
    fields_limit = 1000
    server_name = ''

    def __init__(self, protocol: str,
                 route: str,
                 method: str,
                 args: dict,
                 headers: dict,
                 cookies: dict,
                 body: Optional[TempFile]):
        self.protocol = protocol
        self.route = route
        self.method = method
        self.headers: ReadOnlyDict[str, str] = ReadOnlyDict(CaseInsensitiveDict(headers))
        self.cookies: ReadOnlyDict[str, str] = ReadOnlyDict(cookies)
        self.args: ReadOnlyDict[str, str] = ReadOnlyDict(args)
        self.route_vars: ReadOnlyDict[str, str] = ReadOnlyDict()
        self.body = body
        self.__form = None
        self.__files = None
        self.__json: Optional[dict] = None

    def delete(self):
        if self.body:
            self.body.delete()

    @property
    def content_type(self) -> str:
        return self.headers.get(header_keys.CONTENT_TYPE)

    @property
    def keep_connection(self):
        option = self.headers.get(header_keys.CONNECTION)
        option = option.lower() if option else 'keep-alive'
        return option == 'keep-alive'

    @property
    def json(self):
        if self.__json:
            return self.__json
        if not (self.content_type == content_types.JSON):
            return None
        elif self.body.size > myjson.MAX_JSON_LENGTH:
            raise HttpError(status_codes.PAYLOAD_TOO_LARGE, "JSON too large!")
        self.__json = myjson.deserialize_JSON(self.body.data.decode())
        return self.__json

    @cached_property
    def multipart_boundary(self):
        return get_header_param(self.content_type, 'boundary')

    @cached_property
    def charset(self):
        if not self.is_body_text:
            return None
        return get_header_param(self.content_type, 'charset')

    @cached_property
    def is_body_text(self):
        """
        returns True if the body is text
        """
        # if the content type is a known text type, or if there's a charset parameter then the body is text
        return is_text(self.content_type.split(';', 1)[0]) or bool(self.charset)

    def check_form(self):
        """
        raises an exception if the content body isn't multipart/form-data
        """
        if not self.content_type.startswith(content_types.MULTIPART_FORM):
            raise HttpError(status_codes.BAD_REQUEST, "No multipart form data")
        if not self.multipart_boundary:
            raise HttpError(status_codes.BAD_REQUEST, "No form boundary")

    def open_form_reader(self):
        self.check_form()
        return FormReader(self.body.open_stream(), self.multipart_boundary)

    def form_to_folder(self, folder: str) -> Dict[str, CopiedFile]:
        """
        Loads a form and downloads all the files to the given folder
        :param folder: the folder
        :return: a dictionary with the metadata and path of all the form files
        """
        self.check_form()
        copied, self.__form = parse_form(self.multipart_boundary, self.body.open_stream, folder)
        return copied

    def __load_form(self):
        if content_types.URL_FORM in self.content_type:
            try:
                self.__form.fields = [item.split('=', 1) for item in self.body.data.decode().split('&')]
                return
            except IndexError:
                raise HttpError(status_codes.BAD_REQUEST, "Form not formatted correctly")
        elif not self.multipart_boundary:
            self.__form, self.__files = ReadOnlyDict(), ReadOnlyDict()
            return
        files, form = parse_form(self.multipart_boundary, self.body.open_stream)
        self.__files: ReadOnlyDict[str, FormFile] = ReadOnlyDict(files)
        self.__form: ReadOnlyDict[str, str] = ReadOnlyDict(form)

    @property
    def form(self) -> ReadOnlyDict[str, str]:
        if not self.__form:
            self.__load_form()
        return self.__form

    @property
    def files_list(self) -> List[FormFile]:
        return list(self.files.values())

    @property
    def files(self) -> ReadOnlyDict[str, FormFile]:
        if not self.__files:
            self.__load_form()
        return self.__files


def _get_status_table():
    path = os.path.join(__file__, '..', 'http-status-codes.json')
    with open(path, "r") as file:
        status_json = myjson.deserialize_JSON(file.read())
    return dict((int(key), val) for key, val in status_json.items())


_status_table = _get_status_table()


def _get_status_title(code: int):
    if code not in _status_table.keys():
        raise ValueError("Invalid HTTP code")
    return _status_table[code]


def _capitalize_header(header: str):
    char_list = list(header)
    char_list[0] = char_list[0].upper()
    start = 0
    while True:
        try:
            start = char_list.index('-', start) + 1
            char_list[start] = char_list[start].upper()
        except (ValueError, IndexError):
            return ''.join(char_list)


# class HeaderValue:
#     def __init__(self, header: str):
#         self.values = set(header.split(','))
#
#     def __str__(self):
#         return ','.join(self.values)
#
#     def add(self, value: str):
#         self.values.add(value)
#
#     def remove(self, item: str):
#         self.values.remove(item)


class HttpResponse:
    first_headers = tuple([header_keys.SERVER])
    last_headers = (header_keys.TRAILER,
                    header_keys.CONTENT_DISPOSITION,
                    header_keys.CONTENT_TYPE,
                    header_keys.TRANSFER_ENCODING,
                    header_keys.CONTENT_LANGUAGE,
                    header_keys.CONTENT_LOCATION,
                    header_keys.TRANSFER_ENCODING,
                    header_keys.CONTENT_LENGTH)

    def __init__(self, body=None, code=200):

        self.protocol = None
        self.code = code
        self.__headers: CaseInsensitiveDict[str, str] = CaseInsensitiveDict()
        self.cookies: Dict[str, HttpCookie] = dict()
        self.__body: Optional[BinaryIO] = None
        if body:
            self.set_body(body)
        else:
            self.__set_content_length(0)

    def set_header_order(self, first_headers: tuple = None, last_headers: tuple = None):
        """
        Determines the order in which the headers show up in get_header_string().
        Order is first_headers -> all other headers -> cookies -> last headers
        :param first_headers: Keys for the headers that will show up first in the header string
        :param last_headers: Keys for the headers that will show up last in the header string.
        """
        if first_headers is not None:
            self.first_headers = first_headers
        if last_headers is not None:
            self.last_headers = last_headers

    def get_header_order(self):
        """
        Determines the order in which the headers show up in get_header_string().
        Order is first_headers -> all other headers -> cookies -> last headers
        :return: first_headers and last_headers as lists

        """
        return self.first_headers, self.last_headers

    @property
    def headers(self):
        return self.__headers

    @headers.setter
    def headers(self, headers: dict):
        self.__headers = CaseInsensitiveDict(headers)

    def set_body(self, body, length: int = None):
        """
        Sets the response body
        :param body: a string, bytes, bytearray, Binary stream, or some other object that will be converted to JSON.
        If a binary stream is provided without a length, the response will be chunked
        :param length: The length of the body. This parameter is ignored if the body parameter is not a stream
        """
        if not body:
            return
        if isinstance(body, str):
            body = body.encode()
            self.set_body_stream(io.BytesIO(body), len(body))
            self.content_type = content_types.TEXT_PLAIN
        elif isinstance(body, (bytes, bytearray)):
            self.set_body_stream(io.BytesIO(body), len(body))
            self.content_type = content_types.OCTET_STREAM
        elif isinstance(body, BufferedIOBase):
            self.set_body_stream(body, length)
            self.content_type = content_types.OCTET_STREAM
        else:
            try:
                json = myjson.serialize_JSON(body).encode()
            except TypeError:
                raise TypeError("body argument must be str, bytes, or a type that can be serialzied with JSON")
            self.set_body_stream(io.BytesIO(json), len(json))
            self.content_type = content_types.JSON

    @property
    def content_length(self):
        cl = self.headers.get(header_keys.CONTENT_LENGTH)
        return int(cl if cl else 0)

    def __set_content_length(self, value: int):
        value = max(value, 0)
        self.headers[header_keys.CONTENT_LENGTH] = str(value)

    def get_header_string(self) -> bytes:
        """
        Returns a binary string with all the response's headers.
        """
        if not self.protocol:
            raise ValueError("Protocol not set")
        lines = [f"{self.protocol} {self.code} {_get_status_title(self.code)}".encode()]
        for header in self.first_headers:
            if header in self.headers:
                lines.append(f"{_capitalize_header(header)}: {self.headers[header]}".encode())
        not_middle_keys = set(a.lower() for a in self.first_headers + self.last_headers)
        for header in self.headers:
            if header not in not_middle_keys:
                lines.append(f"{_capitalize_header(header)}: {self.headers[header]}".encode())
        for cookie in self.cookies.values():
            lines.append(f'{header_keys.SET_COOKIE}: {cookie}'.encode())
        for header in self.last_headers:
            if header in self.headers:
                lines.append(f"{_capitalize_header(header)}: {self.headers[header]}".encode())
        lines.append(b'\r\n')
        return b'\r\n'.join(lines)

    def remove_header(self, key: str):
        if key in self.headers:
            del self.headers[key]

    @property
    def content_type(self):
        return self.headers.get(header_keys.CONTENT_TYPE)

    @content_type.setter
    def content_type(self, value: str):
        self.headers[header_keys.CONTENT_TYPE] = value

    def _set_chunked(self):
        self.remove_header(header_keys.CONTENT_LENGTH)
        te = self.headers.get(header_keys.TRANSFER_ENCODING)
        if not te:
            self.headers[header_keys.TRANSFER_ENCODING] = 'chunked'
        elif 'chunked' not in te:
            self.headers[header_keys.TRANSFER_ENCODING] = te + ',chunked'

    def _un_chunked(self):
        te = self.headers.get(header_keys.TRANSFER_ENCODING)
        if not te:
            return
        if 'chunked' in te:
            te = te.lower().split(',')
            te.remove('chunked')
            te = ','.join(te)
            if not te:
                del self.headers[header_keys.TRANSFER_ENCODING]
            else:
                self.headers[header_keys.TRANSFER_ENCODING] = te

    def set_body_stream(self, body, size: int = None):
        """
        Set the Response body
        :param body: An object that must contain a read() method, with a size argument
        :param size: length of the body. IF not provided, the response will be chunked
        """
        self.__body = body
        if size:
            self.__set_content_length(size)
            self._un_chunked()
        else:
            self._set_chunked()

    @property
    def is_chunked(self) -> bool:
        return header_keys.TRANSFER_ENCODING in self.headers

    @property
    def keep_connection(self):
        option = self.headers.get(header_keys.CONNECTION)
        option = option.lower() if option else 'keep-alive'
        return option == 'keep-alive'

    @keep_connection.setter
    def keep_connection(self, val: bool):
        if val:
            self.headers[header_keys.CONNECTION] = 'Keep-Alive'
        else:
            self.headers[header_keys.CONNECTION] = 'Close'

    @property
    def body(self):
        return self.__body

    def add_cookie(self, name: str, value: str, path='/',
                   expire_date=None, max_age=None, http_only=False,
                   secure=False, same_site='Lax', domain=None):
        self.cookies[name] = \
                    HttpCookie(name, value, path, expire_date, max_age, http_only, secure, same_site, domain)

    def delete(self):
        """
        Frees any unmanaged resources.
        """
        self.body.close()


def file_response(src: Union[str, BinaryIO], name=None, attachment=False,
                  content_type=None, last_modified: datetime.datetime = None):
    """
    Returns a response with a file
    :param src: path or stream of the file
    :param name: name of the file. If not provided the name will be based on the path. If a path is not provided,
    filename will be 'file' and the extension will be base on the content type. If neither are provided,
    the filename will be 'file.bin'
    :param attachment: True if the file should be an attachment
    :param content_type: File MIME type. If not provided, it will be based on the file name. If neither are provided,
    it will be 'application/octet-stream'
    :param last_modified: time when the file was last modified
    """
    resp = HttpResponse()
    length = None
    enc = None
    if last_modified:
        last_modified = last_modified.timestamp()
    if isinstance(src, str):
        stream = open(src, 'rb')
        if not last_modified:
            last_modified = os.path.getmtime(src)
        if not name:
            name = ''.join(os.path.splitext(src))
        if not content_type:
            content_type, enc = mimetypes.guess_type(name)
        length = os.stat(src).st_size
    else:
        stream = src
        if not content_type:
            content_type = content_types.OCTET_STREAM
        if not name:
            name = 'file' + mimetypes.guess_extension(content_type)
    content_dis = 'attachment' if attachment else 'inline' + f'; filename=\"{name}\"'
    resp.headers.update({
        header_keys.CONTENT_TYPE: content_type,
        header_keys.CONTENT_DISPOSITION: content_dis
    })
    if enc:
        resp.headers[header_keys.CONTENT_ENCODING] = enc
    if last_modified:
        resp.headers[header_keys.LAST_MODIFIED] = format_date_time(last_modified)
    if length:
        resp.set_body(stream, length)
    else:
        resp.set_body(stream)
    return resp
