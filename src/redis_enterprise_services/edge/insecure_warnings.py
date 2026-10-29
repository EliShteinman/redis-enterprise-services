import urllib3
from urllib3.exceptions import InsecureRequestWarning


def silence_insecure_request_warnings() -> None:
    urllib3.disable_warnings(category=InsecureRequestWarning)
