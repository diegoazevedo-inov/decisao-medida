#!/usr/bin/env python3
"""Condutor de fila da bancada DE-002, opção O1: LangGraph.

A fila é um grafo com checkpointer SQLite. Cada mensagem percorre:

    decidir -> [visualizador] -> rastrear -> [aguardar_humano -> decidir ...] -> fim

- `decidir` é a transição pura. Com durability="sync", o checkpoint dela é gravado
  antes de `visualizador` começar, o que cumpre a regra de durabilidade.
- Depois de uma queda, o nó interrompido volta a rodar a partir do checkpoint.
- Com pedido pendente, o grafo para em `interrupt()` e fica parado até `confirmar`.
  As demais mensagens entram pelo mesmo ponto, com Command(resume=...).
- `estado` só lê o checkpoint e não percorre o grafo.

O agente é um segundo grafo, sem checkpointer: as ferramentas chegam à fila pela
porta TCP, e é a fila que guarda o estado durável. Retomar um comando pela metade
repetiria uma ferramenta já executada.
"""
import argparse
import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, RetryPolicy, interrupt

INSTRUCAO = ("Você opera uma fila de trabalho. Use as ferramentas para atender ao pedido. "
             "Se o pedido não for sobre a fila, responda sem usar ferramenta.")
SERVIDOR_MCP = Path(__file__).resolve().parents[2] / "bancada" / "mcp_operacoes.py"
FILA = {"configurable": {"thread_id": "fila"}}
OPERACOES = {"iniciar", "estado", "proximo", "anterior", "pausar", "retomar", "pular", "encerrar",
             "confirmar", "comando", "evento", "priorizar"}
SO_DO_HUMANO = {"confirmar", "comando"}
CAMPOS_DA_FILA = ("itens", "posicao", "concluidos", "situacao", "pendente", "pendente_item")
ESPERA_VISOR = 5
ESPERA_MODELO = 30
ESPERA_COMANDO = 80


class Fila(TypedDict, total=False):
    itens: list[str]
    posicao: int
    concluidos: list[str]
    situacao: str | None
    pendente: str | None
    pendente_item: str | None
    entrada: dict[str, Any]
    ferramenta: str | None
    efeito: str | None
    decisao: str
    resposta: dict[str, Any]


def atual(s: Fila) -> str | None:
    itens, posicao = s.get("itens") or [], s.get("posicao", 0)
    return itens[posicao] if s.get("situacao") != "encerrada" and posicao < len(itens) else None


def fotografia(s: Fila) -> dict[str, Any]:
    return {"ok": True, "atual": atual(s), "posicao": s.get("posicao", 0), "total": len(s.get("itens") or []),
            "situacao": s.get("situacao") or "encerrada", "concluidos": s.get("concluidos") or [],
            "pendente": s.get("pendente")}


def passo(decisao: str, resposta: dict[str, Any], efeito: str | None = None, **mudancas: Any) -> Fila:
    return {"decisao": decisao, "resposta": resposta, "efeito": efeito, **mudancas}


def recusa(motivo: str) -> Fila:
    """A resposta do contrato é só {"ok":false}: o motivo fica no rastro."""
    return passo(f"recusar: {motivo}", {"ok": False})


def abrir(item: str) -> str:
    return f"abrir {item}"


def fim_da_fila(decisao: str, **mudancas: Any) -> Fila:
    return passo(decisao, {"ok": True}, "fechar", situacao="encerrada", pendente=None, pendente_item=None, **mudancas)


def ids_validos(itens: Any) -> bool:
    """O id vai numa linha do protocolo do visualizador: espaço ou quebra de linha o corromperia."""
    return (isinstance(itens, list) and len(set(map(str, itens))) == len(itens)
            and all(isinstance(i, str) and i and not any(c.isspace() for c in i) for i in itens))


