import os
import zipfile
from time import time

import cv2
from PIL import Image
from flask import Blueprint, request, send_file

from accounts import Accounts
from configuration import ConfigFile
from file_manager import FileManager
from utils import require_login

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
            create_thumbnail(file_path, thumbnail_path, size)
            print("Created thumbnail for", file_path)

        elif fm.metadata(f_id).get("type") == "video":
            create_video_thumbnail(file_path, thumbnail_path, size)
            print("Created thumbnail for video", file_path)
        else:
            return {"message": "Thumbnail not available"}, 400

    # Cache the thumbnail for 1 day
    return (
        send_file(
            thumbnail_path,
            mimetype="image/png",
            as_attachment=False,
            download_name=f_id + ".png",
        ),
        200,
        {"Cache-Control": f"max-age={conf.cache_time}"},
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
                create_thumbnail(file_path, thumbnail_path, size)
                print("Created thumbnail for", file_path)
            elif fm.metadata(f_id).get("type") == "video":
                create_video_thumbnail(file_path, thumbnail_path, size)
                print("Created thumbnail for video", file_path)
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


def create_thumbnail(self, source: str, destination: str, size: int | None = None):
    if size is None:
        size = self.config.thumbnail_size
    with Image.open(source) as im:
        # Crop the image to a square (centered)
        width, height = im.size

        if width > height:
            left = (width - height) / 2
            top = 0
            right = (width + height) / 2
            bottom = height
        else:
            left = 0
            top = (height - width) / 2
            right = width
            bottom = (height + width) / 2

        im = im.crop((left, top, right, bottom))

        # Resize the image to the thumbnail size
        im.thumbnail((size, size), Image.ANTIALIAS)

        im.save(destination)


def create_video_thumbnail(video_path: str, thumbnail_path: str, size: int):

    # Open the video
    cap = cv2.VideoCapture(video_path)

    # Get the total number of frames
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Get the frame at 1/3rd of the video
    cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 3)
    _, frame = cap.read()

    # Save the frame as a thumbnail
    cv2.imwrite(thumbnail_path, frame)

    cap.release()

    # Resize the thumbnail
    FileManager.create_thumbnail(thumbnail_path, thumbnail_path, size)


# Get the main color of the image as #RRGGBB
def get_file_color(path, type):
    if type == "image":
        img = Image.open(path)
        img = img.resize((1, 1))
        color = img.getpixel((0, 0))
        if isinstance(color, int):
            color = (color, color, color)
        return "#" + "".join([f"{c:02x}" for c in color])
    elif type == "video":
        cap = cv2.VideoCapture(path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames // 3)
        _, frame = cap.read()
        frame.resize((1, 1))
        color = frame[0][0]
        cap.release()
        return f"#{color:06x}"
    else:
        return "#000000"
