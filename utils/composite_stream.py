# import os
# from typing import IO, AnyStr, List, Iterator
#
#
# class CompositeReadStream(IO):
#     """
#     A concatenation of multiple streams
#     """
#     def __init__(self, streams: List[IO]):
#         self.__streams = streams
#         self.__pos = 0
#         self.__current_stream = 0
#
#     def __next__(self) -> AnyStr:
#         res = self.readline()
#         if not res:
#             raise StopIteration()
#         return res
#
#     def __iter__(self) -> Iterator[AnyStr]:
#         return self
#
#     def readlines(self, hint: int = -1) -> List[AnyStr]:
#         lines = []
#         while True:
#             line = self.readline(hint)
#             if not line:
#                 return lines
#             lines.append(line)
#             if hint != -1:
#                 hint -= len(line)
#                 if hint <= 0:
#                     return lines
#
#     def truncate(self, size=...):
#         raise NotImplementedError("Can't write to this stream")
#
#     def writelines(self, lines):
#         raise NotImplementedError("Can't write to this stream")
#
#     def write(self, s):
#         raise NotImplementedError("Can't write to this stream")
#
#     def __exit__(self, t, value, traceback):
#         self.close()
#
#     def __enter__(self) -> IO[AnyStr]:
#         return self
#
#     def isatty(self) -> bool:
#         return False
#
#     def flush(self) -> None:
#         pass
#
#     def fileno(self) -> int:
#         pass
#
#     def tell(self):
#         return self.__pos
#
#     def seek(self, offset: int, whence: int = os.SEEK_SET, /):
#         raise NotImplementedError("Can't seek with this stream")
#
#     def final_stream
#
#     def read(self, n=-1):
#         while True:
#             res = self.__streams[self.__current_stream].read(n)
#             if (len(res) != n or n == -1) and self.__current_stream != len(self.__streams)-1:
#
#
#
#     def readline(self, limit=-1):
#         self.initialize()
#         if limit < 0:
#             limit = self._length - self.tell()
#         else:
#             limit = min(self._length - self.tell(), limit)
#         self._inner.readline(limit)
#
#     def close(self):
#         self._inner.close()
#
#     def closed(self):
#         return self._inner.closed
#
#     def readable(self):
#         return True
#
#     def seekable(self):
#         return True
#
#     def writable(self):
#         return False
#
