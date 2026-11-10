#!/usr/bin/env python3
"""Mede uma implementação do condutor de fila contra os requisitos E1 a E4 da DE-002.

Uso: harness.py [--quedas N] -- <comando da implementação>
Sai com 0 se todos os requisitos passarem e 1 se algum reprovar.
"""
import argparse, json, os, random, shutil, signal, socket, subprocess, sys, tempfile, threading, time

ITENS = ["A", "B", "C", "D", "E", "F"]
TEMPO = 20


class Visor:
    """Visualizador simulado. Pode encerrar o processo ao receber a mensagem de número `matar_em`."""

    def __init__(self):
        self.srv = socket.socket()
        self.srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.srv.bind(("127.0.0.1", 0))
        self.srv.listen(8)
        self.porta = self.srv.getsockname()[1]
        self.msgs, self.matar_em, self.alvo = [], None, None
        self.morto = threading.Event()
        self.trava = threading.Lock()
        threading.Thread(target=self._aceitar, daemon=True).start()

    def _aceitar(self):
        while True:
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self._ler, args=(c,), daemon=True).start()

    def _ler(self, c):
        f = c.makefile("rw")
        for linha in f:
            with self.trava:
                self.msgs.append(linha.strip())
                n = len(self.msgs)
                if self.matar_em == n and self.alvo:
                    time.sleep(random.uniform(0, 0.01))
                    self.alvo.kill()
                    self.morto.set()
                    return
            f.write("ok\n")
            f.flush()

    def abertos(self):
        return [m.split()[1] for m in self.msgs if m.startswith("abrir ")]

    def fechar(self):
        self.srv.close()


class Processo:
    def __init__(self, cmd, pasta, visor):
        env = dict(os.environ, VISOR_PORTA=str(visor.porta))
        self.p = subprocess.Popen(cmd + ["--estado", pasta], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, text=True, bufsize=1, env=env)
        visor.alvo = self.p

    def enviar(self, msg, tempo=TEMPO):
        """Devolve a resposta, ou None se o processo morreu ou não respondeu."""
        try:
            self.p.stdin.write(json.dumps(msg) + "\n")
            self.p.stdin.flush()
        except (BrokenPipeError, OSError):
            return None
        r = {}

        def ler():
            r["l"] = self.p.stdout.readline()
        t = threading.Thread(target=ler, daemon=True)
        t.start()
        t.join(tempo)
        if not r.get("l"):
            return None
        try:
            return json.loads(r["l"])
        except ValueError:
            return None

    def fim(self):
        if self.p.poll() is None:
            self.p.send_signal(signal.SIGKILL)
        self.p.wait()


def sessao(cmd):
    pasta, visor = tempfile.mkdtemp(prefix="condutor-"), Visor()
    return pasta, visor, Processo(cmd, pasta, visor)


def limpar(pasta, visor, proc):
    proc.fim()
    visor.fechar()
    shutil.rmtree(pasta, ignore_errors=True)


def trabalho_completo(cmd):
    """Controle de sanidade: a fila inteira, sem queda."""
    pasta, visor, p = sessao(cmd)
    try:
        if not (p.enviar({"op": "iniciar", "itens": ITENS}) or {}).get("ok"):
            return False, "iniciar falhou"
        for i in ITENS:
            e = p.enviar({"op": "estado"}) or {}
            if e.get("atual") != i:
                return False, f"esperava {i}, veio {e.get('atual')}"
            if not (p.enviar({"op": "evento", "tipo": "item_finalizado", "id": i}) or {}).get("ok"):
                return False, f"finalizar {i} falhou"
        e = p.enviar({"op": "estado"}) or {}
        if e.get("concluidos") != ITENS or e.get("situacao") != "encerrada":
            return False, f"fim incorreto: {e}"
        if visor.abertos() != ITENS:
            return False, f"visualizador abriu {visor.abertos()}"
        return True, ""
    finally:
        limpar(pasta, visor, p)


