#!/usr/bin/env python3
"""Mede a camada do agente: roteiro de 30 comandos, com efeito conferido na fila.

Uso: harness_agente.py [--repeticoes N] [--real] -- <comando da implementação>
Sem --real, usa o modelo simulado, sem custo. Com --real, usa as variáveis MODELO_* do ambiente.
"""
import argparse, json, os, sys
import harness as h
import modelo_simulado

TEMPO_COMANDO = 90
ROTEIRO = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "roteiro.json"), encoding="utf-8"))


def um_comando(cmd, c, exato=False):
    """Com o modelo simulado (exato=True), as ferramentas usadas precisam ser exatamente a esperada.
    Com modelo real, basta a esperada estar entre as usadas: o modelo pode consultar o estado antes."""
    pasta, visor, p = h.sessao(cmd)
    try:
        p.enviar({"op": "iniciar", "itens": h.ITENS})
        for m in c["preparo"]:
            p.enviar(m)
        r = p.enviar({"op": "comando", "texto": c["texto"]}, TEMPO_COMANDO)
        if r is None:
            return "sem resposta"
        if not r.get("ok"):
            return f"comando falhou: {r}"
        usadas = [n.split("_")[-1] for n in r.get("ferramentas", [])]
        esperadas = [c["ferramenta"]] if c["ferramenta"] else []
        if (exato and usadas != esperadas) or (c["ferramenta"] and c["ferramenta"] not in usadas) or (not c["ferramenta"] and usadas):
            return f"ferramenta {usadas}, esperada {c['ferramenta']}"
        e = p.enviar({"op": "estado"}) or {}
        for k in ("atual", "situacao", "pendente"):
            if e.get(k) != c[k]:
                return f"{k} {e.get(k)}, esperado {c[k]}"
        return None
    finally:
        h.limpar(pasta, visor, p)


def falha_do_modelo(cmd):
    """Regra 11: erro do modelo responde ok false e não muda a fila. Só com o modelo simulado."""
    pasta, visor, p = h.sessao(cmd)
    try:
        p.enviar({"op": "iniciar", "itens": h.ITENS})
        base = len(visor.msgs)
        r = p.enviar({"op": "comando", "texto": modelo_simulado.FALHA}, TEMPO_COMANDO) or {}
        e = p.enviar({"op": "estado"}) or {}
        return r.get("ok") is False and e.get("atual") == h.ITENS[0] and len(visor.msgs) == base
    finally:
        h.limpar(pasta, visor, p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeticoes", type=int, default=1)
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--reduzido", action="store_true", help="um comando por tipo, para modelo local pequeno")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    os.environ.setdefault("MCP_PYTHON", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "python"))
    if not a.real:
        _, porta = modelo_simulado.iniciar()
        api = os.environ.get("MODELO_API", "openai")
        base = f"http://127.0.0.1:{porta}" + ("/v1" if api == "openai" else "")
        os.environ.update(MODELO_URL=base, MODELO_API=api, MODELO_NOME="simulado", MODELO_CHAVE="simulado")
    falhas = []
    roteiro = [ROTEIRO[i] for i in (0, 6, 10, 14, 17, 21, 24, 27)] if a.reduzido else ROTEIRO
    total = len(roteiro) * a.repeticoes
    sem_resposta = 0
    for _ in range(a.repeticoes):
        for c in roteiro:
            erro = um_comando(cmd, c, exato=not a.real)
            if erro:
                falhas.append(f"{c['texto']}: {erro}")
                sem_resposta += erro.startswith(("sem resposta", "comando falhou"))
    acertos = total - len(falhas)
    print(f"Respondidos: {total - sem_resposta}/{total}")
    if a.real:
        for f in falhas:
            print("  " + f[:110])
    print(f"C1: {acertos}/{total} ({100 * acertos / total:.1f}%)" + (f"; ex.: {falhas[0]}" if falhas else ""))
    falha_ok = confirmar_ok = True
    if not a.real:
        falha_ok = falha_do_modelo(cmd)
        print(f"Falha do modelo: {'passou' if falha_ok else 'REPROVOU'}")
        expostas = sorted(n for n in modelo_simulado.OFERECIDAS if n == "confirmar" or n.endswith("_confirmar"))
        confirmar_ok = not expostas
        print(f"Confirmar fora do agente: {'passou' if confirmar_ok else 'REPROVOU ' + ', '.join(expostas)}")
    sys.exit(0 if not falhas and falha_ok and confirmar_ok else 1)


if __name__ == "__main__":
    main()
