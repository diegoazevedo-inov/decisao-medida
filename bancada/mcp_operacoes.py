#!/usr/bin/env python3
"""Servidor MCP por stdio, igual para todas as opções. Encaminha cada ferramenta ao condutor por TCP."""
import json, os, socket
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("operacoes-da-fila")


def chamar(op, **dados):
    with socket.create_connection(("127.0.0.1", int(os.environ["CONDUTOR_PORTA"])), timeout=10) as c:
        f = c.makefile("rw")
        f.write(json.dumps({"op": op, **dados}) + "\n")
        f.flush()
        return f.readline().strip()


@mcp.tool()
def proximo() -> str:
    """Abre o próximo item da fila."""
    return chamar("proximo")


@mcp.tool()
def anterior() -> str:
    """Volta ao item anterior."""
    return chamar("anterior")


@mcp.tool()
def pausar() -> str:
    """Para a troca automática de itens."""
    return chamar("pausar")


@mcp.tool()
def retomar() -> str:
    """Retoma a troca automática."""
    return chamar("retomar")


@mcp.tool()
def pular() -> str:
    """Pede para mandar o item atual ao fim da fila. Depende de confirmação humana."""
    return chamar("pular")


@mcp.tool()
def encerrar() -> str:
    """Pede para encerrar a fila. Depende de confirmação humana."""
    return chamar("encerrar")


@mcp.tool()
def priorizar(id: str) -> str:
    """Coloca o item indicado logo depois do item atual."""
    return chamar("priorizar", id=id)


@mcp.tool()
def estado() -> str:
    """Informa item atual, posição e situação da fila."""
    return chamar("estado")


if __name__ == "__main__":
    mcp.run()
