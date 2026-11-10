"""Escrita em disco que não deixa arquivo pela metade depois de uma queda."""
from __future__ import annotations

import os
from pathlib import Path


def gravar_atomico(caminho: Path, dados: bytes) -> None:
    temporario = caminho.with_suffix(".tmp")
    with open(temporario, "wb") as f:
        f.write(dados)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporario, caminho)
    pasta = os.open(caminho.parent, os.O_RDONLY)
    try:
        os.fsync(pasta)
    finally:
        os.close(pasta)
