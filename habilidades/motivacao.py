import random

FRASES = [
    "Você consegue! O único limite é a sua mente.",
    "Todo código tem bugs, o importante é não desistir de debugá-los!",
    "Beba água, estique as costas e volte com tudo!",
    "Você é mais inteligente do que o seu último erro de sintaxe.",
    "Um passo de cada vez. A montanha se escala um passo por vez.",
    "Não se compare com os outros, compare-se com quem você era ontem."
]

def executar(shimeji=None):
    """Fala uma frase motivacional."""
    if shimeji is not None:
        shimeji.set_mood("feliz")
        shimeji.falar(random.choice(FRASES))
        # Animação segura: roda no thread principal via .after
        def _pulo():
            orig_y = shimeji.root.winfo_y()
            shimeji.root.geometry(f"+{shimeji.root.winfo_x()}+{orig_y - 15}")
            shimeji.root.after(250, lambda: shimeji.root.geometry(f"+{shimeji.root.winfo_x()}+{orig_y}"))
        shimeji.root.after(0, _pulo)
        shimeji.ganhar_xp(2)
    else:
        print(random.choice(FRASES))
