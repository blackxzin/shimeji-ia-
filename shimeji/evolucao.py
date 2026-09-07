"""Auto-modificação do código-fonte, com trava, backup e validação.

Este é o recurso mais perigoso da Shimeji: texto gerado por um modelo vira código
executável. A versão anterior o deixava sempre ligado e ainda o disparava sozinho
a cada hora. Aqui ele é **desligado por padrão** (`--permitir-auto-modificacao`),
e mesmo ligado passa por: sanitização do nome, validação de sintaxe do bloco,
compilação do arquivo inteiro em um temporário e backup antes de gravar.
"""

from __future__ import annotations

import datetime
import json
import os
import py_compile
import re
import shutil
import tempfile
import unicodedata

from .config import ARQUIVO_MELHORIAS

NOME_FUNCAO_VALIDO = re.compile(r"^[a-z_][a-z0-9_]*$")
MARCADOR_ENTRADA = "if __name__"
XP_POR_MELHORIA = 20

# Construções que nunca fazem parte de uma melhoria legítima e que transformariam
# a auto-evolução em execução de código arbitrário.
PADROES_PROIBIDOS = (
    r"\b__import__\b",
    r"\bexec\s*\(",
    r"\beval\s*\(",
    r"\bcompile\s*\(",
    r"\bsubprocess\b",
    r"\bos\.system\b",
    r"\bos\.remove\b",
    r"\bos\.rmdir\b",
    r"\bshutil\.rmtree\b",
    r"\bsocket\b",
    r"\bopen\s*\([^)]*[\"']w",
)


class ErroDeEvolucao(RuntimeError):
    """A melhoria proposta foi rejeitada."""


def sanitizar_nome(nome: str) -> str:
    """Reduz o nome proposto a um identificador Python seguro."""
    sem_acento = unicodedata.normalize("NFKD", (nome or "")).encode("ascii", "ignore").decode("ascii")
    limpo = re.sub(r"[^a-z0-9_]+", "_", sem_acento.strip().lower()).strip("_")
    if not limpo or not NOME_FUNCAO_VALIDO.match(limpo):
        raise ErroDeEvolucao(f"nome de função inválido: {nome!r}")
    return limpo


def verificar_conteudo(codigo: str) -> None:
    """Rejeita blocos com construções perigosas."""
    for padrao in PADROES_PROIBIDOS:
        if re.search(padrao, codigo):
            raise ErroDeEvolucao(f"a melhoria usa uma construção proibida ({padrao})")


def montar_bloco(nome_funcao: str, comandos: str) -> str:
    """Monta o método a ser injetado a partir de comandos separados por `;`."""
    linhas = [linha.strip() for linha in (comandos or "").split(";") if linha.strip()]
    if not linhas:
        raise ErroDeEvolucao("nenhum comando informado")

    corpo = f'\n    def {nome_funcao}(self):\n        """Método gerado automaticamente pela auto-evolução."""\n'
    for linha in linhas:
        corpo += f"        {linha}\n"

    verificar_conteudo(corpo)
    try:
        compile(f"class _Teste:\n{corpo}", "<melhoria>", "exec")
    except SyntaxError as erro:
        raise ErroDeEvolucao(f"erro de sintaxe: {erro.msg} (linha {erro.lineno})") from erro
    return corpo


def inserir_bloco(conteudo: str, bloco: str) -> str:
    """Insere o bloco antes do `if __name__`, ou no fim do arquivo."""
    if MARCADOR_ENTRADA in conteudo:
        antes, depois = conteudo.rsplit(MARCADOR_ENTRADA, 1)
        return f"{antes}{bloco}\n{MARCADOR_ENTRADA}{depois}"
    return f"{conteudo}\n{bloco}"


def validar_arquivo_completo(conteudo: str, pasta: str) -> None:
    """Compila o arquivo resultante em um temporário antes de tocar no original."""
    descritor, temporario = tempfile.mkstemp(suffix=".py", dir=pasta)
    try:
        with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
            arquivo.write(conteudo)
        py_compile.compile(temporario, cfile=temporario + "c", doraise=True)
    except py_compile.PyCompileError as erro:
        raise ErroDeEvolucao(f"o arquivo resultante não compila: {erro}") from erro
    finally:
        for caminho in (temporario, temporario + "c"):
            if os.path.exists(caminho):
                os.remove(caminho)


def fazer_backup(caminho: str, agora: datetime.datetime | None = None) -> str:
    agora = agora or datetime.datetime.now()
    destino = f"{caminho}.backup_{agora.strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(caminho, destino)
    return destino


def registrar(nome: str, backup: str, arquivo_log: str | None = None) -> None:
    """Anexa a melhoria ao histórico (JSON Lines).

    O caminho é resolvido na chamada, não no import: um valor padrão amarrado à
    constante no momento da definição impediria testes e reconfiguração.
    """
    arquivo_log = arquivo_log or ARQUIVO_MELHORIAS
    entrada = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "funcao": nome,
        "backup": backup,
        "xp": XP_POR_MELHORIA,
    }
    try:
        with open(arquivo_log, "a", encoding="utf-8") as log:
            log.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    except OSError as erro:
        print(f"[evolucao] não consegui registrar a melhoria: {erro}")


def aplicar_melhoria(caminho_alvo: str, nome_funcao: str, comandos: str, permitido: bool) -> str:
    """Aplica uma melhoria ao arquivo indicado. Retorna o nome final da função.

    Levanta ErroDeEvolucao em qualquer etapa de validação que falhar — nesse caso
    o arquivo original permanece intocado.
    """
    if not permitido:
        raise ErroDeEvolucao("auto-modificação desligada (use --permitir-auto-modificacao)")
    if not os.path.isfile(caminho_alvo):
        raise ErroDeEvolucao(f"arquivo alvo não encontrado: {caminho_alvo}")

    nome = sanitizar_nome(nome_funcao)
    bloco = montar_bloco(nome, comandos)

    with open(caminho_alvo, "r", encoding="utf-8") as arquivo:
        conteudo = arquivo.read()

    novo_conteudo = inserir_bloco(conteudo, bloco)
    pasta = os.path.dirname(os.path.abspath(caminho_alvo))
    validar_arquivo_completo(novo_conteudo, pasta)

    backup = fazer_backup(caminho_alvo)
    with open(caminho_alvo, "w", encoding="utf-8") as arquivo:
        arquivo.write(novo_conteudo)

    registrar(nome, backup)
    return nome
