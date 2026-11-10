#!/usr/bin/env python3
"""Condutor de fila da DE-002, opção O0: SDK do provedor com MCP, sem framework de orquestração.

Três camadas, nesta ordem no arquivo:

1. Núcleo: `decidir(fila, mensagem)`, função pura que devolve resposta, novo estado e efeito.
2. Casca: `Condutor` grava o estado, grava o rastro e só então toca no visualizador.
3. Agente: laço próprio sobre a API do modelo, com as ferramentas vindas do servidor MCP.

Os SDKs e o cliente MCP só são importados no primeiro `comando`: as operações diretas
funcionam sem modelo, sem as variáveis MODELO_* e sem pagar o custo de importação.
"""
import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

SERVIDOR_MCP = Path(__file__).resolve().parents[2] / "bancada" / "mcp_operacoes.py"
INSTRUCAO = ("Você opera uma fila de trabalho. Use as ferramentas para atender ao pedido. "
             "Se o pedido não for sobre a fila, responda sem usar ferramenta.")
SO_DO_HUMANO = ("confirmar", "comando")  # a porta do agente recusa estas operações
MAX_PASSOS = 8          # idas ao modelo por comando
MAX_TOKENS = 1024
TEMPO_VISOR = 5         # segundos, por mensagem ao visualizador
TEMPO_MODELO = 30       # segundos, por chamada ao modelo
TEMPO_FERRAMENTA = 15   # segundos, por chamada de ferramenta
TEMPO_COMANDO = 60      # segundos, para o comando inteiro


# --- Núcleo: regras da fila, sem E/S ---------------------------------------------------------

@dataclass(frozen=True)
class Fila:
    itens: list[str]
    posicao: int = 0
    situacao: str = "ativa"
    concluidos: list[str] = field(default_factory=list)
    pendente: str | None = None
    pendente_item: str | None = None  # item que estava aberto quando o humano viu o pedido

    @property
    def atual(self):
        if self.situacao == "encerrada" or self.posicao >= len(self.itens):
            return None
        return self.itens[self.posicao]

    def publico(self):
        return {"atual": self.atual, "posicao": self.posicao, "total": len(self.itens),
                "situacao": self.situacao, "concluidos": self.concluidos, "pendente": self.pendente}


@dataclass(frozen=True)
class Passo:
    resposta: dict
    decisao: str
    fila: Fila | None = None   # novo estado a gravar; None mantém o atual
    efeito: str | None = None  # linha para o visualizador


def recusa(decisao, **extra):
    return Passo({"ok": False, **extra}, decisao)


def aceite(decisao, fila=None, efeito=None):
    return Passo({"ok": True}, decisao, fila, efeito)


def abrir(fila, decisao):
    return aceite(decisao, fila, f"abrir {fila.atual}")


def sem_pedido(fila):
    return replace(fila, pendente=None, pendente_item=None)


def iniciar(fila, msg):
    itens = msg.get("itens")
    if fila is not None and fila.situacao != "encerrada":
        return recusa("recusa iniciar: já há fila em andamento", erro="já há fila em andamento")
    # O id vai numa linha do protocolo do visualizador: espaço ou quebra de linha o corromperia.
    validos = (isinstance(itens, list) and itens and len(set(map(str, itens))) == len(itens)
               and all(isinstance(i, str) and i and not any(c.isspace() for c in i) for i in itens))
    if not validos:
        return recusa("recusa iniciar: itens inválidos", erro="itens inválidos")
    return abrir(Fila(itens=list(itens)), f"cria a fila e abre {itens[0]}")


def mover(fila, passo):
    if fila.situacao == "parada":
        return recusa("recusa navegar: fila parada")
    destino = fila.posicao + passo
    if not 0 <= destino < len(fila.itens):
        return recusa("recusa navegar: fora da fila")
    nova = replace(fila, posicao=destino)
    return abrir(nova, f"abre {nova.atual}")


