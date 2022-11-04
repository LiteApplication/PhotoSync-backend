import hashlib
import json
import logging
import os
import shutil
import uuid
from timeit import default_timer as timer

from flask import Blueprint, request, send_file
from werkzeug.utils import secure_filename

from accounts import Accounts
from configuration import ConfigFile
from utils import Singleton, get_exif_date, require_admin, require_login

log = logging.getLogger("file_manager")

bp = Blueprint("file_manager", __name__, url_prefix="/api/files")
fileio = Blueprint("fileio", __name__, url_prefix="/api/fileio")


SHARED_KEYS = [
    "color",
    "path",
    "date",
    "extension",
    "type",
    "format",
    "owner",
    "id",
    "hash",
]


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
        self.ordered_files = []
        self.load_index()  # Index is a dict with the id as key

        if not os.path.exists(self.path):
            os.makedirs(self.path)

    def load_index(self):
        if not os.path.exists(self.config.index):
            self.index = {}
            with open(self.config.index, "w") as f:
                f.write("{}")
            self.known_files = set()
            self.ordered_files = []
            print("Index file created")
            return
        with open(self.config.index, "r") as f:
            self.index = json.load(f)
            self.known_files = {f["path"] for f in self.index.values()}
            self.update_order()
            print("Loaded index with", len(self.index), "files")

    def update_order(self):
        self.ordered_files = sorted(
            self.index, key=lambda f: self.index[f]["date"], reverse=True
        )

    def save_index(self):
        with open(self.config.index, "w") as f:
            json.dump(self.index, f)

    def get_file_path(self, name: str):
        return os.path.join(self.path, name)

    def get_path_id(self, f_id: str):
        if not f_id in self.index:
            return None
        return self.get_file_path(self.index[f_id]["path"])

    def metadata(self, f_id: str):
        if not f_id in self.index:
            return None
        return self.index[f_id]

    def get_extension(self, name: str):
        return os.path.splitext(name)[1]

    def get_known_files(self):
        for f_id in self.index:
            yield self.index[f_id]["id"]

    def get_file_info(self, rel_path: str, force_update: bool = False):
        import thumbnails

        if (
            not force_update
            and rel_path in self.known_files
            and os.path.exists(self.get_file_path(rel_path))
        ):
            return self.index[rel_path]
        self.known_files.add(rel_path)
        if not os.path.exists(self.get_file_path(rel_path)):
            return None
        info = {}
        info["path"] = rel_path
        info["extension"] = self.get_extension(rel_path)
        info["date"] = creation_date(self.get_file_path(rel_path))
        info["owner"] = "<index>"
        info["id"] = str(uuid.uuid4())
        info["metadata"] = {}
        info["user_tags"] = {}
        info["rights"] = []

        # Compute hash md5 for the file
        h = hashlib.md5()
        with open(self.get_file_path(rel_path), "rb") as f:
            while True:
                data = f.read(self.config.hash_buffer_size)
                if not data:
                    break
                h.update(data)

        info["hash"] = h.hexdigest()

        unsupported = False
        match self.get_extension(rel_path).lower():
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
            case (".3gp"):
                info["type"] = "video"
                info["format"] = "3gp"
            case _:
                print("Unsupported file type :", rel_path)
                unsupported = True
                info["type"] = "unknown"
                info["format"] = os.path.splitext(rel_path)[1][1:]
        if info["type"] == "image":
            try:
                d = get_exif_date(self.get_file_path(rel_path))
                info["date"] = d if d else info["date"]
            except:
                raise
                print("Error while reading exif data for :", rel_path)

        elif info["type"] == "video":
            # Get the creation date from the video metadata
            try:
                import mutagen

                metadata = mutagen.File(self.get_file_path(rel_path))
                if metadata:
                    d = metadata.get("creation_time")
                    if d:
                        info["date"] = d[0]
            except:
                print("Error while reading metadata for :", rel_path)

        info["color"] = thumbnails.get_file_color(
            self.get_file_path(rel_path), info["type"]
        )

        return info, info["id"]

    def populate_index(
        self, force_update: bool = False, path_id: dict[str, str] | None = None
    ):
        # Use name_id to preserve ids across upgrades in the index
        use_name = path_id is not None
        for root, dirs, files in os.walk(self.path):
            root = root.replace(self.path, "", 1)
            if root.startswith(os.sep):
                root = root[1:]
            for file in files:
                path = os.path.join(root, file)
                if path in self.known_files:
                    continue
                f_info, f_id = self.get_file_info(path, force_update)
                if use_name:
                    f_id = path_id.get(path, f_id)  # Change f_id if available
                    f_info["id"] = f_id
                self.index[f_id] = f_info
                log.debug(f"Indexed {file}")

    def get_all_infos(self):
        return self.index

    def is_allowed(self, f_id: str, user: str):
        # Check if the file exists
        if not f_id in self.index:
            return False

        # Check if the user is the owner
        if self.index[f_id]["owner"] == user:
            return True

        # Check if the file is public
        if "public" in self.index[f_id]["rights"]:
            return True

        # Check if the user is in the allowed list
        if user in self.index[f_id]["rights"]:
            return True

        # Check if the user is an admin
        return Accounts()._get_accounts()[user]["admin"]

    def get_user_files(self, username):
        return [f for f in self.ordered_files if self.is_allowed(f, username)]


