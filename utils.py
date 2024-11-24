def login(hostname=HOSTNAME, username=USERNAME, password=PASSWORD):
    global jwt_token
    if jwt_token:
        return jwt_token

    url = f"{HOSTNAME}/api/token/"
    payload = {"email": USERNAME, "password": PASSWORD}
    headers = {"Content-Type": "application/json"}

    response = post_request(url, headers, payload)

    if response is None or response.status_code != 200:
        log_unsuccessful_request(response)
        display_on_lcd("Login", "Failed", timeout=2)
        return None

    jwt_token = response.json().get("access", None)
    return jwt_token