def pausar(fila, _msg):
    if fila.situacao == "parada":
        return recusa("recusa pausar: fila parada")
    return aceite("pausa a fila", replace(fila, situacao="pausada"))


def retomar(fila, _msg):
    if fila.situacao == "parada":
        return recusa("recusa retomar: fila parada")
    return aceite("retoma a fila", replace(fila, situacao="ativa"))


def pedir(fila, op):
    if op == "pular" and fila.situacao == "parada":
        return recusa("recusa pular: fila parada")
    nova = replace(fila, pendente=op, pendente_item=fila.atual)
    return Passo({"ok": False, "precisa_confirmacao": True}, f"registra o pedido {op}", nova)


def confirmar(fila, msg):
    aceito = msg.get("aceito")
    if fila.pendente is None:
        return recusa("nada a confirmar")
    if not isinstance(aceito, bool):
        return recusa("confirmação sem aceito booleano", erro="aceito deve ser true ou false")
    if not aceito:
        return aceite(f"cancela o pedido {fila.pendente}", sem_pedido(fila))
    if fila.pendente == "encerrar":
        return aceite("encerra a fila", replace(sem_pedido(fila), situacao="encerrada"), "fechar")
    if fila.atual != fila.pendente_item:
        # O humano confirmou vendo outro item: aplicar agora atingiria o item errado.
        return Passo({"ok": False, "erro": "o item mudou depois do pedido"},
                     f"cancela o pedido pular: o item {fila.pendente_item} não é mais o atual", sem_pedido(fila))
    itens = fila.itens[:fila.posicao] + fila.itens[fila.posicao + 1:] + [fila.atual]
    nova = replace(sem_pedido(fila), itens=itens)
    if nova.atual == fila.atual:
        return aceite(f"{fila.atual} já é o último item", nova)
    return abrir(nova, f"manda {fila.atual} para o fim e abre {nova.atual}")


def priorizar(fila, msg):
    item = msg.get("id")
    if fila.situacao == "parada" or item == fila.atual or item not in fila.itens or item in fila.concluidos:
        return recusa(f"recusa priorizar {item}")
    resto = [i for i in fila.itens if i != item]
    posicao = resto.index(fila.atual)  # o item pode estar antes do atual, depois de um `proximo`
    itens = resto[:posicao + 1] + [item] + resto[posicao + 1:]
    return aceite(f"coloca {item} depois de {fila.atual}", replace(fila, itens=itens, posicao=posicao))


def evento(fila, msg):
    tipo, item = msg.get("tipo"), msg.get("id")
    if tipo == "falha_de_carga":
        return aceite(f"falha de carga em {item}: para a fila", replace(fila, situacao="parada"))
    if tipo != "item_finalizado":
        return recusa("evento desconhecido", erro="evento desconhecido")
    # Regra 8: identidade antes da pausa.
    if item != fila.atual:
        return Passo({"ok": False, "divergencia": True}, f"divergência: chegou {item}, atual {fila.atual}",
                     replace(fila, situacao="parada"))
    if fila.situacao != "ativa":
        return recusa(f"ignora o fim de {item}: fila {fila.situacao}")
    concluidos = fila.concluidos if item in fila.concluidos else [*fila.concluidos, item]
    nova = replace(fila, posicao=fila.posicao + 1, concluidos=concluidos)
    if nova.atual is None:
        return aceite(f"conclui {item} e encerra a fila", replace(sem_pedido(nova), situacao="encerrada"), "fechar")
    return abrir(nova, f"conclui {item} e abre {nova.atual}")


OPERACOES = {
    "proximo": lambda f, _m: mover(f, 1),
    "anterior": lambda f, _m: mover(f, -1),
    "pausar": pausar,
    "retomar": retomar,
    "pular": lambda f, _m: pedir(f, "pular"),
    "encerrar": lambda f, _m: pedir(f, "encerrar"),
    "confirmar": confirmar,
    "priorizar": priorizar,
    "evento": evento,
}


