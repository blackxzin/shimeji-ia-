"""Carregador de habilidades (plugins) da pasta `habilidades/`.

Cada arquivo `.py` que expõe `executar()` vira um comando de voz. A sintaxe é
validada antes da importação para que um plugin quebrado não derrube a Shimeji.
"""

from __future__ import annotations

import importlib.util
import inspect
import os
import re
import traceback
from typing import Callable

from .config import PASTA_HABILIDADES

NOME_VALIDO = re.compile(r"^[a-z_][a-z0-9_]*$")
CABECALHO_HABILIDADE = "import time, os, webbrowser\n\n\ndef executar(shimeji=None):\n"


class ErroDeHabilidade(RuntimeError):
    """Plugin inválido ou que falhou ao carregar."""


def nome_de_arquivo_seguro(nome: str) -> str:
    """Converte um nome falado em um identificador de módulo válido."""
    limpo = re.sub(r"\W+", "", (nome or "").strip().lower())
    if not limpo or not NOME_VALIDO.match(limpo):
        raise ErroDeHabilidade(f"nome de habilidade inválido: {nome!r}")
    return limpo


def montar_codigo(comandos: str) -> str:
    """Monta o corpo de uma habilidade a partir de comandos separados por `;`."""
    corpo = CABECALHO_HABILIDADE
    linhas = [linha.strip() for linha in (comandos or "").split(";") if linha.strip()]
    if not linhas:
        raise ErroDeHabilidade("nenhum comando informado")
    for linha in linhas:
        corpo += f"    {linha}\n"
    return corpo


def validar_sintaxe(codigo: str) -> None:
    """Levanta ErroDeHabilidade se o código não compilar."""
    try:
        compile(codigo, "<habilidade>", "exec")
    except SyntaxError as erro:
        raise ErroDeHabilidade(f"erro de sintaxe: {erro.msg} (linha {erro.lineno})") from erro


class RegistroDeHabilidades:
    """Guarda as habilidades carregadas e sabe recarregá-las do disco."""

    def __init__(self, pasta: str = PASTA_HABILIDADES):
        self.pasta = pasta
        self._habilidades: dict[str, Callable] = {}
        os.makedirs(self.pasta, exist_ok=True)

    @property
    def nomes(self) -> tuple[str, ...]:
        return tuple(sorted(self._habilidades))

    def __contains__(self, nome: str) -> bool:
        return nome in self._habilidades

    def __len__(self) -> int:
        return len(self._habilidades)

    def carregar_tudo(self) -> tuple[str, ...]:
        """Importa todos os plugins válidos da pasta. Retorna os nomes carregados."""
        self._habilidades.clear()
        if not os.path.isdir(self.pasta):
            return ()
        for arquivo in sorted(os.listdir(self.pasta)):
            if not arquivo.endswith(".py") or arquivo.startswith("_"):
                continue
            nome = arquivo[:-3]
            if not NOME_VALIDO.match(nome):
                continue
            try:
                self.importar(nome)
            except ErroDeHabilidade as erro:
                print(f"[habilidades] '{nome}' ignorada: {erro}")
        return self.nomes

    def importar(self, nome: str) -> Callable:
        """Importa um plugin pelo nome, validando a sintaxe antes."""
        caminho = os.path.join(self.pasta, f"{nome}.py")
        if not os.path.isfile(caminho):
            raise ErroDeHabilidade(f"arquivo não encontrado: {caminho}")

        with open(caminho, "r", encoding="utf-8") as arquivo:
            validar_sintaxe(arquivo.read())

        especificacao = importlib.util.spec_from_file_location(f"habilidade_{nome}", caminho)
        if especificacao is None or especificacao.loader is None:
            raise ErroDeHabilidade(f"não consegui preparar o módulo {nome}")

        modulo = importlib.util.module_from_spec(especificacao)
        try:
            especificacao.loader.exec_module(modulo)
        except Exception as erro:  # o plugin é código de terceiros: isole a falha
            raise ErroDeHabilidade(f"falhou ao executar o módulo: {erro}") from erro

        funcao = getattr(modulo, "executar", None)
        if not callable(funcao):
            raise ErroDeHabilidade("o módulo não expõe uma função executar()")

        self._habilidades[nome] = funcao
        return funcao

    def salvar_nova(self, nome: str, comandos: str) -> str:
        """Grava uma nova habilidade em disco e a carrega. Retorna o nome final."""
        nome_seguro = nome_de_arquivo_seguro(nome)
        codigo = montar_codigo(comandos)
        validar_sintaxe(codigo)

        caminho = os.path.join(self.pasta, f"{nome_seguro}.py")
        with open(caminho, "w", encoding="utf-8") as arquivo:
            arquivo.write(codigo)
        self.importar(nome_seguro)
        return nome_seguro

    def executar(self, nome: str, shimeji=None) -> None:
        """Executa a habilidade, passando a instância da Shimeji se ela aceitar."""
        funcao = self._habilidades.get(nome)
        if funcao is None:
            raise ErroDeHabilidade(f"habilidade desconhecida: {nome}")
        try:
            if len(inspect.signature(funcao).parameters) >= 1:
                funcao(shimeji)
            else:
                funcao()
        except Exception as erro:
            print(f"[habilidades] erro ao executar '{nome}': {erro}")
            traceback.print_exc()
            raise ErroDeHabilidade(str(erro)) from erro