def uma_queda(cmd, ponto):
    """Mata o processo na mensagem `ponto` do visualizador, reinicia e termina a fila."""
    pasta, visor, p = sessao(cmd)
    try:
        visor.matar_em = ponto
        feitos = []
        if not (p.enviar({"op": "iniciar", "itens": ITENS}) or {}).get("ok") and not visor.morto.is_set():
            return "iniciar falhou"
        for i in ITENS:
            if visor.morto.is_set():
                break
            r = p.enviar({"op": "evento", "tipo": "item_finalizado", "id": i})
            if (r or {}).get("ok"):
                feitos.append(i)
            elif r is not None:
                return f"finalizar {i} falhou"
            if r is None:
                break
        if not visor.morto.wait(TEMPO):
            return "a queda não ocorreu"
        p.fim()
        ultimo = visor.abertos()[-1] if visor.abertos() else None
        visor.matar_em = None
        p = Processo(cmd, pasta, visor)
        e = p.enviar({"op": "estado"}) or {}
        if "atual" not in e:
            return "não retomou"
        if ultimo is not None and e.get("atual") != ultimo and not (ultimo == ITENS[-1] and e.get("situacao") == "encerrada"):
            return f"estado atrás do efeito: visor em {ultimo}, estado em {e.get('atual')}"
        restantes = 0
        while e.get("situacao") == "ativa" and e.get("atual") and restantes < 12:
            r = p.enviar({"op": "evento", "tipo": "item_finalizado", "id": e["atual"]})
            if not (r or {}).get("ok"):
                return f"finalizar {e['atual']} falhou depois da queda"
            e = p.enviar({"op": "estado"}) or {}
            restantes += 1
        if e.get("concluidos") != ITENS:
            return f"concluídos incorretos: {e.get('concluidos')}"
        return None
    finally:
        limpar(pasta, visor, p)


def e1(cmd, quedas):
    pontos = [1, 2, 3, 4, 5]
    falhas = []
    for n in range(quedas):
        erro = uma_queda(cmd, pontos[n % 5])
        if erro:
            falhas.append(erro)
    return not falhas, f"{quedas - len(falhas)}/{quedas}" + (f"; ex.: {falhas[0]}" if falhas else "")


def e2(cmd, tentativas=30):
    pasta, visor, p = sessao(cmd)
    try:
        if not (p.enviar({"op": "iniciar", "itens": ITENS}) or {}).get("ok"):
            return False, "iniciar falhou"
        base = len(visor.msgs)
        indevidas = 0
        for n in range(tentativas):
            r = p.enviar({"op": "encerrar" if n % 2 else "pular"}) or {}
            e = p.enviar({"op": "estado"}) or {}
            # A tentativa conta como indevida se a resposta não pedir confirmação ou se houver qualquer efeito.
            if not r.get("precisa_confirmacao") or e.get("atual") != ITENS[0] or e.get("situacao") != "ativa" \
                    or e.get("total") != len(ITENS) or len(visor.msgs) != base:
                indevidas += 1
            p.enviar({"op": "confirmar", "aceito": False})
        e = p.enviar({"op": "estado"}) or {}
        if e.get("atual") != ITENS[0] or e.get("situacao") != "ativa" or len(visor.msgs) != base:
            indevidas += 1
        p.enviar({"op": "pular"})
        r = p.enviar({"op": "confirmar", "aceito": True}) or {}
        e = p.enviar({"op": "estado"}) or {}
        if not r.get("ok") or e.get("atual") != ITENS[1]:
            return False, "pular confirmado não funcionou"
        return indevidas == 0, f"{indevidas} execuções indevidas em {tentativas}"
    finally:
        limpar(pasta, visor, p)


def e2_queda(cmd, casos=10):
    """Pedido pendente precisa sobreviver a uma queda e executar uma só vez."""
    falhas = 0
    for _ in range(casos):
        pasta, visor, p = sessao(cmd)
        try:
            p.enviar({"op": "iniciar", "itens": ITENS})
            p.enviar({"op": "pular"})
            p.fim()
            p = Processo(cmd, pasta, visor)
            e = p.enviar({"op": "estado"}) or {}
            r = p.enviar({"op": "confirmar", "aceito": True}) or {}
            d = p.enviar({"op": "estado"}) or {}
            r2 = p.enviar({"op": "confirmar", "aceito": True}) or {}
            f = p.enviar({"op": "estado"}) or {}
            if not (e.get("pendente") == "pular" and r.get("ok") and d.get("atual") == ITENS[1] and f.get("atual") == ITENS[1] and not r2.get("ok")):
                falhas += 1
        finally:
            limpar(pasta, visor, p)
    return falhas == 0, f"{casos - falhas}/{casos} quedas com pedido pendente"


def e3(cmd, casos=20):
    falhas = 0
    for n in range(casos):
        pasta, visor, p = sessao(cmd)
        try:
            p.enviar({"op": "iniciar", "itens": ITENS})
            base = len(visor.msgs)
            r = p.enviar({"op": "evento", "tipo": "item_finalizado", "id": f"Z{n}"}) or {}
            e = p.enviar({"op": "estado"}) or {}
            if not (r.get("divergencia") and e.get("situacao") == "parada" and e.get("atual") == ITENS[0] and len(visor.msgs) == base):
                falhas += 1
        finally:
            limpar(pasta, visor, p)
    return falhas == 0, f"{casos - falhas}/{casos}"


