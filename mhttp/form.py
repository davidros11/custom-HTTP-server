import os
import shutil
import sys
import mimetypes
from typing import IO, AnyStr, List, Iterator, Callable
from utils.mcollections import FifoBuffer, CaseInsensitiveDict, ReadOnlyDict
from mhttp.constants import content_types, header_keys, status_codes
from mhttp.helpers import is_text, get_header_param, HttpError


class _RelativeReadStream(IO):

    def __next__(self) -> AnyStr:
        res = self.readline()
        if not res:
            raise StopIteration()
        return res

    def __iter__(self) -> Iterator[AnyStr]:
        return self

    def readlines(self, hint: int = -1) -> List[AnyStr]:
        lines = []
        while True:
            line = self.readline(hint)
            if not line:
                return lines
            lines.append(line)
            if hint != -1:
                hint -= len(line)
                if hint <= 0:
                    return lines

    def truncate(self, size=...):
        raise NotImplementedError("Can't write to this open_stream")

    def writelines(self, lines):
        raise NotImplementedError("Can't write to this open_stream")

    def write(self, s):
        raise NotImplementedError("Can't write to this open_stream")

    def __exit__(self, t, value, traceback):
        self.close()

    def __enter__(self) -> IO[AnyStr]:
        return self

    def isatty(self) -> bool:
        return False

    def flush(self) -> None:
        pass

    def fileno(self) -> int:
        pass

    def __init__(self, stream: IO, offset: int, length: int):
        self._inner = stream
        self._offset = offset
        self._length = length
        self.__has_init = False

    def initialize(self):
        if not self.__has_init:
            self._inner.seek(self._offset)
            self.__has_init = True

    def tell(self):
        self.initialize()
        return self._inner.tell() - self._offset

    def seek(self, offset: int, whence: int = os.SEEK_SET, /):
        self.initialize()
        if whence == os.SEEK_SET:
            offset = self._offset + min(self._length, offset)
            self._inner.seek(offset)
        elif whence == os.SEEK_CUR:
            offset = min(self._inner.tell() + offset, self._offset + self._length)
            self._inner.seek(offset)
        elif whence == os.SEEK_END:
            end = self._offset + self._length
            offset = min(end, end + offset)
            self._inner.seek(offset)
        else:
            raise ValueError(f'whence must be one of {[os.SEEK_SET, os.SEEK_CUR, os.SEEK_END]}')

    def read(self, n=-1):
        self.initialize()
        remaining = self._length - self.tell()
        n = min(remaining, n) if n >= 0 else remaining
        return self._inner.read(n)

    def readline(self, limit=-1):
        self.initialize()
        if limit < 0:
            limit = self._length - self.tell()
        else:
            limit = min(self._length - self.tell(), limit)
        self._inner.readline(limit)

    def close(self):
        self._inner.close()

    def closed(self):
        return self._inner.closed

    def readable(self):
        return True

    def seekable(self):
        return True

    def writable(self):
        return False