@bp.route("/upgrade-index", methods=["PATCH"])
@require_admin
def upgrade_index():
    print("Upgrading index")

    begin = timer()

    fm = FileManager()
    config = ConfigFile()

    # Stats
    entries_modified = 0
    fields_dropped = set()
    entries_dropped = 0

    # Read the index
    fm.load_index()
    index = fm.get_all_infos().copy()

    # Save the name-id matchings
    path_id = {v["path"]: k for k, v in index.items()}

    # Clear the index
    fm.index = {}
    shutil.copy(config.index, config.index + ".bak")
    try:
        with open(config.index, "w") as f:
            json.dump({}, f)
        fm.known_files = set()
        fm.odered_files = []

        # Repopulate the index
        fm.populate_index(force_update=True, path_id=path_id)

        # Merge the old index with the new one
        for f_id in index:
            if f_id in fm.index:
                # The file is still here, we can merge the data
                for k in index[f_id]:
                    if k in fm.index[f_id]:
                        t = type(fm.index[f_id][k])
                        if fm.index[f_id][k] != index[f_id][k]:
                            fm.index[f_id][k] = t(index[f_id][k])
                            entries_modified += 1
                        # Convert the type if possible
                        try:
                            fm.index[f_id][k] = t(fm.index[f_id][k])
                        except:
                            pass
                    else:
                        if not k in fields_dropped:
                            print("Dropping field :", k)
                        fields_dropped.add(k)

            else:
                # The file was removed, we can't merge the data
                entries_dropped += 1
                print("Dropping entry :", f_id)
                pass

        # Save the index
        with open(config.index, "w") as f:
            json.dump(fm.index, f)
        fm.update_order()

        return {
            "message": "OK",
            "entries_modified": entries_modified,
            "fields_dropped": list(fields_dropped),
            "entries_dropped": entries_dropped,
            "elapsed_time_ms": (timer() - begin) * 1000,
        }
    except Exception as e:
        import traceback

        # Restore index in case of failure
        shutil.move(config.index + ".bak", config.index)

        print(traceback.format_exc())
        return traceback.format_exc()


@bp.route("/get-by/<string:attribute>/<path:value>")
@require_login
def get_by_attribute(attribute, value):
    fm = FileManager()
    account = Accounts()

    user = account.get_user()
    admin = user["admin"]

    if attribute not in SHARED_KEYS:
        return {"message": "Invalid attribute"}, 400

    if attribute == "owner":
        if value == "me" or value == user["username"]:
            value = user["username"]
        elif not admin:
            return {"message": "You are not allowed to do that"}, 403

    if attribute == "id":
        if value not in fm.index:
            return {"message": "File not found"}, 404
        if not fm.is_allowed(value, user["username"]):
            return {"message": "You are not allowed to do that"}, 403
        return {k: fm.index[value][k] for k in SHARED_KEYS}

    return [
        {k: fm.index[f_id][k] for k in SHARED_KEYS}
        for f_id in fm.index
        if fm.index[f_id][attribute] == value and fm.is_allowed(f_id, user["username"])
    ]


@bp.route("/get-all")
@require_admin
def get_all():
    # Return all files in the index
    fm = FileManager()
    return fm.get_all_infos()


@bp.route("/file-list")
@require_login
def get_file_list():
    # Return all the files owned by the user
    # in the correct order
    fm = FileManager()
    account = Accounts()

    user = account.get_user()

    return [
        {k: fm.index[f_id][k] for k in SHARED_KEYS}
        for f_id in fm.ordered_files
        if fm.index[f_id]["owner"] == user["username"]
    ]


@bp.route("/file-list/id/<string:last_id>/<int:count>")
@require_login
def get_file_list_from(last_id, count):
    # Return all the files owned by the user
    # in the correct order
    fm = FileManager()
    account = Accounts()

    user = account.get_user()
    user_files = fm.get_user_files(user["username"])

    if last_id == "null":
        last_index = 0
    elif last_id not in fm.index:
        return {"message": "File not found"}, 404
    else:
        last_index = user_files.index(last_id)

    count = min(count, len(user_files) + last_index)

    return [
        {k: fm.index[f_id][k] for k in SHARED_KEYS}
        for f_id in user_files[last_index + 1 : last_index + count]
        if fm.index[f_id]["owner"] == user["username"]
    ]


