from abc import abstractmethod, ABC
from utils import tempfiles
import io
import os
import shutil
from typing import IO


class TempFile(ABC):
    """
    Represents temporary file
    """
    def __len__(self):
        return self.size

    @property
    @abstractmethod
    def size(self) -> int:
        """
        size of file
        """
        pass

    @abstractmethod
    def open_stream(self) -> IO:
        """
        Open file as input stream
        """
        pass

    @property
    @abstractmethod
    def data(self) -> bytes:
        """
        Get file binary data
        """
        pass

    @abstractmethod
    def move_to(self, dest_path: str):
        """
        Moves the file to the specified path. This deletes the buffered file.
        :param dest_path: file destination
        """
        pass

    @abstractmethod
    def copy_to(self, dest_path: str):
        """
        Copies file to destination
        """
        pass

    @abstractmethod
    def delete(self):
        """
        Deletes the file.
        :return:
        """
        pass

    def __del__(self):
        self.delete()


class TempFileSmall(TempFile):
    """
    On-Memory file
    """

    def __str__(self):
        return f"content: {self.__content[:20].hex()}..."

    def __repr__(self):
        return str(self)

    def __init__(self, content: bytes):
        """
        In-memory TempFile constructor
        :param content: file content in bytes
        """
        super(TempFileSmall, self).__init__()
        self.__content = content

    @property
    def size(self) -> int:
        return len(self.__content)

    def open_stream(self):
        return io.BytesIO(self.__content)

    @property
    def data(self) -> bytes:
        return self.__content

    def move_to(self, dest_path: str) -> None:
        self.copy_to(dest_path)
        self.delete()

    def copy_to(self, dest_path: str):
        with open(dest_path, "wb") as dest:
            dest.write(self.__content)
            dest.flush()

    def delete(self):
        self.__content = None


class TempFileBig(TempFile):
    """
    On-Disk file
    """

    def __str__(self):
        return f"path: {self.path}"

    def __repr__(self):
        return str(self)

    def __init__(self, path: str, size: int = None):
        """
        on-Disk TempFile constructor
        :param path: file path
        :param size: file size
        """
        self.__size = size
        super(TempFileBig, self).__init__()
        self.path = path

    @property
    def size(self) -> int:
        if self.__size is None:
            self.__size = os.stat(self.path).st_size
        return self.__size

    def open_stream(self):
        return open(self.path, "rb")

    @property
    def data(self):
        with self.open_stream:
            return self.open_stream().read()

    def move_to(self, dest_path: str):
        shutil.move(self.path, dest_path)
        self.delete()

    def copy_to(self, dest_path: str):
        shutil.copy(self.path, dest_path)

    def delete(self):
        if os.path.isfile(self.path):
            os.remove(self.path)
        self.path = None


class TempFileFactory:
    """
    Factory for generating TempFiles
    """

    def __init__(self, max_mem_size=1024*64, encoding=None):
        """
        Initializes factory
        :param max_mem_size: if a file exceeds this memory, it will be moved to Disk
        :param encoding: file encoding
        """
        self.encoding = encoding
        self.__stream = None
        self.__content = bytearray()
        self.has_file = False
        self.__path = None
        self.size = 0
        self.__max_mem_size = max_mem_size

    @property
    def max_mem_size(self):
        return self.__max_mem_size

    @max_mem_size.setter
    def max_mem_size(self, val):
        self.__max_mem_size = val
        if not self.__stream:
            self.append_to_file(b'')

    def append_to_file(self, received: bytes):
        """
        Appends data to file
        :param received: bytes to add
        """
        if self.__stream:
            self.__stream.write(received)
            self.size += len(received)
            return
        elif len(self.__content) + len(received) > self.max_mem_size:
            self.size = len(self.__content) + len(received)
            self.__path = tempfiles.get_temp_file()
            self.__stream = open(self.__path, "wb")
            self.__stream.write(self.__content)
            self.__stream.write(received)
            self.__content.clear()
        else:
            self.__content.extend(received)

    def get_file(self) -> TempFile:
        """
        Returns the file. Cannot add data to the file after calling.
        """
        if self.__stream:
            self.__stream.close()
            return TempFileBig(self.__path, self.size)
        return TempFileSmall(bytes(self.__content))

    def clear(self):
        """
        Clears the current file.
        """
        if self.__stream:
            self.__stream.close()
            self.__stream = None
            os.remove(self.__path)
        self.__content = bytearray()
        self.__path = None