def decidir(fila, msg):
    op = msg.get("op")
    if op == "iniciar":
        return iniciar(fila, msg)
    if fila is None:
        return recusa("sem fila", erro="não há fila iniciada")
    if op == "estado":
        return Passo({"ok": True, **fila.publico()}, "consulta o estado")
    if op not in OPERACOES:
        return recusa("operação desconhecida", erro="operação desconhecida")
    if fila.situacao == "encerrada":
        return recusa("fila encerrada")
    return OPERACOES[op](fila, msg)


# --- Casca: durabilidade, rastro e visualizador ----------------------------------------------

class Armazem:
    """Estado num arquivo trocado de forma atômica; rastro só de acréscimo. Ambos com fsync."""

    def __init__(self, pasta):
        self.pasta = Path(pasta)
        self.pasta.mkdir(parents=True, exist_ok=True)
        self.arquivo = self.pasta / "estado.json"
        self.rastro = os.open(self.pasta / "rastro.jsonl", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)

    def carregar(self):
        # Arquivo ilegível derruba o processo de propósito: recomeçar vazio perderia a fila.
        if not self.arquivo.exists():
            return None
        return Fila(**json.loads(self.arquivo.read_text(encoding="utf-8")))

    def gravar(self, fila):
        temporario = self.arquivo.with_suffix(".tmp")
        with open(temporario, "w", encoding="utf-8") as f:
            json.dump(asdict(fila), f, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporario, self.arquivo)
        pasta = os.open(self.pasta, os.O_RDONLY)
        try:
            os.fsync(pasta)
        finally:
            os.close(pasta)

    def registrar(self, entrada, decisao, ferramenta, resultado, origem):
        linha = {"entrada": entrada, "decisao": decisao, "ferramenta": ferramenta, "resultado": resultado, "origem": origem}
        # Uma única escrita por linha: uma queda não deixa linha pela metade no meio do arquivo.
        os.write(self.rastro, (json.dumps(linha, ensure_ascii=False) + "\n").encode())
        os.fsync(self.rastro)


class Visor:
    """Conexão persistente com o visualizador. `abrir` e `fechar` são idempotentes, então repetir é seguro."""

    def __init__(self, porta):
        self.porta = porta
        self.leitor = self.escritor = None

    def desconectar(self):
        if self.escritor:
            self.escritor.close()
        self.leitor = self.escritor = None

    async def _trocar(self, linha):
        if self.escritor is None:
            self.leitor, self.escritor = await asyncio.open_connection("127.0.0.1", self.porta)
        self.escritor.write(linha.encode() + b"\n")
        await self.escritor.drain()
        if (await self.leitor.readline()).strip() != b"ok":
            raise ConnectionError("o visualizador não respondeu ok")

    async def enviar(self, linha):
        for ultima in (False, True):  # uma nova tentativa cobre conexão velha
            try:
                return await asyncio.wait_for(self._trocar(linha), TEMPO_VISOR)
            except (OSError, TimeoutError):
                self.desconectar()
                if ultima:
                    raise


