from http.cookiejar import DefaultCookiePolicy

import requests


def session_without_cookies() -> requests.Session:
    session: requests.Session = requests.Session()
    session.cookies.set_policy(policy=DefaultCookiePolicy(allowed_domains=[]))
    return session