def transicao(s: Fila, m: dict[str, Any]) -> Fila:
    """Regras da fila, sem efeito externo."""
    op, situacao, item = m.get("op"), s.get("situacao"), atual(s)
    ok = {"ok": True}

    if op == "reabrir":
        return passo(f"reabrir {item} depois do reinício", ok, abrir(item) if item else None)

    if op == "restaurar":
        antes = atual(m["foto"])
        return passo(f"desfazer comando que falhou, voltar a {antes}", ok,
                     abrir(antes) if antes and antes != item else None, **m["foto"])

    if op == "iniciar":
        if situacao not in (None, "encerrada"):
            return recusa("fila em andamento")
        itens = m.get("itens")
        if not ids_validos(itens):
            return recusa("itens invalidos")
        novo = {"itens": itens, "posicao": 0, "concluidos": [], "pendente": None, "pendente_item": None}
        if not itens:
            return passo("fila vazia", ok, situacao="encerrada", **novo)
        return passo(f"abrir {itens[0]}", ok, abrir(itens[0]), situacao="ativa", **novo)

    if situacao in (None, "encerrada"):
        return recusa("sem fila ativa")

    itens, posicao = s["itens"], s["posicao"]

    if op in ("proximo", "anterior"):
        if situacao == "parada":
            return recusa("fila parada")
        destino = posicao + (1 if op == "proximo" else -1)
        if not 0 <= destino < len(itens):
            return recusa("sem item nessa direcao")
        return passo(f"abrir {itens[destino]}", ok, abrir(itens[destino]), posicao=destino)

    if op == "pausar":
        return recusa("fila parada") if situacao == "parada" else passo("pausar", ok, situacao="pausada")

    if op == "retomar":
        return recusa("fila parada") if situacao == "parada" else passo("retomar", ok, situacao="ativa")

    if op in ("pular", "encerrar"):
        if op == "pular" and situacao == "parada":
            return recusa("fila parada")
        return passo(f"aguardar confirmacao de {op}", {"ok": False, "precisa_confirmacao": True},
                     pendente=op, pendente_item=item)

    if op == "priorizar":
        alvo = m.get("id")
        if situacao == "parada" or alvo == item or alvo not in itens or alvo in s["concluidos"]:
            return recusa(f"nao priorizar {alvo}")
        resto = [i for i in itens if i != alvo]
        depois = resto.index(item) + 1
        return passo(f"priorizar {alvo}", ok, itens=[*resto[:depois], alvo, *resto[depois:]], posicao=depois - 1)

    if op == "confirmar":
        pedido, aceito = s.get("pendente"), m.get("aceito")
        if not pedido:
            return recusa("sem pedido pendente")
        if not isinstance(aceito, bool):
            return recusa("aceito precisa ser booleano")
        if not aceito:
            return passo(f"cancelar {pedido}", ok, pendente=None, pendente_item=None)
        if pedido == "encerrar":
            return fim_da_fila("encerrar")
        if s.get("pendente_item") != item:  # O humano aprovou pular outro item.
            return {**recusa("pedido expirado"), "pendente": None, "pendente_item": None}
        ordem = itens[:posicao] + itens[posicao + 1:] + [item]
        return passo(f"pular {item}, abrir {ordem[posicao]}", ok, abrir(ordem[posicao]), itens=ordem,
                     pendente=None, pendente_item=None)

    if op == "evento":
        tipo, ident = m.get("tipo"), m.get("id")
        if tipo == "falha_de_carga":
            if situacao == "parada":
                return recusa("fila parada")
            return passo(f"parar por falha de carga em {ident}", ok, situacao="parada")
        if tipo == "item_finalizado":
            if ident != item:  # A identidade vale antes da pausa.
                return passo(f"divergencia: {ident} em vez de {item}", {"ok": False, "divergencia": True},
                             situacao="parada")
            if situacao in ("pausada", "parada"):
                return recusa(f"fila {situacao}")
            concluidos = s["concluidos"] if item in s["concluidos"] else [*s["concluidos"], item]
            destino = posicao + 1
            if destino >= len(itens):
                return fim_da_fila(f"concluir {item}, fim da fila", concluidos=concluidos, posicao=destino)
            return passo(f"concluir {item}, abrir {itens[destino]}", ok, abrir(itens[destino]),
                         concluidos=concluidos, posicao=destino)
        return recusa("evento desconhecido")

    return recusa("operacao desconhecida")


async def falar_com_visor(porta: int, linha: str) -> None:
    async def conversa() -> bytes:
        leitor, escritor = await asyncio.open_connection("127.0.0.1", porta)
        try:
            escritor.write(linha.encode() + b"\n")
            await escritor.drain()
            return await leitor.readline()
        finally:
            escritor.close()

    resposta = await asyncio.wait_for(conversa(), ESPERA_VISOR)
    if resposta.strip() != b"ok":
        raise ConnectionError(f"visualizador respondeu {resposta!r}")


class Rastro:
    def __init__(self, pasta: Path):
        self.arquivo = open(pasta / "rastro.jsonl", "a", encoding="utf-8")

    def registrar(self, entrada: Any, decisao: str, ferramenta: Any, resultado: Any) -> None:
        linha = {"entrada": entrada, "decisao": decisao, "ferramenta": ferramenta, "resultado": resultado}
        self.arquivo.write(json.dumps(linha, ensure_ascii=False) + "\n")
        self.arquivo.flush()


