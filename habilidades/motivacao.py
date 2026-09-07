"""Habilidade: frase motivacional com um pulinho."""

import random

FRASES = (
    "Você consegue! O único limite é a sua mente.",
    "Todo código tem bugs; o importante é não desistir de debugar.",
    "Bebe água, estica as costas e volta com tudo.",
    "Você é mais inteligente do que o seu último erro de sintaxe.",
    "Um passo de cada vez. A montanha se escala um passo por vez.",
    "Não se compare com os outros; compare-se com quem você era ontem.",
)


def executar(shimeji=None):
    frase = random.choice(FRASES)
    if shimeji is None:
        print(frase)
        return
    shimeji.set_mood("feliz")
    shimeji.falar(frase)
    shimeji.pular()
    shimeji.ganhar_xp(2)
