#!/usr/bin/env python3
"""Grava `docs/demo.gif` com o personagem real reagindo na tela.

Cada quadro é uma captura da região ocupada pela janela da Shimeji enquanto um
roteiro de humores e animações roda de verdade — nada é desenhado à mão aqui.

    python3 scripts/gerar_gif.py
"""

from __future__ import annotations

import os
import sys
import time
import tkinter as tk

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image  # noqa: E402

from shimeji.app import ShimejiApp  # noqa: E402
from shimeji.config import Config  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAMINHO_GIF = os.path.join(RAIZ, "docs", "demo.gif")

POSICAO = (120, 120)
MILISSEGUNDOS_POR_QUADRO = 140
LADO_QUADRO = 320
RECORTE_SOMBRA = 8

# Fundo chapado, igual ao fundo que a janela usa: a moldura da janela some no
# quadro e a área de trabalho de quem grava nunca aparece.
COR_FUNDO_HEX = "#181825"
COR_FUNDO_RGB = (0x18, 0x18, 0x25)

# (humor, animação, quantos quadros segurar)
ROTEIRO = (
    ("normal", None, 4),
    ("piscando", None, 1),
    ("normal", None, 3),
    ("feliz", "pular", 8),
    ("normal", None, 2),
    ("brava", "tremer", 8),
    ("normal", None, 2),
    ("triste", None, 4),
    ("feliz", "pular", 6),
    ("normal", None, 4),
)


def main() -> int:
    app = ShimejiApp(Config(sem_voz=True, sem_microfone=True))
    app.despachante.iniciar()
    root = app.root
    personagem = app.personagem
    personagem.mover_para(*POSICAO)

    from shimeji import tela

    root.config(bg=COR_FUNDO_HEX)
    personagem.label.config(bg=COR_FUNDO_HEX)
    try:
        root.attributes("-alpha", 1.0)
    except tk.TclError:
        pass

    quadros: list[Image.Image] = []

    def assentar(vezes: int = 2) -> None:
        for _ in range(vezes):
            root.update_idletasks()
            root.update()
            time.sleep(0.02)

    def capturar_quadro() -> None:
        """Recorta apenas a janela do personagem e a centraliza no fundo gerado."""
        assentar()
        x = root.winfo_rootx() + RECORTE_SOMBRA
        y = root.winfo_rooty() + RECORTE_SOMBRA
        largura = root.winfo_width() - RECORTE_SOMBRA * 2
        altura = root.winfo_height() - RECORTE_SOMBRA * 2
        completa = tela.capturar().convert("RGB")
        recorte = completa.crop((x, y, x + largura, y + altura))
        if recorte.width > LADO_QUADRO or recorte.height > LADO_QUADRO:
            recorte.thumbnail((LADO_QUADRO, LADO_QUADRO), Image.Resampling.LANCZOS)

        quadro = Image.new("RGB", (LADO_QUADRO, LADO_QUADRO), COR_FUNDO_RGB)
        quadro.paste(recorte, ((LADO_QUADRO - recorte.width) // 2, (LADO_QUADRO - recorte.height) // 2))
        quadros.append(quadro)

    def gravar():
        for humor, animacao, repeticoes in ROTEIRO:
            personagem.definir_humor(humor)
            if animacao:
                getattr(personagem, animacao)()
            for _ in range(repeticoes):
                capturar_quadro()
        app.encerrar()

    root.after(400, gravar)
    root.mainloop()

    if not quadros:
        print("nenhum quadro capturado", file=sys.stderr)
        return 1

    reduzidos = [quadro.convert("P", palette=Image.Palette.ADAPTIVE, colors=128) for quadro in quadros]

    os.makedirs(os.path.dirname(CAMINHO_GIF), exist_ok=True)
    reduzidos[0].save(
        CAMINHO_GIF, save_all=True, append_images=reduzidos[1:],
        duration=MILISSEGUNDOS_POR_QUADRO, loop=0, optimize=False, disposal=1,
    )
    tamanho_kb = os.path.getsize(CAMINHO_GIF) / 1024
    print(f"gerado: docs/demo.gif  ({len(reduzidos)} quadros, {tamanho_kb:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
