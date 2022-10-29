from configuration import ConfigFile
import os
import json
import hashlib
from PIL import Image



def creation_date(path_to_file):
    stat = os.stat(path_to_file)
    try:
        return stat.st_birthtime
    except AttributeError:
        # We're probably on Linux. No easy way to get creation dates here,
        # so we'll settle for when its content was last modified.
        return stat.st_mtime


class FileManager:
    def __init__(self, config: ConfigFile):
        self.config = config
        self.path = config.storage
        self.index = self.load_index()
    
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
        if not force_update and name in self.index and os.path.exists(name):
            return self.index[name]
        if not os.path.exists(self.get_file_path(name)):
            return None
        info = {}
        info["name"] = name
        info["path"] = self.get_file_path(name)
        info["extension"] = self.get_extension(name)
        info["date"] = creation_date(self.get_file_path(name))
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
                return None
        if info["type"] == "image":
            try:
                info["date"] = Image.open(self.get_file_path(name)).getexif().get(36867, default=info["date"])
            except:
                print("Error while reading exif data for :", name)
        info["path"] = self.get_file_path(name)
        return info

    def populate_index(self, force_update: bool = False):
        for root, dirs, files in os.walk(self.path):
            root = root.replace(self.path, "", 1)
            for file in files:
                if self.config.index in file:
                    continue
                self.index[file] = self.get_file_info(os.path.join(root, file), force_update)
        self.save_index()
    
    def get_file_list(self):
        return self.index.keys()
    
    def get_file_list_by_type(self, type: str):
        return [file for file in self.index if self.index[file]["type"] == type]
    
    def get_file_list_by_format(self, format: str):
        return [file for file in self.index if self.index[file]["format"] == format]

    def get_all_infos(self):
        return self.index
