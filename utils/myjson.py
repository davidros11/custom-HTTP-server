import random
from abc import ABC, abstractmethod
import time
from typing import Any
from collections.abc import Mapping, Sequence, Set
MAX_JSON_LENGTH = 2*1024*1024


class JSONSerializable(ABC):
    """
    Class for JSON serializable objects. Override the method for custom JSON parsing.
    """
    @abstractmethod
    def to_json(self) -> str:
        """ Converts object to JSON """
        pass


def _get_rand_list(num):
    """
    Generate random list of numbers
    :param num: size of the list
    :return: the list
    """
    rand_set = set()
    max_int = 2**31
    for i in range(num):
        rand_set.add(random.randint(0, max_int))
    return list(rand_set)


class JSONDecodeError(Exception):
    """
    Error while decoding JSON
    """
    def __init__(self, message):
        super().__init__(message)


# separation characters
_separators = {' ', '\n', '\t', ',', '\r'}
# number characters
_num_chars = {'0', '1', '2', '3', '4', '5', '6', '7', '8', '9', '.', 'e', '-', 'E', '+'}


def _raise_error(json: str, pos: int):
    """
    Raises an error for an unexpected token
    :param json: json string
    :param pos: position of the token
    """
    raise JSONDecodeError(f"position {pos}: expected value. Got {json[pos]}")


def _skip(json: str, pos: int) -> int:
    """
    Skips all separator tokens
    :param json: json string
    :param pos: position to start skipping from
    :return: the position of the first non separator token
    """
    while json[pos] in _separators:
        pos += 1
    return pos


def _parse_true(json: str, pos: int) -> (bool, int):
    """
    Parses the "true" expression
    :param json: json string
    :param pos: position of the expression
    :return: True, and the position after the expression
    """
    if json[pos:pos+4] == 'true':
        return True, pos+4
    raise JSONDecodeError(f"position {pos}: Illegal token")


def _parse_false(json: str, pos: int) -> (bool, int):
    """
    Parses the "false" expression
    :param json: json string
    :param pos: position of the expression
    :return: True, and the position after the expression
    """
    if json[pos:pos+5] == 'false':
        return False, pos+5
    raise JSONDecodeError(f"position {pos}: Illegal token")


def _parse_null(json: str, pos: int) -> (None, int):
    """
   Parses the "null" expression
   :param json: json string
   :param pos: position of the expression
   :return: True, and the position after the expression
   """
    if json[pos:pos+4] == 'null':
        return None, pos+4
    raise JSONDecodeError(f"position {pos}: Illegal token")


escaped_dict = {'n': '\n', 't': '\t', '\"': '\"', '\\': '\\', 'r': '\r'}


def _parse_string(json: str, pos: int) -> (str, int):
    """
    Parses string expressions
    :param json: JSON string
    :param pos: expression starting position
    :return: the string expression, and the position after the expression
    """
    pos += 1
    orig_pos = pos
    length = len(json)
    build = []
    while pos < length and json[pos] != '\"':
        # handle escaped characters
        if json[pos] == '\\':
            if json[pos+1] in escaped_dict.keys():
                build.append(escaped_dict[json[pos + 1]])
                pos += 2
                continue
        else:
            build.append(json[pos])
        pos += 1
    if pos >= length:
        raise JSONDecodeError(f"position {orig_pos}: unterminated string")
    return ''.join(build), pos+1


def _parse_num(json: str, pos: int):
    """
        Parses number expressions
        :param json: JSON string
        :param pos: expression starting position
        :return: the expression
        """
    start_pos = pos
    # find expression length
    while pos < len(json) and json[pos] in _num_chars:
        pos += 1
    # parse expression as int or float
    num = json[start_pos:pos]
    try:
        return int(num), pos
    except ValueError:
        pass
    try:
        return float(num), pos
    except ValueError:
        raise JSONDecodeError(f"position {start_pos}: Illegal token")


def _parse_dict(json: str, pos: int, max_depth: int) -> (dict, int):
    """
    Parse JSON objects/dictionaries
    :param json: JSON string
    :param pos: expression starting position
    :param max_depth: the amount of allowed nexted objects past this one
    :return: the expression as a dictionary
    """
    if max_depth == 0:
        raise JSONDecodeError(f"position {pos}: maximum depth exceeded")
    pos += 1
    obj = dict()
    pos = _skip(json, pos)
    while pos < len(json) and json[pos] != '}':
        if json[pos] != '\"':
            raise JSONDecodeError(f"position {pos}: Keys must be in quotes")
        key, pos = _parse_string(json, pos)
        pos = _skip(json, pos)
        if json[pos] != ':':
            raise JSONDecodeError(f"position {pos}: No colon found in position {pos}")
        pos += 1
        pos = _skip(json, pos)
        value, pos = _parse_value(json, pos, max_depth)
        obj[key] = value
        pos = _skip(json, pos)
    pos += 1
    return obj, pos


def _parse_array(json: str, pos: int, max_depth: int) -> (list, int):
    """
    Parses a JSON array
    :param json: JSON string
    :param pos: expression starting position
    :param max_depth: the amount of allowed nested objects past this one
    :return: the expression as a list
    """
    if max_depth == 0:
        raise JSONDecodeError(f"position {pos}: max depth reached")
    pos += 1
    lst = []
    pos = _skip(json, pos)
    while pos < len(json) and json[pos] != ']':
        member, pos = _parse_value(json, pos, max_depth)
        lst.append(member)
        pos = _skip(json, pos)
    return lst, pos+1


