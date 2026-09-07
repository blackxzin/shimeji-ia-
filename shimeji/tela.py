"""Captura de tela multiplataforma.

`ImageGrab` do Pillow não funciona em sessões Wayland puras, que é o caso comum
no Linux moderno. Aqui há uma cadeia de fallbacks por ferramenta externa antes de
desistir, e a captura acontece **uma única vez** por pedido (a versão anterior
capturava a tela duas vezes: uma para a IA e outra para salvar em disco).
"""

from __future__ import annotations

import datetime
import os
import shutil
import subprocess
import sys
import tempfile

TIMEOUT_CAPTURA = 15
PREFIXO_ARQUIVO = "screenshot_"

# Ferramentas de captura por sessão gráfica, em ordem de preferência.
CAPTURADORES_EXTERNOS = (
    ("grim", lambda destino: ["grim", destino]),
    ("spectacle", lambda destino: ["spectacle", "-b", "-n", "-o", destino]),
    ("gnome-screenshot", lambda destino: ["gnome-screenshot", "-f", destino]),
    ("scrot", lambda destino: ["scrot", "-o", destino]),
    ("maim", lambda destino: ["maim", destino]),
    ("screencapture", lambda destino: ["screencapture", "-x", destino]),
)


class ErroDeCaptura(RuntimeError):
    """Não foi possível capturar a tela nesta sessão gráfica."""


def sessao_wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY")) and not os.environ.get("DISPLAY")


def _capturar_com_pillow():
    try:
        from PIL import ImageGrab

        imagem = ImageGrab.grab()
        return imagem if imagem is not None else None
    except Exception:
        return None


def _capturar_com_ferramenta_externa():
    from PIL import Image

    for executavel, montar_comando in CAPTURADORES_EXTERNOS:
        if not shutil.which(executavel):
            continue
        descritor, destino = tempfile.mkstemp(suffix=".png")
        os.close(descritor)
        try:
            resultado = subprocess.run(
                montar_comando(destino),
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=TIMEOUT_CAPTURA, check=False,
            )
            if resultado.returncode == 0 and os.path.getsize(destino) > 0:
                with Image.open(destino) as arquivo:
                    return arquivo.copy()
        except (OSError, subprocess.SubprocessError):
            continue
        finally:
            if os.path.exists(destino):
                os.remove(destino)
    return None


def capturar():
    """Devolve uma imagem PIL com a tela inteira. Levanta ErroDeCaptura se falhar."""
    ordem = (_capturar_com_ferramenta_externa, _capturar_com_pillow) if sessao_wayland() \
        else (_capturar_com_pillow, _capturar_com_ferramenta_externa)

    for tentativa in ordem:
        imagem = tentativa()
        if imagem is not None:
            return imagem

    dica = "instale grim (Wayland) ou scrot/maim (X11)" if sys.platform.startswith("linux") else ""
    raise ErroDeCaptura(f"nenhum método de captura disponível. {dica}".strip())


def salvar(imagem, pasta: str, agora: datetime.datetime | None = None) -> str:
    """Salva a captura com nome baseado no horário e devolve o caminho."""
    agora = agora or datetime.datetime.now()
    caminho = os.path.join(pasta, f"{PREFIXO_ARQUIVO}{agora.strftime('%Y%m%d_%H%M%S')}.png")
    imagem.save(caminho)
    return caminho
