#!/usr/bin/env python3
"""Confere a operação priorizar, medição C2 da DE-002. Sai com 0 se passar."""
import json, os, sys
import harness as h
import modelo_simulado

CASOS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "roteiro_c2.json"), encoding="utf-8"))


def direto(cmd):
    pasta, visor, p = h.sessao(cmd)
    try:
        p.enviar({"op": "iniciar", "itens": h.ITENS})
        base = len(visor.msgs)
        if not (p.enviar({"op": "priorizar", "id": "D"}) or {}).get("ok") or len(visor.msgs) != base:
            return "priorizar falhou ou mexeu no visualizador"
        for ruim in ("Z", "A"):
            if (p.enviar({"op": "priorizar", "id": ruim}) or {"ok": True}).get("ok") is not False:
                return f"aceitou {ruim}"
        p.fim()
        p = h.Processo(cmd, pasta, visor)
        p.enviar({"op": "estado"})
        p.enviar({"op": "proximo"})
        if (p.enviar({"op": "estado"}) or {}).get("atual") != "D":
            return "ordem perdida depois de queda"
        return None
    finally:
        h.limpar(pasta, visor, p)


def agente(cmd, caso):
    pasta, visor, p = h.sessao(cmd)
    try:
        p.enviar({"op": "iniciar", "itens": h.ITENS})
        r = p.enviar({"op": "comando", "texto": caso["texto"]}, 90) or {}
        if not r.get("ok"):
            return f"comando falhou: {r}"
        p.enviar({"op": "proximo"})
        e = p.enviar({"op": "estado"}) or {}
        return None if e.get("atual") == caso["id"] else f"atual {e.get('atual')}, esperado {caso['id']}"
    finally:
        h.limpar(pasta, visor, p)


def main():
    cmd = sys.argv[2:] if sys.argv[1:2] == ["--"] else sys.argv[1:]
    os.environ.setdefault("MCP_PYTHON", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "python"))
    _, porta = modelo_simulado.iniciar()
    api = os.environ.get("MODELO_API", "openai")
    os.environ.update(MODELO_URL=f"http://127.0.0.1:{porta}" + ("/v1" if api == "openai" else ""), MODELO_API=api, MODELO_NOME="simulado", MODELO_CHAVE="simulado")
    erros = [e for e in [direto(cmd)] + [agente(cmd, c) for c in CASOS] if e]
    print("C2: " + ("passou" if not erros else "REPROVOU " + "; ".join(erros)))
    sys.exit(1 if erros else 0)


if __name__ == "__main__":
    main()