_parser_dict = {
        't': _parse_true,
        'f': _parse_false,
        'n': _parse_null,
        '\"': _parse_string,
        '}': _raise_error,
        ']': _raise_error
}
_obj_or_arr = {
    '{': _parse_dict,
    '[': _parse_array
}


def _parse_value(json: str, pos: int, max_depth: int):
    """
      Parses the next JSON expression.
      :param json: JSON string
      :param pos: expression starting position
      :param max_depth: the amount of allowed nested objects past this one
      :return: the expression
    """
    if json[pos] in _parser_dict.keys():
        return _parser_dict[json[pos]](json, pos)
    elif json[pos] in _obj_or_arr:
        return _obj_or_arr[json[pos]](json, pos, max_depth - 1)
    else:
        return _parse_num(json, pos)


def deserialize_JSON(json: str, max_depth=32) -> Any:
    """
    Parses a JSON string
    :param json: the JSON string
    :param max_depth: maximum depth of the object
    """
    pos = _skip(json, 0)
    return _parse_value(json, pos, max_depth)[0]


def _write_str(string: str) -> str:
    if string is not str:
        string = str(string)
    """ Converts a string into a JSON string. """
    string = string.replace('\\', '\\\\').replace('\n', '\\n').replace('\t', '\\t')\
        .replace('\"', '\\\"').replace('\r', '\\r')
    return f"\"{string}\""


def _write_num(num: int) -> str:
    """ Converts a number into a JSON string. """
    return str(num)


def _write_sequence(seq: Sequence) -> str:
    """ Converts a list into a JSON string. """
    if len(seq) == 0:
        return '[]'
    build = [f"[{serialize_JSON(seq[0])}"]
    for index in range(1, len(seq)):
        build.append(f", {serialize_JSON(seq[index])}")
    build.append(']')
    return ''.join(build)


def _write_set(s: Set) -> str:
    """ Converts a list into a JSON string. """
    iterator = iter(s)
    try:
        build = [f"[{serialize_JSON(next(iterator))}"]
    except StopIteration:
        return '[]'
    while True:
        try:
            build.append(f", {serialize_JSON(next(iterator))}")
        except StopIteration:
            build.append(']')
            return ''.join(build)


def _write_cast_to_list(obj) -> str:
    """ Converts a set into JSON format. """
    return _write_sequence(list(obj))


def _write_bool(boolean: bool) -> str:
    """ Converts a boolean into a JSON string. """
    return str(boolean).lower()


def _write_mapping(diction: Mapping) -> str:
    """Converts a dictionary into a JSON string. """
    keys = list(diction.keys())
    if not keys:
        return '{}'
    build = [f"{{{_write_str(keys[0])}: {serialize_JSON(diction[keys[0]])}"]
    for key in keys[1:]:
        build.append(f", {_write_str(key)}: {serialize_JSON(diction[key])}")
    build.append('}')
    return ''.join(build)


_common_types = {
    type(None): lambda a: 'null',
    int: _write_num,
    float: _write_num,
    bool: _write_bool,
    str: _write_str,
    list: _write_sequence,
    dict: _write_mapping,
    tuple: _write_sequence,
    set: _write_set,
    bytes: _write_cast_to_list,
    bytearray: _write_cast_to_list,
    range: _write_cast_to_list
}

_more_types = {
    str: _write_str,
    Mapping: _write_mapping,
    Sequence: _write_sequence,
    Set: _write_set,
    int: _write_num,
    float: _write_num,
}


def serialize_JSON(value) -> str:
    """
    Converts an object into a JSON string
    """
    t = type(value)
    if t in _common_types.keys():
        return _common_types[t](value)
    for key in _more_types.keys():
        if isinstance(value, key):
            return _more_types[key](value)
    if not hasattr(value, '__dict__'):
        raise TypeError(f"Type {t} not supported")
    elif issubclass(t, JSONSerializable):
        return _write_mapping(value.to_json())
    # Default serialization. Serialize all non private class and instance attributes
    fields = {key: value for key, value in vars(t).items() if not key.startswith('_')
              and not callable(getattr(t, key))}
    fields.update({key: value for key, value in vars(value).items() if not key.startswith('_')})
    return _write_mapping(fields)


class _A:
    aaa = 15
    bbb = "\n b \" a \\ c"

    def __init__(self):
        self.ccc = True
        self.ddd = None


def main():
    """ Test JSON functions """
    filename = "../ex.json"
    with open(filename, "r") as file:
        content = file.read()
    print(content)
    print(deserialize_JSON(content)['aaa'])
    num = 10000
    #####
    lst1 = _get_rand_list(100)
    lst2 = _get_rand_list(100)
    lst3 = _get_rand_list(100)
    lst4 = _get_rand_list(100)
    diction = {(a, b): c for (a, b, c) in zip(lst1, lst2, lst3)}
    diction["list"] = lst4
    start = time.time()
    string = serialize_JSON(diction)
    print(len(string))
    print(string)
    end = time.time()
    print(end - start)
    start = time.time()
    diction = deserialize_JSON(string)
    end = time.time()
    print(end - start)
    orig_aaa = _A()
    aaa = orig_aaa
    for i in range(3):
        aaa.ddd = _A()
        aaa = aaa.ddd
    st = serialize_JSON(orig_aaa)
    print(st)
    print(deserialize_JSON(st, 32))


if __name__ == "__main__":
    main()
