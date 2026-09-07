#!/usr/bin/env python3
"""Gera as capturas de tela usadas no README.

Em vez de disputar empilhamento de janelas com o compositor, cada widget é
capturado no seu retângulo exato (`winfo_rootx`/`winfo_rooty`) e depois composto
sobre um fundo gerado com Pillow. O resultado é determinístico e não vaza a área
de trabalho de quem roda o script.

    python3 scripts/gerar_capturas.py
"""

from __future__ import annotations

import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from shimeji.app import ShimejiApp  # noqa: E402
from shimeji.config import Config, HUMORES, PASTA_ASSETS  # noqa: E402
from shimeji.ui import JanelaConfiguracoes, recortar_transparencia  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_DOCS = os.path.join(RAIZ, "docs")

COR_TOPO = (36, 36, 56)
COR_BASE = (17, 17, 27)
TAMANHO_SPRITE = 200
ESPACO = 28
QUADROS_PARA_ASSENTAR = 8


# ---------------------------------------------------------------- fundo
def gradiente(largura: int, altura: int) -> Image.Image:
    """Fundo vertical suave, no mesmo tema escuro da interface."""
    fundo = Image.new("RGB", (largura, altura))
    pixels = fundo.load()
    for y in range(altura):
        proporcao = y / max(1, altura - 1)
        cor = tuple(round(topo + (base - topo) * proporcao) for topo, base in zip(COR_TOPO, COR_BASE))
        for x in range(largura):
            pixels[x, y] = cor
    return fundo


def compor(elementos: list[Image.Image], preenchimento: int = 48, espaco: int = ESPACO) -> Image.Image:
    """Alinha os elementos lado a lado, centralizados sobre o gradiente."""
    largura = sum(e.width for e in elementos) + espaco * (len(elementos) - 1) + preenchimento * 2
    altura = max(e.height for e in elementos) + preenchimento * 2
    fundo = gradiente(largura, altura)

    x = preenchimento
    for elemento in elementos:
        fundo.paste(
            elemento,
            (x, (altura - elemento.height) // 2),
            elemento if elemento.mode == "RGBA" else None,
        )
        x += elemento.width + espaco
    return fundo


def salvar(imagem: Image.Image, nome: str) -> str:
    os.makedirs(PASTA_DOCS, exist_ok=True)
    caminho = os.path.join(PASTA_DOCS, nome)
    imagem.convert("RGB").save(caminho, quality=92)
    print(f"gerado: docs/{nome}  ({imagem.width}x{imagem.height})")
    return caminho


# ------------------------------------------------------------- sprites
def carregar_sprite(humor: str, tamanho: int = TAMANHO_SPRITE) -> Image.Image:
    imagem = recortar_transparencia(Image.open(os.path.join(PASTA_ASSETS, f"{humor}.png")).convert("RGBA"))
    imagem.thumbnail((tamanho, tamanho), Image.Resampling.LANCZOS)
    return imagem


def gerar_humores() -> None:
    """Os cinco humores lado a lado — não precisa de captura de tela."""
    salvar(compor([carregar_sprite(humor) for humor in HUMORES], preenchimento=32, espaco=16),
           "preview-humores.jpg")


# ------------------------------------------------------------- capturas
def capturar_widget(widget: tk.Misc, assentar, recorte: int = 0) -> Image.Image:
    """Captura o retângulo ocupado por um widget na tela.

    `recorte` apara a moldura de sombra que o compositor desenha em volta da
    janela — sem ele, a área de trabalho aparece sangrando pelos cantos.
    """
    from shimeji import tela

    assentar()
    x, y = widget.winfo_rootx() + recorte, widget.winfo_rooty() + recorte
    largura = widget.winfo_width() - recorte * 2
    altura = widget.winfo_height() - recorte * 2
    completa = tela.capturar().convert("RGB")
    return completa.crop((x, y, min(completa.width, x + largura), min(completa.height, y + altura)))


def main() -> int:
    gerar_humores()

    app = ShimejiApp(Config(sem_voz=True, sem_microfone=True))
    app.despachante.iniciar()
    root = app.root
    app.personagem.mover_para(60, 60)

    # Estado de exemplo, só na memória, para os números da captura ficarem realistas.
    app.memoria._salvar_automaticamente = False
    app.memoria.nome_user = "polar"
    app.memoria.xp = 340
    app.memoria.afeto = 42
    app.memoria.notas = [{"texto": "revisar o pull request", "data": "06/09 14:20"},
                         {"texto": "subir o deploy", "data": "06/09 15:05"}]

    def assentar(quadros: int = QUADROS_PARA_ASSENTAR) -> None:
        for _ in range(quadros):
            root.update_idletasks()
            root.update()
            time.sleep(0.04)

    def gerar_status() -> None:
        app.personagem.definir_humor("feliz")
        app._ao_entrar_mouse(None)
        balao = capturar_widget(app.tooltip._janela, assentar, recorte=1)
        app.tooltip.esconder()
        salvar(compor([carregar_sprite("feliz"), balao]), "preview-status.jpg")

    def gerar_configuracoes() -> None:
        janela = JanelaConfiguracoes(
            root, nome_atual=app.memoria.nome_user, chave_atual="gsk_" + "x" * 28,
            status=app.resumo_status(), ao_salvar=lambda *_: None, ao_limpar_notas=lambda: None,
        )
        janela.janela.geometry("+320+160")
        imagem = capturar_widget(janela.janela, assentar, recorte=8)
        janela.fechar()
        salvar(compor([carregar_sprite("normal"), imagem]), "preview-configuracoes.jpg")

    def gerar_menu() -> None:
        """O menu é uma janela nativa; capturamos pela geometria que o Tk reporta."""
        from shimeji import tela
        from shimeji.ui import construir_menu

        itens = [("💤  Dormir", lambda: None), ("📊  Status do sistema", lambda: None),
                 ("🧠  Habilidades", lambda: None), ("👀  Olhar a tela", lambda: None),
                 ("📖  Ler a tela", lambda: None), ("🕐  Hora e data", lambda: None),
                 ("📝  Minhas notas", lambda: None), ("😂  Piada", lambda: None), ("", None),
                 ("⚡  Auto-melhoria", lambda: None), ("⚙️  Configurações", lambda: None),
                 ("", None), ("❌  Sair", lambda: None)]
        menu = construir_menu(root, itens)
        origem_x, origem_y = 400, 120
        menu.post(origem_x, origem_y)
        assentar()

        largura = menu.winfo_reqwidth()
        altura = menu.winfo_reqheight()
        completa = tela.capturar().convert("RGB")
        imagem = completa.crop((origem_x, origem_y, origem_x + largura, origem_y + altura))
        menu.unpost()
        assentar(2)
        salvar(compor([carregar_sprite("normal"), imagem]), "preview-menu.jpg")

    def executar():
        for etapa in (gerar_status, gerar_menu, gerar_configuracoes):
            etapa()
            assentar(2)
        app.encerrar()

    root.after(400, executar)
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
