"""Regras da fila: transições puras, sem E/S e sem modelo."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel

Pedido = Literal["pular", "encerrar"]


class Decisao(BaseModel):
    pedido: Pedido
    aceito: bool


class Fila(BaseModel):
    """Tudo o que precisa sobreviver a uma queda. É o que vai para o disco."""

    itens: list[str]
    posicao: int = 0
    situacao: Literal["ativa", "pausada", "parada", "encerrada"] = "ativa"
    concluidos: list[str] = []
    pendente: Pedido | None = None
    ultima_decisao: Decisao | None = None

    @property
    def atual(self) -> str | None:
        return self.itens[self.posicao] if self.posicao < len(self.itens) else None

    def retrato(self) -> dict[str, Any]:
        return {"ok": True, "atual": self.atual, "posicao": self.posicao, "total": len(self.itens),
                "situacao": self.situacao, "concluidos": self.concluidos, "pendente": self.pendente}


@dataclass
class Passo:
    """Resultado de uma mensagem: novo estado, resposta, motivo e efeitos no visualizador."""

    fila: Fila | None
    resposta: dict[str, Any]
    decisao: str
    efeitos: list[str] = field(default_factory=list)


def _recusa(fila: Fila | None, motivo: str) -> Passo:
    return Passo(fila, {"ok": False}, f"recusado: {motivo}")


def _item_valido(item: Any) -> bool:
    return isinstance(item, str) and bool(item) and not any(c.isspace() for c in item)


def _fechar(f: Fila) -> list[str]:
    f.posicao, f.situacao, f.pendente = len(f.itens), "encerrada", None
    return ["fechar"]


def _abrir_atual(f: Fila) -> list[str]:
    return [f"abrir {f.atual}"] if f.atual is not None else _fechar(f)


def _iniciar(fila: Fila | None, msg: dict[str, Any]) -> Passo:
    itens = msg.get("itens")
    if fila is not None and fila.situacao != "encerrada":
        return _recusa(fila, "fila em andamento")
    if not isinstance(itens, list) or not itens or not all(map(_item_valido, itens)) or len(set(itens)) != len(itens):
        return _recusa(fila, "itens inválidos")
    f = Fila(itens=itens)
    return Passo(f, {"ok": True}, f"fila criada, abrir {f.atual}", _abrir_atual(f))


def _mover(f: Fila, delta: int) -> Passo:
    alvo = f.posicao + delta
    if not 0 <= alvo < len(f.itens):
        return _recusa(f, "limite da fila")
    f.posicao = alvo
    return Passo(f, {"ok": True}, f"abrir {f.atual}", _abrir_atual(f))


def _pausar(f: Fila) -> Passo:
    f.situacao = "pausada"
    return Passo(f, {"ok": True}, "fila pausada")


def _retomar(f: Fila) -> Passo:
    f.situacao = "ativa"
    return Passo(f, {"ok": True}, "fila ativa")


def _priorizar(f: Fila, msg: dict[str, Any]) -> Passo:
    item, atual = msg.get("id"), f.atual
    if item not in f.itens or item == atual or item in f.concluidos:
        return _recusa(f, f"priorizar {item}")
    f.itens.remove(item)
    f.posicao = f.itens.index(atual)  # o item pode ter saído de antes do atual
    f.itens.insert(f.posicao + 1, item)
    return Passo(f, {"ok": True}, f"{item} logo depois de {atual}")


def _pedir(f: Fila, pedido: Pedido) -> Passo:
    f.pendente = pedido
    return Passo(f, {"ok": False, "precisa_confirmacao": True}, f"{pedido} aguarda confirmação humana")


def _confirmar(f: Fila, msg: dict[str, Any]) -> Passo:
    pedido = f.pendente
    if pedido is None:
        return _recusa(f, "sem pedido pendente")
    aceito = msg.get("aceito") is True
    f.pendente, f.ultima_decisao = None, Decisao(pedido=pedido, aceito=aceito)
    if not aceito:
        return Passo(f, {"ok": True}, f"{pedido} cancelado pelo humano")
    if pedido == "encerrar":
        return Passo(f, {"ok": True}, "encerrar confirmado", _fechar(f))
    f.itens.append(f.itens.pop(f.posicao))
    return Passo(f, {"ok": True}, f"pular confirmado, abrir {f.atual}", _abrir_atual(f))


def _item_finalizado(f: Fila, msg: dict[str, Any]) -> Passo:
    item = msg.get("id")
    if item != f.atual:
        f.situacao = "parada"
        return Passo(f, {"ok": False, "divergencia": True}, f"divergência: veio {item}, atual {f.atual}")
    if f.situacao != "ativa":
        return _recusa(f, f"fila {f.situacao}")
    if item not in f.concluidos:
        f.concluidos.append(item)
    f.posicao += 1
    while f.atual in f.concluidos:  # quem voltou com `anterior` não reabre o que já foi concluído
        f.posicao += 1
    return Passo(f, {"ok": True}, f"{item} concluído", _abrir_atual(f))


def _evento(f: Fila, msg: dict[str, Any]) -> Passo:
    match msg.get("tipo"):
        case "item_finalizado":
            return _item_finalizado(f, msg)
        case "falha_de_carga" if f.situacao != "parada":
            f.situacao = "parada"
            return Passo(f, {"ok": True}, f"falha de carga em {msg.get('id')}, fila parada")
    return _recusa(f, "evento sem efeito")


def aplicar(fila: Fila | None, msg: dict[str, Any]) -> Passo:
    """Aplica uma mensagem a uma cópia do estado. Quem chama grava antes de executar os efeitos."""
    op = msg.get("op")
    if op == "iniciar":
        return _iniciar(fila, msg)
    if fila is None:
        return _recusa(None, "fila não iniciada")
    if op == "estado":
        return Passo(fila, fila.retrato(), "consulta")
    if op not in ("proximo", "anterior", "pausar", "retomar", "priorizar", "pular", "encerrar", "confirmar", "evento"):
        return _recusa(fila, "operação desconhecida")
    if fila.situacao == "encerrada":
        return _recusa(fila, "fila encerrada")
    if fila.situacao == "parada" and op not in ("encerrar", "confirmar", "evento"):
        return _recusa(fila, "fila parada")  # regra 7; `evento` decide sozinho, porque a identidade vem antes
    f = fila.model_copy(deep=True)
    match op:
        case "proximo":
            return _mover(f, 1)
        case "anterior":
            return _mover(f, -1)
        case "pausar":
            return _pausar(f)
        case "retomar":
            return _retomar(f)
        case "priorizar":
            return _priorizar(f, msg)
        case "pular" | "encerrar":
            return _pedir(f, op)
        case "confirmar":
            return _confirmar(f, msg)
    return _evento(f, msg)
