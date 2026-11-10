"""Camada do agente em Pydantic AI. Só é importada no primeiro `comando`."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastmcp.client.transports import StdioTransport
from pydantic_ai import (Agent, ApprovalRequired, Conversation, ConversationTypeAdapter, DeferredToolRequests,
                         ToolDenied, UsageLimits)
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import ModelRequest, ToolCallPart, UserPromptPart

from fila import Fila
from persistencia import gravar_atomico

INSTRUCAO = ("Você opera uma fila de trabalho. Use as ferramentas para atender ao pedido. "
             "Se o pedido não for sobre a fila, responda sem usar ferramenta.")
SERVIDOR_MCP = Path(__file__).resolve().parents[2] / "bancada" / "mcp_operacoes.py"
TURNOS_GUARDADOS = 10
PEDIDOS_POR_COMANDO = 8
TEMPO_MODELO = 60


def criar_modelo() -> Any:
    """Monta o modelo a partir das variáveis MODELO_*. Trocar de provedor é trocar as variáveis."""
    api, url, nome, chave = (os.environ[f"MODELO_{v}"] for v in ("API", "URL", "NOME", "CHAVE"))
    if api == "openai":
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider
        return OpenAIChatModel(nome, provider=OpenAIProvider(base_url=url, api_key=chave))
    if api == "anthropic":
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider
        return AnthropicModel(nome, provider=AnthropicProvider(base_url=url, api_key=chave))
    raise ValueError(f"MODELO_API inválido: {api!r}")


def _precisa_confirmacao(retorno: Any) -> bool:
    if isinstance(retorno, str):
        try:
            retorno = json.loads(retorno)
        except ValueError:
            return False
    return isinstance(retorno, dict) and retorno.get("precisa_confirmacao") is True


async def _exigir_confirmacao(ctx: Any, chamar: Any, nome: str, argumentos: dict[str, Any]) -> Any:
    """Suspende a execução do agente quando o condutor registra um pedido que depende do humano.

    A ferramenta MCP roda primeiro, porque é ela que registra o pedido. Na retomada aprovada, o
    condutor já executou o pedido, então a ferramenta não é chamada de novo.
    """
    if ctx.tool_call_approved:
        return "Confirmado pelo humano e executado."
    retorno = await chamar(nome, argumentos)
    if _precisa_confirmacao(retorno):
        raise ApprovalRequired(metadata={"pedido": nome})
    return retorno


def _respostas(pedidos: DeferredToolRequests, fila: Fila | None) -> Any:
    """Traduz a decisão gravada na fila para a retomada da conversa suspensa."""
    respostas: dict[str, bool | ToolDenied] = {}
    for chamada in pedidos.approvals:
        decisao = fila.ultima_decisao if fila else None
        if fila is not None and fila.pendente is not None:
            respostas[chamada.tool_call_id] = ToolDenied("Ainda sem decisão humana. O pedido continua pendente.")
        elif decisao is not None and decisao.pedido == chamada.tool_name and decisao.aceito:
            respostas[chamada.tool_call_id] = True
        else:
            respostas[chamada.tool_call_id] = ToolDenied("O humano não confirmou o pedido.")
    return pedidos.build_results(approvals=respostas)


def _aparar(mensagens: list[Any]) -> list[Any]:
    """Guarda só os últimos turnos, cortando sempre no início de um pedido do usuário."""
    inicios = [i for i, m in enumerate(mensagens)
               if isinstance(m, ModelRequest) and any(isinstance(p, UserPromptPart) for p in m.parts)]
    return mensagens[inicios[-TURNOS_GUARDADOS]:] if len(inicios) > TURNOS_GUARDADOS else mensagens


class AgenteFila:
    """Agente com ferramentas do servidor MCP e conversa guardada em `<pasta>/conversa.json`."""

    def __init__(self, pasta: Path, porta: int):
        transporte = StdioTransport(command=os.environ["MCP_PYTHON"], args=[str(SERVIDOR_MCP)],
                                    env={"CONDUTOR_PORTA": str(porta)})
        self.arquivo = pasta / "conversa.json"
        self.agente = Agent(criar_modelo(), instructions=INSTRUCAO, output_type=[str, DeferredToolRequests],
                            # Erro do servidor MCP é falha do comando (regra 11), não assunto para o modelo tentar de novo.
                            toolsets=[MCPToolset(transporte, process_tool_call=_exigir_confirmacao,
                                                 tool_error_behavior="error")],
                            model_settings={"timeout": TEMPO_MODELO})

    async def __aenter__(self) -> AgenteFila:
        await self.agente.__aenter__()
        return self

    async def __aexit__(self, *erro: Any) -> None:
        await self.agente.__aexit__(*erro)

    def _carregar(self) -> Conversation:
        return ConversationTypeAdapter.validate_json(self.arquivo.read_bytes()) if self.arquivo.exists() else Conversation()

    def _guardar(self, conversa: Conversation) -> None:
        conversa.messages = _aparar(conversa.messages)
        gravar_atomico(self.arquivo, ConversationTypeAdapter.dump_json(conversa))

    async def atender(self, texto: str, fila: Fila | None) -> tuple[list[str], str]:
        """Devolve as ferramentas usadas e a resposta. Conversa suspensa é retomada com a decisão humana."""
        conversa = self._carregar()
        pedidos = conversa.deferred_tool_requests
        with Agent.parallel_tool_call_execution_mode("sequential"):  # a ordem das ferramentas muda a fila
            resultado = await self.agente.run(
                texto, conversation=conversa, deferred_tool_results=_respostas(pedidos, fila) if pedidos else None,
                # O uso acumula na conversa; o limite vale para este comando.
                usage_limits=UsageLimits(request_limit=conversa.usage.requests + PEDIDOS_POR_COMANDO))
        self._guardar(resultado.conversation)
        ferramentas = [p.tool_name for m in resultado.new_messages() for p in m.parts if isinstance(p, ToolCallPart)]
        if isinstance(resultado.output, DeferredToolRequests):
            nomes = ", ".join(c.tool_name for c in resultado.output.approvals)
            return ferramentas, f"Pedido registrado, aguarda confirmação humana: {nomes}."
        return ferramentas, resultado.output
