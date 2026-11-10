#!/usr/bin/env python3
"""Implementação de referência do condutor, usada só para provar a régua.

CONTROLE seleciona o defeito plantado: ok, memoria, efeito_antes, sem_confirmacao, pendente_memoria,
ignora_id, sem_limites, priorizar_memoria, nada, agente_confirma, agente_cego, agente_quebrado,
pausa_ignorada, pular_descarta, parada_navega, ignora_falha, encerrar_apaga, nao_reabre, rastro_vazio,
confirmar_exposto, agente_extra.
"""
import argparse, json, os, socket, sys, urllib.request

CONTROLE = os.environ.get("CONTROLE", "ok")
ap = argparse.ArgumentParser()
ap.add_argument("--estado", required=True)
pasta = ap.parse_args().estado
ARQ, RASTRO = os.path.join(pasta, "estado.json"), os.path.join(pasta, "rastro.jsonl")
s = {"fila": [], "pos": 0, "situacao": "nova", "concluidos": [], "pendente": None}


def gravar():
    if CONTROLE == "memoria":
        return
    with open(ARQ + ".tmp", "w") as f:
        json.dump(s, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(ARQ + ".tmp", ARQ)


def visor(*linhas):
    c = socket.create_connection(("127.0.0.1", int(os.environ["VISOR_PORTA"])))
    f = c.makefile("rw")
    for l in linhas:
        f.write(l + "\n")
        f.flush()
        f.readline()
    c.close()


def atual():
    return s["fila"][s["pos"]] if s["pos"] < len(s["fila"]) else None


def abrir():
    if atual() is None:
        visor("fechar")
    else:
        visor("abrir " + atual())


def mudar(fn):
    """Grava antes do efeito. O defeito efeito_antes inverte essa ordem, um erro comum."""
    if CONTROLE == "efeito_antes":
        fn()
        novo = json.dumps(s)
        abrir()
        s.update(json.loads(novo))
        gravar()
    else:
        fn()
        gravar()
        abrir()


def executar(op):
    def f():
        if op == "pular":
            item = s["fila"].pop(s["pos"])
            if CONTROLE != "pular_descarta":
                s["fila"].append(item)
        else:
            s.update(situacao="encerrada", pos=len(s["fila"]))
            if CONTROLE == "encerrar_apaga":
                s["concluidos"] = []
    mudar(f)
    return {"ok": True}


FERRAMENTAS = ["proximo", "anterior", "pausar", "retomar", "pular", "encerrar", "estado", "priorizar"]
if CONTROLE == "confirmar_exposto":
    FERRAMENTAS.append("confirmar")


def agente(texto):
    """Agente mínimo, só para provar a régua. A implementação real usa o servidor MCP."""
    if CONTROLE == "agente_cego":
        return {"ok": True, "ferramentas": [], "resposta": ""}
    if CONTROLE == "agente_quebrado":
        return {"ok": False, "erro": "modelo indisponível"}
    corpo = {"model": os.environ.get("MODELO_NOME", "simulado"), "messages": [{"role": "user", "content": texto}],
             "tools": [{"type": "function", "function": {"name": n, "parameters": {"type": "object", "properties": {}}}} for n in FERRAMENTAS]}
    r = urllib.request.Request(os.environ["MODELO_URL"].rstrip("/") + "/chat/completions", json.dumps(corpo).encode(),
                               {"Content-Type": "application/json"})
    try:
        msg = json.load(urllib.request.urlopen(r, timeout=30))["choices"][0]["message"]
    except OSError:
        return {"ok": False}
    usadas = []
    for c in msg.get("tool_calls") or []:
        nome = c["function"]["name"]
        usadas.append(nome)
        tratar({"op": nome, **json.loads(c["function"].get("arguments") or "{}")})
        if CONTROLE == "agente_confirma" and nome in ("pular", "encerrar"):
            tratar({"op": "confirmar", "aceito": True})
    if CONTROLE == "agente_extra" and usadas:
        tratar({"op": "estado"})
        usadas.append("estado")
    return {"ok": True, "ferramentas": usadas, "resposta": msg.get("content") or ""}


def tratar(m):
    op = m.get("op")
    if op == "iniciar":
        def f():
            s.update(fila=list(m["itens"]), pos=0, situacao="ativa", concluidos=[])
        mudar(f)
        return {"ok": True}
    if op == "estado":
        return {"ok": True, "atual": atual(), "posicao": s["pos"], "total": len(s["fila"]),
                "situacao": s["situacao"], "concluidos": s["concluidos"], "pendente": s["pendente"]}
    if op in ("pular", "encerrar"):
        if CONTROLE == "sem_confirmacao":
            return executar(op)
        s["pendente"] = op
        if CONTROLE != "pendente_memoria":
            gravar()
        return {"ok": False, "precisa_confirmacao": True}
    if op == "confirmar":
        pedido, s["pendente"] = s["pendente"], None
        gravar()
        if pedido is None:
            return {"ok": False}
        return executar(pedido) if m.get("aceito") else {"ok": True}
    if op == "comando":
        return agente(m["texto"])
    if s["situacao"] == "parada" and op not in ("evento",) and not (CONTROLE == "parada_navega" and op == "proximo"):
        return {"ok": False}
    if op == "proximo" or op == "anterior":
        novo = s["pos"] + (1 if op == "proximo" else -1)
        if not 0 <= novo < len(s["fila"]) and CONTROLE != "sem_limites":
            return {"ok": False}

        def f():
            s["pos"] = novo
        mudar(f)
        return {"ok": True}
    if op == "priorizar":
        i = m.get("id")
        if i not in s["fila"][s["pos"] + 1:]:
            return {"ok": False}
        s["fila"].remove(i)
        s["fila"].insert(s["pos"] + 1, i)
        if CONTROLE != "priorizar_memoria":
            gravar()
        return {"ok": True}
    if op in ("pausar", "retomar"):
        s["situacao"] = "pausada" if op == "pausar" else "ativa"
        gravar()
        return {"ok": True}
    if op == "evento" and m.get("tipo") == "falha_de_carga":
        if CONTROLE != "ignora_falha":
            s["situacao"] = "parada"
            gravar()
        return {"ok": True}
    if op == "evento" and m.get("tipo") == "item_finalizado":
        if m.get("id") != atual() and CONTROLE != "ignora_id":
            s["situacao"] = "parada"
            gravar()
            return {"ok": False, "divergencia": True}
        if s["situacao"] != "ativa" and not (CONTROLE == "pausa_ignorada" and s["situacao"] == "pausada"):
            return {"ok": False}

        def f():
            s["concluidos"].append(atual())
            s["pos"] += 1
            if atual() is None:
                s["situacao"] = "encerrada"
        mudar(f)
        return {"ok": True}
    return {"ok": False}


if os.path.exists(ARQ):
    s.update(json.load(open(ARQ)))
    if s["situacao"] == "ativa" and atual() is not None and CONTROLE != "nao_reabre":
        abrir()

for linha in sys.stdin:
    m = json.loads(linha)
    r = {"ok": False} if CONTROLE == "nada" else tratar(m)
    if CONTROLE != "nada":
        if CONTROLE == "rastro_vazio":
            reg = {"entrada": None, "decisao": None, "ferramenta": None, "resultado": None}
        else:
            reg = {"entrada": m, "decisao": m.get("op"), "ferramenta": r.get("ferramentas") or m.get("op"), "resultado": r}
        with open(RASTRO, "a") as f:
            f.write(json.dumps(reg) + "\n")
    print(json.dumps(r), flush=True)
