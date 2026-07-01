import os
import time
import threading
import http.server
import socketserver

PORT = int(os.environ.get("PORT", 8080))

print("=" * 60)
print("[DIAGNOSTICO] Iniciando...")
print(f"[DIAGNOSTICO] PORT={PORT}")
print("=" * 60)

# Servidor HTTP simple
class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def servidor():
    print(f"[DIAGNOSTICO] Servidor en puerto {PORT}")
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()

# Bucle de prueba
def bucle():
    print("[DIAGNOSTICO] Bucle iniciando...")
    for i in range(100):
        print(f"[DIAGNOSTICO] Tick {i}")
        time.sleep(5)

if __name__ == "__main__":
    t = threading.Thread(target=servidor, name="HTTP")
    t.daemon = False
    t.start()
    
    print("[DIAGNOSTICO] Thread servidor iniciado, entrando a bucle...")
    bucle()
