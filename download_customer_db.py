import json
import logging
import os
import time

import requests
from dotenv import load_dotenv

load_dotenv()

HOSTNAME = os.getenv("HOSTNAME")
USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
jwt_token = None  # Initializing the jwt_token variable

logging.basicConfig(level=logging.INFO)


def login():
    global jwt_token
    if jwt_token:
        return jwt_token

    url = f"{HOSTNAME}/api/token/"
    payload = json.dumps({"email": USERNAME, "password": PASSWORD})
    headers = {"Content-Type": "application/json"}

    response = make_request("POST", url, headers, payload)  # Specify the method as "POST"
    if response is None or response.status_code != 200:
        log_unsuccessful_request(response)
        return None

    jwt_token = response.json().get("access", None)
    return jwt_token


def get_customers():
    global jwt_token

    if jwt_token is None:
        jwt_token = login()
        if jwt_token is None:
            logging.error("Could not get JWT token.")
            return None

    url = f"{HOSTNAME}/customers/"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {jwt_token}"}

    response = make_request("GET", url, headers=headers)
    if response is None or response.status_code != 200:
        log_unsuccessful_request(response)
        return None

    customer_uuid_dict = {customer["customer_uuid"]: customer for customer in response.json()}
    card_number_dict = {customer["card_number"]: customer for customer in response.json() if customer.get("card_number")}
    second_card_number_dict = {customer["second_card_number"]: customer for customer in response.json() if
                               customer.get("second_card_number")}
    # merge the two dictionaries
    return {**customer_uuid_dict, **card_number_dict, **second_card_number_dict}


def make_request(method, url, headers=None, payload=None, retries=60, sleep_duration=10):
    for i in range(retries):
        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, data=payload)
            else:
                logging.error(f"Unsupported HTTP method: {method}.")
                return None

            return response
        except requests.exceptions.RequestException as e:
            logging.warning(f"Internet connection error: {e}. Retrying...")
            time.sleep(sleep_duration)  # sleep for 10 seconds before retrying

    logging.error("Exhausted all retries. Check your internet connection.")
    return None


def log_unsuccessful_request(response):
    endpoint = response.url  # Get the URL from the response object
    log_message = "\n".join(response.text.split("\n")[-4:])
    logging.info(f"Unsuccessful request to endpoint {endpoint}. Response: {log_message}")


if __name__ == "__main__":
    customers = get_customers()
    if customers is not None:
        # get the directory of the current script
        dir_path = os.path.dirname(os.path.realpath(__file__))
        # construct the full path for the output file
        output_path = os.path.join(dir_path, 'customers.json')

        with open(output_path, 'w') as f:
            json.dump(customers, f)
        logging.info(f'Successfully written customers to {output_path}')
    else:
        logging.error('Failed to retrieve customers')
