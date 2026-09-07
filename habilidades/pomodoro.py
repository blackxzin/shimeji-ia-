"""Habilidade: ciclo Pomodoro de 25 minutos de foco."""

import threading

MINUTOS_DE_FOCO = 25


def executar(shimeji=None):
    if shimeji is None:
        print(f"Pomodoro de {MINUTOS_DE_FOCO} minutos iniciado.")
        return

    shimeji.set_mood("feliz")
    shimeji.falar(f"Pomodoro ativado. Foco total por {MINUTOS_DE_FOCO} minutos; eu te aviso no fim.")
    shimeji.ganhar_xp(5)

    def concluir():
        # `parar_evento` é sinalizado no encerramento: não fale com a janela fechada.
        if shimeji.parar_evento.is_set():
            return
        shimeji.set_mood("feliz")
        shimeji.falar("Pomodoro concluído! Parabéns pelo foco. Faz uma pausa de 5 minutos.")
        shimeji.pular(vezes=2)
        shimeji.ganhar_xp(15)

    temporizador = threading.Timer(MINUTOS_DE_FOCO * 60, concluir)
    temporizador.daemon = True
    temporizador.start()
