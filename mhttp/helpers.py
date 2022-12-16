class HttpError(Exception):
    """
    Error while processing HTTP
    """
    def __init__(self, code: int, *args):
        super(HttpError, self).__init__(*args)
        self.code = code


def is_text(content_type: str) -> bool:
    """
    :param content_type: string representing the mimetype
    :return: True if the mimetype is a known text mimetype. False otherwise.
    """
    sections = content_type.split('/')
    if len(sections) == 1:
        return False
    mime_type, subtype = sections
    if mime_type == "text":
        return True
    if mime_type != "application":
        return False
    return subtype in ["json", "ld+json", "x-httpd-php", "x-sh", "x-csh", "xhtml+xml", "xml"]


def get_header_param(header: str, param: str):
    """
    Extract parameter from HTTP header value
    :param header: header value
    :param param: parameter name
    :return: parameter value
    """
    header = header.strip()
    param_start = header.find(f'{param}=')
    if param_start == -1:
        return None
    param_start += len(param) + 1
    param_end = header.find(';', param_start)
    if param_end == -1:
        param_end = len(header)
    return header[param_start:param_end]