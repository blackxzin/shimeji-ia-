"""
Habilidade: Filosofia da Verdade
Faz a Shimeji compartilhar uma reflexão filosófica sobre a busca pela verdade.
"""
import random


REFLEXOES = [
    "A verdade exige coragem: buscar fontes confiáveis, analisar informações e questionar pressupostos.",
    "A verdade é um conceito complexo e multifacetado que pode variar dependendo do contexto e da perspectiva.",
    "Para encontrar a verdade, é fundamental buscar informações de fontes confiáveis e respeitadas.",
    "Ao receber informações, é importante analisá-las criticamente, considerando contextos, fontes e motivações.",
    "Questionar pressupostos é essencial para garantir que não sejamos influenciados por viés ou preconceitos.",
    "A verdade pode ser relativa e dependente da perspectiva — considere diferentes pontos de vista.",
    "Refletir e avaliar as informações é o passo final para formar uma opinião própria e bem fundamentada.",
    "Lembre-se: a verdade é um processo contínuo de busca e descoberta. Esteja aberto a novas perspectivas.",
]


def executar(shimeji=None):
    """Compartilha uma reflexão filosófica sobre a verdade."""
    reflexao = random.choice(REFLEXOES)
    if shimeji is not None:
        shimeji.falar(reflexao)
        shimeji.set_mood("feliz")
        shimeji.ganhar_xp(2)
    else:
        print(reflexao)
