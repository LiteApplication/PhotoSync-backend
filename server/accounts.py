import json
import os
import re
import time
import uuid

import passlib.hash
from cryptography import fernet
from flask import Blueprint, request
from flask_restful import Resource

from configuration import ConfigFile
from utils import Singleton, require_admin, require_login

bp = Blueprint("accounts", __name__, url_prefix="/api/accounts")
admin = Blueprint("admin", __name__, url_prefix="/api/admin")

INDEX_ACCOUNT = {
    "username": "<index>",
    "fullname": "System Indexer",
    "password": "",
    "encrypted": "",
    "user_id": "<index>",
    "created": 0,
    "last_login": 0,
    "admin": True,
    "unlocked": False,
    "google": [],
    "metadata": {},
}


class Accounts(metaclass=Singleton):
    """Class to manage accounts (this is an API endpoint)
    Accounts are stored in a json file
    {
        "username": {
            "username": "username",
            "fullname": "Full Name",
            "password": "<hashed password>",
            "encrypted": "<encrypted password>", // Needed for password algorithm change
            "user_id": "<user id (uuid4)>",
            "created": "<creation date (unix timestamp)>",
            "last_login": "<last login date (unix timestamp)>",
            "admin": <boolean>, // Future use
            "unlocked": <boolean>, // Reset password
            "google": [], // Future use
            "metadata": {}, // Future use

        }
    }

    Once a user is logged in, a token is generated and stored in config.authorization_file
    {
        "<token (uuid4)>": {
            "username": "<username>",
            "expiration": "<expiration date (unix timestamp)>",
            "ip": "<ip address>"
        }

    }

    """

    def __init__(self, config: ConfigFile):
        self.config = config
        self.path = config.accounts
        self.auth_file = config.authorization_file

    def _get_accounts(self):
        if not os.path.exists(self.path):
            return {"<index>": INDEX_ACCOUNT}
        with open(self.path, "r") as f:
            return json.load(f)

    def _set_accounts(self, accounts: dict):
        if "<index>" not in accounts:
            accounts["<index>"] = INDEX_ACCOUNT
        with open(self.path, "w") as f:
            json.dump(accounts, f)

    def _add_valid_token(self, username: str, token: str = None) -> str:
        """Add a valid token to the account"""

        # Get the current tokens
        if os.path.exists(self.auth_file):
            with open(self.auth_file, "r") as f:
                tokens = json.load(f)
        else:
            tokens = {}

        # Check if the user already has a token from the same ip
        for t in (
            tokens if token is None else []
        ):  # If the token has been provided, don't check for existing token
            if (
                tokens[t]["username"] == username
                and tokens[t]["ip"] == request.remote_addr
            ):
                # Do not create a new token, just update the expiration date
                tokens[t]["expiration"] = (
                    int(time.time()) + self.config.token_expiration
                )
                return t

        if token is None:
            # Generate a token
            token = str(uuid.uuid4())

        # Add the new token
        tokens[token] = {
            "username": username,
            "expiration": int(time.time()) + self.config.token_expiration,
            "ip": request.remote_addr,
        }

        # Count the number of tokens for this user
        count = 0
        for t in tokens:
            if tokens[t]["username"] == username:
                count += 1

        # If there are too many tokens, remove the oldest
        if count > self.config.max_tokens:
            oldest = None
            for t in tokens:
                if tokens[t]["username"] == username:
                    if (
                        oldest is None
                        or tokens[t]["expiration"] < tokens[oldest]["expiration"]
                    ):
                        oldest = t
            del tokens[oldest]

        # Save the tokens
        with open(self.auth_file, "w") as f:
            json.dump(tokens, f)

        # Send it to the user
        return token

    def _check_token(self, token: str) -> bool:
        """Check if a token is valid and return the username"""
        if not os.path.exists(self.auth_file):
            # No token file, no valid token
            return False

        # Load the tokens
        with open(self.auth_file, "r") as f:
            tokens = json.load(f)

        if token not in tokens:
            # Invalid token
            return False
        if tokens[token]["expiration"] < int(time.time()):
            # Token expired
            return False
        return tokens[token]["username"]

    def _revoke_token(self, token: str):
        """Revoke a token"""
        if not os.path.exists(self.auth_file):
            return
        with open(self.auth_file, "r") as f:
            tokens = json.load(f)
        if token in tokens:
            del tokens[token]
        else:
            print('Token "{}" not found'.format(token))
        with open(self.auth_file, "w") as f:
            json.dump(tokens, f)

    def get_user(self) -> dict:
        """Get the user from the token"""
        token = request.headers.get("Token")
        if not token:
            return None
        username = self._check_token(token)
        if not username:
            return None
        accounts = self._get_accounts()
        if username not in accounts:

            return None
        return accounts[username]


