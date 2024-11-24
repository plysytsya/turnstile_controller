import requests

def login(hostname, username, password, logger):
    url = f"{hostname}/api/token/"
    payload = {"email": username, "password": password}
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, headers, payload)

    if response is None or response.status_code != 200:
        log_unsuccessful_request(response, logger)
        return None

    jwt_token = response.json().get("access", None)
    return jwt_token


def log_unsuccessful_request(response, logger):
    endpoint = response.url  # Get the URL from the response object
    log_message = "\n".join(response.text.split("\n")[-4:])
    logger.error(f"Unsuccessful request to endpoint {endpoint}. Response: {log_message}")
