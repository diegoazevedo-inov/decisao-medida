#!/usr/bin/env python3
"""Condutor de fila: JSON por linha na entrada e na saída, estado durável e agente sob demanda."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any

from fila import Fila, Passo, aplicar
from persistencia import gravar_atomico

TEMPO_VISOR = 5
TEMPO_COMANDO = 80
OPERACOES_VEDADAS_AO_AGENTE = ("confirmar", "comando")


class Condutor:
    def __init__(self, pasta: Path, porta_visor: int):
        self.pasta, self.porta_visor = pasta, porta_visor
        self.arquivo = pasta / "fila.json"
        self.fila = Fila.model_validate_json(self.arquivo.read_bytes()) if self.arquivo.exists() else None
        self.trava = asyncio.Lock()
        self.porta_operacoes = 0
        self.pilha = AsyncExitStack()
        self.agente: Any = None

    def _rastrear(self, entrada: Any, decisao: str, ferramenta: Any, resultado: Any) -> None:
        linha = {"entrada": entrada, "decisao": decisao, "ferramenta": ferramenta, "resultado": resultado}
        with open(self.pasta / "rastro.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    async def _visor(self, mensagem: str) -> None:
        leitor, escritor = await asyncio.wait_for(asyncio.open_connection("127.0.0.1", self.porta_visor), TEMPO_VISOR)
        try:
            escritor.write(f"{mensagem}\n".encode())
            await escritor.drain()
            linha = await asyncio.wait_for(leitor.readline(), TEMPO_VISOR)
            if linha.strip() != b"ok":
                raise ConnectionError(f"visualizador respondeu {linha!r}")
        finally:
            escritor.close()

    def _gravar(self, fila: Fila) -> None:
        gravar_atomico(self.arquivo, fila.model_dump_json().encode())
        self.fila = fila

    async def _executar(self, efeitos: list[str], entrada: Any, ferramenta: Any) -> str | None:
        """Aplica os efeitos no visualizador. Se ele falhar, a fila para, como numa falha de carga."""
        try:
            for efeito in efeitos:
                await self._visor(efeito)
        except (OSError, TimeoutError) as e:
            erro = f"visualizador indisponível: {e}"
            if self.fila is not None and self.fila.situacao != "encerrada":
                self._gravar(self.fila.model_copy(update={"situacao": "parada"}))
            self._rastrear(entrada, f"fila parada: {erro}", ferramenta, {"ok": False, "erro": erro})
            return erro
        return None

    async def operar(self, msg: dict[str, Any], ferramenta: str | None = None) -> dict[str, Any]:
        """Regras 4 e 12: grava o estado, registra o rastro e só então toca o visualizador."""
        async with self.trava:
            passo: Passo = aplicar(self.fila, msg)
            if passo.fila is not None and passo.fila != self.fila:
                self._gravar(passo.fila)
            self._rastrear(msg, passo.decisao, ferramenta, passo.resposta)
            erro = await self._executar(passo.efeitos, msg, ferramenta)
            return {"ok": False} if erro else passo.resposta

    async def retomar_depois_de_queda(self) -> None:
        """Regra 4: reabre o item atual. Fila encerrada repete `fechar`, que pode ter se perdido na queda."""
        if self.fila is None:
            return
        efeito = f"abrir {self.fila.atual}" if self.fila.atual is not None else "fechar"
        entrada = {"op": "retomada"}
        self._rastrear(entrada, f"reinício: {efeito}", None, {"ok": True})
        await self._executar([efeito], entrada, None)

    async def atender_agente(self, leitor: asyncio.StreamReader, escritor: asyncio.StreamWriter) -> None:
        """Porta das ferramentas MCP. `confirmar` e `comando` não existem deste lado."""
        try:
            while linha := await leitor.readline():
                msg = self._ler(linha)
                if msg is None or msg.get("op") in OPERACOES_VEDADAS_AO_AGENTE:
                    resposta = {"ok": False}
                    self._rastrear(linha.decode(errors="replace").strip(), "recusado na porta do agente", None, resposta)
                else:
                    resposta = await self.operar(msg, ferramenta=msg.get("op"))
                escritor.write((json.dumps(resposta, ensure_ascii=False) + "\n").encode())
                await escritor.drain()
        finally:
            escritor.close()

    @staticmethod
    def _ler(linha: bytes | str) -> dict[str, Any] | None:
        try:
            msg = json.loads(linha)
        except ValueError:
            return None
        return msg if isinstance(msg, dict) else None

    async def _garantir_agente(self) -> Any:
        if self.agente is None:
            from agente import AgenteFila
            self.agente = await self.pilha.enter_async_context(AgenteFila(self.pasta, self.porta_operacoes))
        return self.agente

    async def comando(self, msg: dict[str, Any]) -> dict[str, Any]:
        texto, antes = msg.get("texto"), self.fila
        try:
            if not isinstance(texto, str) or not texto.strip():
                raise ValueError("comando sem texto")
            async with asyncio.timeout(TEMPO_COMANDO):
                agente = await self._garantir_agente()
                ferramentas, resposta = await agente.atender(texto, self.fila)
            saida = {"ok": True, "ferramentas": ferramentas, "resposta": resposta}
            decisao = f"agente usou {ferramentas}" if ferramentas else "agente respondeu sem ferramenta"
        except Exception as e:  # o processo segue atendendo as operações diretas
            ferramentas, saida, decisao = [], {"ok": False}, f"falha no agente: {type(e).__name__}: {e}"
            await self._descartar_agente()
            await self._desfazer(antes, msg)
        self._rastrear(msg, decisao, ferramentas, saida)
        return saida

    async def _desfazer(self, antes: Fila | None, entrada: Any) -> None:
        """Regra 11: se o agente falhou depois de usar uma ferramenta, a fila volta a como estava."""
        async with self.trava:
            if antes is None or self.fila == antes:
                return
            reabrir = self.fila.atual != antes.atual
            self._gravar(antes)
            self._rastrear(entrada, "estado anterior ao comando restaurado", None, {"ok": False})
            if reabrir:
                await self._executar([f"abrir {antes.atual}"], entrada, None)

    async def _descartar_agente(self) -> None:
        """Reconecta no próximo comando, caso o servidor MCP tenha caído."""
        self.agente = None
        try:
            await self.pilha.aclose()
        except Exception as e:
            print(f"ao fechar o agente: {e}", file=sys.stderr)

    async def receber(self, linha: str) -> dict[str, Any]:
        msg = self._ler(linha)
        if msg is None:
            resposta = {"ok": False}
            self._rastrear(linha.strip(), "recusado: mensagem inválida", None, resposta)
            return resposta
        return await (self.comando(msg) if msg.get("op") == "comando" else self.operar(msg))


async def principal(pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    condutor = Condutor(pasta, int(os.environ["VISOR_PORTA"]))
    servidor = await asyncio.start_server(condutor.atender_agente, "127.0.0.1", 0)
    condutor.porta_operacoes = servidor.sockets[0].getsockname()[1]
    await condutor.retomar_depois_de_queda()
    sys.stdin.reconfigure(errors="replace")  # byte inválido vira mensagem inválida, não queda
    try:
        while linha := await asyncio.to_thread(sys.stdin.readline):
            if linha.strip():
                print(json.dumps(await condutor.receber(linha)), flush=True)
    finally:
        await condutor.pilha.aclose()
        servidor.close()


if __name__ == "__main__":
    argumentos = argparse.ArgumentParser()
    argumentos.add_argument("--estado", required=True, type=Path)
    asyncio.run(principal(argumentos.parse_args().estado))
