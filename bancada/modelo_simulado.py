#!/usr/bin/env python3
"""Modelo de linguagem simulado, determinístico e sem custo, nos formatos OpenAI e Anthropic.

Escolhe a ferramenta pelo roteiro. Serve para testar o caminho completo sem gastar modelo real.
Ele sempre acerta, então não mede C1: C1 exige modelo real.
"""
import json, os, sys, threading, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROTEIRO = {c["texto"]: c["ferramenta"] for c in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "roteiro.json"), encoding="utf-8"))}


ARGUMENTOS = {c["texto"]: {"id": c["id"]} for c in json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "roteiro_c2.json"), encoding="utf-8"))}
ROTEIRO.update({t: "priorizar" for t in ARGUMENTOS})


def texto_de(c):
    if isinstance(c, str):
        return c
    return " ".join(b.get("text", "") for b in c or [] if isinstance(b, dict) and b.get("type") in ("text", "input_text"))


FALHA = "__falha_do_modelo__"

# Nomes de ferramenta oferecidos ao modelo em qualquer chamada. O harness confere que `confirmar`
# nunca aparece aqui (regra 1: confirmar não pode ser exposta ao agente).
OFERECIDAS = set()


def ultimo_texto(msgs):
    for m in reversed(msgs):
        if m.get("role") == "user":
            return texto_de(m.get("content")).strip()
    return ""


def decidir(msgs, nomes):
    """Devolve a ferramenta a chamar, ou None se já houve resultado de ferramenta depois do pedido."""
    for m in reversed(msgs):
        c = m.get("content")
        if m.get("role") == "tool":
            return None
        if m.get("role") == "user":
            texto = texto_de(c).strip()
            if isinstance(c, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in c) and not texto:
                return None
            alvo = ROTEIRO.get(texto)
            if alvo is None:
                return None
            return next((n for n in nomes if n == alvo or n.endswith("_" + alvo)), None)
    return None


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def responder(self, obj):
        b = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_POST(self):
        q = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        if ultimo_texto(q.get("messages", [])) == FALHA:
            self.send_error(400, "falha simulada")
            return
        if self.path == "/v1/chat/completions":
            nomes = [t["function"]["name"] for t in q.get("tools", [])]
            OFERECIDAS.update(nomes)
            f = decidir(q.get("messages", []), nomes)
            msg = {"role": "assistant", "content": None if f else "Feito."}
            if f:
                msg["tool_calls"] = [{"id": "call_" + uuid.uuid4().hex[:8], "type": "function", "function": {"name": f, "arguments": json.dumps(ARGUMENTOS.get(ultimo_texto(q.get("messages", [])), {}))}}]
            self.responder({"id": "c" + uuid.uuid4().hex[:8], "object": "chat.completion", "created": 0, "model": q.get("model", "simulado"),
                            "choices": [{"index": 0, "finish_reason": "tool_calls" if f else "stop", "message": msg}],
                            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}})
        elif self.path == "/v1/messages":
            nomes = [t["name"] for t in q.get("tools", [])]
            OFERECIDAS.update(nomes)
            f = decidir(q.get("messages", []), nomes)
            blocos = [{"type": "tool_use", "id": "toolu_" + uuid.uuid4().hex[:8], "name": f, "input": ARGUMENTOS.get(ultimo_texto(q.get("messages", [])), {})}] if f else [{"type": "text", "text": "Feito."}]
            self.responder({"id": "msg_" + uuid.uuid4().hex[:8], "type": "message", "role": "assistant", "model": q.get("model", "simulado"),
                            "content": blocos, "stop_reason": "tool_use" if f else "end_turn", "stop_sequence": None,
                            "usage": {"input_tokens": 10, "output_tokens": 5}})
        else:
            self.send_error(404)


def iniciar(porta=0):
    s = ThreadingHTTPServer(("127.0.0.1", porta), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s, s.server_address[1]


if __name__ == "__main__":
    s, p = iniciar(int(sys.argv[1]) if len(sys.argv) > 1 else 0)
    print(f"http://127.0.0.1:{p}/v1", flush=True)
    threading.Event().wait()
