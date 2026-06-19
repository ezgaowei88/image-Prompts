"""Local server for image-Prompts: serves static files + provides image upload API.

Usage: python server.py
Then open http://localhost:8000 in your browser.

Features:
- Serves index.html and all static files (images/, etc.)
- POST /api/upload: saves uploaded image to images/{category}/{folder}/output.jpg
- POST /api/delete: deletes an image folder
- GET /api/cases: returns allCases JSON from index.html
"""
import http.server
import json
import os
import re
import socketserver
import urllib.parse
from http import HTTPStatus

PORT = 8000
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(ROOT_DIR, "images")


class PromptHandler(http.server.SimpleHTTPRequestHandler):
    """Custom handler that serves static files and handles API endpoints."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT_DIR, **kwargs)

    def do_POST(self):
        """Handle image upload and delete."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/api/upload":
            self._handle_upload()
        elif path == "/api/delete":
            self._handle_delete()
        else:
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

    def _handle_upload(self):
        """Save uploaded image to images/{category}/{folder}/output.jpg"""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._json_response({"error": "No data"}, HTTPStatus.BAD_REQUEST)
            return

        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._json_response({"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return

        category = data.get("category", "").strip()
        folder = data.get("folder", "").strip()
        image_data = data.get("image", "")  # base64 data URL

        # Validate inputs
        if not category or not folder or not image_data:
            self._json_response({"error": "Missing category, folder, or image"}, HTTPStatus.BAD_REQUEST)
            return

        # Sanitize: prevent path traversal
        if "/" in category or "\\" in category or ".." in category:
            self._json_response({"error": "Invalid category"}, HTTPStatus.BAD_REQUEST)
            return
        if "/" in folder or "\\" in folder or ".." in folder:
            self._json_response({"error": "Invalid folder"}, HTTPStatus.BAD_REQUEST)
            return

        # Parse base64 data URL: data:image/jpeg;base64,/9j/4AAQ...
        if "," in image_data:
            header, b64data = image_data.split(",", 1)
        else:
            b64data = image_data

        import base64
        try:
            img_bytes = base64.b64decode(b64data)
        except Exception:
            self._json_response({"error": "Invalid image data"}, HTTPStatus.BAD_REQUEST)
            return

        if len(img_bytes) < 100:
            self._json_response({"error": "Image too small"}, HTTPStatus.BAD_REQUEST)
            return

        # Create directory and save
        save_dir = os.path.join(IMAGES_DIR, category, folder)
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, "output.jpg")

        with open(save_path, "wb") as f:
            f.write(img_bytes)

        # Return the relative path for the frontend
        rel_path = f"images/{category}/{folder}/output.jpg"
        self._json_response({
            "success": True,
            "path": rel_path,
            "size": len(img_bytes)
        })
        print(f"  [UPLOAD] Saved {len(img_bytes)//1024}KB -> {rel_path}")

    def _handle_delete(self):
        """Delete an image folder."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._json_response({"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return

        category = data.get("category", "").strip()
        folder = data.get("folder", "").strip()

        if not category or not folder:
            self._json_response({"error": "Missing category or folder"}, HTTPStatus.BAD_REQUEST)
            return

        # Prevent path traversal
        if "/" in category or "\\" in category or ".." in category:
            self._json_response({"error": "Invalid category"}, HTTPStatus.BAD_REQUEST)
            return
        if "/" in folder or "\\" in folder or ".." in folder:
            self._json_response({"error": "Invalid folder"}, HTTPStatus.BAD_REQUEST)
            return

        import shutil
        del_path = os.path.join(IMAGES_DIR, category, folder)
        if os.path.exists(del_path) and os.path.isdir(del_path):
            shutil.rmtree(del_path)
            self._json_response({"success": True})
            print(f"  [DELETE] Removed images/{category}/{folder}/")
        else:
            self._json_response({"error": "Folder not found"}, HTTPStatus.NOT_FOUND)

    def _json_response(self, data, status=HTTPStatus.OK):
        """Send a JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        """Handle CORS preflight."""
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def end_headers(self):
        """Add CORS headers to all responses."""
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()

    def log_message(self, format, *args):
        """Custom logging - suppress static file noise, show API calls."""
        msg = format % args
        if "/api/" in msg:
            print(f"  {msg}")
        # Suppress static file request logs for cleaner output


def main():
    # Ensure images directory exists
    os.makedirs(IMAGES_DIR, exist_ok=True)

    print("=" * 50)
    print(f"  Image Prompts Local Server")
    print(f"  Serving at: http://localhost:{PORT}")
    print(f"  Root dir:   {ROOT_DIR}")
    print(f"  Images dir: {IMAGES_DIR}")
    print("=" * 50)
    print()
    print("  Press Ctrl+C to stop the server")
    print()

    with socketserver.TCPServer(("", PORT), PromptHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nServer stopped.")


if __name__ == "__main__":
    main()
