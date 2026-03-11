import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

trades = []

class TradesHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/trades':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(trades).encode())
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/trades':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                trade = json.loads(post_data)
                # Ensure it has a timestamp if not provided
                if 'timestamp' not in trade:
                    trade['timestamp'] = time.time()
                # Ensure it has value calculated if price and amount are present
                if 'price' in trade and 'amount' in trade and 'value' not in trade:
                    trade['value'] = trade['price'] * trade['amount']

                trades.append(trade)
                self.send_response(201)
                self.end_headers()
                self.wfile.write(b'{"status": "success"}')
            except Exception as e:
                self.send_error(400, str(e))
        else:
            self.send_error(404)

def run(server_class=HTTPServer, handler_class=TradesHandler, port=8080):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting mock trades server on port {port}...')
    httpd.serve_forever()

if __name__ == '__main__':
    run()