@bp.route("/login", methods=["POST"])
def login():
    """Login to the server"""
    self = Accounts()
    accounts = self._get_accounts()
    data = request.get_json()

    # Check if the required parameters are present
    if "username" not in data or "password" not in data:
        return {"message": "Missing parameters"}, 400

    username = data["username"]
    password = data["password"]

    username = username.lower()

    if username not in accounts:
        return {"message": "Account does not exist"}, 404

    # Check if the password is correct
    try:
        if (
            not passlib.hash.sha512_crypt.verify(
                password, accounts[username]["password"]
            )
            and not accounts[username]["unlocked"]
        ):
            return {"message": "Wrong password"}, 401
    except ValueError:
        return {"message": "Authentication failed"}, 401

    # Update last login
    accounts[username]["last_login"] = int(time.time())
    self._set_accounts(accounts)

    # Add a valid token
    token = self._add_valid_token(username)

    return {"message": "OK", "token": token}, 200


@bp.route("/logout", methods=["POST"])
def logout():
    """Logout from the server"""
    self = Accounts()
    token = request.headers.get("Token")
    if not token:
        return {"message": "Missing token"}, 400
    self._revoke_token(token)
    return {"message": "OK"}, 200


@bp.route("/create", methods=["PUT"])
def create():
    """Create an account on the server"""

    self = Accounts()

    accounts = self._get_accounts()
    data = request.get_json()

    # Check if the required parameters are present
    if "username" not in data or "password" not in data or "fullname" not in data:
        return {"message": "Missing parameters"}, 400

    username = data["username"]
    password = data["password"]

    # Check if the username contains only letters and numbers
    username = username.lower()
    if not re.match("^[a-z0-9]*$", username):
        return {"message": "Invalid username"}, 400

    if username in accounts:
        return {"message": "Account already exists"}, 204
    if username in ("admin", "system indexer"):
        return {"message": "This username is reserved"}, 403

    # Encrypt password using the server's key
    f = fernet.Fernet(self.config.password_key.encode("utf-8"))
    encrypted = f.encrypt(password.encode("utf-8")).decode("utf-8")

    accounts[username] = {
        "username": username,
        "fullname": data["fullname"],
        "password": passlib.hash.sha512_crypt.hash(password),
        "encrypted": encrypted,
        "user_id": str(uuid.uuid4()),
        "created": int(time.time()),
        "last_login": int(time.time()),
        "admin": False,
        "unlocked": False,
        "google": [],  # Future use
        "metadata": {},  # Future use
    }
    self._set_accounts(accounts)
    return {"message": "OK"}, 201


@bp.route("/get-user/<string:username>", methods=["GET"])
def get_name(username: str):
    """Get the full name of a user"""
    self = Accounts()
    accounts = self._get_accounts()
    username = username.lower()

    AVAILABLE_INFOS = [
        "username",
        "fullname",
        "user_id",
        "created",
    ]

    if username not in accounts:
        return {"message": "Account does not exist"}, 404

    return {
        "message": "OK",
        "user": {k: accounts[username][k] for k in AVAILABLE_INFOS},
    }, 200


@bp.route("/test")
@require_login
def test_logged_in():
    """Test if the user is logged in"""
    return {"message": "OK"}, 200


@admin.route("/test")
@require_admin
def test_admin():
    """Test if the user is an admin"""
    return {"message": "OK"}, 200


@admin.route("/switch-index", methods=["PATCH"])
@require_admin
def switch_index():
    """Make the current auth token point to the <index> account"""
    self = Accounts()
    current_token = request.headers.get("Token")
    current_user = self._check_token(current_token)

    self._revoke_token(current_token)
    self._add_valid_token(username="<index>", token=current_token)

    return {"message": "OK", "username": current_user}, 200


@bp.route("/get-users", methods=["GET"])
@require_login
def get_users():
    """Get a list of users"""
    self = Accounts()
    accounts = self._get_accounts()

    AVAILABLE_INFOS = [
        "username",
        "fullname",
        "user_id",
        "created",
    ]

    users = []
    for username in accounts:
        user = {}
        for info in AVAILABLE_INFOS:
            user[info] = accounts[username][info]
        users.append(user)

    return {"message": "OK", "users": users}, 200
