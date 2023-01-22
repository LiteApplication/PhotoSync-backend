#!/usr/bin/python3.10
import logging
import os

from flask import Flask, redirect, send_from_directory, request
from flask_cors import CORS

from .configuration import ConfigFile

from . import accounts, file_manager, thumbnails

app = None


def setup_logger():
    # create logger
    logger = logging.getLogger("PhotoSync")
    logger.setLevel(logging.DEBUG)

    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # create formatter
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    # add formatter to ch
    ch.setFormatter(formatter)

    # add ch to logger
    logger.addHandler(ch)


def main(config_file: str | None = None, run: bool = True):
    global app

    setup_logger()

    if config_file is None:
        config_file = os.environ.get("PHOTOSYNC_CONFIG", default="/etc/photosync.conf")

    config = ConfigFile(config_file)

    if os.getenv("PHOTOSYNC_TESTING", default=False):
        import shutil

        # Restore the default configuration
        source_path = os.getenv("PHOTOSYNC_TESTING")

        def restore(path):
            if not os.path.exists(path):
                return
            if os.path.isdir(path):
                os.system(f"rm -rf {path}")
                shutil.copytree(os.path.join(source_path, os.path.basename(path)), path)
            else:
                shutil.copy(os.path.join(source_path, os.path.basename(path)), path)

        def reset_all():
            from utils import Singleton

            print("Server reset (testing) ...")

            for file in [
                config.index,
                config.storage,
                config.thumbnails_folder,
                config.temp_folder,
                config.trash_folder,
                config.accounts,
                config.authorization_file,
            ]:
                restore(file)
            Singleton._instances[file_manager.FileManager] = None
            Singleton._instances[accounts.Accounts] = None

            fm = file_manager.FileManager(config)
            account_manager = accounts.Accounts(config)
            return "ok", 200

    else:
        fm = file_manager.FileManager(config)
        account_manager = accounts.Accounts(config)

    app = Flask(__name__)

    # Allow cross origin requests
    CORS(app, resources={r"*": {"origins": "*"}}, max_age=config.cache_time)

    if config.ssl:
        context = (config.ssl_cert, config.ssl_key)
    else:
        context = None

    # Add api endpoint
    app.register_blueprint(accounts.bp)
    app.register_blueprint(accounts.admin)
    app.register_blueprint(file_manager.bp)
    app.register_blueprint(file_manager.fileio)
    app.register_blueprint(thumbnails.bp)
    app.add_url_rule("/", "index", index_html)

    if os.getenv("PHOTOSYNC_TESTING", default=False):
        app.add_url_rule("/test-reset", "reset", reset_all)

    app.add_url_rule("/<path:path>", "static_web", static_web)

    if run:
        print("SSL:", config.ssl)
        app.run(config.address, config.port, ssl_context=context, threaded=True)
    else:
        config.ssl = False


def index_html():
    return redirect("/index.html")


def static_web(path):
    if path == "js/api.js":
        # Return the api.js file with the correct address
        # Read the file
        with open(os.path.join(ConfigFile().web_folder, path), "r") as f:
            content = f.read()

        # Replace the address with the Origin
        if request.headers.get("Host", False):
            api_host = "{}://{}".format(
                "https" if ConfigFile().ssl else "http", request.headers.get("Host")
            )
        else:
            api_host = "{protocol}://{host}:{port}".format(
                protocol="https" if ConfigFile().ssl else "http",
                host=ConfigFile().address
                if ConfigFile().address != "0.0.0.0"
                else "localhost",
                port=ConfigFile().port,
            )

        content = content.replace("${API_HOST}", api_host)
        return content, 200, {"Content-Type": "text/javascript"}

    return send_from_directory(ConfigFile().web_folder, path)


if __name__ == "__main__":
    import argparse

    default_config = os.environ.get("PHOTOSYNC_CONFIG", default="/etc/photosync.conf")

    parser = argparse.ArgumentParser(
        description="Photo synchronizer with a client app, this will store photos on the server leaving space on your phone."
    )
    parser.add_argument(
        "--config", "-c", required=False, default=default_config, type=str
    )
    args = parser.parse_args()

    main(config_file=args.config)
else:
    main(run=False)
