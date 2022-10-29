from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import file_manager
import json

from configuration import ConfigFile

class ApiRequestHandler(BaseHTTPRequestHandler):
    def send_data(self, data, headers:bool = True, code: int = 200):
        if headers:
            self.send_response(code)
        encoded = json.dumps(data, indent=4).encode("utf-8")
        if headers:
            self.send_header('Content-type', 'text/plain')
            self.send_header('Content-length', len(encoded))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
        self.wfile.write(encoded)
    def do_API(self):        
        if self.path[1] == "all":
            print("Sending all")
            self.send_data(self.server.file_manager.get_all_infos())

class HTTPRequestsHandler(ApiRequestHandler):
    def _send_headers(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
    def do_GET(self):
        self.path = [p for p in self.path.split("/") if p] # remove empty elements
        if self.path[0] == "api":
            self.do_API()
        else:
            # Serve the static files
            self._send_headers()
            self.wfile.write(b"Not the API")
            

class PhotoSyncServer(ThreadingHTTPServer):
    def __init__(self, config: ConfigFile):
        super().__init__((config.address, config.port), HTTPRequestsHandler)
        self.config = config
        self.file_manager = file_manager.FileManager(config)
    def start(self):
        self.file_manager.populate_index()
        print('Starting server...')
        try:
            self.serve_forever()
        except KeyboardInterrupt:
            print('Server stopped.')
            self.server_close()
            exit()
    
