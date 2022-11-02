import logging
import os
import random
import re

from cryptography import fernet

from utils import Singleton

log = logging.getLogger("configuration")


class ConfigFile(metaclass=Singleton):
    DEFAULT = {
        "storage": "/srv/photosync/storage",
        "thumbnails_folder": "/srv/photosync/thumbnails",
        "temp_folder": "/srv/photosync/temp",
        "web_folder": "/srv/photosync/web",
        "index": "/srv/photosync/index.json",
        "accounts": "/srv/photosync/accounts.json",
        "authorization_file": "/srv/photosync/auth.json",
        "address": "0.0.0.0",
        "port": "8080",
        "ssl": False,
        "ssl_cert": "/srv/photosync/photosync.crt",
        "ssl_key": "/srv/photosync/photosync.key",
        "hash_buffer_size": 65536,  # 64kb
        # Random key to encrypt passwords
        "password_key": fernet.Fernet.generate_key().decode("utf-8"),
        "token_expiration": 31536000,  # 1 year
        "max_tokens": 32,  # Maximum number of tokens per user
        "download_buffer_size": 65536,  # 64kb
        "thumbnail_size": 128,
        "cache_time": 2628000,  # 1 month
    }
    TYPES = {
        "storage": str,
        "thumbnails_folder": str,
        "temp_folder": str,
        "web_folder": str,
        "index": str,
        "accounts": str,
        "authorization_file": str,
        "address": str,
        "port": int,
        "ssl": bool,
        "ssl_cert": str,
        "ssl_key": str,
        "hash_buffer_size": int,
        "password_key": str,
        "token_expiration": int,
        "max_tokens": int,
        "download_buffer_size": int,
        "thumbnail_size": int,
        "cache_time": int,
    }

    def __init__(self, file_name: str):
        self.file_name = file_name
        self.config = dict()
        self.check_config()
        self.load_config()

    def load_config(self, name=None):
        if name is None:
            name = self.file_name
        log.debug("Loading config ...")
        with open(name, "r") as f:
            for line in f.readlines():
                match line.replace("=", " = ", 1).split():
                    case ("#", *comment):
                        # log.debug("Comment : ", " ".join(comment))
                        pass
                    case (name, "=", value):
                        if "${" in value:
                            # Replace ${variable} with previously defined variable
                            try:
                                value = re.sub(
                                    r"\${(.*)}",
                                    lambda m: self.config[m.group(1)],
                                    value,
                                )
                            except KeyError:
                                log.debug(
                                    f"Error : Invalid variable in line {line}. Currently defined variables : {self.config.keys()}"
                                )
                        if name in self.config:
                            log.debug(
                                f"WARNING : {name} is already defined as {self.config[name]}, redefining as {value}"
                            )
                        if name in self.TYPES:
                            if self.TYPES[name] is bool:
                                value = value.lower() == "true"
                            self.config[name] = self.TYPES[name](value)
                            log.debug(f"Loaded {name}")
                        else:
                            log.warning(f"{name} is not a valid setting")
                            self.config[
                                name
                            ] = value  # Can still be used for other settings
                    case ():
                        pass
                    case _:
                        log.warning("Weird line :", line)
        log.debug("Loaded config.")

    def check_config(self):
        if not os.path.exists(self.file_name):
            self.create_config(self.file_name)

    def create_config(self, name):
        log.debug("Creating config file ...")
        with open(name, "x") as f:  # Create and open the file for write
            lines = list()
            for name, value in self.DEFAULT.items():
                lines.append(f"{name}={value}")
                log.debug(f"Saved {name}")
            f.write("\n".join(lines))
        log.debug("Config created successfully. ")

    def __getattr__(self, name):
        if name in self.config:
            return self.config[name]
        elif name in self.DEFAULT:
            return self.TYPES[name](self.DEFAULT[name])
        else:
            raise AttributeError(f"ConfigFile has no attribute {name}")
