import requests
import unittest

HOST = "http://localhost:2701"
TEST_TOKEN = "f4bcfedf-297b-4a3d-a858-31845bb86307"
ADMIN_TOKEN = "577f00b0-c02c-45ce-b81b-acbdd7435f1b"

# Admin account is
# username: adminact
# password: admin

# Test account is
# username: test
# password: valid_password

# TEST_TOKEN is the token for the test account and ip 127.0.0.1
# ADMIN_TOKEN is the token for the admin account and ip 127.0.0.1


def generate_request(
    method: str, path: str, data: dict | None = None, token: str | None = None
):
    if data is None:
        data = {}
    headers = {"Content-Type": "application/json"}
    if token is not None:
        headers["Token"] = token
    return requests.request(method, HOST + path, json=data, headers=headers)


class ServerTest(unittest.TestCase):
    def setUp(self) -> None:
        # Reset the server and all it's files before each test
        generate_request("GET", "/test-reset")
        return super().setUp()