class Condutor:
    def __init__(self, pasta):
        self.armazem = Armazem(pasta)
        self.fila = self.armazem.carregar()
        self.visor = Visor(int(os.environ["VISOR_PORTA"]))
        self.trava = asyncio.Lock()  # uma transição por vez: humano e agente entram por portas diferentes
        self.agente = Agente(self)

    async def reabrir_apos_queda(self):
        if self.fila is None:
            return
        efeito = f"abrir {self.fila.atual}" if self.fila.atual else "fechar"
        self.armazem.registrar({"op": "reinicio"}, f"retoma a fila: {efeito}", None, {"ok": True}, "processo")
        await self._efeito(efeito, {"op": "reinicio"}, {"ok": True}, "processo")

    async def atender(self, linha, origem):
        try:
            msg = json.loads(linha)
            if not isinstance(msg, dict):
                raise ValueError
        except ValueError:
            resposta = {"ok": False, "erro": "mensagem inválida"}
            self.armazem.registrar(linha.decode(errors="replace").strip(), "mensagem inválida", None, resposta, origem)
            return resposta
        if origem == "agente" and msg.get("op") in SO_DO_HUMANO:
            resposta = {"ok": False, "erro": "operação reservada ao humano"}
            self.armazem.registrar(msg, "recusa: operação reservada ao humano", msg.get("op"), resposta, origem)
            return resposta
        if msg.get("op") == "comando":
            return await self.agente.atender(msg)
        return await self.operar(msg, origem)

    async def operar(self, msg, origem):
        async with self.trava:
            passo = decidir(self.fila, msg)
            if passo.fila is not None:
                self.armazem.gravar(passo.fila)
                self.fila = passo.fila
            ferramenta = msg.get("op") if origem == "agente" else None
            self.armazem.registrar(msg, passo.decisao, ferramenta, passo.resposta, origem)
            return await self._efeito(passo.efeito, msg, passo.resposta, origem) if passo.efeito else passo.resposta

    async def restaurar(self, antes, msg):
        """Regra 11: comando que falhou não deixa a fila mudada, mesmo com ferramentas já executadas."""
        async with self.trava:
            if antes is None or self.fila == antes:
                return
            reabrir = antes.atual != self.fila.atual
            self.armazem.gravar(antes)
            self.fila = antes
            self.armazem.registrar(msg, "desfaz o que o comando mudou na fila", None, {"ok": False}, "processo")
            if reabrir:
                await self._efeito(f"abrir {antes.atual}", msg, {"ok": False}, "processo")

    async def _efeito(self, efeito, msg, resposta, origem):
        """Chamado depois de gravar estado e rastro. Visualizador que não responde equivale a falha de carga."""
        try:
            await self.visor.enviar(efeito)
            return resposta
        except (OSError, TimeoutError) as erro:
            if self.fila.situacao != "encerrada":
                self.fila = replace(self.fila, situacao="parada")
                self.armazem.gravar(self.fila)
            falha = {"ok": False, "erro": "visualizador indisponível"}
            self.armazem.registrar(msg, f"efeito '{efeito}' falhou ({type(erro).__name__}): fila {self.fila.situacao}",
                                   None, falha, origem)
            return falha


# --- Agente: laço próprio, um adaptador por formato de API -----------------------------------

@dataclass(frozen=True)
class Chamada:
    id: str
    nome: str
    argumentos: dict | None  # None: o modelo mandou argumentos que não são JSON


class ApiOpenAI:
    def __init__(self, url, nome, chave, ferramentas):
        from openai import AsyncOpenAI
        self.cliente = AsyncOpenAI(base_url=url, api_key=chave, timeout=TEMPO_MODELO, max_retries=1)
        self.nome = nome
        self.ferramentas = [{"type": "function", "function": {"name": t.name, "description": t.description or "",
                                                              "parameters": t.input_schema}} for t in ferramentas]

    def nova_conversa(self, texto):
        return [{"role": "system", "content": INSTRUCAO}, {"role": "user", "content": texto}]

    async def perguntar(self, conversa):
        r = await self.cliente.chat.completions.create(model=self.nome, messages=conversa, tools=self.ferramentas)
        m = r.choices[0].message
        pedidas = m.tool_calls or []
        turno = {"role": "assistant", "content": m.content}
        if pedidas:
            turno["tool_calls"] = [{"id": c.id, "type": "function", "function": {
                "name": c.function.name, "arguments": c.function.arguments}} for c in pedidas]
        conversa.append(turno)
        return m.content or "", [Chamada(c.id, c.function.name, self._argumentos(c.function.arguments)) for c in pedidas]

    @staticmethod
    def _argumentos(bruto):
        try:
            return json.loads(bruto or "{}")
        except ValueError:
            return None

    def anexar(self, conversa, resultados):
        conversa.extend({"role": "tool", "tool_call_id": c.id, "content": texto} for c, texto, _erro in resultados)