def construir_fila(rastro: Rastro, porta_visor: int, checkpointer: AsyncSqliteSaver):
    async def decidir(s: Fila) -> Fila:
        return transicao(s, s["entrada"])

    async def visualizador(s: Fila) -> Fila:
        await falar_com_visor(porta_visor, s["efeito"])
        return {"efeito": None}

    async def rastrear(s: Fila) -> None:
        rastro.registrar(s["entrada"], s["decisao"], s.get("ferramenta"), s["resposta"])

    async def aguardar_humano(s: Fila) -> Fila:
        return interrupt({"pendente": s["pendente"]})

    g = StateGraph(Fila)
    g.add_node("decidir", decidir)
    g.add_node("visualizador", visualizador,
               retry_policy=RetryPolicy(max_attempts=3, initial_interval=0.2, retry_on=OSError))
    g.add_node("rastrear", rastrear)
    g.add_node("aguardar_humano", aguardar_humano)
    g.add_edge(START, "decidir")
    g.add_conditional_edges("decidir", lambda s: "visualizador" if s.get("efeito") else "rastrear",
                            ["visualizador", "rastrear"])
    g.add_edge("visualizador", "rastrear")
    g.add_conditional_edges("rastrear", lambda s: "aguardar_humano" if s.get("pendente") else END,
                            ["aguardar_humano", END])
    g.add_edge("aguardar_humano", "decidir")
    return g.compile(checkpointer=checkpointer)


def criar_modelo():
    """Único ponto que conhece o provedor. Importado aqui para as operações diretas não dependerem de modelo."""
    api, url = os.environ.get("MODELO_API"), os.environ.get("MODELO_URL", "")
    nome, chave = os.environ.get("MODELO_NOME"), os.environ.get("MODELO_CHAVE")
    if api == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=nome, base_url=url, api_key=chave, timeout=ESPERA_MODELO, max_retries=1)
    if api == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model=nome, base_url=url, api_key=chave, max_tokens=1024, timeout=ESPERA_MODELO,
                             max_retries=1)
    raise ValueError(f"MODELO_API invalida: {api!r}")


def construir_agente(modelo, ferramentas):
    from langchain_core.messages import SystemMessage
    from langgraph.graph import MessagesState
    from langgraph.prebuilt import ToolNode, tools_condition

    com_ferramentas = modelo.bind_tools(ferramentas)

    async def pensar(s: MessagesState) -> dict:
        return {"messages": [await com_ferramentas.ainvoke([SystemMessage(INSTRUCAO), *s["messages"]])]}

    g = StateGraph(MessagesState)
    g.add_node("pensar", pensar)
    g.add_node("tools", ToolNode(ferramentas))
    g.add_edge(START, "pensar")
    g.add_conditional_edges("pensar", tools_condition, ["tools", END])
    g.add_edge("tools", "pensar")
    return g.compile()


