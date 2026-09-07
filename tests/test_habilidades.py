"""Plugins são código de terceiros: nada neles pode derrubar a Shimeji."""

import os

import pytest

from shimeji.habilidades import (ErroDeHabilidade, RegistroDeHabilidades, montar_codigo,
                                 nome_de_arquivo_seguro, validar_sintaxe)

HABILIDADE_VALIDA = "def executar(shimeji=None):\n    return 'ok'\n"
HABILIDADE_QUEBRADA = "def executar(:\n    isso não é python\n"
HABILIDADE_SEM_EXECUTAR = "def outra_coisa():\n    pass\n"


def escrever(pasta, nome, conteudo):
    caminho = os.path.join(pasta, f"{nome}.py")
    with open(caminho, "w", encoding="utf-8") as arquivo:
        arquivo.write(conteudo)
    return caminho


def test_carrega_habilidade_valida(registro, pasta_habilidades):
    escrever(pasta_habilidades, "saudar", HABILIDADE_VALIDA)
    assert registro.carregar_tudo() == ("saudar",)
    assert "saudar" in registro


def test_habilidade_com_erro_de_sintaxe_e_ignorada(registro, pasta_habilidades):
    """Regressão: um plugin quebrado não pode impedir o carregamento dos outros."""
    escrever(pasta_habilidades, "boa", HABILIDADE_VALIDA)
    escrever(pasta_habilidades, "quebrada", HABILIDADE_QUEBRADA)
    assert registro.carregar_tudo() == ("boa",)


def test_habilidade_sem_executar_e_ignorada(registro, pasta_habilidades):
    escrever(pasta_habilidades, "incompleta", HABILIDADE_SEM_EXECUTAR)
    assert registro.carregar_tudo() == ()


def test_ignora_arquivos_privados_e_nomes_invalidos(registro, pasta_habilidades):
    escrever(pasta_habilidades, "__init__", HABILIDADE_VALIDA)
    escrever(pasta_habilidades, "9invalido", HABILIDADE_VALIDA)
    assert registro.carregar_tudo() == ()


def test_salvar_nova_habilidade(registro, pasta_habilidades):
    nome = registro.salvar_nova("Contar Piada", "print('oi'); print('tchau')")
    assert nome == "contarpiada"
    assert os.path.isfile(os.path.join(pasta_habilidades, "contarpiada.py"))
    assert nome in registro


def test_salvar_habilidade_com_sintaxe_invalida_nao_grava(registro, pasta_habilidades):
    with pytest.raises(ErroDeHabilidade):
        registro.salvar_nova("ruim", "print('sem fechar'")
    assert os.listdir(pasta_habilidades) == []


@pytest.mark.parametrize("nome", ["", "   ", "123", "!!!"])
def test_nome_invalido_e_recusado(nome):
    with pytest.raises(ErroDeHabilidade):
        nome_de_arquivo_seguro(nome)


def test_executa_passando_a_instancia(registro, pasta_habilidades):
    escrever(pasta_habilidades, "eco", "recebido = []\n\ndef executar(shimeji=None):\n    recebido.append(shimeji)\n")
    registro.carregar_tudo()
    marcador = object()
    registro.executar("eco", marcador)  # não deve levantar


def test_executa_habilidade_sem_parametro(registro, pasta_habilidades):
    escrever(pasta_habilidades, "simples", "def executar():\n    return 1\n")
    registro.carregar_tudo()
    registro.executar("simples", object())


def test_erro_dentro_da_habilidade_vira_erro_tratado(registro, pasta_habilidades):
    escrever(pasta_habilidades, "explode", "def executar(shimeji=None):\n    raise RuntimeError('boom')\n")
    registro.carregar_tudo()
    with pytest.raises(ErroDeHabilidade, match="boom"):
        registro.executar("explode", None)


def test_executar_habilidade_inexistente(registro):
    with pytest.raises(ErroDeHabilidade):
        registro.executar("fantasma")


def test_montar_codigo_recusa_lista_vazia():
    with pytest.raises(ErroDeHabilidade):
        montar_codigo("   ;  ;  ")


def test_montar_codigo_indenta_cada_comando():
    codigo = montar_codigo("a = 1; b = 2")
    assert "    a = 1\n    b = 2\n" in codigo
    validar_sintaxe(codigo)
