from t_tools import ADMIN_TOKEN, TEST_TOKEN, generate_request, ServerTest


class TestAccounts(ServerTest):
    def test_create_valid(self):
        payload = {
            "username": "testaccount",
            "fullname": "Test Account",
            "password": "v@lid_password1234#!<>",
        }
        req = generate_request("PUT", "/api/accounts/create", payload)
        self.assertEqual(req.status_code, 201)
        self.assertDictEqual(req.json(), {"message": "OK"})

    def test_create_invalid(self):
        payload = {
            "username": "admin",
            "fullname": "Test Account",
            "password": "invalid",
        }
        req = generate_request("PUT", "/api/accounts/create", payload)
        self.assertEqual(req.status_code, 403)
        self.assertDictEqual(req.json(), {"message": "This username is reserved"})

        payload = {
            "username": "<index>",
            "fullname": "Test Account",
            "password": "invalid",
        }
        req = generate_request("PUT", "/api/accounts/create", payload)
        self.assertEqual(req.status_code, 400)
        self.assertDictEqual(req.json(), {"message": "Invalid username"})

        payload = {
            "username": "",
            "fullname": "Test Account",
            "password": "invalid",
        }
        req = generate_request("PUT", "/api/accounts/create", payload)
        self.assertEqual(req.status_code, 400)
        self.assertDictEqual(req.json(), {"message": "Invalid username"})

        payload = {
            "username": "test account",
            "fullname": "Test Account",
            "password": "invalid",
        }
        req = generate_request("PUT", "/api/accounts/create", payload)
        self.assertEqual(req.status_code, 400)
        self.assertDictEqual(req.json(), {"message": "Invalid username"})

    def test_login_valid(self):
        payload = {
            "username": "test",
            "password": "valid_password",
        }
        req = generate_request("POST", "/api/accounts/login", payload)
        self.assertEqual(req.status_code, 200)
        token = req.json().get("token")
        self.assertIsNotNone(token)
        self.assertEqual(len(token), 36)
        self.assertEqual(token, TEST_TOKEN)

    def test_login_invalid(self):
        payload = {
            "username": "test",
            "password": "invalid",
        }
        req = generate_request("POST", "/api/accounts/login", payload)
        self.assertEqual(req.status_code, 401)
        self.assertDictEqual(req.json(), {"message": "Wrong password"})

        payload = {
            "username": "test",
            "password": "",
        }
        req = generate_request("POST", "/api/accounts/login", payload)
        self.assertEqual(req.status_code, 401)
        self.assertDictEqual(req.json(), {"message": "Wrong password"})
        payload = {
            "username": "test2",
            "password": "valid_password",
        }
        req = generate_request("POST", "/api/accounts/login", payload)
        self.assertEqual(req.status_code, 404)
        self.assertDictEqual(req.json(), {"message": "Account does not exist"})
        payload = {
            "username": "test2",
            "password": "",
        }
        req = generate_request("POST", "/api/accounts/login", payload)
        self.assertEqual(req.status_code, 404)
        self.assertDictEqual(req.json(), {"message": "Account does not exist"})
        payload = {
            "username": "",
            "password": "valid_password",
        }
        req = generate_request("POST", "/api/accounts/login", payload)
        self.assertEqual(req.status_code, 404)
        self.assertDictEqual(req.json(), {"message": "Account does not exist"})
        payload = {
            "username": "",
            "password": "",
        }
        req = generate_request("POST", "/api/accounts/login", payload)
        self.assertEqual(req.status_code, 404)
        self.assertDictEqual(req.json(), {"message": "Account does not exist"})
        payload = {
            "username": "test",
        }
        req = generate_request("POST", "/api/accounts/login", payload)
        self.assertEqual(req.status_code, 400)
        self.assertDictEqual(req.json(), {"message": "Missing parameters"})

    def test_logged_in_valid(self):
        req = generate_request("GET", "/api/accounts/test", token=TEST_TOKEN)
        self.assertEqual(req.status_code, 200)
        self.assertDictEqual(req.json(), {"message": "OK"})

    def test_logged_in_invalid(self):
        req = generate_request("GET", "/api/accounts/test", token="invalid")
        self.assertEqual(req.status_code, 401)
        self.assertDictEqual(req.json(), {"message": "Unauthorized"})
        req = generate_request("GET", "/api/accounts/test", token="")
        self.assertEqual(req.status_code, 401)
        self.assertDictEqual(req.json(), {"message": "Unauthorized"})
        req = generate_request("GET", "/api/accounts/test")
        self.assertEqual(req.status_code, 401)
        self.assertDictEqual(req.json(), {"message": "Unauthorized"})

    def test_logout(self):
        req = generate_request("POST", "/api/accounts/logout", token="invalid")
        self.assertEqual(req.status_code, 200)
        self.assertDictEqual(req.json(), {"message": "OK"})

        req = generate_request("POST", "/api/accounts/logout")
        self.assertEqual(req.status_code, 400)
        self.assertDictEqual(req.json(), {"message": "Missing token"})

        req = generate_request("POST", "/api/accounts/logout", token=TEST_TOKEN)
        self.assertEqual(req.status_code, 200)
        self.assertDictEqual(req.json(), {"message": "OK"})

    def test_get_user(self):
        req = generate_request("GET", "/api/accounts/get-user/test", token=TEST_TOKEN)
        self.assertEqual(req.status_code, 200)
        self.assertDictEqual(
            req.json(),
            {
                "message": "OK",
                "user": {
                    "created": 1667857209,
                    "fullname": "Test Account",
                    "user_id": "h26acb90-a2f8-4c6f-91b3-1234hfcf4f",
                    "username": "test",
                },
            },
        )

        req = generate_request(
            "GET", "/api/accounts/get-user/<index>", token=TEST_TOKEN
        )
        print(req.json())
        self.assertEqual(req.status_code, 200)
        self.assertDictEqual(
            req.json(),
            {
                "message": "OK",
                "user": {
                    "created": 0,
                    "fullname": "System Indexer",
                    "user_id": "<index>",
                    "username": "<index>",
                },
            },
        )
        req = generate_request("GET", "/api/accounts/get-user/<index>", token="invalid")
        self.assertEqual(req.status_code, 200)

        req = generate_request("GET", "/api/accounts/get-user/<index>", token="")
        self.assertEqual(req.status_code, 200)

        req = generate_request(
            "GET", "/api/accounts/get-user/unregistered", token=TEST_TOKEN
        )
        self.assertEqual(req.status_code, 404)
        self.assertDictEqual(req.json(), {"message": "Account does not exist"})


class TestAdmin(ServerTest):
    def test_admin(self):
        # Get an admin token
        payload = {
            "username": "adminact",
            "password": "admin",
        }
        req = generate_request("POST", "/api/accounts/login", payload)
        self.assertEqual(req.status_code, 200)
        admin_token = req.json()["token"]
        self.assertEqual(admin_token, ADMIN_TOKEN)
        print(admin_token)

        req = generate_request("GET", "/api/admin/test", token=admin_token)
        self.assertEqual(req.status_code, 200)
        self.assertDictEqual(req.json(), {"message": "OK"})

        req = generate_request("GET", "/api/admin/test", token="invalid")
        self.assertEqual(req.status_code, 401)
        self.assertDictEqual(req.json(), {"message": "Unauthorized"})

        req = generate_request("GET", "/api/admin/test", token=TEST_TOKEN)
        self.assertEqual(req.status_code, 401)
        self.assertDictEqual(req.json(), {"message": "Unauthorized"})