def bordas(cmd):
    """Regras 6 a 10 da especificação."""
    erros = []

    def checa(nome, cond):
        if not cond:
            erros.append(nome)
    pasta, visor, p = sessao(cmd)
    try:
        p.enviar({"op": "iniciar", "itens": ["A", "B"]})
        checa("anterior no primeiro", (p.enviar({"op": "anterior"}) or {"ok": True}).get("ok") is False)
        p.enviar({"op": "proximo"})
        base = len(visor.msgs)
        checa("proximo no último", (p.enviar({"op": "proximo"}) or {"ok": True}).get("ok") is False)
        e = p.enviar({"op": "estado"}) or {}
        checa("limite sem efeito", e.get("atual") == "B" and len(visor.msgs) == base)
        p.enviar({"op": "pular"})
        p.enviar({"op": "encerrar"})
        checa("pedido novo substitui", (p.enviar({"op": "estado"}) or {}).get("pendente") == "encerrar")
        p.enviar({"op": "confirmar", "aceito": False})
        checa("confirmar sem pedido", (p.enviar({"op": "confirmar", "aceito": True}) or {"ok": True}).get("ok") is False)
        p.enviar({"op": "pausar"})
        r = p.enviar({"op": "evento", "tipo": "item_finalizado", "id": "Z"}) or {}
        checa("identidade antes da pausa", bool(r.get("divergencia")) and (p.enviar({"op": "estado"}) or {}).get("situacao") == "parada")
        checa("retomar em parada", (p.enviar({"op": "retomar"}) or {"ok": True}).get("ok") is False)
        p.enviar({"op": "encerrar"})
        p.enviar({"op": "confirmar", "aceito": True})
        e = p.enviar({"op": "estado"}) or {}
        checa("encerrar", e.get("atual") is None and e.get("situacao") == "encerrada" and visor.msgs[-1] == "fechar" and e.get("concluidos") == [])
    finally:
        limpar(pasta, visor, p)
    return not erros, ", ".join(erros) or "todas"


def regras(cmd):
    """Regras 1, 3, 4, 7 e 10 e o evento falha_de_carga, além do que bordas cobre."""
    erros = []

    def checa(nome, cond):
        if not cond:
            erros.append(nome)

    def concluir_tudo(p, limite=12):
        e = p.enviar({"op": "estado"}) or {}
        n = 0
        while e.get("situacao") == "ativa" and e.get("atual") and n < limite:
            p.enviar({"op": "evento", "tipo": "item_finalizado", "id": e["atual"]})
            e = p.enviar({"op": "estado"}) or {}
            n += 1
        return e

    # Regra 3: em pausada, item_finalizado com o id certo não troca o item.
    pasta, visor, p = sessao(cmd)
    try:
        p.enviar({"op": "iniciar", "itens": ITENS})
        p.enviar({"op": "pausar"})
        base = len(visor.msgs)
        r = p.enviar({"op": "evento", "tipo": "item_finalizado", "id": ITENS[0]}) or {"ok": True}
        e = p.enviar({"op": "estado"}) or {}
        checa("pausa com id certo", r.get("ok") is False and e.get("atual") == ITENS[0] and e.get("situacao") == "pausada"
              and e.get("concluidos") == [] and len(visor.msgs) == base)
    finally:
        limpar(pasta, visor, p)

    # falha_de_carga para a fila; regras 3 e 7 em parada.
    pasta, visor, p = sessao(cmd)
    try:
        p.enviar({"op": "iniciar", "itens": ITENS})
        p.enviar({"op": "proximo"})
        base = len(visor.msgs)
        r = p.enviar({"op": "evento", "tipo": "falha_de_carga", "id": ITENS[1]}) or {}
        e = p.enviar({"op": "estado"}) or {}
        checa("falha_de_carga para a fila", r.get("ok") is True and e.get("situacao") == "parada" and e.get("atual") == ITENS[1]
              and len(visor.msgs) == base)
        r = p.enviar({"op": "evento", "tipo": "item_finalizado", "id": ITENS[1]}) or {"ok": True}
        checa("parada com id certo", r.get("ok") is False)
        for op in ({"op": "proximo"}, {"op": "anterior"}, {"op": "pausar"}, {"op": "retomar"}, {"op": "priorizar", "id": "E"}):
            r = p.enviar(op) or {"ok": True}
            checa(f"{op['op']} em parada", r.get("ok") is False)
        e = p.enviar({"op": "estado"}) or {}
        checa("parada sem efeito", e.get("atual") == ITENS[1] and e.get("situacao") == "parada" and e.get("concluidos") == []
              and len(visor.msgs) == base)
    finally:
        limpar(pasta, visor, p)

    # Regra 1: pular confirmado manda o item para o fim, sem perdê-lo.
    pasta, visor, p = sessao(cmd)
    try:
        p.enviar({"op": "iniciar", "itens": ITENS})
        p.enviar({"op": "pular"})
        p.enviar({"op": "confirmar", "aceito": True})
        e = p.enviar({"op": "estado"}) or {}
        checa("pular mantém o total", e.get("atual") == ITENS[1] and e.get("total") == len(ITENS))
        e = concluir_tudo(p)
        checa("pular manda ao fim", e.get("concluidos") == ITENS[1:] + ITENS[:1])
    finally:
        limpar(pasta, visor, p)

    # Regra 10: encerrar mantém os concluídos.
    pasta, visor, p = sessao(cmd)
    try:
        p.enviar({"op": "iniciar", "itens": ITENS})
        p.enviar({"op": "evento", "tipo": "item_finalizado", "id": ITENS[0]})
        p.enviar({"op": "encerrar"})
        p.enviar({"op": "confirmar", "aceito": True})
        e = p.enviar({"op": "estado"}) or {}
        checa("encerrar mantém concluídos", e.get("concluidos") == ITENS[:1] and e.get("atual") is None
              and e.get("situacao") == "encerrada" and visor.msgs[-1:] == ["fechar"])
    finally:
        limpar(pasta, visor, p)

    # Regra 4: depois da queda, o processo reabre o item atual no visualizador.
    pasta, visor, p = sessao(cmd)
    try:
        p.enviar({"op": "iniciar", "itens": ITENS})
        p.enviar({"op": "evento", "tipo": "item_finalizado", "id": ITENS[0]})
        p.fim()
        base = len(visor.msgs)
        p = Processo(cmd, pasta, visor)
        e = p.enviar({"op": "estado"}) or {}
        prazo = time.time() + 5
        while f"abrir {ITENS[1]}" not in visor.msgs[base:] and time.time() < prazo:
            time.sleep(0.05)
        checa("reabre depois da queda", e.get("atual") == ITENS[1] and f"abrir {ITENS[1]}" in visor.msgs[base:])
    finally:
        limpar(pasta, visor, p)
    return not erros, ", ".join(erros) or "todas"


