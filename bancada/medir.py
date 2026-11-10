#!/usr/bin/env python3
"""Mede os comparáveis que não dependem de modelo real: C3, C4 e C5, além do tempo de início.

Uso: medir.py <pasta da implementação>
"""
import json, os, statistics as st, subprocess, sys, time
import harness as h
import modelo_simulado

pasta = os.path.abspath(sys.argv[1])
py = os.path.join(pasta, ".venv", "bin", "python")
cmd = [py, os.path.join(pasta, "condutor.py")]


def linhas():
    total = arqs = 0
    for raiz, dirs, fs in os.walk(pasta):
        dirs[:] = [d for d in dirs if d not in (".venv", "__pycache__", "testes", "tests")]
        for f in fs:
            if f.endswith(".py") and not f.startswith("test"):
                arqs += 1
                doc = False
                for l in open(os.path.join(raiz, f), encoding="utf-8"):
                    s = l.strip()
                    if s.count('"""') == 1:
                        doc = not doc
                        continue
                    if s and not s.startswith("#") and not doc and not (s.startswith('"""') and s.endswith('"""')):
                        total += 1
    return total, arqs


def dependencias():
    r = subprocess.run([py, "-m", "pip", "list", "--format=json"], capture_output=True, text=True)
    pacotes = [p for p in json.loads(r.stdout) if p["name"] not in ("pip", "setuptools")]
    diretas = [l for l in open(os.path.join(pasta, "requirements.txt"), encoding="utf-8") if l.strip() and not l.startswith("#")]
    mb = int(subprocess.run(["du", "-sm", os.path.join(pasta, ".venv")], capture_output=True, text=True).stdout.split()[0])
    return len(diretas), len(pacotes), mb


def p95(v):
    return round(sorted(v)[int(len(v) * .95) - 1] * 1000, 2)


def tempos():
    _, porta = modelo_simulado.iniciar()
    os.environ.update(MODELO_URL=f"http://127.0.0.1:{porta}/v1", MODELO_API="openai", MODELO_NOME="simulado", MODELO_CHAVE="simulado")
    os.environ.setdefault("MCP_PYTHON", os.path.join(os.path.dirname(os.path.abspath(__file__)), ".venv", "bin", "python"))
    t0 = time.perf_counter()
    d, visor, p = h.sessao(cmd)
    p.enviar({"op": "iniciar", "itens": h.ITENS})
    inicio = time.perf_counter() - t0
    leitura, troca, comando = [], [], []
    try:
        for _ in range(200):
            a = time.perf_counter(); p.enviar({"op": "estado"}); leitura.append(time.perf_counter() - a)
        for i in range(200):
            a = time.perf_counter(); p.enviar({"op": "proximo" if i % 2 == 0 else "anterior"}); troca.append(time.perf_counter() - a)
        for _ in range(20):
            a = time.perf_counter(); p.enviar({"op": "comando", "texto": "onde estou?"}); comando.append(time.perf_counter() - a)
    finally:
        h.limpar(d, visor, p)
    return round(inicio, 2), p95(leitura), p95(troca), p95(comando)


l, a = linhas()
d, t, mb = dependencias()
i, r, x, c = tempos()
print(json.dumps({"opcao": os.path.basename(pasta), "linhas": l, "arquivos": a, "deps_diretas": d, "deps_total": t, "venv_mb": mb,
                  "inicio_s": i, "estado_p95_ms": r, "troca_p95_ms": x, "comando_p95_ms": c}))
