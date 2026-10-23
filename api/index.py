import sys
import os

# Add project root directory to path so imports work seamlessly on Vercel
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app

class VercelPathMiddleware:
    """
    Normalizes PATH_INFO when Vercel routes traffic through /api/index
    so Flask correctly matches all declared routes (/ , /scan, /compare, etc.).
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path_info = environ.get('PATH_INFO', '')
        # Check original forwarded URI or matched path from Vercel edge proxy
        forwarded_uri = (
            environ.get('HTTP_X_FORWARDED_URI')
            or environ.get('HTTP_X_NOW_ROUTE_MATCHES')
            or environ.get('HTTP_X_VERCEL_PATH')
        )
        if forwarded_uri:
            clean_path = forwarded_uri.split('?')[0]
            if clean_path.startswith('/api/index'):
                clean_path = clean_path[len('/api/index'):] or '/'
            elif clean_path.startswith('/api'):
                clean_path = clean_path[len('/api'):] or '/'
            environ['PATH_INFO'] = clean_path
        elif path_info.startswith('/api/index'):
            rest = path_info[len('/api/index'):]
            environ['PATH_INFO'] = rest if rest else '/'
        elif path_info.startswith('/api'):
            rest = path_info[len('/api'):]
            environ['PATH_INFO'] = rest if rest else '/'
            
        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
