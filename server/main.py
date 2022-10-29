#!/usr/bin/python3.10
import argparse

from configuration import ConfigFile
import server

def main():
    parser = argparse.ArgumentParser(description="Photo synchronizer with a client app, this will store photos on the server leaving space on your phone.")
    parser.add_argument("--config", "-c", required=False, default="/etc/photosync.conf", type=str)
    args = parser.parse_args()
    config = ConfigFile(args.config)
    server.PhotoSyncServer(config).start()


if __name__ == "__main__":
    main()