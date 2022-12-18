from collections.abc import Mapping
from typing import Dict, Generic, TypeVar
K = TypeVar('K')
V = TypeVar('V')


def to_lower(key):
    return key.lower() if isinstance(key, str) else key


class CaseInsensitiveDict(dict, Generic[K, V]):
    """
    Dictionary that's case-insensitive for string keys
    """
    def __init__(self, *args, **kwargs):
        super(CaseInsensitiveDict, self).__init__(*args, **kwargs)
        for k in list(self.keys()):
            v = super(CaseInsensitiveDict, self).pop(k)
            self.__setitem__(to_lower(k), v)

    def __getitem__(self, key: K) -> V:
        return super(CaseInsensitiveDict, self).__getitem__(to_lower(key))

    def __setitem__(self, key: K, value: V):
        super(CaseInsensitiveDict, self).__setitem__(to_lower(key), value)

    def __delitem__(self, key: K):
        return super(CaseInsensitiveDict, self).__delitem__(to_lower(key))

    def __contains__(self, key: K):
        return super(CaseInsensitiveDict, self).__contains__(to_lower(key))

    def pop(self, key: K, *args, **kwargs):
        return super(CaseInsensitiveDict, self).pop(to_lower(key), *args, **kwargs)

    def get(self, key: K, *args, **kwargs) -> V:
        return super(CaseInsensitiveDict, self).get(to_lower(key), *args, **kwargs)

    def setdefault(self, key: K, *args, **kwargs):
        return super(CaseInsensitiveDict, self).setdefault(to_lower(key), *args, **kwargs)

    def update(self, E=None, **F):
        E = E if E else dict()
        super(CaseInsensitiveDict, self).update(self.__class__(E))
        super(CaseInsensitiveDict, self).update(self.__class__(**F))


class ReadOnlyDict(Mapping, Generic[K, V]):
    def __init__(self, d: Dict[K, V] = None, **kwargs):
        self.__dict: Dict[K, V] = d if d else dict()
        self.__dict.update(kwargs)

    def __getitem__(self, item: K):
        return self.__dict[item]

    def __contains__(self, item: K):
        return item in self.__dict

    def get(self, key: K):
        return self.__dict.get(key)

    def __len__(self):
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

    def inner_dict(self):
        """
        :return: Get the copy of the inner mutable dictionary
        """
        return self.__dict.copy()
