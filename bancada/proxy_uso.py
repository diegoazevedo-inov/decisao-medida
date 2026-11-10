#!/usr/bin/env python3
"""Proxy local de uso: encaminha ao provedor, conta tokens e recusa ao atingir o limite de chamadas.

Uso: proxy_uso.py <URL do provedor> <porta> <arquivo de registro> <limite de chamadas>
"""
import json, re, sys, threading, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE, PORTA, ARQ, LIMITE = sys.argv[1].rstrip("/"), int(sys.argv[2]), sys.argv[3], int(sys.argv[4])
trava, chamadas = threading.Lock(), [0]


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        corpo = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        with trava:
            chamadas[0] += 1
            n = chamadas[0]
        if n > LIMITE:
            self.send_error(429, "limite de chamadas da bancada")
            return
        cab = {k: v for k, v in self.headers.items() if k.lower() not in ("host", "content-length", "accept-encoding", "connection")}
        r = urllib.request.Request(BASE + self.path, corpo, cab, method="POST")
        try:
            with urllib.request.urlopen(r, timeout=120) as x:
                dados, status, tipo = x.read(), x.status, x.headers.get("Content-Type", "application/json")
        except urllib.error.HTTPError as e:
            dados, status, tipo = e.read(), e.code, e.headers.get("Content-Type", "application/json")
        texto = dados.decode("utf-8", "replace")
        uso = {k: max([int(v) for v in re.findall(rf'"{k}":\s*(\d+)', texto)] or [0])
               for k in ("input_tokens", "output_tokens", "prompt_tokens", "completion_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")}
        modelo = (json.loads(corpo or b"{}")).get("model")
        with trava, open(ARQ, "a") as f:
            f.write(json.dumps({"status": status, "modelo": modelo, **uso}) + "\n")
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(dados)))
        self.end_headers()
        self.wfile.write(dados)


ThreadingHTTPServer(("127.0.0.1", PORTA), H).serve_forever()
