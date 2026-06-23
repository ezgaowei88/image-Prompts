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
import sys
import urllib.parse
from http import HTTPStatus

# Fix Windows console encoding for Chinese characters
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

PORT = 8000
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGES_DIR = os.path.join(ROOT_DIR, "images")
LOCAL_CASES_FILE = os.path.join(ROOT_DIR, "local_cases.json")


def _read_local_cases():
    """Read local cases from JSON file."""
    if os.path.exists(LOCAL_CASES_FILE):
        try:
            with open(LOCAL_CASES_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    return []


def _write_local_cases(cases, custom_categories=None, custom_models=None):
    """Write local cases to JSON file and update local_cases.js."""
    with open(LOCAL_CASES_FILE, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
    # Also write local_cases.js for file:// protocol support
    js_path = os.path.join(ROOT_DIR, "local_cases.js")
    js_content = "var LOCAL_CASES = " + json.dumps(cases, ensure_ascii=False, indent=2) + ";\n"
    # Also persist custom categories and models so file:// protocol can access them
    if custom_categories is not None:
        js_content += "var LOCAL_CUSTOM_CATEGORIES = " + json.dumps(custom_categories, ensure_ascii=False, indent=2) + ";\n"
    if custom_models is not None:
        js_content += "var LOCAL_CUSTOM_MODELS = " + json.dumps(custom_models, ensure_ascii=False, indent=2) + ";\n"
    with open(js_path, "w", encoding="utf-8") as f:
        f.write(js_content)


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
        elif path == "/api/move":
            self._handle_move()
        elif path == "/api/local-cases":
            self._handle_save_local_cases()
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

    def _handle_move(self):
        """Move an image folder from one category to another."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._json_response({"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return

        old_category = data.get("old_category", "").strip()
        new_category = data.get("new_category", "").strip()
        folder = data.get("folder", "").strip()

        if not old_category or not new_category or not folder:
            self._json_response({"error": "Missing old_category, new_category, or folder"}, HTTPStatus.BAD_REQUEST)
            return

        # Prevent path traversal
        for val in [old_category, new_category, folder]:
            if "/" in val or "\\" in val or ".." in val:
                self._json_response({"error": "Invalid parameter"}, HTTPStatus.BAD_REQUEST)
                return

        import shutil
        old_path = os.path.join(IMAGES_DIR, old_category, folder)
        new_path = os.path.join(IMAGES_DIR, new_category, folder)

        # If specified source doesn't exist, search all categories for this folder
        if not os.path.exists(old_path):
            found = False
            for cat_name in os.listdir(IMAGES_DIR):
                cat_dir = os.path.join(IMAGES_DIR, cat_name)
                if os.path.isdir(cat_dir):
                    candidate = os.path.join(cat_dir, folder)
                    if os.path.exists(candidate) and os.path.isdir(candidate):
                        old_path = candidate
                        old_category = cat_name
                        found = True
                        break
            if not found:
                self._json_response({"error": "Source folder not found in any category"}, HTTPStatus.NOT_FOUND)
                return

        os.makedirs(os.path.join(IMAGES_DIR, new_category), exist_ok=True)
        shutil.move(old_path, new_path)
        self._json_response({"success": True, "path": f"images/{new_category}/{folder}/output.jpg"})
        print(f"  [MOVE] images/{old_category}/{folder}/ -> images/{new_category}/{folder}/")

    def _json_response(self, data, status=HTTPStatus.OK):
        """Send a JSON response."""
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        """Handle GET API endpoints."""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/locate"):
            self._handle_locate()
        elif path == "/api/local-cases":
            self._handle_get_local_cases()
        else:
            super().do_GET()

    def _handle_get_local_cases(self):
        """Return local cases from the JSON file."""
        cases = _read_local_cases()
        self._json_response({"cases": cases})

    def _handle_save_local_cases(self):
        """Save local cases to the JSON file and update local_cases.js."""
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            self._json_response({"error": "Invalid JSON"}, HTTPStatus.BAD_REQUEST)
            return

        cases = data.get("cases", [])
        if not isinstance(cases, list):
            self._json_response({"error": "cases must be an array"}, HTTPStatus.BAD_REQUEST)
            return

        custom_categories = data.get("customCategories", None)
        custom_models = data.get("customModels", None)
        _write_local_cases(cases, custom_categories, custom_models)
        self._json_response({"success": True, "count": len(cases)})
        print(f"  [LOCAL-CASES] Saved {len(cases)} local cases")

    def _handle_locate(self):
        """Find which category directory an image folder lives in."""
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        folder = params.get("folder", [""])[0].strip()

        if not folder:
            self._json_response({"error": "Missing folder parameter"}, HTTPStatus.BAD_REQUEST)
            return

        # Prevent path traversal
        if "/" in folder or "\\" in folder or ".." in folder:
            self._json_response({"error": "Invalid folder"}, HTTPStatus.BAD_REQUEST)
            return

        # Search all category directories for this folder
        if os.path.exists(IMAGES_DIR):
            for cat_name in os.listdir(IMAGES_DIR):
                cat_dir = os.path.join(IMAGES_DIR, cat_name)
                if os.path.isdir(cat_dir):
                    candidate = os.path.join(cat_dir, folder, "output.jpg")
                    if os.path.exists(candidate):
                        self._json_response({
                            "found": True,
                            "category": cat_name,
                            "path": f"images/{cat_name}/{folder}/output.jpg"
                        })
                        return

        self._json_response({"found": False})

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

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORT), PromptHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\nServer stopped.")


if __name__ == "__main__":
    main()
