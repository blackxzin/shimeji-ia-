"""Habilidade: reflexão sobre como avaliar informação."""

import random

REFLEXOES = (
    "A verdade exige coragem: buscar fontes confiáveis, analisar e questionar pressupostos.",
    "Ao receber uma informação, considere o contexto, a fonte e a motivação de quem a produziu.",
    "Questionar pressupostos é o que impede que um viés vire conclusão.",
    "Considere pontos de vista diferentes antes de fechar uma opinião.",
    "Buscar a verdade é um processo contínuo. Fique aberto a rever o que você já concluiu.",
)


def executar(shimeji=None):
    reflexao = random.choice(REFLEXOES)
    if shimeji is None:
        print(reflexao)
        return
    shimeji.set_mood("feliz")
    shimeji.falar(reflexao)
    shimeji.ganhar_xp(2)
