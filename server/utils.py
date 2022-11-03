import datetime
import re

from flask import Blueprint, Response, jsonify, request
from PIL import Image


class Singleton(type):
    _instance = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instance:
            cls._instance[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instance[cls]


def blueprint_api(blueprint: Blueprint, *args, **kwargs):
    def decorator(func):
        def wrapper(*args, **kwargs):
            response = func(*args, **kwargs)
            if isinstance(response, Response):
                return response
            elif isinstance(response, tuple):
                return Response(jsonify(response[0]), *response[1:])
            else:
                return Response(jsonify(response))

        # Give the wrapper the same attributes as the original function
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__dict__.update(func.__dict__)

        blueprint.add_url_rule(*args, **kwargs, view_func=wrapper)

        return wrapper

    return decorator


def require_login(func):
    def wrapper(*args, **kwargs):
        from flask import request

        from accounts import Accounts

        if not Accounts()._check_token(request.headers.get("Token")):
            return {"message": "Unauthorized"}, 401
        return func(*args, **kwargs)

    # Give the wrapper the same attributes as the original function
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    wrapper.__dict__.update(func.__dict__)

    return wrapper


def require_admin(func):
    def wrapper(*args, **kwargs):
        from accounts import Accounts

        if not Accounts()._check_token(request.headers.get("Token")):
            return {"message": "Unauthorized"}, 401
        if not Accounts().get_user().get("admin"):
            return {"message": "Unauthorized"}, 401
        return func(*args, **kwargs)

    # Give the wrapper the same attributes as the original function
    wrapper.__name__ = func.__name__
    wrapper.__doc__ = func.__doc__
    wrapper.__dict__.update(func.__dict__)

    return wrapper


def get_exif_date(filename):
    # Exif date has the format %Y:%m:%d %H:%M:%S
    # We need to convert it to unix timestamp (int)

    convert = lambda x: int(
        datetime.datetime.strptime(x, "%Y:%m:%d %H:%M:%S").timestamp()
    )
    image = Image.open(filename)
    try:
        exif = image._getexif()
    except AttributeError:
        exif = {}
    if exif is None:
        exif = {}

    # 36867 is the EXIF tag for DateTimeOriginal
    exif_date = exif.get(36867)
    if exif_date is not None:
        return convert(exif_date)
    # 36868 is the EXIF tag for DateTimeDigitized
    exif_date = exif.get(36868)
    if exif_date is not None:
        return convert(exif_date)
    # 306 is the EXIF tag for DateTime
    exif_date = exif.get(306)
    if exif_date is not None:
        return convert(exif_date)

    # If we reach this point, we didn't find any date
    # we try to get the date from the filename
    return get_date_filename(filename)


def get_date_filename(filename):
    if filename is None:
        return None
    pattern = r".*?((?:20|19)\d{2})-?(0\d|1[0-2])-?(0\d|1\d|2\d|3[0-1])"
    match = re.search(pattern, filename)
    if match is not None:
        return int(
            datetime.datetime(
                year=int(match.group(1)),
                month=int(match.group(2)),
                day=int(match.group(3)),
            ).timestamp()
        )
    pattern = r".*?((?:20|19)\d{2})"
    match = re.search(pattern, filename)
    if match is not None:
        return int(
            datetime.datetime(year=int(match.group(1)), month=1, day=1).timestamp()
        )
    return None
