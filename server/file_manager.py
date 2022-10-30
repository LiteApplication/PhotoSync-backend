import hashlib
import json
import logging
import os
import uuid

from flask import request, Blueprint
from flask_restful import Resource
from flask_httpauth import HTTPBasicAuth
from PIL import Image
from accounts import Accounts

from configuration import ConfigFile
from utils import Singleton, blueprint_api, require_admin, require_login

log = logging.getLogger("file_manager")

bp = Blueprint("file_manager", __name__, url_prefix="/api/file_manager")


def creation_date(path_to_file):
    stat = os.stat(path_to_file)
    try:
        return int(stat.st_birthtime)
    except AttributeError:
        # We're probably on Linux. No easy way to get creation dates here,
        # so we'll settle for when its content was last modified.
        return int(stat.st_mtime)


# Make FileManager a singleton


class FileManager(Resource, metaclass=Singleton):
    """Class to manage files (this is an API endpoint)"""

    def __init__(self, config: ConfigFile):
        self.config = config
        self.path = config.storage
        self.index = self.load_index()

        if not os.path.exists(self.path):
            os.makedirs(self.path)

    def load_index(self):
        if not os.path.exists(self.config.index):
            return {}
        with open(self.config.index, "r") as f:
            return json.load(f)

    def save_index(self):
        with open(self.config.index, "w") as f:
            json.dump(self.index, f)

    def get_file_path(self, name: str):
        return os.path.join(self.path, name)

    def get_extension(self, name: str):
        return os.path.splitext(name)[1]

    def get_file_info(self, name: str, force_update: bool = False):
        if (
            not force_update
            and name in self.index
            and os.path.exists(self.get_file_path(name))
        ):
            return self.index[name]
        if not os.path.exists(self.get_file_path(name)):
            return None
        info = {}
        info["name"] = name
        info["path"] = self.get_file_path(name)
        info["extension"] = self.get_extension(name)
        info["date"] = creation_date(self.get_file_path(name))
        info["owner"] = "<index>"
        info["id"] = str(uuid.uuid4())

        # Compute hash md5 for the file
        h = hashlib.md5()
        with open(self.get_file_path(name), "rb") as f:
            while True:
                data = f.read(self.config.hash_buffer_size)
                if not data:
                    break
                h.update(data)

        info["hash"] = h.hexdigest()

        unsupported = False
        match self.get_extension(name):
            case (".jpg" | ".jpeg"):
                info["type"] = "image"
                info["format"] = "jpeg"
            case (".png"):
                info["type"] = "image"
                info["format"] = "png"
            case (".gif"):
                info["type"] = "image"
                info["format"] = "gif"
            case (".webp"):
                info["type"] = "image"
                info["format"] = "webp"
            case (".mp4"):
                info["type"] = "video"
                info["format"] = "mp4"
            case (".webm"):
                info["type"] = "video"
                info["format"] = "webm"
            case (".avi"):
                info["type"] = "video"
                info["format"] = "avi"
            case (".mov"):
                info["type"] = "video"
                info["format"] = "mov"
            case (".m4v"):
                info["type"] = "video"
                info["format"] = "m4v"
            case (".mkv"):
                info["type"] = "video"
                info["format"] = "mkv"
            case _:
                print("Unsupported file type :", name)
                unsupported = True
                info["type"] = "unknown"
                info["format"] = os.path.splitext(name)[1][1:]
        if info["type"] == "image":
            try:
                info["date"] = (
                    Image.open(self.get_file_path(name))
                    .getexif()
                    .get(36867, default=info["date"])
                )
            except:
                print("Error while reading exif data for :", name)
        info["path"] = self.get_file_path(name)
        if not unsupported:
            self.index[name] = info
        return info

    def populate_index(self, force_update: bool = False):
        for root, dirs, files in os.walk(self.path):
            root = root.replace(self.path, "", 1)
            if root.startswith(os.sep):
                root = root[1:]
            for file in files:
                self.index[os.path.join(root, file)] = self.get_file_info(
                    os.path.join(root, file), force_update
                )
                log.debug(f"Indexed {file}")
        self.save_index()

    def get_all_infos(self):
        return self.index


@require_login
@blueprint_api(bp, "/get-by/<string:attribute>/<string:value>")
def get_by_attribute(attribute, value):
    self = FileManager()
    account = Accounts()

    user = account.get_user()
    admin = user["admin"]
    return [
        file
        for file in FileManager().index
        if self.index[file][attribute] == value
        and (self.index[file]["owner"] == user or admin)
    ]


@require_login
@blueprint_api(bp, "/get-all")
def get():
    return FileManager().get_all_infos()


@require_admin
@blueprint_api(bp, "/reload")
def reload_index():
    try:
        FileManager().populate_index()
    except Exception as e:
        return {"message": e.args}, 500
    return 200
