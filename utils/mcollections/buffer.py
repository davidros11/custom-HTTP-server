from math import log2, floor


def highest_log(num):
    return 2**(floor(log2(num)) + 1)


class FifoBuffer:
    """
    Buffer for storing data
    """
    def __init__(self, init_size=1024):
        self.__array = bytearray(init_size)
        self.__top = 0
        self.__bottom = 0

    def __len__(self):
        return self.__top - self.__bottom

    def push(self, data):
        """
        Adds bytes to the buffer
        :param data: the bytes
        """
        if len(data) + len(self) > len(self.__array):
            self.__resize(highest_log(len(data) + len(self)))
        if len(data) + self.__top > len(self.__array):
            self.__reposition()
        top = self.__top
        new_top = top + len(data)
        self.__array[top:new_top] = data
        self.__top = new_top

    def peek(self, length=1):
        """
        returns bytes from the buffer without removing them
        :param length: number of bytes. Default is 1.
        """
        end = min(self.__bottom + length, self.__top)
        return self.__array[self.__bottom:end]

    def pop(self, length=1):
        """
        Removes bytes from the buffer and returns them
        :param length: number of bytes. Default is 1.
        """
        res = self.peek(length)
        self.__bottom += len(res)
        if self.__bottom == self.__top:
            self.__bottom = self.__top = 0
        return res

    def peek_all(self):
        """ Returns all bytes from the buffer """
        return self.peek(len(self))

    def pop_all(self):
        return self.pop(len(self))

    def pop_until(self, string):
        if isinstance(string, str):
            string = string.encode()
        try:
            loc = self.__array.find(string, self.__bottom, self.__top) + 1
            res = self.__array[self.__bottom:loc]
            self.__bottom = loc
            return res
        except ValueError:
            return self.pop_all()

    def pop_line(self):
        """ Returns and removes a line from the array """
        return self.pop_until(b'\n')
    def __reposition(self):
        """ Repositions the contents of the buffer to the start of the internal array """
        length = len(self)
        self.__array[0:length] = self.__array[self.__bottom:self.__top]
        self.__bottom = 0
        self.__top = length

    def __resize(self, size=None):
        """
        Resizes the internal array.
        :param size: the new size of the array. Default is the size of the current array times 2
        """
        if not size:
            size = len(self.__array) * 2
        length = len(self)
        new_arr = bytearray(size)
        new_arr[0:length] = new_arr[self.__bottom:self.__top]
        self.__bottom = 0
        self.__top = length

    def __bool__(self):
        """ Returns true if the buffer is not empty """
        return bool(len(self))
