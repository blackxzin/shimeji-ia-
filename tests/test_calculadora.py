"""A calculadora precisa acertar a conta e recusar tudo que não for conta."""

import pytest

from shimeji.calculadora import ErroDeCalculo, calcular, formatar, normalizar


@pytest.mark.parametrize("expressao, esperado", [
    ("2 + 2", 4),
    ("25 x 4", 100),
    ("25 × 4", 100),
    ("10 dividido por 4", 2.5),
    ("7 vezes 8", 56),
    ("100 menos 30", 70),
    ("2 elevado a 10", 1024),
    ("5 ao quadrado", 25),
    ("(2 + 3) * 4", 20),
    ("1,5 + 1,5", 3),
])
def test_calcula_expressoes_comuns(expressao, esperado):
    assert calcular(expressao) == pytest.approx(esperado)


def test_modulo_nao_vira_porcentagem():
    """Regressão: `10 % 3` virava `10 /100 3` e explodia em SyntaxError."""
    assert calcular("10 % 3") == 1
    assert calcular("resto de 10 por 3") == 1


def test_porcentagem_de_um_valor():
    assert calcular("50% de 200") == 100
    assert calcular("10 por cento de 250") == 25


@pytest.mark.parametrize("expressao, esperado", [
    ("raiz quadrada de 144", 12),
    ("raiz de 81", 9),
    ("raiz 25", 5),
])
def test_raiz_quadrada(expressao, esperado):
    assert calcular(expressao) == pytest.approx(esperado)


def test_aceita_frase_falada_completa():
    assert calcular("quanto é 7 vezes 8") == 56


@pytest.mark.parametrize("ataque", [
    '__import__("os").system("ls")',
    'open("/etc/passwd").read()',
    "().__class__.__bases__",
    "exec('x=1')",
    "eval('1+1')",
    "[].__class__",
])
def test_recusa_execucao_de_codigo(ataque):
    """Nenhuma entrada de voz pode virar execução de código arbitrário."""
    with pytest.raises(ErroDeCalculo):
        calcular(ataque)


@pytest.mark.parametrize("bomba", ["9**9**9", "2 elevado a 999999", "10**100000"])
def test_recusa_potencias_gigantes(bomba):
    """Regressão: `9**9**9` no eval antigo travava a Shimeji consumindo CPU."""
    with pytest.raises(ErroDeCalculo):
        calcular(bomba)


def test_divisao_por_zero_vira_erro_tratado():
    with pytest.raises(ErroDeCalculo, match="zero"):
        calcular("10 / 0")


@pytest.mark.parametrize("vazio", ["", "   ", "abacaxi com laranja"])
def test_recusa_entrada_sem_conta(vazio):
    with pytest.raises(ErroDeCalculo):
        calcular(vazio)


def test_normalizar_traduz_fala_para_operadores():
    assert normalizar("25 vezes 4") == "25 * 4"


@pytest.mark.parametrize("valor, esperado", [(4.0, "4"), (2.5, "2.5"), (1 / 3, "0.333333")])
def test_formatar_resultado(valor, esperado):
    assert formatar(valor) == esperado
