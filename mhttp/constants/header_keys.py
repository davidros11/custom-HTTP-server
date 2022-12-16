"""
Constants representing header keys for HTTP
"""

ACCEPT = 'Accept'
ACCEPT_CHARSET = 'Accept-Charset'
ACCEPT_ENCODING = 'Content-Encoding'
ACCEPT_LANGUAGE = 'Accept-Language'
CONNECTION = 'Connection'
CONTENT_DISPOSITION = 'Content-Disposition'
CONTENT_ENCODING = 'Content-Encoding'
CONTENT_LANGUAGE = 'Content-Language'
CONTENT_LENGTH = 'Content-Length'
CONTENT_LOCATION = 'Content-Location'
CONTENT_TYPE = 'Content-Type'
HOST = "Host"
LAST_MODIFIED = 'Last-Modified'
USER_AGENT = 'User-Agent'
LOCATION = 'Location'
SET_COOKIE = 'Set-Cookie'
TRANSFER_ENCODING = 'Transfer-Encoding'
TRAILER = 'Trailer'
SERVER = 'Server'


REP_HEADERS = {
    CONTENT_TYPE,
    CONTENT_ENCODING,
    CONTENT_LENGTH,
    CONTENT_LOCATION,
    CONTENT_LANGUAGE,
    TRANSFER_ENCODING,
    TRAILER
}

# AcceptLanguage	23
# Allow	10
# Authorization	24
# CacheControl	0
# Connection	1
# ContentEncoding	13
# ContentLanguage	14
# ContentLength	11
# ContentLocation	15
# ContentMd5	16
# ContentRange	17
# ContentType	12
# Cookie	25
# Date	2
# Expect	26
# Expires	18
# From	27
# Host	28
# IfMatch	29
# IfModifiedSince	30
# IfNoneMatch	31
# IfRange	32
# IfUnmodifiedSince	33
# KeepAlive	3
# LastModified	19
# MaxForwards	34
# Pragma	4
# ProxyAuthorization	35
# Range	37
# Referer	36
# Te	38
# Trailer	5
# TransferEncoding	6
# Translate	39
# Upgrade	7
# UserAgent	40
# Via	8
# Warning	9