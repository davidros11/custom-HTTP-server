from typing import AnyStr
import secrets
import base64
from hashlib import sha256
from utils.mcollections import ExpiringDict


class SessionManager:
    def __init__(self, session_ttl_seconds: int, hasher=sha256):
        """

        :param session_ttl_seconds: session time to lvie in seconds.
        :param hasher: Hash function for session key. default is sha256
        :param serializer: object for serializing sessions. Needs to implement get_all(), delete(key),
        and set(key, values) methods.
        """
        self.__dict = ExpiringDict(session_ttl_seconds)
        self.hasher = hasher if hasher else lambda a: a

    @property
    def session_ttl_seconds(self):
        return self.__dict.ttl

    @session_ttl_seconds.setter
    def session_ttl_seconds(self, value):
        self.__dict.ttl = value

    def b64hash(self, inp: AnyStr) -> str:
        if isinstance(inp, str):
            inp = inp.encode()
        return base64.b64encode(self.hasher(inp).digest()).decode()

    def add_session(self, session_data: dict) -> str:
        session_key = base64.b64encode(secrets.token_bytes(32)).decode()
        self.set_session(session_key, session_data)
        return session_key

    def set_session(self, session_key: str, session_data: dict):
        if not isinstance(session_key, str):
            return
        key_hash = self.b64hash(session_key)
        self.__dict[key_hash] = session_data

    def get_session(self, session_key: str):
        if not isinstance(session_key, str):
            return None
        return self.__dict.get(self.b64hash(session_key))

    def delete_session(self, session_key: str):
        if not isinstance(session_key, str):
            return
        key_hash = self.b64hash(session_key)
        self.__dict.delete(key_hash)

    def __contains__(self, session_key: str):
        if not isinstance(session_key, str):
            return False
        return session_key in self.__dict