class ApiAnthropic:
    def __init__(self, url, nome, chave, ferramentas):
        from anthropic import AsyncAnthropic
        self.cliente = AsyncAnthropic(base_url=url, api_key=chave, timeout=TEMPO_MODELO, max_retries=1)
        self.nome = nome
        self.ferramentas = [{"name": t.name, "description": t.description or "", "input_schema": t.input_schema}
                            for t in ferramentas]

    def nova_conversa(self, texto):
        return [{"role": "user", "content": texto}]

    async def perguntar(self, conversa):
        r = await self.cliente.messages.create(model=self.nome, max_tokens=MAX_TOKENS, system=INSTRUCAO,
                                               messages=conversa, tools=self.ferramentas)
        conversa.append({"role": "assistant", "content": r.content})
        texto = " ".join(b.text for b in r.content if b.type == "text")
        return texto, [Chamada(b.id, b.name, b.input) for b in r.content if b.type == "tool_use"]

    def anexar(self, conversa, resultados):
        conversa.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": c.id, "content": texto, "is_error": erro}
            for c, texto, erro in resultados]})


APIS = {"openai": ApiOpenAI, "anthropic": ApiAnthropic}


class SessaoMCP:
    """Mantém o servidor MCP vivo entre comandos.

    O cliente usa escopos do anyio, que precisam abrir e fechar na mesma tarefa: por isso uma tarefa
    própria é dona da sessão. Se o servidor cair, o próximo comando percebe e abre outro.
    """

    def __init__(self, porta):
        self.porta = porta
        self.cliente = None
        self.ferramentas = []
        self.fim = asyncio.Event()
        self.tarefa = None

    async def garantir(self):
        from mcp import MCPError
        if self.cliente is not None:
            try:
                await self.cliente.list_tools(cache_mode="refresh")  # o cliente não avisa que o servidor morreu
                return
            except MCPError:
                await self.descartar()
        pronto = asyncio.get_running_loop().create_future()
        self.tarefa = asyncio.create_task(self._manter(pronto))
        try:
            await pronto
        except asyncio.CancelledError:
            self.tarefa.cancel()
            raise

    async def _manter(self, pronto):
        from mcp import Client, StdioServerParameters
        try:
            # O servidor é peça externa à opção: roda no ambiente da bancada, não no venv do condutor.
            # O SDK só herda variáveis seguras do ambiente: MODELO_CHAVE não chega ao servidor.
            parametros = StdioServerParameters(command=os.environ["MCP_PYTHON"], args=[str(SERVIDOR_MCP)],
                                               env={"CONDUTOR_PORTA": str(self.porta)})
            async with Client(parametros, read_timeout_seconds=TEMPO_FERRAMENTA) as cliente:
                self.ferramentas = (await cliente.list_tools()).tools
                self.cliente = cliente
                pronto.set_result(None)
                await self.fim.wait()
        except Exception as erro:
            if not pronto.done():
                pronto.set_exception(erro)
        finally:
            self.cliente = None

    async def chamar(self, chamada):
        """Devolve (texto, erro?). Pedido errado do modelo volta a ele; falha do servidor derruba o comando."""
        from mcp import MCPError
        if chamada.nome not in {t.name for t in self.ferramentas}:
            return f"ferramenta inexistente: {chamada.nome}", True
        if chamada.argumentos is None:
            return "argumentos inválidos: não são JSON", True
        try:
            r = await self.cliente.call_tool(chamada.nome, chamada.argumentos)
        except MCPError:
            await self.descartar()
            raise
        texto = "\n".join(b.text for b in r.content if b.type == "text")
        if r.is_error:
            raise RuntimeError(f"servidor MCP falhou em {chamada.nome}: {texto}")
        return texto, False

    async def descartar(self):
        self.fim.set()
        if self.tarefa:
            await self.tarefa
        self.fim = asyncio.Event()


