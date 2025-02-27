import aiohttp
import logging
from .const import (
    API_AUTH_FAIL_RETRY_DELAY_SECONDS,
    API_TIMEOUT_SECONDS,
    NEST_API_HOSTNAME,
    USER_AGENT_STRING
)

_LOGGER = logging.getLogger(__name__)

class NestAuth:
    def __init__(self, session, issue_token, api_key, cookies):
        self.session = session
        self.issue_token = issue_token
        self.api_key = api_key
        self.cookies = cookies
        self.access_token = None

    async def fetch_google_token(self):
        """Fetch a Google OAuth token from the issue_token URL."""
        _LOGGER.debug(f"Fetching Google OAuth token from URL: {self.issue_token}")
        headers = {
            "Sec-Fetch-Mode": "cors",
            "User-Agent": USER_AGENT_STRING,
            "X-Requested-With": "XmlHttpRequest",
            "Referer": "https://accounts.google.com/o/oauth2/iframe",
        }
        try:
            async with self.session.get(self.issue_token, headers=headers, cookies=self.cookies, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT_SECONDS)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    token = data.get("access_token")
                    if not token:
                        _LOGGER.error(f"No access_token in response: {data}")
                        raise Exception("Failed to extract Google OAuth token")
                    _LOGGER.debug(f"Successfully fetched Google OAuth token: {token[:10]}...")
                    return token
                else:
                    response_text = await resp.text()
                    _LOGGER.error(f"Failed to fetch Google token: {resp.status} - {response_text}")
                    raise Exception(f"Google token fetch failed with status {resp.status}")
        except Exception as e:
            _LOGGER.error(f"Error fetching Google token: {e}", exc_info=True)
            raise

    async def authenticate(self):
        """Authenticate with the Nest API."""
        google_token = await self.fetch_google_token()
        url = "https://nestauthproxyservice-pa.googleapis.com/v1/issue_jwt"
        headers = {
            "User-Agent": USER_AGENT_STRING,
            "Content-Type": "application/json",
            "Referer": f"https://{NEST_API_HOSTNAME}",
            "Authorization": f"Bearer {google_token}",
        }
        if self.api_key:
            headers["x-goog-api-key"] = self.api_key

        data = {
            "embed_google_oauth_access_token": True,
            "expire_after": "3600s",
            "google_oauth_access_token": google_token,
            "policy_id": "authproxy-oauth-policy"
        }
        _LOGGER.debug(f"Exchanging Google token for Nest JWT at {url} with headers: {headers}")
        try:
            async with self.session.post(url, headers=headers, json=data, cookies=self.cookies, timeout=aiohttp.ClientTimeout(total=API_TIMEOUT_SECONDS)) as resp:
                if resp.status == 200:
                    token_data = await resp.json()
                    self.access_token = token_data.get("jwt")
                    if not self.access_token:
                        _LOGGER.error(f"No jwt in response: {token_data}")
                        raise Exception("Failed to extract Nest JWT")
                    _LOGGER.info("Authentication successful")
                else:
                    response_text = await resp.text()
                    _LOGGER.error(f"JWT exchange failed with status {resp.status}: {response_text}")
                    raise Exception(f"JWT exchange failed: {resp.status}")
        except Exception as e:
            _LOGGER.error(f"Authentication error: {e}", exc_info=True)
            raise