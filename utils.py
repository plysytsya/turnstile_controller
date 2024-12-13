import logging
import sys

import requests
import sentry_sdk


def login(hostname, username, password, logger):
    url = f"{hostname}/api/token/"
    payload = {"email": username, "password": password}
    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, json=payload)

    if response is None or response.status_code != 200:
        log_unsuccessful_request(response, logger)
        return None

    jwt_token = response.json().get("access", None)
    return jwt_token


def log_unsuccessful_request(response, logger):
    endpoint = response.url  # Get the URL from the response object
    log_message = "\n".join(response.text.split("\n")[-4:])
    logger.error(f"Unsuccessful request to endpoint {endpoint}. Response: {log_message}")


class SentryLogger(logging.Logger):
    def error(self, msg, *args, exc_info=None, **kwargs):
        if exc_info is True:  # Handle `True` explicitly
            exc_info = sys.exc_info()
        if exc_info or "exc_info" in kwargs:
            sentry_sdk.capture_exception(exc_info or kwargs.get("exc_info"))
        super().error(msg, *args, exc_info=exc_info, **kwargs)

    def exception(self, msg, *args, exc_info=True, **kwargs):
        if exc_info is True:  # Retrieve exception info
            exc_info = sys.exc_info()
        sentry_sdk.capture_exception(exc_info)
        super().exception(msg, *args, exc_info=exc_info, **kwargs)