class Agente:
    def __init__(self, condutor):
        self.condutor = condutor
        self.porta = None
        self.mcp = None
        self.api = None

    async def _atender_ferramenta(self, leitor, escritor):
        try:
            while linha := await leitor.readline():
                resposta = await self.condutor.atender(linha, "agente")
                escritor.write(json.dumps(resposta).encode() + b"\n")
                await escritor.drain()
        finally:
            escritor.close()

    async def _preparar(self):
        if self.porta is None:
            self.porta = await asyncio.start_server(self._atender_ferramenta, "127.0.0.1", 0)
            self.mcp = SessaoMCP(self.porta.sockets[0].getsockname()[1])
        await self.mcp.garantir()
        if self.api is None:
            tipo = os.environ.get("MODELO_API")
            if tipo not in APIS:
                raise ValueError(f"MODELO_API deve ser openai ou anthropic, veio {tipo!r}")
            self.api = APIS[tipo](os.environ["MODELO_URL"], os.environ["MODELO_NOME"], os.environ["MODELO_CHAVE"],
                                  self.mcp.ferramentas)

    async def _conduzir(self, texto, usadas, recusadas):
        await self._preparar()
        conversa = self.api.nova_conversa(texto)
        for _ in range(MAX_PASSOS):
            resposta, chamadas = await self.api.perguntar(conversa)
            if not chamadas:
                return resposta
            resultados = []
            for chamada in chamadas:
                saida, erro = await self.mcp.chamar(chamada)
                (recusadas if erro else usadas).append(chamada.nome)
                resultados.append((chamada, saida, erro))
            self.api.anexar(conversa, resultados)
        raise RuntimeError(f"o agente não terminou em {MAX_PASSOS} passos")

    async def atender(self, msg):
        """Cada comando é uma conversa nova. Depois de uma queda não há conversa a retomar: o que conta está na fila."""
        texto, usadas, recusadas = msg.get("texto"), [], []
        antes = self.condutor.fila
        try:
            if not isinstance(texto, str) or not texto.strip():
                raise ValueError("comando sem texto")
            async with asyncio.timeout(TEMPO_COMANDO):
                resposta = {"ok": True, "ferramentas": usadas, "resposta": await self._conduzir(texto, usadas, recusadas)}
            decisao = "agente respondeu"
        except Exception as erro:
            await self.condutor.restaurar(antes, msg)
            resposta = {"ok": False}
            decisao = f"agente falhou ({type(erro).__name__}: {erro})"
        if recusadas:
            decisao += f"; tentativas recusadas: {', '.join(recusadas)}"
        self.condutor.armazem.registrar(msg, decisao, usadas, resposta, "humano")
        return resposta

    async def fechar(self):
        if self.mcp:
            await self.mcp.descartar()
        if self.porta:
            self.porta.close()


# --- Processo --------------------------------------------------------------------------------

async def principal(pasta):
    condutor = Condutor(pasta)
    await condutor.reabrir_apos_queda()
    while linha := await asyncio.to_thread(sys.stdin.buffer.readline):
        if not linha.strip():
            continue
        resposta = await condutor.atender(linha, "humano")
        sys.stdout.write(json.dumps(resposta) + "\n")
        sys.stdout.flush()
    await condutor.agente.fechar()
    condutor.visor.desconectar()


def main():
    ap = argparse.ArgumentParser(description="Condutor de fila, opção O0")
    ap.add_argument("--estado", required=True, help="pasta do estado e do rastro")
    asyncio.run(principal(ap.parse_args().estado))


if __name__ == "__main__":
    main()