class FormReader:
    def __init__(self, s: IO, boundary: str):

        self.__inner = s
        self.boundary = ('--' + boundary).encode()
        self.boundary_with_nl = b'\r\n' + self.boundary
        self.__buffer = FifoBuffer()
        self.field_end = True
        self.__init = False

    def __read(self, bytes_num: int):
        read = self.__buffer.pop(bytes_num)
        if len(read) != bytes_num:
            return read + self.__inner.read(bytes_num - len(read))
        return read

    def __readline(self):
        line = self.__buffer.pop_line()
        if not line or line[-1] != ord('\n'):
            line += self.__inner.readline()
        line = line[:-2]
        return line

    def read(self, bytes_num: int = -1) -> bytes:
        """
        Reads from the current form field. Once the field end, next_field() must be called
        before reading further.
        :param: bytes_num: number of bytes to read
        :return:
        """
        if self.field_end:
            return bytes()
        t = bytearray()
        while True:
            if bytes_num == -1:
                a = self.__read(1024)
            else:
                a = self.__read(bytes_num)
            buff = self.__read(len(self.boundary_with_nl))
            total = a + buff
            if self.boundary_with_nl in total:
                self.field_end = True
                rest, for_next = total.split(self.boundary_with_nl, 1)
                self.__buffer.push(for_next)
                if t:
                    return t + rest
                return rest
            self.__buffer.push(buff)
            if bytes_num != -1:
                return a
            t.extend(a)

    def read_line(self):
        if self.field_end:
            return bytes()
        line = self.__readline()
        if line == self.boundary:
            self.field_end = True
        return line

    def __skip_to_end(self):
        while True:
            a = self.read(1024)
            if not a:
                return

    def next_field(self):
        """
        Allows the open_stream to proceed to the next form field. Skips the current field if it wasn't fully read yet.
        :return: the headers of the next form field
        """
        if not self.__init:
            self.__inner.seek(len(self.boundary))
            self.__init = True
        if not self.field_end:
            self.__skip_to_end()
        read = self.__read(2)
        if not read or read == b'--':
            return None
        headers = CaseInsensitiveDict()
        while read:
            line = self.__readline()
            if line == self.boundary:
                raise HttpError(status_codes.BAD_REQUEST, 'Bad form-data format')
            elif not line:
                break
            keyval = line.split(b':', 1)
            if len(keyval) != 2:
                raise HttpError(status_codes.BAD_REQUEST, 'Bad form-data header format')
            headers[keyval[0].decode().strip()] = keyval[1].decode().strip()
        self.field_end = False
        return FormMetadata(headers)

    def copy_field(self, dest: str):
        with open(dest, 'wb') as file:
            shutil.copyfileobj(self, file)

    def close(self):
        self.__inner.close()
        self.__buffer = None

    def tell(self):
        return self.__inner.tell() - len(self.__buffer)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.__inner.__exit__(exc_type, exc_val, exc_tb)


class FormMetadata:
    def __init__(self, headers: CaseInsensitiveDict):
        if header_keys.CONTENT_DISPOSITION not in headers:
            raise HttpError(status_codes.BAD_REQUEST, "No field name")
        name = get_header_param(headers[header_keys.CONTENT_DISPOSITION], 'name')
        if not name:
            raise HttpError(status_codes.BAD_REQUEST, "No field name")
        self.name = name.replace('\"', '')
        self.filename = get_header_param(headers[header_keys.CONTENT_DISPOSITION], 'filename')
        if header_keys.CONTENT_TYPE not in headers:
            if not self.filename:
                headers[header_keys.CONTENT_TYPE] = content_types.TEXT_PLAIN
            else:
                headers[header_keys.CONTENT_TYPE] = content_types.OCTET_STREAM
        if self.filename:
            self.filename = self.filename.replace('\"', '')
        elif not is_text(headers[header_keys.CONTENT_TYPE]):
            content_type = headers[header_keys.CONTENT_TYPE]
            ext = mimetypes.guess_extension(content_type)
            self.filename = self.name + ext if ext else '.bin'
        self.headers = ReadOnlyDict(headers)

    def __sizeof__(self):
        return sys.getsizeof(self.headers) \
               + sys.getsizeof(self.name)\
               + sys.getsizeof(self.filename)\
               + 4

    @property
    def is_file(self):
        return bool(self.filename)


class FormFile:
    """
    Represents file
    """
    def __init__(self, metadata: FormMetadata, stream_giver: Callable, length: int):
        """
        Initializes FormFile instance
        :param metadata: metadata of a form field.
        :param stream_giver: function that returns a stream
        :param length: file length
        """
        self.name = metadata.name
        self.filename = metadata.filename
        self.headers = metadata.headers
        self.open_stream: Callable[[], IO] = stream_giver
        self.size = length

    def copy_to(self, dest: str):
        """
        Copies file to disk
        :param dest: destination path
        """
        with open(dest, 'wb') as file:
            with self.open_stream() as stream:
                shutil.copyfileobj(stream, file, self.size)

    @property
    def content_type(self):
        return self.headers.get(header_keys.CONTENT_TYPE)


