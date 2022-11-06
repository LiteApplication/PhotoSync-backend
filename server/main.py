#!/usr/bin/python3.10
import logging

from flask import Flask, send_from_directory, redirect
from flask_restful import Api
from flask_cors import CORS

import accounts
import file_manager
import thumbnails
from configuration import ConfigFile

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
        config_file = "config.conf"
    config = ConfigFile(config_file)

    fm = file_manager.FileManager(config)
    account_manager = accounts.Accounts(config)

    app = Flask(__name__)

    # Allow cross origin requests
    CORS(app, resources={r"*": {"origins": "*"}}, max_age=config.cache_time)
    api = Api(app, "/api")

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
    app.add_url_rule("/<path:path>", "static_web", static_web)

    if run:
        print(config.ssl)
        app.run(config.address, config.port, ssl_context=context, threaded=True)


def index_html():
    return redirect("/index.html")


def static_web(path):
    return send_from_directory(ConfigFile().web_folder, path)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Photo synchronizer with a client app, this will store photos on the server leaving space on your phone."
    )
    parser.add_argument(
        "--config", "-c", required=False, default="/etc/photosync.conf", type=str
    )
    args = parser.parse_args()

    main(config_file=args.config)
else:
    main(run=False)