class Condutor:
    def __init__(self, grafo, rastro: Rastro):
        self.grafo, self.rastro = grafo, rastro
        self.trava = asyncio.Lock()
        self.incompleto = True  # Pode haver mensagem pela metade: sempre verdadeiro ao reiniciar.
        self.porta = 0
        self.agente = None
        self.pilha_mcp: AsyncExitStack | None = None

    async def concluir_interrompida(self) -> bool:
        """Termina a mensagem que ficou no meio do grafo. Devolve True se o visualizador foi reaberto por ela."""
        foto = await self.grafo.aget_state(FILA)
        reaberto = "visualizador" in foto.next
        if foto.next and not foto.interrupts:
            await self.grafo.ainvoke(None, FILA, durability="sync")
        self.incompleto = False
        return reaberto

    async def executar(self, m: dict[str, Any], ferramenta: str | None) -> dict[str, Any]:
        foto = await self.grafo.aget_state(FILA)
        entrada = {"entrada": m, "ferramenta": ferramenta}
        saida = await self.grafo.ainvoke(Command(resume=entrada) if foto.interrupts else entrada, FILA,
                                         durability="sync")
        return saida["resposta"]

    async def retomar(self) -> None:
        async with self.trava:
            try:
                if (await self.grafo.aget_state(FILA)).values and not await self.concluir_interrompida():
                    await self.executar({"op": "reabrir"}, None)
                self.incompleto = False
            except OSError as e:
                self.incompleto = True
                print(f"visualizador indisponivel ao retomar: {e}", file=sys.stderr)

    async def operar(self, m: dict[str, Any], ferramenta: str | None) -> dict[str, Any]:
        async with self.trava:
            if m["op"] == "estado":
                resposta = fotografia((await self.grafo.aget_state(FILA)).values)
                self.rastro.registrar(m, "consultar", ferramenta, resposta)
                return resposta
            try:
                if self.incompleto:
                    await self.concluir_interrompida()
                return await self.executar(m, ferramenta)
            except OSError as e:
                # O estado já avançou; o efeito é refeito antes da próxima mensagem.
                self.incompleto = True
                resposta = {"ok": False, "erro": "visualizador indisponivel"}
                self.rastro.registrar(m, f"falha no visualizador: {e}", ferramenta, resposta)
                return resposta

    async def preparar_agente(self):
        if self.agente:
            return self.agente
        from langchain_mcp_adapters.client import MultiServerMCPClient
        from langchain_mcp_adapters.tools import load_mcp_tools

        cliente = MultiServerMCPClient({"fila": {
            "transport": "stdio", "command": os.environ["MCP_PYTHON"], "args": [str(SERVIDOR_MCP)],
            "env": {**os.environ, "CONDUTOR_PORTA": str(self.porta)}}})
        modelo = criar_modelo()
        self.pilha_mcp = AsyncExitStack()
        sessao = await self.pilha_mcp.enter_async_context(cliente.session("fila"))
        self.agente = construir_agente(modelo, await load_mcp_tools(sessao))
        return self.agente

    async def soltar_agente(self) -> None:
        pilha, self.pilha_mcp, self.agente = self.pilha_mcp, None, None
        if pilha:
            try:
                await pilha.aclose()
            except Exception as e:  # O servidor pode já ter morrido, e a resposta ao humano não depende dele.
                print(f"sessao MCP: {e}", file=sys.stderr)

    async def foto_da_fila(self) -> dict[str, Any]:
        async with self.trava:
            valores = (await self.grafo.aget_state(FILA)).values
        return {k: valores[k] for k in CAMPOS_DA_FILA if k in valores}

    async def comando(self, m: dict[str, Any]) -> dict[str, Any]:
        """Sem a trava: as ferramentas voltam pela porta TCP e tomam a trava a cada operação."""
        from langchain_core.messages import AIMessage, HumanMessage
        antes = await self.foto_da_fila()
        try:
            async with asyncio.timeout(ESPERA_COMANDO):
                agente = await self.preparar_agente()
                saida = await agente.ainvoke({"messages": [HumanMessage(str(m.get("texto", "")))]},
                                             {"recursion_limit": 16})
        except Exception as e:
            await self.soltar_agente()
            # O modelo pode falhar depois de uma ferramenta já executada: a fila volta ao que era.
            if await self.foto_da_fila() != antes:
                await self.operar({"op": "restaurar", "foto": antes}, None)
            resposta = {"ok": False}
            self.rastro.registrar(m, f"falha do agente: {type(e).__name__}: {e}", None, resposta)
            return resposta
        ferramentas = [c["name"] for msg in saida["messages"] if isinstance(msg, AIMessage) for c in msg.tool_calls]
        resposta = {"ok": True, "ferramentas": ferramentas, "resposta": saida["messages"][-1].text}
        self.rastro.registrar(m, "agente: " + (", ".join(ferramentas) or "sem ferramenta"), ferramentas, resposta)
        return resposta

    async def receber(self, linha: str, do_humano: bool) -> dict[str, Any]:
        try:
            m = json.loads(linha)
            op = m["op"]
        except (ValueError, KeyError, TypeError):
            resposta = {"ok": False}
            self.rastro.registrar(linha.strip(), "recusar: mensagem invalida", None, resposta)
            return resposta
        if op not in OPERACOES or (op in SO_DO_HUMANO and not do_humano):
            resposta = {"ok": False}
            self.rastro.registrar(m, "recusar: operacao indisponivel", None if do_humano else op, resposta)
            return resposta
        if op == "comando":
            return await self.comando(m)
        return await self.operar(m, None if do_humano else op)

    async def atender_ferramenta(self, leitor: asyncio.StreamReader, escritor: asyncio.StreamWriter) -> None:
        try:
            while linha := await leitor.readline():
                escritor.write(json.dumps(await self.receber(linha.decode(), False), ensure_ascii=False).encode() + b"\n")
                await escritor.drain()
        finally:
            escritor.close()


async def principal(pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    rastro = Rastro(pasta)
    async with AsyncSqliteSaver.from_conn_string(str(pasta / "fila.sqlite")) as saver:
        condutor = Condutor(construir_fila(rastro, int(os.environ["VISOR_PORTA"]), saver), rastro)
        await condutor.retomar()
        servidor = await asyncio.start_server(condutor.atender_ferramenta, "127.0.0.1", 0)
        condutor.porta = servidor.sockets[0].getsockname()[1]
        try:
            while linha := await asyncio.to_thread(sys.stdin.readline):
                resposta = await condutor.receber(linha, True)
                sys.stdout.write(json.dumps(resposta, ensure_ascii=False) + "\n")
                sys.stdout.flush()
        finally:
            await condutor.soltar_agente()
            servidor.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--estado", required=True, type=Path)
    asyncio.run(principal(ap.parse_args().estado))
