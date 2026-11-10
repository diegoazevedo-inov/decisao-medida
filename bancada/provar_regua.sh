#!/usr/bin/env bash
# Prova a régua: o caso bom precisa passar, e cada defeito precisa reprovar no requisito esperado.
cd "$(dirname "$0")"
falhou=0
rodar() {
  local nome=$1 esperado=$2 saida
  saida=$(CONTROLE=$nome python3 harness.py --quedas "${QUEDAS:-50}" -- python3 controles/referencia.py 2>&1)
  local reprovados
  reprovados=$(grep REPROVOU <<<"$saida" | cut -d: -f1 | tr '\n' ' ' | sed 's/ $//')
  if [[ "$esperado" == "nenhum" && -z "$reprovados" ]] || [[ "$esperado" != "nenhum" && " $reprovados " == *" $esperado "* ]]; then
    echo "OK    $nome: reprovou [${reprovados:-nenhum}]"
  else
    echo "FALHA $nome: esperava [$esperado], reprovou [${reprovados:-nenhum}]"; echo "$saida"; falhou=1
  fi
}
agente() {
  local nome=$1 esperado=$2 saida rc
  saida=$(CONTROLE=$nome python3 harness_agente.py -- python3 controles/referencia.py 2>&1); rc=$?
  if [[ "$esperado" == "passa" && $rc -eq 0 ]] || [[ "$esperado" == "reprova" && $rc -ne 0 ]]; then
    echo "OK    agente $nome: $(cut -c1-90 <<<"$saida")"
  else
    echo "FALHA agente $nome: esperava $esperado: $saida"; falhou=1
  fi
}
c2() {
  local nome=$1 esperado=$2 saida rc
  saida=$(CONTROLE=$nome python3 harness_c2.py -- python3 controles/referencia.py 2>&1); rc=$?
  if [[ "$esperado" == "passa" && $rc -eq 0 ]] || [[ "$esperado" == "reprova" && $rc -ne 0 ]]; then
    echo "OK    c2 $nome: $(cut -c1-90 <<<"$saida")"
  else
    echo "FALHA c2 $nome: esperava $esperado: $saida"; falhou=1
  fi
}
rodar ok nenhum
rodar memoria E1
rodar efeito_antes E1
rodar sem_confirmacao E2
rodar pendente_memoria E2q
rodar ignora_id E3
rodar sem_limites bordas
rodar nada sanidade
# Defeitos acrescentados depois da auditoria de 10/11/2026: cada um fora dos controles originais.
rodar pausa_ignorada regras
rodar pular_descarta regras
rodar parada_navega regras
rodar ignora_falha regras
rodar encerrar_apaga regras
rodar nao_reabre regras
rodar rastro_vazio E4
agente ok passa
agente agente_confirma reprova
agente agente_cego reprova
agente agente_quebrado reprova
agente confirmar_exposto reprova
agente agente_extra reprova
c2 ok passa
c2 priorizar_memoria reprova
exit $falhou
