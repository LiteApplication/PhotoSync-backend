import os
from time import time
import zipfile

from flask import Blueprint, send_file, request

from accounts import Accounts
from file_manager import FileManager
from utils import require_login
from configuration import ConfigFile

bp = Blueprint("thumbnails", __name__, url_prefix="/api/timg")


@bp.route("/get/<string:f_id>/<int:size>")
@require_login
def get_thumbnail(f_id: str, size: int):
    user = Accounts().get_user()
    fm = FileManager()
    conf = ConfigFile()

    if size == 0:
        size = conf.thumbnail_size

    # Check if the file exists
    file_path = fm.get_path_id(f_id)
    if file_path is None:
        return {"message": "File not found"}, 404

    # Check if the user has access to the file
    if not user.get("admin"):
        if not fm.metadata(f_id).get("owner") == user.get("username"):
            return {"message": "Unauthorized"}, 401

    # Check if the thumbnail exists
    thumbnail_path = os.path.join(conf.thumbnails_folder, f_id + f"{size}.png")
    if not os.path.exists(thumbnail_path):
        # Create the thumbnail folder if it doesn't exist
        if not os.path.exists(conf.thumbnails_folder):
            os.mkdir(conf.thumbnails_folder)

        # Create the thumbnail
        if fm.metadata(f_id).get("type") == "image":
            fm.create_thumbnail(file_path, thumbnail_path, size)
            print("Created thumbnail for", file_path)
        else:
            return {"message": "Thumbnail not found"}, 404

    return send_file(
        thumbnail_path,
        mimetype="image/png",
        as_attachment=False,
        download_name=f_id + ".png",
    )


@bp.route("/get-multiple/<int:size>", methods=["POST"])
@require_login
def get_multiple_thumbnails(size: int):
    user = Accounts().get_user()
    fm = FileManager()
    conf = ConfigFile()

    if size == 0:
        size = conf.thumbnail_size

    # Check if the user provided a list of files
    if not request.json:
        return {"message": "Invalid request"}, 400

    # Check if the user has access to the files
    if not user.get("admin"):
        for f_id in request.json:
            if not fm.metadata(f_id).get("owner") == user.get("username"):
                return {"message": f"Unauthorized ({f_id})"}, 401

    # Create the thumbnail folder if it doesn't exist
    if not os.path.exists(conf.thumbnails_folder):
        os.mkdir(conf.thumbnails_folder)

    # Create the required thumbnails
    for f_id in request.json:
        # Check if the file exists
        file_path = fm.get_path_id(f_id)
        if file_path is None:
            return {"message": f"File not found ({f_id})"}, 404

        # Check if the thumbnail exists
        thumbnail_path = os.path.join(conf.thumbnails_folder, f_id + f"{size}.png")
        if not os.path.exists(thumbnail_path):
            # Create the thumbnail
            if fm.metadata(f_id).get("type") == "image":
                fm.create_thumbnail(file_path, thumbnail_path, size)
                print("Created thumbnail for", file_path)
            else:
                return {"message": f"Could not create thumbnail ({f_id})"}, 404

    # Create a temporary zip folder
    if not os.path.exists(conf.temp_folder):
        os.mkdir(conf.temp_folder)

    # Zip the thumbnails
    zip_path = os.path.join(
        conf.temp_folder, f"timg_{user['username']}_{int(time())}.zip"
    )
    with zipfile.ZipFile(zip_path, "w") as zipf:
        for f_id in request.json:
            thumbnail_path = os.path.join(conf.thumbnails_folder, f_id + f"{size}.png")
            zipf.write(thumbnail_path, f_id + ".png")

    return send_file(
        zip_path,
        mimetype="application/zip",
        as_attachment=True,
        download_name="thumbnails.zip",
    )
