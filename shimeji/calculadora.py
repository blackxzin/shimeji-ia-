"""Calculadora segura baseada em AST.

Substitui o `eval()` da versão anterior. Nada de builtins, nada de atributos,
nada de chamadas arbitrárias: apenas uma árvore aritmética validada nó a nó.
"""

from __future__ import annotations

import ast
import math
import operator
import re

LIMITE_EXPOENTE = 1000
LIMITE_BASE_POTENCIA = 10**15
CASAS_DECIMAIS = 6

OPERADORES_BINARIOS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

OPERADORES_UNARIOS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

FUNCOES_PERMITIDAS = {
    "raiz": math.sqrt,
    "sqrt": math.sqrt,
    "abs": abs,
    "arredonda": round,
    "round": round,
    "seno": math.sin,
    "sin": math.sin,
    "cosseno": math.cos,
    "cos": math.cos,
    "tangente": math.tan,
    "tan": math.tan,
    "log": math.log10,
    "ln": math.log,
}

CONSTANTES_PERMITIDAS = {"pi": math.pi, "e": math.e}

# Palavras faladas que viram operadores. Ordem importa: as mais longas primeiro.
SUBSTITUICOES_FALADAS = [
    (r"\bresto\s+(?:da\s+divis[ãa]o\s+)?(?:de\s+)?([\d.]+)\s+por\s+([\d.]+)", r"\1 % \2"),
    (r"\bmais\b", "+"),
    (r"\bmenos\b", "-"),
    (r"\bvezes\b", "*"),
    (r"\bmultiplicado\s+por\b", "*"),
    (r"\bdividido\s+por\b", "/"),
    (r"\bdividido\b", "/"),
    (r"\belevado\s+a\b", "**"),
    (r"\bao\s+quadrado\b", "**2"),
    (r"\bao\s+cubo\b", "**3"),
    (r"\bpor\s+cento\s+de\b", "%DE%"),
    (r"\bpor\s+cento\b", "%PCT%"),
    (r"\braiz\s+(?:quadrada\s+)?(?:de\s+)?([\d.]+)", r"raiz(\1)"),
    (r"\braiz\s+(?:quadrada\s+)?(?:de\s+)?\(", "raiz("),
    (r"[x×]", "*"),
    (r"[÷:]", "/"),
    (r"\^", "**"),
]

CARACTERES_VALIDOS = re.compile(r"^[\d\s+\-*/%().a-z_]*$")


class ErroDeCalculo(ValueError):
    """Expressão inválida ou insegura."""


def normalizar(expressao: str) -> str:
    """Converte linguagem falada em uma expressão aritmética textual.

    >>> normalizar("25 vezes 4")
    '25 * 4'
    >>> normalizar("10 por cento de 200")
    '10 /100* 200'
    """
    texto = expressao.lower().strip()
    texto = texto.replace(",", ".")
    for padrao, substituto in SUBSTITUICOES_FALADAS:
        texto = re.sub(padrao, substituto, texto)

    # `%` só é módulo quando fica entre dois números; "50% de 200" é fração.
    texto = texto.replace("%DE%", "/100*")
    texto = texto.replace("%PCT%", "/100")
    texto = re.sub(r"(\d)\s*%\s*de\s+", r"\1/100*", texto)

    # Ruído de linguagem natural que sobra depois das substituições.
    texto = re.sub(r"\b(?:quanto|é|e|da|dá|o|resultado|de|igual|a|em|com)\b", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _avaliar_no(no: ast.AST) -> float:
    if isinstance(no, ast.Expression):
        return _avaliar_no(no.body)

    if isinstance(no, ast.Constant):
        if isinstance(no.value, bool) or not isinstance(no.value, (int, float)):
            raise ErroDeCalculo("só aceito números")
        return no.value

    if isinstance(no, ast.Name):
        if no.id not in CONSTANTES_PERMITIDAS:
            raise ErroDeCalculo(f"nome não permitido: {no.id}")
        return CONSTANTES_PERMITIDAS[no.id]

    if isinstance(no, ast.UnaryOp):
        operacao = OPERADORES_UNARIOS.get(type(no.op))
        if operacao is None:
            raise ErroDeCalculo("operador unário não permitido")
        return operacao(_avaliar_no(no.operand))

    if isinstance(no, ast.BinOp):
        operacao = OPERADORES_BINARIOS.get(type(no.op))
        if operacao is None:
            raise ErroDeCalculo("operador não permitido")
        esquerda = _avaliar_no(no.left)
        direita = _avaliar_no(no.right)
        if isinstance(no.op, ast.Pow):
            _validar_potencia(esquerda, direita)
        return operacao(esquerda, direita)

    if isinstance(no, ast.Call):
        if not isinstance(no.func, ast.Name) or no.func.id not in FUNCOES_PERMITIDAS:
            raise ErroDeCalculo("função não permitida")
        if no.keywords:
            raise ErroDeCalculo("argumentos nomeados não são aceitos")
        argumentos = [_avaliar_no(arg) for arg in no.args]
        return FUNCOES_PERMITIDAS[no.func.id](*argumentos)

    raise ErroDeCalculo("expressão não suportada")


def _validar_potencia(base: float, expoente: float) -> None:
    """Impede que `9**9**9` congele a Shimeji consumindo toda a CPU."""
    if abs(expoente) > LIMITE_EXPOENTE or abs(base) > LIMITE_BASE_POTENCIA:
        raise ErroDeCalculo("número grande demais para calcular")


def calcular(expressao: str) -> float:
    """Avalia uma expressão aritmética vinda da voz do usuário.

    Levanta ErroDeCalculo para qualquer entrada inválida, insegura ou vazia.
    """
    if not expressao or not expressao.strip():
        raise ErroDeCalculo("expressão vazia")

    texto = normalizar(expressao)
    if not texto:
        raise ErroDeCalculo("expressão vazia")
    if not CARACTERES_VALIDOS.match(texto):
        raise ErroDeCalculo("caracteres inválidos na expressão")

    try:
        arvore = ast.parse(texto, mode="eval")
    except SyntaxError as erro:
        raise ErroDeCalculo("não entendi a expressão") from erro

    try:
        resultado = _avaliar_no(arvore)
    except ZeroDivisionError:
        raise ErroDeCalculo("divisão por zero")
    except OverflowError as erro:
        raise ErroDeCalculo("número grande demais") from erro
    except (TypeError, ValueError) as erro:
        if isinstance(erro, ErroDeCalculo):
            raise
        raise ErroDeCalculo("não consegui calcular isso") from erro

    if isinstance(resultado, complex):
        raise ErroDeCalculo("resultado não é um número real")
    return resultado


def formatar(resultado: float) -> str:
    """Formata o resultado para leitura em voz alta."""
    if isinstance(resultado, float):
        if resultado.is_integer():
            return str(int(resultado))
        return f"{round(resultado, CASAS_DECIMAIS):g}"
    return str(resultado)
