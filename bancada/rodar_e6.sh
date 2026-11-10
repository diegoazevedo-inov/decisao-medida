#!/usr/bin/env bash
# E6: roda o roteiro reduzido com modelo local e registra toda conexão de rede do processo.
# Sem privilégio para bloquear a rede, a prova é a ausência de conexão fora de 127.0.0.1.
# Uso: rodar_e6.sh <pasta do ollama> <modelo> <python> <condutor>
set -u
D=$1 MODELO=$2 PY=$3 COND=$4
cd "$(dirname "$0")"
OLLAMA_HOST=127.0.0.1:11455 OLLAMA_MODELS=$D/models "$D/bin/ollama" serve >/dev/null 2>&1 &
S=$!
for i in $(seq 1 60); do (exec 3<>/dev/tcp/127.0.0.1/11455) 2>/dev/null && break; python3 -c "import time;time.sleep(.5)"; done
# Carrega o modelo antes de medir, para o tempo de carga não contar como falha da opção.
python3 - "$MODELO" <<'PY'
import json, sys, urllib.request
r = urllib.request.Request("http://127.0.0.1:11455/v1/chat/completions", json.dumps({"model": sys.argv[1], "messages": [{"role": "user", "content": "ok"}], "max_tokens": 1}).encode(), {"Content-Type": "application/json"})
urllib.request.urlopen(r, timeout=180).read()
PY
L=$(mktemp)
MODELO_API=openai MODELO_URL=http://127.0.0.1:11455/v1 MODELO_NOME=$MODELO MODELO_CHAVE=local \
  strace -f -qq -e trace=connect -o "$L" python3 harness_agente.py --real --reduzido --repeticoes "${REPETICOES:-1}" -- "$PY" "$COND"
echo "conexões registradas: $(grep -c 'connect(' "$L"); fora de 127.0.0.1 e ::1: $(grep -E 'AF_INET6?' "$L" | grep -v -E '127\.0\.0\.1|::1' | wc -l)"
grep -E 'AF_INET6?' "$L" | grep -v -E '127\.0\.0\.1|::1' | sed -E 's/^[0-9]+ +//' | cut -c1-110 | sort | uniq -c | head -5
rm -f "$L"; kill $S; wait $S 2>/dev/null
pkill -P $S 2>/dev/null; true
