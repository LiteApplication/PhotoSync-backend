from flask import Response, jsonify, Blueprint


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

        blueprint.add_url_rule(*args, **kwargs, view_func=func)
        return wrapper

    return decorator


def require_login(func):
    if "logged_in" in func.__code__.co_varnames:

        def wrapper(*args, **kwargs):
            from flask import request
            from accounts import Accounts

            return func(
                *args,
                **kwargs,
                logged_in=Accounts()._check_token(request.headers.get("Token"))
            )

        return wrapper

    def wrapper(*args, **kwargs):
        from flask import request
        from accounts import Accounts

        if not Accounts()._check_token(request.headers.get("Token")):
            return {"message": "Unauthorized"}, 401
        return func(*args, **kwargs)

    return wrapper


def require_admin(func):
    def wrapper(*args, **kwargs):
        from flask import request
        from accounts import Accounts

        if not Accounts()._check_token(request.headers.get("Token")):
            return {"message": "Unauthorized"}, 401
        if not Accounts().get_user().get("admin"):
            return {"message": "Unauthorized"}, 401
        return func(*args, **kwargs)

    return wrapper
