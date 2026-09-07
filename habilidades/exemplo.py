"""Habilidade de exemplo: o molde para escrever a sua.

Qualquer arquivo .py nesta pasta que exponha `executar()` vira um comando de voz:
diga "executa exemplo". O argumento `shimeji` é opcional — se você declará-lo,
recebe a instância da aplicação com a API pública documentada no README.
"""


def executar(shimeji=None):
    if shimeji is None:
        print("Habilidade de exemplo executada fora da Shimeji.")
        return

    shimeji.set_mood("feliz")
    shimeji.falar(f"Oi {shimeji.memoria.nome_user}! Esta é a habilidade de exemplo.")
    shimeji.pular()
    shimeji.ganhar_xp(1)
