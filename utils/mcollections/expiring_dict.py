from typing import Dict, Generic, TypeVar, Tuple, Any, Iterator
from threading import RLock
from time import time
K = TypeVar('K')
V = TypeVar('V')


class _ExpiringDictKeys(Generic[K]):
    def __init__(self, d: Dict[K, Tuple[Any, float]]):
        self.__dict = d

    class _ExpKeyIter(Generic[K]):
        def __init__(self, i: Iterator):
            self.__inner = i

        def __iter__(self):
            return self

        def __next__(self) -> K:
            while True:
                key, (_, t) = next(self.__inner)
                if t > time():
                    return key

    def __contains__(self, key: K):
        res = self.__dict.get(key)
        if not res or res[1] <= time():
            return False
        return True

    def __iter__(self) -> _ExpKeyIter[K]:
        return self._ExpKeyIter(iter(self.__dict.items()))

    def __str__(self):
        return str(list(self))


class _ExpiringDictValues(Generic[V]):
    def __init__(self, d: Dict[Any, Tuple[V, float]]):
        self.__values = d.values()

    class _ExpValueIter(Generic[V]):
        def __init__(self, i: Iterator):
            self.__inner = i

        def __iter__(self):
            return self

        def __next__(self) -> V:
            while True:
                value, t = next(self.__inner)
                if t > time():
                    return value

    def __contains__(self, value: V):
        for (v, t) in self:
            if value == v and t > time():
                return True
        return False

    def __iter__(self) -> _ExpValueIter[V]:
        return self._ExpValueIter(iter(self.__values))

    def __str__(self):
        return str(list(self))


class _ExpiringDictItems(Generic[K, V]):
    def __init__(self, d: Dict[K, Tuple[V, float]]):
        self.__dict = d

    class _ExpItemsIter(Generic[K, V]):
        def __init__(self, i: Iterator):
            self.__inner = i

        def __iter__(self):
            return self

        def __next__(self) -> Tuple[K, V]:
            while True:
                key, (value, t) = next(self.__inner)
                if t > time():
                    return key, value

    def __contains__(self, key_val: Tuple[K, V]):
        val = self.__dict.get(key_val[0])
        if not val or val[1] <= time():
            return False
        return True

    def __iter__(self) -> _ExpItemsIter[K, V]:
        return self._ExpItemsIter(iter(self.__dict.items()))

    def __str__(self):
        return str(list(self))


class ExpiringDict(Generic[K, V]):
    """
    Dictionary with an expiration date for its entries.
    Make sure to use 'ExpiringDict.lock' in when making operations with multiple threads.
    Including its views (keys, values, items)

    Notes
        - len is O(n) complexity since it needs to check for expired entries
    """

    def __init__(self, ttl: int, **kwargs):
        self.__ttl = ttl
        self.__old_len = 0
        self.__dict: Dict[K, Tuple[V, float]] = dict()
        self._lock = RLock()
        self.update(kwargs)

    def expire(self, now=False):
        """
        Goes over the dictionary, deleting all expired
        :param now: if False, expired entries will only be deleted if the size of the dictionary has doubled.
        If True, deletes expired entries regardless
        :return:
        """
        with self.lock:
            if not now and not self.__old_len * 2 <= len(self.__dict):
                return
            for key, (_, exp) in list(self.__dict.items()):
                if exp < time():
                    self.delete(key)
            self.__old_len = len(self.__dict)

    @property
    def lock(self):
        return self._lock

    @property
    def ttl(self):
        with self.lock:
            return self.__ttl

    @ttl.setter
    def ttl(self, value: float):
        with self.lock:
            self.__ttl = value

    def __len__(self):
        with self.lock:
            self.expire(now=True)
            return len(self.__dict)

    def __getitem__(self, key: K) -> V:
        with self.lock:
            a = self.__dict[key]
            if a[1] <= time():
                del self[key]
                raise KeyError("Item expired")
            self[key] = a[0]
            return a[0]

    def get(self, key: K) -> V:
        with self.lock:
            a = self.__dict.get(key)
            if a is None:
                return None
            if a[1] <= time():
                del self[key]
                return None
            self[key] = a[0]
            return a[0]

    def keys(self) -> _ExpiringDictKeys[K]:
        with self.lock:
            return _ExpiringDictKeys(self.__dict)

    def values(self):
        with self.lock:
            return _ExpiringDictValues(self.__dict)

    def items(self):
        with self.lock:
            return _ExpiringDictItems(self.__dict)

    def __setitem__(self, key: K, value: V):
        with self.lock:
            self.__dict[key] = (value, time() + self.__ttl)
            self.expire()

    def __delitem__(self, key: K):
        with self.lock:
            del self.__dict[key]

    def delete(self, key: K):
        try:
            del self[key]
        except KeyError:
            pass

    def __contains__(self, key: K):
        with self.lock:
            return key in self.__dict

    def __deepcopy__(self, memodict=None):
        return self.deepcopy()

    def deepcopy(self):
        with self.lock:
            new_dict = ExpiringDict(self.ttl)
            new_dict.update(self)
            return new_dict

    def pop(self, key: K) -> V:
        with self.lock:
            return self.__dict.pop(key)[0]

    def setdefault(self, key: K, default: V):
        with self.lock:
            self.expire()
            if key in self:
                return self[key]
            self[key] = default
            return default

    def update(self, E=None, **F):
        with self.lock:
            E = E if E else dict()
            if hasattr(E, 'keys') and callable(E.keys):
                for k in E.keys():
                    try:
                        self[k] = E[k]
                    except KeyError:
                        pass
            else:
                for k, v in E:
                    self[k] = v
            for k in F:
                self[k] = F[k]

    def __iter__(self):
        with self.lock:
            return iter(self.keys())

    def __str__(self):
        with self.lock:
            self.expire(now=True)
            return str({key: self.__dict[key][0] for key in self.__dict})
