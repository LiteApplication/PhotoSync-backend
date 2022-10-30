import hashlib
import json
import logging
import os
import uuid
from distutils.command.config import config
from timeit import default_timer as timer

from flask import Blueprint, request, send_file
from PIL import Image
from werkzeug.utils import secure_filename

from accounts import Accounts
from configuration import ConfigFile
from utils import Singleton, require_admin, require_login

log = logging.getLogger("file_manager")

bp = Blueprint("file_manager", __name__, url_prefix="/api/files")
fileio = Blueprint("fileio", __name__, url_prefix="/api/fileio")


def creation_date(path_to_file):
    stat = os.stat(path_to_file)
    try:
        return int(stat.st_birthtime)
    except AttributeError:
        # We're probably on Linux. No easy way to get creation dates here,
        # so we'll settle for when its content was last modified.
        return int(stat.st_mtime)


# Make FileManager a singleton


class FileManager(metaclass=Singleton):
    """Class to manage files (this is an API endpoint)"""

    def __init__(self, config: ConfigFile):
        self.config = config
        self.path = config.storage
        self.known_files = set()
        self.load_index()  # Index is a dict with the id as key

        if not os.path.exists(self.path):
            os.makedirs(self.path)

    def load_index(self):
        if not os.path.exists(self.config.index):
            self.index = {}
        with open(self.config.index, "r") as f:
            self.index = json.load(f)
            self.known_files = {f["name"] for f in self.index.values()}

    def save_index(self):
        with open(self.config.index, "w") as f:
            json.dump(self.index, f)

    def get_file_path(self, name: str):
        return os.path.join(self.path, name)

    def get_extension(self, name: str):
        return os.path.splitext(name)[1]

    def get_known_files(self):
        for f_id in self.index:
            yield self.index[f_id]["name"]

    def get_file_info(self, name: str, force_update: bool = False):
        if (
            not force_update
            and name in self.known_files
            and os.path.exists(self.get_file_path(name))
        ):
            return self.index[name]
        self.known_files.add(name)
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

        return info, info["id"]

    def populate_index(self, force_update: bool = False):
        for root, dirs, files in os.walk(self.path):
            root = root.replace(self.path, "", 1)
            if root.startswith(os.sep):
                root = root[1:]
            for file in files:
                if os.path.join(root, file) in self.known_files:
                    continue
                f_info, f_id = self.get_file_info(
                    os.path.join(root, file), force_update
                )
                self.index[f_id] = f_info
                log.debug(f"Indexed {file}")

    def get_all_infos(self):
        return self.index


@bp.route("/get-by/<string:attribute>/<path:value>")
@require_login
def get_by_attribute(attribute, value):
    fm = FileManager()
    account = Accounts()

    user = account.get_user()
    admin = user["admin"]

    shared_keys = [
        "name",
        "date",
        "extension",
        "type",
        "format",
        "owner",
        "id",
        "hash",
    ]

    if attribute not in shared_keys:
        return {"message": "Invalid attribute"}, 400

    if attribute == "owner":
        if value == "me" or value == user["username"]:
            value = user["username"]
        elif not admin:
            return {"message": "You are not allowed to do that"}, 403

    if attribute == "id":
        if value not in fm.index:
            return {"message": "File not found"}, 404
        return {k: fm.index[value][k] for k in shared_keys}

    return [
        {k: fm.index[f_id][k] for k in shared_keys}
        for f_id in fm.index
        if fm.index[f_id][attribute] == value
        and (fm.index[f_id]["owner"] == user["username"] or admin)
    ]


@bp.route("/get-all")
@require_admin
def get_all():
    return FileManager().get_all_infos()


@bp.route("/reload", methods=["PATCH"])
@require_admin
def reload_index():
    """Reindex the whole storage"""
    try:
        # Time the reload
        start = timer()
        fm = FileManager()
        fm.populate_index()

        # Remove files that are not in the storage anymore
        for f_id in fm.index:
            if not os.path.exists(fm.get_file_path(fm.index[f_id]["name"])):
                name = fm.index[f_id]["name"]
                del fm.index[f_id]
                if name in fm.known_files:
                    fm.known_files.remove(name)
        fm.save_index()
        end = timer()
    except Exception as e:
        return {"message": e.args}, 500
    return {"message": "OK", "elapsed": (end - start) * 1000}, 200


@bp.route("/refesh-index", methods=["PATCH"])
@require_admin
def refresh_index():
    """Read the index file and update the index (does not reindex the whole storage)"""
    fm = FileManager()
    fm.index = fm.load_index()
    fm.known_files.clear()
    for f_id in fm.index:
        fm.known_files.add(fm.index[f_id]["name"])
    return {"message": "OK"}, 200


@fileio.route("/download/<string:f_id>", methods=["GET"])
@require_login
def download_file(f_id: str):
    fm = FileManager()
    account = Accounts()

    user = account.get_user()
    admin = user["admin"]

    if f_id not in fm.index:
        return {"message": "File not found"}, 404

    if not admin and fm.index[f_id]["owner"] != user["username"]:
        print(fm.index[f_id]["owner"], user["username"])
        return {"message": "You are not allowed to do that"}, 403

    return send_file(
        fm.get_file_path(fm.index[f_id]["name"]),
        as_attachment=True,
        download_name=fm.index[f_id]["name"],
        last_modified=fm.index[f_id]["date"],
    )


@fileio.route("/upload", methods=["POST"])
@require_login
def upload_file():
    fm = FileManager()
    account = Accounts()

    user = account.get_user()

    if "file" not in request.files:
        return {"message": "No file part"}, 400

    if "name" not in request.form:
        return {"message": f"No name provided"}, 400

    file = request.files["file"]
    if file.filename == "":
        return {"message": "No selected file"}, 400

    # jpg, jpeg, png, gif, webp, mp4, webm, avi, mov, m4v, mkv
    if not file.filename.endswith(
        (
            ".jpg",
            ".jpeg",
            ".png",
            ".gif",
            ".webp",
            ".mp4",
            ".webm",
            ".avi",
            ".mov",
            ".m4v",
            ".mkv",
        )
    ):
        return {"message": "Invalid file type"}, 400

    if file:
        filename = secure_filename(file.filename)
        file.save(
            fm.get_file_path(filename), buffer_size=ConfigFile().download_buffer_size
        )
        f_info, f_id = fm.get_file_info(filename, force_update=True)
        if "date" in request.form and request.form["date"] != "0":
            try:
                f_info["date"] = int(request.form["date"])
            except ValueError:
                pass  # Use the guessed date
        fm.index[f_id] = f_info
        fm.save_index()
        return {"message": "OK", "id": f_id}, 200
    return {"message": "Invalid file"}, 400