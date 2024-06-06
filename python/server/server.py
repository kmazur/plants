import os
import shutil
import http.server
import urllib.parse
from http import HTTPStatus

# Configuration
UPLOAD_FOLDER = 'uploads'
AUTH_TOKEN = 'your_secret_token'

class SimpleHTTPRequestHandler(http.server.BaseHTTPRequestHandler):

    def do_GET(self):
        token = self.get_auth_token()
        if token != AUTH_TOKEN:
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.end_headers()
            self.wfile.write(b'Unauthorized')
            return

        parsed_path = urllib.parse.urlparse(self.path)
        file_path = os.path.join(UPLOAD_FOLDER, os.path.basename(parsed_path.path))

        if os.path.exists(file_path) and os.path.isfile(file_path):
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-type', 'application/octet-stream')
            self.end_headers()
            with open(file_path, 'rb') as file:
                shutil.copyfileobj(file, self.wfile)
        else:
            self.send_response(HTTPStatus.NOT_FOUND)
            self.end_headers()
            self.wfile.write(b'File not found')

    def do_POST(self):
        token = self.get_auth_token()
        if token != AUTH_TOKEN:
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.end_headers()
            self.wfile.write(b'Unauthorized')
            return

        content_length = int(self.headers['Content-Length'])
        parsed_path = urllib.parse.urlparse(self.path)
        file_path = os.path.join(UPLOAD_FOLDER, os.path.basename(parsed_path.path))

        with open(file_path, 'wb') as output_file:
            output_file.write(self.rfile.read(content_length))

        self.send_response(HTTPStatus.CREATED)
        self.end_headers()
        self.wfile.write(b'File uploaded')

    def get_auth_token(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query_params = urllib.parse.parse_qs(parsed_path.query)
        return query_params.get('token', [None])[0]

def run(server_class=http.server.HTTPServer, handler_class=SimpleHTTPRequestHandler, port=8080):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting server on port {port}')
    httpd.serve_forever()

if __name__ == '__main__':
    run()