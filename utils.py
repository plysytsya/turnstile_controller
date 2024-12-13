import requests

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


def init_sentry():
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration
    import logging
    import os

    sentry_logging = LoggingIntegration(
        level=logging.ERROR,  # Capture errors and above
        event_level=logging.ERROR  # Send events for errors
    )

    sentry_sdk.init(
        dsn=os.getenv("SENTRY_DSN"),
        environment=os.getenv("SENTRY_ENV"),
        traces_sample_rate=1.0,
        integrations=[sentry_logging]
    )

    logging.warning("Sentry initialized.")