@bp.route("/file-list/before/<int:timestamp>/<int:count>")
@require_login
def get_file_list_after(timestamp, count):
    # Return all the files owned by the user
    # in the correct order
    fm = FileManager()
    account = Accounts()

    user = account.get_user()
    user_files = fm.get_user_files(user["username"])

    # Find the first file before the timestamp
    last_index = 0
    for f_id in user_files:
        if fm.index[f_id]["date"] < timestamp:
            break
        last_index += 1

    count = min(count, len(user_files) + last_index)

    return [
        {k: fm.index[f_id][k] for k in SHARED_KEYS}
        for f_id in user_files[last_index + 1 : last_index + count]
        if fm.index[f_id]["owner"] == user["username"]
    ]


@bp.route("/file-list/between/<int:timestamp1>/<int:timestamp2>/<int:count>")
@require_login
def get_file_list_between(timestamp1, timestamp2, count):
    # Return all the files owned by the user
    # in the correct order
    fm = FileManager()
    account = Accounts()

    user = account.get_user()
    user_files = fm.get_user_files(user["username"])

    # Find the first file before the timestamp
    last_index = 0
    for f_id in user_files:
        if fm.index[f_id]["date"] < timestamp1:
            break
        last_index += 1

    count = min(count, len(user_files) + last_index)

    return [
        {k: fm.index[f_id][k] for k in SHARED_KEYS}
        for f_id in user_files[last_index + 1 : last_index + count]
        if fm.index[f_id]["owner"] == user["username"]
        and fm.index[f_id]["date"] < timestamp2
    ]


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
        for f_id in list(fm.index):
            if not os.path.exists(fm.get_file_path(fm.index[f_id]["path"])):
                name = fm.index[f_id]["path"]
                del fm.index[f_id]
                if name in fm.known_files:
                    fm.known_files.remove(name)
        fm.save_index()
        end = timer()
    except Exception as e:
        raise
        return {"message": e.args}, 500
    return {"message": "OK", "elapsed": (end - start) * 1000}, 200


@bp.route("/refesh-index", methods=["PATCH"])
@require_admin
def refresh_index():
    """Read the index file and update the index (does not reindex the whole storage)"""
    fm = FileManager()
    fm.load_index()
    fm.known_files.clear()
    for f_id in fm.index:
        fm.known_files.add(fm.index[f_id]["path"])
    return {"message": "OK"}, 200


@fileio.route("/download/<string:f_id>", methods=["GET"])
@require_login
def download_file(f_id: str):
    fm = FileManager()
    account = Accounts()

    user = account.get_user()

    if f_id not in fm.index:
        return {"message": "File not found"}, 404

    if not fm.is_allowed(f_id, user["username"]):
        print(fm.index[f_id]["owner"], user["username"])
        return {"message": "You are not allowed to do that"}, 403

    return send_file(
        fm.get_file_path(fm.index[f_id]["path"]),
        as_attachment=True,
        download_name=fm.index[f_id]["path"],
        last_modified=fm.index[f_id]["date"],
    )


@fileio.route("/upload", methods=["POST"])
@require_login
def upload_file():
    fm = FileManager()
    account = Accounts()

    user = account.get_user()
    username = user["username"]

    if "file" not in request.files:
        return {"message": "No file part"}, 400

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

        # Store the file in the user's folder (does not impact ownership but it is easier to manage)
        if not os.path.exists(fm.get_file_path(username)):
            os.makedirs(fm.get_file_path(username))
        filename = os.path.join(username, filename)

        # Check if the file already exists
        if filename in fm.known_files:
            return {"message": "File already exists"}, 400
        file.save(
            fm.get_file_path(filename),
            buffer_size=ConfigFile().download_buffer_size,
        )
        f_info, f_id = fm.get_file_info(filename, force_update=True)
        if "date" in request.form and request.form["date"] != "0":
            try:
                f_info["date"] = int(request.form["date"])
            except ValueError:
                pass  # Use the guessed date
        f_info["owner"] = username
        fm.index[f_id] = f_info
        fm.save_index()
        return {"message": "OK", "id": f_id}, 200
    return {"message": "Invalid file"}, 400


@bp.route("/delete/<string:f_id>", methods=["DELETE"])
@require_login
def delete_file(f_id: str):
    fm = FileManager()
    account = Accounts()
    trash = ConfigFile().trash_folder

    user = account.get_user()

    if f_id not in fm.index:
        return {"message": "File not found"}, 404

    if not fm.is_allowed(f_id, user["username"]):
        return {"message": "You are not allowed to do that"}, 403

    # Move the file to the trash folder (create a folder for the user)
    if not os.path.exists(os.path.join(trash, user["username"])):
        os.makedirs(os.path.join(trash, user["username"]))
    os.rename(
        fm.get_file_path(fm.index[f_id]["path"]),
        os.path.join(trash, user["username"], os.path.basename(fm.index[f_id]["path"])),
    )

    del fm.index[f_id]
    fm.save_index()

    return {"message": "OK"}, 200