class CopiedFile:
    def __init__(self, metadata: FormMetadata, path):
        self.name = metadata.name
        self.filename = metadata.filename
        self.headers = metadata.headers
        self.path = path

    @property
    def content_type(self):
        return self.headers.get(header_keys.CONTENT_TYPE)


def _relative_stream_opener(stream_opener: Callable, offset: int, length: int):
    """
    Returns functions that opens a relative stream given an offset and length
    :param stream_opener: function that opens a stream
    :param offset: stream offset
    :param length: stream length
    """
    def inner():
        return _RelativeReadStream(stream_opener(), offset, length)
    return inner


def _read_to_limit(reader: FormReader, limit: int) -> str:
    """
    Read entire current field of FormReader
    :param reader: the FormReader
    :param limit: maximum size of field. Exception thrown if its exceeded
    :return: field in string form
    """
    total = bytearray()
    while True:
        bytes_read = reader.read(1024)
        if not bytes_read:
            return total.decode()
        limit -= len(bytes_read)
        if limit < 0:
            raise HttpError(status_codes.PAYLOAD_TOO_LARGE, "Form fields too big")
        total.extend(bytes_read)


def _meta_length(metadata: FormMetadata) -> int:
    """
    Returns the total length of all strings in a metadata object
    """
    size = len(metadata.name.encode()) + len(metadata.filename.encode())
    for key, value in metadata.headers.items():
        size += len(key.encode()) + len(value.encode())
    return size


def parse_form(boundary: str, stream_func, folder=None, max_mem=64 * 1024, max_entries=1000):
    """
    Parses the form from the given open_stream.
    :param: boundary: open_stream boundary
    :param: stream_func: function that opens and returns a open_stream
    :param: folder: folder to send all the files to
    :param: max_mem: Max amount of memory in bytes that can be used for the form. This includes headers
    :param: max_entries: maximum number of fields the form can have
    and none file fields
    :return: tuple of dictionaries:
    dict 1: all files.
    dict 2: all none file-fields
    """
    files = {}
    fields = {}
    stream = FormReader(stream_func(), boundary)
    for i in range(max_entries):
        metadata = stream.next_field()
        if not metadata:
            stream.close()
            return files, fields
        elif metadata.is_file:
            if folder:
                dest = os.path.join(folder, metadata.filename)
                stream.copy_field(dest)
                files[metadata.name] = CopiedFile(metadata, dest)
                max_mem -= _meta_length(metadata)
                continue
            total = 0
            offset = stream.tell()
            while True:
                length = len(stream.read(1024))
                total += length
                if not length:
                    func = _relative_stream_opener(stream_func, offset, total)
                    files[metadata.name] = FormFile(metadata, func, total)
                    max_mem -= _meta_length(metadata)
                    break
        else:
            max_mem -= len(metadata.name)
            value = _read_to_limit(stream, max_mem)
            max_mem -= len(value)
            fields[metadata.name] = value
        if max_mem < 0:
            raise HttpError(status_codes.PAYLOAD_TOO_LARGE, f"Form requires too much memory. Max for headers and"
                                                            f"none-file fields is {max_mem}")
    raise HttpError(status_codes.PAYLOAD_TOO_LARGE, f"Too many form fields. Max is {max_entries}")


if __name__ == '__main__':
    def opener(): return open('form.txt', 'rb')
    g = parse_form('--------------------------408853281213317803450759', opener)
    st = g[0]['ddd'].open_stream()
    x = st.read().decode()
    print(g[1])
    print(g[0]['ddd'].open_stream().read())
    print(g[0]['eee'].open_stream().read())
