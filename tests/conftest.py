"""Fixtures compartilhadas pelos testes."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _tem_display() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or sys.platform == "win32")


precisa_de_tela = pytest.mark.skipif(not _tem_display(), reason="requer uma sessão gráfica")


@pytest.fixture
def caminho_memoria(tmp_path):
    return str(tmp_path / "memoria.json")


@pytest.fixture
def memoria(caminho_memoria):
    from shimeji.memoria import Memoria

    return Memoria(caminho_memoria)


@pytest.fixture
def pasta_habilidades(tmp_path):
    pasta = tmp_path / "habilidades"
    pasta.mkdir()
    return str(pasta)


@pytest.fixture
def registro(pasta_habilidades):
    from shimeji.habilidades import RegistroDeHabilidades

    return RegistroDeHabilidades(pasta_habilidades)


class ClienteGroqFalso:
    """Dublê do cliente da Groq: registra chamadas e devolve respostas fixas."""

    def __init__(self, respostas=("resposta padrão",)):
        self.respostas = list(respostas)
        self.chamadas = []
        self.chat = self

    @property
    def completions(self):
        return self

    def create(self, **parametros):
        self.chamadas.append(parametros)
        texto = self.respostas.pop(0) if self.respostas else "resposta padrão"

        class _Mensagem:
            content = texto

        class _Escolha:
            message = _Mensagem()

        class _Resposta:
            choices = [_Escolha()]

        return _Resposta()


@pytest.fixture
def cliente_falso():
    return ClienteGroqFalso
