#!/usr/bin/env python3
"""Conta o código próprio de cada opção em tokens, para a sensibilidade de C3 da DE-002.

Uso: contar_tokens.py <pasta da implementação> [<pasta> ...]
Conta os tokens do tokenize do Python nos arquivos .py da pasta, sem comentários, docstrings,
quebras de linha e indentação. Os números da DE-002 usam o tokenize do Python 3.12 ou mais novo:
a partir do 3.12 cada f-string vira vários tokens, e no 3.11 um só, o que muda a contagem.
"""
import glob, io, os, sys, tokenize

IGNORAR = (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER)


def tokens(pasta):
    n = 0
    for arquivo in sorted(glob.glob(os.path.join(pasta, "*.py"))):
        fonte = open(arquivo, encoding="utf-8").read()
        for t in tokenize.generate_tokens(io.StringIO(fonte).readline):
            if t.type in IGNORAR:
                continue
            if t.type == tokenize.STRING and t.line.strip().startswith(('"""', "'''")):
                continue
            n += 1
    return n


if __name__ == "__main__":
    contagem = {os.path.basename(os.path.normpath(p)): tokens(p) for p in sys.argv[1:]}
    menor = min(contagem.values())
    for nome, n in contagem.items():
        print(f"{nome}: {n} tokens (razão para a menor: {n / menor:.3f})")
