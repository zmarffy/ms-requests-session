import re

import requests
from bs4 import BeautifulSoup

POST_URL_RE = r"""urlPost: ?'([A-Za-z0-9:\?_\-\.&/=]+)"""
PPFT_URL_RE = r"""sFTTag: ?'.*value="(.*?)"/>"""
PPFT_URL_RE_2 = r"""sFT: ?'(.*?)'"""
PASSPORT_TEXT_RE = r"""sRandomBlob: ?'(.*?)'"""
PASSWORD_INCORRECT_TEXT_RE = r"""sErrTxt: ?'Your account or password is incorrect\."""
REQUIRED_LOGIN_POST_KEYS = {"pprid", "t", "NAP", "ANON"}
LIVE_URL = "https://login.live.com/"


class MSRequestsSessionLoginError(Exception):
    pass


def _regex_search_and_get_first_group(pattern: str, string: str) -> str:
    m = re.search(pattern, string)
    if m:
        return m.group(1)
    else:
        raise MSRequestsSessionLoginError(
            f"Group 1 of {pattern} not found in input string"
        )


class MSRequestsSession(requests.Session):
    def __init__(self, email: str, password: str, user_agent: str) -> None:
        """A `requests.Session` object that logs you into your Microsoft account.

        Args:
            email (str): Microsoft account email.
            password (str): Microsoft account password.
            user_agent (str): The user agent to use to login.
        """
        super().__init__()
        self.headers.update({"User-Agent": user_agent}),
        self._login(email, password)

    def _login(self, email: str, password: str) -> None:
        next_url = LIVE_URL
        r = self.get(next_url)

        # Retrieve the next URL specified by the login page
        next_url = _regex_search_and_get_first_group(POST_URL_RE, r.text)
        # Get the special PPFT value which is required for the next POST
        ppft = _regex_search_and_get_first_group(PPFT_URL_RE, r.text)
        # This is a thing for some reason. Attach some substring of the word "Passport" onto the... uh... passport
        ppsx = _regex_search_and_get_first_group(PASSPORT_TEXT_RE, r.text)
        data = {
            "ps": 2,
            "psRNGCDefaultType": None,
            "psRNGCEntropy": None,
            "psRNGCSLK": None,
            "canary": None,
            "ctx": None,
            "hpgrequestid": None,
            "PPFT": ppft,
            "PPSX": ppsx,
            "NewUser": 1,
            "FoundMSAs": None,
            "fspost": 0,
            "i21": 0,
            "CookieDisclosure": 0,
            "IsFidoSupported": 1,
            "isSignupPost": 0,
            "isRecoveryAttemptPost": 0,
            "i13": "1",
            "i18": None,
            "login": email,
            "loginfmt": email,
            "type": 11,
            "LoginOptions": 3,
            "lrt": None,
            "lrtPartition": None,
            "hisRegion": None,
            "hisScaleUnit": None,
            "passwd": password,
        }
        r = self.post(next_url, data=data, allow_redirects=True)
        if re.search(PASSWORD_INCORRECT_TEXT_RE, r.text):
            raise MSRequestsSessionLoginError("Incorrect creds")
        next_url = _regex_search_and_get_first_group(POST_URL_RE, r.text)
        ppft = _regex_search_and_get_first_group(PPFT_URL_RE_2, r.text)
        data = {
            "LoginOptions": 3,
            "type": 28,
            "ctx": None,
            "hpgrequestid": None,
            "PPFT": ppft,
            "canary": None,
        }
        r = self.post(next_url, data=data, allow_redirects=True)
        s = BeautifulSoup(r.text, "html.parser")
        # POST to get the T value
        next_url = s.find(id="fmHF")
        if next_url is None:
            raise MSRequestsSessionLoginError("fmHF key was missing from response")
        next_url = next_url.get("action")
        data = {}
        # Collect the keys required for the post from the page source
        for key in REQUIRED_LOGIN_POST_KEYS:
            value = s.find(id=key)
            if value is None:
                raise MSRequestsSessionLoginError(
                    f"{key} value missing from response. Possibly try to manually login to your account, and then try again"
                )
            data[key] = value.get("value")

        # Last POST to get your cookies!
        self.post(
            next_url,
            data=data,
            allow_redirects=True,
            headers={
                "Origin": LIVE_URL,
                "Referer": LIVE_URL,
            },
        )
