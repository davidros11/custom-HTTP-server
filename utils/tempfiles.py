from uuid import uuid4
import os
LOCATION = os.path.join(os.getcwd(), 'temp')
if not os.path.isdir(LOCATION):
    os.mkdir(LOCATION)


def get_temp_file():
    return str(os.path.join(LOCATION, f"{uuid4()}.tmp"))



