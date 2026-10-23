"""Loopback-only synthetic hosted fixture for browser checks; never use this proxy for real banks or hosting.

The proxy injects the fixed token like a production proxy. Its HTTP-only test transport strips Secure from the
synthetic session cookie; the actual application always sends Secure. The supplied bank must be a throwaway demo.
"""
import argparse
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/interview-bank/scripts'))
from ibank_core.web import LocalServer, WebApp
from ibank_core.weblogin import make_login


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bank', required=True)
    args = parser.parse_args()
    bank = Path(args.bank).resolve()
    app = WebApp(bank, True, True, True)
    backend = LocalServer(app, public_origins=['https://fixture.example'],
                          login=make_login('demo', 'synthetic browser password'), public_bank=bank)
    thread = threading.Thread(target=backend.serve_forever, daemon=True)
    thread.start()

    class Proxy(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def route(self):
            own = f'http://127.0.0.1:{self.server.server_port}'
            if self.headers.get('Origin') not in (None, own):
                self.send_error(403)
                return
            conn = http.client.HTTPConnection('127.0.0.1', backend.server_port, timeout=20)
            headers = {'X-Interview-Token': backend.token, 'Origin': 'https://fixture.example',
                       'Content-Type': 'application/json'}
            if self.headers.get('Cookie'):
                headers['Cookie'] = self.headers['Cookie']
            size = int(self.headers.get('Content-Length', '0'))
            conn.request(self.command, self.path, self.rfile.read(size) if size else None, headers)
            response = conn.getresponse()
            body = response.read()
            self.send_response(response.status)
            for name, value in response.getheaders():
                if name.lower() in ('server', 'date', 'connection', 'transfer-encoding'):
                    continue
                self.send_header(name, value.replace('; Secure', '') if name.lower() == 'set-cookie' else value)
            self.end_headers()
            self.wfile.write(body)
            conn.close()

        do_GET = route
        do_POST = route

    proxy = ThreadingHTTPServer(('127.0.0.1', 0), Proxy)
    print(json.dumps({'url': f'http://127.0.0.1:{proxy.server_port}/'}), flush=True)
    try:
        proxy.serve_forever(poll_interval=.1)
    except KeyboardInterrupt:
        pass
    finally:
        proxy.server_close()
        backend.shutdown()
        backend.server_close()


if __name__ == '__main__':
    main()
