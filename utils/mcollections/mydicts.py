from typing import Dict, Mapping, Generic, TypeVar, Optional, List, Iterator
T = TypeVar('T')
S = TypeVar('S')


def to_lower(key):
    return key.lower() if isinstance(key, str) else key


class CaseInsensitiveDict(dict):
    """
    Dictionary that's case-insensitive for string keys
    """
    def __init__(self, *args, **kwargs):
        super(CaseInsensitiveDict, self).__init__(*args, **kwargs)
        for k in list(self.keys()):
            v = super(CaseInsensitiveDict, self).pop(k)
            self.__setitem__(to_lower(k), v)

    def __getitem__(self, key):
        return super(CaseInsensitiveDict, self).__getitem__(to_lower(key))

    def __setitem__(self, key, value):
        super(CaseInsensitiveDict, self).__setitem__(to_lower(key), value)

    def __delitem__(self, key):
        return super(CaseInsensitiveDict, self).__delitem__(to_lower(key))

    def __contains__(self, key):
        return super(CaseInsensitiveDict, self).__contains__(to_lower(key))

    def pop(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).pop(to_lower(key), *args, **kwargs)

    def get(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).get(to_lower(key), *args, **kwargs)

    def setdefault(self, key, *args, **kwargs):
        return super(CaseInsensitiveDict, self).setdefault(to_lower(key), *args, **kwargs)

    def update(self, E=None, **F):
        E = E if E else dict()
        super(CaseInsensitiveDict, self).update(self.__class__(E))
        super(CaseInsensitiveDict, self).update(self.__class__(**F))


class ReadOnlyDict(Mapping, Generic[T, S]):
    def __init__(self, d: Dict[T, S] = None):
        self.__dict: Dict[T, S] = d if d else dict()

    def __getitem__(self, item: T) -> S:
        return self.__dict[item]

    def __contains__(self, item: T):
        return item in self.__dict

    def get(self, key: T):
        return self.__dict.get(key)

    def __len__(self) -> int:
        return len(self.__dict)

    def __iter__(self):
        return iter(self.__dict)

    def keys(self):
        return self.__dict.keys()

    def values(self):
        return self.__dict.values()

    def items(self):
        return self.__dict.items()

    def __str__(self):
        return str(self.__dict)

    def __repr__(self):
        return repr(self.__dict)

    def inner_dict(self) -> dict:
        """
        :return: Get the copy of the inner mutable dictionary
        """
        return self.__dict.copy()
