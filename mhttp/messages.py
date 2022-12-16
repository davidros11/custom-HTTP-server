import datetime
import io
import mimetypes
import os
from wsgiref.handlers import format_date_time
from typing import Optional, List, Dict, Union, IO
from functools import cached_property
from utils.mcollections.mydicts import CaseInsensitiveDict
from utils.mcollections import ReadOnlyDict
from mhttp.constants import status_codes, header_keys, content_types
from utils import myjson
from mhttp.helpers import is_text, get_header_param, HttpError
from mhttp.form import FormReader, parse_form, FormFile, CopiedFile
from mhttp.files import TempFile


class HttpCookie:

    def __init__(self, name: str, value: str,
                 path='/', expire_date=None, max_age=None, http_only=False, secure=False,
                 same_site='Lax', domain=None):
        if not secure and same_site == 'None':
            raise ValueError("Cookies with same site None must be Secure.")
        if same_site not in {'Lax', 'Strict', 'None'}:
            raise ValueError("same_site must be 'Lax','Strict', or 'None'")
        self.name = name
        self.max_age = max_age
        self.value = value
        self.path = path
        self.expire_date = expire_date.timestamp()
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
        self.body = body
        self.__form = None
        self.__files = None
        self.__json = None

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
        if not self.content_type == content_types.JSON:
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


class HttpResponse:

    def __init__(self, code=200):
        self.protocol = None
        self.code = code
        self.headers = CaseInsensitiveDict()
        self.cookies = dict()
        self.__body: Optional[IO] = None
        self.__chunk_size = 0

    def get_header_string(self) -> bytes:
        if not self.protocol:
            raise ValueError("Protocol not set")
        if header_keys.CONTENT_LENGTH in self.headers:
            length = self.headers.pop(header_keys.CONTENT_LENGTH)
        else:
            length = '0'
        lines = [f"{self.protocol} {self.code} {_get_status_title(self.code)}".encode()]
        for header, value in self.headers.items():
            lines.append(f"{_capitalize_header(header)}: {value}".encode())
        for cookie in self.cookies.values():
            lines.append(f'{header_keys.SET_COOKIE}: {cookie}'.encode())
        lines.append(f'{header_keys.CONTENT_LENGTH}: {length}'.encode())
        lines.append(b'\r\n')
        return b'\r\n'.join(lines)

    @property
    def chunk_size(self):
        return self.__chunk_size

    @property
    def content_type(self):
        return self.headers.get(header_keys.CONTENT_TYPE)

    @content_type.setter
    def content_type(self, value: str):
        self.headers[header_keys.CONTENT_TYPE] = value

    def set_body(self, body: Optional[IO], size: int):
        """
        Set the Response body with content of a known length
        :param body: the body itself
        :param size: length of the body
        """
        if header_keys.TRANSFER_ENCODING in self.headers:
            del self.headers[header_keys.TRANSFER_ENCODING]
        self.__chunk_size = 0
        self.__body = body
        self.headers[header_keys.CONTENT_LENGTH] = str(size)

    @property
    def is_chunked(self) -> bool:
        return self.__chunk_size > 0

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

    def set_body_chunked(self, body: IO, chunk_size=1024):
        self.__body = body
        self.__chunk_size = chunk_size
        te = self.headers.get(header_keys.TRANSFER_ENCODING)
        self.headers[header_keys.TRANSFER_ENCODING] = f'{te.strip()}, chunked' if te else 'chunked'

    @property
    def body(self) -> IO:
        return self.__body

    def add_cookie(self, name: str, value: str, path='/',
                   expire_date=None, max_age=None, http_only=False,
                   secure=False, same_site='LAX', domain=None):
        self.cookies[name] = \
                    HttpCookie(name, value, path, expire_date, max_age, http_only, secure, same_site, domain)


def make_response(body=None, headers=None, code=200):
    """
    Generartes a response
    :param body:
    :param headers:
    :param code:
    :return:
    """
    resp = HttpResponse(code)
    if headers:
        resp.headers.update(headers)
    if not body:
        return resp
    elif isinstance(body, str):
        body = body.encode()
        resp.set_body(io.BytesIO(body), len(body))
        resp.content_type = content_types.TEXT_PLAIN
    elif isinstance(body, (bytes, bytearray)):
        resp.set_body(io.BytesIO(body), len(body))
        resp.content_type = content_types.OCTET_STREAM
    else:
        json = myjson.serialize_JSON(body).encode()
        resp.set_body(io.BytesIO(json), len(json))
        resp.content_type = content_types.JSON
    return resp


def file_response(src: Union[str, IO], name=None, attachment=False,
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
        resp.set_body_chunked(stream)
    return resp
