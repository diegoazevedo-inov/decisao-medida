#!/usr/bin/env bash
# Coleta com modelo real por trás do proxy de uso.
# Uso: rodar_real.sh <api> <url do provedor> <arquivo da chave> <modelo> <limite de chamadas> <registro> <python> <condutor> [argumentos do harness]
set -u
API=$1 URL=$2 ARQ=$3 MODELO=$4 LIMITE=$5 REG=$6 PY=$7 COND=$8; shift 8
cd "$(dirname "$0")"
python3 proxy_uso.py "$URL" 18790 "$REG" "$LIMITE" & P=$!
python3 -c "import time;time.sleep(.5)"
BASE=http://127.0.0.1:18790; [ "$API" = openai ] && BASE=$BASE/v1
MODELO_CHAVE=$(cut -d= -f2- "$ARQ") MODELO_API=$API MODELO_URL=$BASE MODELO_NOME=$MODELO python3 harness_agente.py --real "$@" -- "$PY" "$COND"
kill $P
