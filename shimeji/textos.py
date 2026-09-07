"""Falas, piadas e roteiros. Separado do código para facilitar tradução e ajuste."""

from __future__ import annotations

SAUDACOES = (
    "Olá {nome}! Como posso ajudar?",
    "E aí {nome}, tudo certo?",
    "Oi {nome}! Em que posso ser útil?",
    "Opa {nome}! Bora codar?",
)

REACOES_CLIQUE = (
    "Oi {nome}!",
    "Hehe, isso faz cócegas!",
    "Estou aqui, é só chamar.",
    "Nível {nivel}, com {xp} de experiência.",
    "Meu afeto por você está em {afeto}.",
)

REACOES_CARINHO = (
    "Ooown, adoro carinho! Afeto em {afeto}.",
    "Que bom! Meu afeto subiu para {afeto}.",
    "Isso me deixa muito feliz! Afeto em {afeto}.",
    "Você é gente boa. Afeto em {afeto}.",
)

PIADAS = (
    "Por que o programador foi demitido? Porque ele não tinha classe.",
    "O que o Java disse pro C? Você não tem classe.",
    "Por que o livro de matemática ficou triste? Porque tinha muitos problemas.",
    "O que um código disse pro outro? Você tá bugado.",
    "Quantos programadores são necessários pra trocar uma lâmpada? Nenhum, isso é problema de hardware.",
    "Existem dez tipos de pessoas: as que entendem binário e as que não entendem.",
    "Meu código não tem bugs, ele tem funcionalidades não documentadas.",
    "Por que o desenvolvedor front-end foi ao terapeuta? Problemas de margem.",
    "O que é um algoritmo guloso? Aquele que sempre pega a maior fatia primeiro.",
    "Fiz um teste unitário e ele passou. Desconfio que o teste esteja errado.",
)

DICAS_SAUDE = (
    "Lembrete: bebe água.",
    "Já descansou os olhos? Olha pra longe por vinte segundos.",
    "Que tal esticar o corpo? Ficar sentado muito tempo cansa.",
    "Postura! Ajeita os ombros e as costas.",
    "Levanta um pouco, dá uma volta e volta com a cabeça mais leve.",
)

# (espera em ms antes do passo, comando)
ROTEIRO_DEMO = (
    (0, "oi shimeji"),
    (4500, "que horas são"),
    (5500, "calcula 25 vezes 4 mais 10"),
    (5000, "anota pra mim: revisar o pull request"),
    (4500, "minhas notas"),
    (6000, "conta uma piada"),
    (6500, "status do sistema"),
    (7000, "volume 40"),
    (4500, "alarme em 3 segundos"),
    (7000, "executa motivacao"),
    (6000, "o que você sabe fazer"),
)


def roteiro_demo() -> tuple[tuple[int, str], ...]:
    """Roteiro do modo `--demo`: só comandos que rodam offline."""
    return ROTEIRO_DEMO