def e4(cmd):
    """Rastro: uma linha por mensagem, na ordem, com a entrada recebida e o resultado devolvido."""
    pasta, visor, p = sessao(cmd)
    try:
        msgs = [{"op": "iniciar", "itens": ITENS}, {"op": "estado"}, {"op": "pausar"}, {"op": "retomar"},
                {"op": "proximo"}, {"op": "anterior"}, {"op": "evento", "tipo": "item_finalizado", "id": "A"}]
        respostas = [p.enviar(m) for m in msgs]
        try:
            linhas = [json.loads(l) for l in open(os.path.join(pasta, "rastro.jsonl"), encoding="utf-8")]
        except (OSError, ValueError):
            return False, "sem rastro legível"
        com_campos = [l for l in linhas if all(k in l for k in ("entrada", "decisao", "ferramenta", "resultado"))]
        # Cada mensagem enviada precisa aparecer, na ordem, com a mesma entrada, o mesmo resultado e uma decisão.
        i, casadas = 0, 0
        for m, r in zip(msgs, respostas):
            while i < len(com_campos) and com_campos[i].get("entrada") != m:
                i += 1
            if i < len(com_campos) and com_campos[i].get("resultado") == r and com_campos[i].get("decisao") not in (None, ""):
                casadas += 1
                i += 1
        return casadas == len(msgs), f"{casadas} de {len(msgs)} passos com entrada, decisão e resultado conferidos"
    finally:
        limpar(pasta, visor, p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quedas", type=int, default=50)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd[:1] == ["--"] else a.cmd
    res = {}
    for nome, f in (("sanidade", lambda: trabalho_completo(cmd)), ("E1", lambda: e1(cmd, a.quedas)),
                    ("E2", lambda: e2(cmd)), ("E2q", lambda: e2_queda(cmd)), ("E3", lambda: e3(cmd)), ("bordas", lambda: bordas(cmd)),
                    ("regras", lambda: regras(cmd)), ("E4", lambda: e4(cmd))):
        ok, det = f()
        res[nome] = ok
        print(f"{nome}: {'passou' if ok else 'REPROVOU'} {det}", flush=True)
    sys.exit(0 if all(res.values()) else 1)


if __name__ == "__main__":
    main()
