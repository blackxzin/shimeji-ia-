import time

def executar(shimeji=None):
    """Inicia um timer Pomodoro de 25 minutos."""
    if shimeji is not None:
        shimeji.set_mood("feliz")
        shimeji.falar("Modo Pomodoro ativado! Foco total por 25 minutos. Eu aviso quando acabar!")
        shimeji.ganhar_xp(5)

    # 25 minutos em segundos
    time.sleep(25 * 60)

    if shimeji is not None:
        shimeji.set_mood("feliz")
        shimeji.falar("Pomodoro concluído! Parabéns pelo foco. Hora de fazer uma pausa de 5 minutos!")
        # Animação segura: roda no thread principal via .after
        def _pulo():
            orig_y = shimeji.root.winfo_y()
            shimeji.root.geometry(f"+{shimeji.root.winfo_x()}+{orig_y - 20}")
            shimeji.root.after(300, lambda: shimeji.root.geometry(f"+{shimeji.root.winfo_x()}+{orig_y}"))
        shimeji.root.after(0, _pulo)
        shimeji.ganhar_xp(15)
    else:
        print("Pomodoro concluído!")
