import requests

def login(hostname, username, password, logger):
    url = f"{hostname}/api/token/"
    payload = {"email": username, "password": password}
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, headers, payload)

    if response is None or response.status_code != 200:
        logger.error(response.text)
        return None

    jwt_token = response.json().get("access", None)
    return jwt_token
