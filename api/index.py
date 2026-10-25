import sys
import os

# Add project root directory to path so imports work seamlessly on Vercel
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app

class CleanScriptNameMiddleware:
    """
    Normalizes SCRIPT_NAME so url_for() generates clean root-relative paths (/login, /scan, etc.)
    without altering Vercel's native PATH_INFO forwarding.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        environ['SCRIPT_NAME'] = ''
        return self.wsgi_app(environ, start_response)

app.wsgi_app = CleanScriptNameMiddleware(app.wsgi_app)
