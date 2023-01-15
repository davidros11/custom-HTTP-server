from dataclasses import dataclass
from mhttp import HttpRequest


@dataclass
class HttpContext:
    request: HttpRequest
    session: dict
