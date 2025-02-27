import os

DOMAIN = "nest_yale"
PLATFORMS = ["lock"]

CONF_ISSUE_TOKEN = "issue_token"
CONF_API_KEY = "api_key"
CONF_COOKIES = "cookies"

DESCRIPTOR_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "my_desc.desc"))

PRODUCTION_HOSTNAME = {
    "api_hostname": "home.nest.com",
    "grpc_hostname": "grpc-web.production.nest.com",
    "camera_api_hostname": "webapi.camera.home.nest.com",
    "cam_auth_cookie": "website_2",
}

REQUEST_TIMEOUT = 10
SUCCESS_STATUS_CODES = [200, 201]
ENDPOINT_OBSERVE = "/nestlabs.gateway.v2.GatewayService/Observe"
API_SUBSCRIBE_DELAY_SECONDS = 0.1
API_RETRY_DELAY_SECONDS = 10

# Moved from api_client.py
API_TIMEOUT_SECONDS = 40
GRPC_HOSTNAME = PRODUCTION_HOSTNAME["grpc_hostname"]
USER_AGENT_STRING = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_0) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/77.0.3865.120 Safari/537.36"

# Moved from auth.py
API_AUTH_FAIL_RETRY_DELAY_SECONDS = 15
NEST_API_HOSTNAME = "home.nest.com"

def parse_cookies(cookie_string):
    """Parse a cookie string into a dictionary."""
    cookies = {}
    for cookie in cookie_string.split(';'):
        if '=' in cookie:
            key, value = cookie.strip().split('=', 1)
            cookies[key] = value
    return cookies