from flask import Blueprint, Response, jsonify, request


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
