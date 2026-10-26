"""Local dev server for Kazi-Kasi"""
from wsgiref.simple_server import make_server
from api.index import handler

def application(environ, start_response):
    # Set __path for Vercel compatibility
    path = environ.get('PATH_INFO', '/')
    environ['QUERY_STRING'] = environ.get('QUERY_STRING', '')
    if '__path' not in environ.get('QUERY_STRING', ''):
        if environ['QUERY_STRING']:
            environ['QUERY_STRING'] += f'&__path={path}'
        else:
            environ['QUERY_STRING'] = f'__path={path}'
    return handler(environ, start_response)

if __name__ == '__main__':
    port = 8000
    print(f"🚀 Kazi-Kasi running on http://0.0.0.0:{port}")
    with make_server('0.0.0.0', port, application) as httpd:
        httpd.serve_forever()
