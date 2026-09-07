"""Captura de tela: Wayland não tem ImageGrab, então a cadeia de fallback importa."""

import os
import subprocess

import pytest
from PIL import Image

from shimeji import tela


@pytest.fixture
def sem_ferramentas(monkeypatch):
    monkeypatch.setattr(tela.shutil, "which", lambda _: None)


def test_detecta_sessao_wayland(monkeypatch):
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.delenv("DISPLAY", raising=False)
    assert tela.sessao_wayland() is True


def test_x11_nao_e_wayland(monkeypatch):
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-1")
    monkeypatch.setenv("DISPLAY", ":0")
    assert tela.sessao_wayland() is False


def test_usa_pillow_quando_funciona(monkeypatch, sem_ferramentas):
    esperada = Image.new("RGB", (10, 10), "blue")
    monkeypatch.setattr(tela, "_capturar_com_pillow", lambda: esperada)
    assert tela.capturar() is esperada


def test_cai_para_ferramenta_externa_quando_pillow_falha(monkeypatch):
    """Regressão: em Wayland o ImageGrab devolve None e a Shimeji ficava cega."""
    monkeypatch.setattr(tela, "_capturar_com_pillow", lambda: None)
    esperada = Image.new("RGB", (5, 5), "red")
    monkeypatch.setattr(tela, "_capturar_com_ferramenta_externa", lambda: esperada)
    assert tela.capturar() is esperada


def test_erro_claro_quando_nada_funciona(monkeypatch):
    monkeypatch.setattr(tela, "_capturar_com_pillow", lambda: None)
    monkeypatch.setattr(tela, "_capturar_com_ferramenta_externa", lambda: None)
    with pytest.raises(tela.ErroDeCaptura, match="nenhum método"):
        tela.capturar()


def test_pillow_com_excecao_nao_propaga(monkeypatch):
    def explodir():
        raise OSError("sem X11")

    monkeypatch.setattr(tela, "ImageGrab", None, raising=False)
    import PIL.ImageGrab

    monkeypatch.setattr(PIL.ImageGrab, "grab", lambda *a, **k: explodir())
    assert tela._capturar_com_pillow() is None


def test_ferramenta_externa_gera_a_imagem(monkeypatch, tmp_path):
    monkeypatch.setattr(tela.shutil, "which", lambda nome: "/usr/bin/grim" if nome == "grim" else None)

    def executar(comando, **_):
        Image.new("RGB", (8, 8), "green").save(comando[-1])
        return subprocess.CompletedProcess(comando, 0)

    monkeypatch.setattr(tela.subprocess, "run", executar)
    imagem = tela._capturar_com_ferramenta_externa()
    assert imagem is not None and imagem.size == (8, 8)


def test_ferramenta_que_falha_e_pulada(monkeypatch):
    monkeypatch.setattr(tela.shutil, "which", lambda _: "/usr/bin/qualquer")
    monkeypatch.setattr(tela.subprocess, "run",
                        lambda comando, **_: subprocess.CompletedProcess(comando, 1))
    assert tela._capturar_com_ferramenta_externa() is None


def test_ferramenta_que_estoura_o_tempo_e_pulada(monkeypatch):
    monkeypatch.setattr(tela.shutil, "which", lambda _: "/usr/bin/qualquer")

    def estourar(comando, **_):
        raise subprocess.TimeoutExpired(comando, 15)

    monkeypatch.setattr(tela.subprocess, "run", estourar)
    assert tela._capturar_com_ferramenta_externa() is None


def test_nao_deixa_arquivo_temporario(monkeypatch, tmp_path):
    monkeypatch.setattr(tela.shutil, "which", lambda _: "/usr/bin/qualquer")
    criados = []

    def executar(comando, **_):
        criados.append(comando[-1])
        return subprocess.CompletedProcess(comando, 1)

    monkeypatch.setattr(tela.subprocess, "run", executar)
    tela._capturar_com_ferramenta_externa()
    assert criados and not any(os.path.exists(caminho) for caminho in criados)


def test_salvar_usa_o_horario_no_nome(tmp_path):
    import datetime

    caminho = tela.salvar(Image.new("RGB", (4, 4)), str(tmp_path),
                          datetime.datetime(2026, 9, 6, 14, 30, 5))
    assert caminho.endswith("screenshot_20260906_143005.png")
    assert os.path.isfile(caminho)
