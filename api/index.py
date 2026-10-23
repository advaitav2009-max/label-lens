import sys
import os
from urllib.parse import parse_qs

# Add project root directory to path so imports work seamlessly on Vercel
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import app

class VercelPathMiddleware:
    """
    Normalizes PATH_INFO and SCRIPT_NAME when Vercel routes traffic through /api/index
    so Flask correctly matches all declared routes (/login, /scan, /compare, etc.)
    and url_for() generates proper absolute URLs.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        query_string = environ.get('QUERY_STRING', '')
        params = parse_qs(query_string)

        # 1. Primary path resolver: explicit parameter passed by vercel.json rewrite
        if '__vercel_route__' in params:
            raw_route = params['__vercel_route__'][0]
            clean_route = raw_route if raw_route.startswith('/') else f'/{raw_route}'
            environ['PATH_INFO'] = clean_route

            # Filter out __vercel_route__ parameter so Flask view args stay pristine
            qs_parts = [p for p in query_string.split('&') if not p.startswith('__vercel_route__=')]
            environ['QUERY_STRING'] = '&'.join(qs_parts)

        # 2. Secondary fallback: check Vercel edge proxy headers
        else:
            forwarded = (
                environ.get('HTTP_X_FORWARDED_URI')
                or environ.get('HTTP_X_NOW_ROUTE_MATCHES')
                or environ.get('HTTP_X_VERCEL_PATH')
            )
            if forwarded:
                environ['PATH_INFO'] = forwarded.split('?')[0]
            else:
                path_info = environ.get('PATH_INFO', '')
                if path_info.startswith('/api/index'):
                    rest = path_info[len('/api/index'):]
                    environ['PATH_INFO'] = rest if rest else '/'
                elif path_info.startswith('/api'):
                    rest = path_info[len('/api'):]
                    environ['PATH_INFO'] = rest if rest else '/'

        # Ensure SCRIPT_NAME is clean so url_for() always outputs clean /login, /scan paths
        environ['SCRIPT_NAME'] = ''

        return self.wsgi_app(environ, start_response)

app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
