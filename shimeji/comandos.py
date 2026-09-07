"""Interpretador de comandos de voz.

Lógica 100% pura: recebe texto, devolve uma `Intencao`. Nenhum efeito colateral,
nenhuma dependência de Tk — é a camada que os testes exercitam de verdade.

As expressões regulares aqui foram reescritas com âncoras de palavra e contexto
porque a versão anterior disparava falsos positivos: "dataframe" virava pedido de
data, "quanto tempo leva" virava previsão do tempo e "memória do Python" virava
relatório de hardware.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class Acao(str, Enum):
    SAUDACAO = "saudacao"
    ABRIR = "abrir"
    PESQUISAR = "pesquisar"
    FECHAR = "fechar"
    HORA = "hora"
    ALARME = "alarme"
    ANOTAR = "anotar"
    LER_NOTAS = "ler_notas"
    PIADA = "piada"
    CALCULAR = "calcular"
    CLIMA = "clima"
    VER_TELA = "ver_tela"
    LER_TELA = "ler_tela"
    STATUS = "status"
    VOLUME = "volume"
    HABILIDADES = "habilidades"
    MELHORAR = "melhorar"
    DORMIR = "dormir"
    ACORDAR = "acordar"
    HABILIDADE_EXTRA = "habilidade_extra"
    CONVERSAR = "conversar"


@dataclass(frozen=True)
class Intencao:
    """Resultado da interpretação de uma fala."""

    acao: Acao
    parametros: dict = field(default_factory=dict)

    def __getitem__(self, chave):
        return self.parametros[chave]


# --- Expressões regulares -------------------------------------------------
# Verbos de comando ancorados no início da frase: evita capturar "vou abrir o PR"
# no meio de uma conversa sobre código.
CMD_SAUDACAO = r"^(?:oi|ol[aá]|hey|bom\s+dia|boa\s+tarde|boa\s+noite|eai|e\s+a[ií]|fala|salve|opa)\b"
CMD_ABRIR = r"^(?:abre|abra|abrir|inicia|inicie|executa\s+o\s+programa)\s+(.+)"
CMD_PESQUISAR = r"^(?:pesquisa|pesquise|pesquisar|busca|busque|procure|procura|search)\s+(?:por\s+|sobre\s+)?(.+)"
CMD_FECHAR = r"^(?:fecha|feche|fechar|mate|matar|encerra|encerre)\s+(?:o\s+|a\s+)?(.+)"
CMD_VER_TELA = (
    r"(?:olh[ae]\s+(?:na\s+|a\s+|pra\s+)?tela|olha\s+isso|o\s+que\s+tem\s+na\s+tela"
    r"|o\s+que\s+voc[eê]\s+v[êe]\b|\bscreenshot\b|captur(?:a|ar)\s+(?:a\s+)?tela"
    r"|analis[ae]\s+(?:a\s+)?tela|revis[ae]\s+(?:esse\s+|este\s+)?c[oó]digo)"
)
CMD_LER_TELA = r"(?:\b(?:l[eê]|leia|ler)\s+(?:o\s+que\s+est[aá]\s+)?(?:[ao]\s+|n[ao]\s+)?tela|\bocr\b|extrai\s+(?:o\s+)?texto\s+(?:d[ao]\s+)?tela)"
CMD_STATUS = (
    r"(?:^status\b|status\s+do\s+(?:sistema|pc|computador)|como\s+est[aá]\s+(?:o\s+)?(?:pc|sistema|computador)"
    r"|uso\s+de\s+(?:cpu|mem[oó]ria|ram|disco)|quanto\s+de\s+(?:ram|mem[oó]ria|bateria|disco)"
    r"|n[ií]vel\s+da\s+bateria|^info(?:rma[cç][oõ]es)?\s+do\s+sistema)"
)
CMD_HABILIDADES = (
    r"(?:o\s+que\s+voc[eê]\s+(?:sabe|pode|consegue)\s+fazer|suas\s+habilidades"
    r"|quais?\s+(?:s[aã]o\s+)?(?:os\s+)?comandos|lista\s+(?:de\s+)?(?:comandos|habilidades))"
)
CMD_VOLUME = r"^volume\s*(?:para|em|no|pro)?\s*(\d{1,3})?\s*%?$"
CMD_MELHORAR = r"^(?:melhora|melhore|melhorar|evolua|evoluir|se\s+aprimore|upgrade)\s*(.*)?$"
CMD_NOTA = r"^(?:anota|anote|anotar|nota|lembra|lembre|lembrete|memoriza|memorize)(?:\s+(?:a[ií]|pra\s+mim|que))?\s*:?\s*(.+)"
CMD_LER_NOTAS = r"(?:minhas?\s+notas?|o\s+que\s+(?:eu\s+)?anotei|meus?\s+lembretes?|l[eê]\s+(?:as\s+)?notas)"
CMD_PIADA = r"(?:cont[ae]\s+(?:uma\s+)?piada|me\s+faz\s+rir|manda\s+(?:uma\s+)?piada|^piada\b)"
CMD_HORA = (
    r"(?:que\s+horas?\s+s[aã]o|que\s+dia\s+[eé]\s+hoje|me\s+diz\s+as?\s+horas?"
    r"|^hora[s]?$|^que\s+dia\b|data\s+de\s+hoje|^data$|^hor[aá]rio$)"
)
CMD_CALCULAR = (
    r"^(?:calcula|calcule|calcular)\s+(.+)"
    r"|^quanto\s+(?:[eé]|d[aá])\s+(.+)"
    r"|^(?:soma|some|multiplica|multiplique|divide|divida|subtrai)\s+(.+)"
)
CMD_ALARME = (
    r"(?:alarme|timer|temporizador|me\s+avisa|me\s+lembra|me\s+chama|despertador)"
    r"\s*(?:em|de|daqui\s+a|para|pra)?\s*(\d+)\s*(minutos?|segundos?|horas?|min|seg|hrs?|h)\b"
)
CMD_CLIMA = (
    r"(?:^clima\b|clima\s+(?:em|de|no|na)\s+|previs[aã]o\s+do\s+tempo|como\s+est[aá]\s+o\s+tempo"
    r"|vai\s+chover|temperatura\s+(?:em|de|no|na|hoje)|^tempo\s+(?:em|de|no|na)\s+)"
)
CMD_CIDADE_CLIMA = r"(?:clima|tempo|temperatura|previs[aã]o)\s+(?:em|de|no|na)\s+(.+)"
CMD_DORMIR = r"^(?:dorme|durma|dormir|hiberna|hibernar|modo\s+soneca|vai\s+dormir|desliga\s+o\s+microfone)\b"
CMD_ACORDAR = r"^(?:acorda|acorde|acordar|volta|desperta|liga\s+o\s+microfone)\b"
CMD_HABILIDADE_EXTRA = r"^(?:executa|execute|roda|rode|usa\s+a|use\s+a|ativa|ative)\s+(?:a\s+)?(?:habilidade\s+)?(.+)"

UNIDADES_EM_SEGUNDOS = {
    "segundo": 1, "segundos": 1, "seg": 1,
    "minuto": 60, "minutos": 60, "min": 60,
    "hora": 3600, "horas": 3600, "hr": 3600, "hrs": 3600, "h": 3600,
}

NOMES_UNIDADES = {1: "segundos", 60: "minutos", 3600: "horas"}


def normalizar_texto(texto: str) -> str:
    """Minúsculas, espaços colapsados e pontuação final removida."""
    return re.sub(r"\s+", " ", texto.lower().strip()).rstrip(".!?")


def _primeiro_grupo(match: re.Match) -> str:
    """Devolve o primeiro grupo capturado não-vazio de um match com alternativas."""
    for grupo in match.groups():
        if grupo:
            return grupo.strip()
    return ""


def segundos_do_alarme(quantidade: str, unidade: str) -> tuple[int, str]:
    """Converte ("10", "minutos") em (600, "minutos"). Levanta ValueError se inválido."""
    fator = UNIDADES_EM_SEGUNDOS.get(unidade.lower())
    if fator is None:
        raise ValueError(f"unidade desconhecida: {unidade}")
    valor = int(quantidade)
    if valor <= 0:
        raise ValueError("o tempo precisa ser maior que zero")
    return valor * fator, NOMES_UNIDADES[fator]


def interpretar(texto: str, habilidades_extras: tuple[str, ...] = ()) -> Intencao:
    """Mapeia uma fala do usuário para uma `Intencao`.

    A ordem das regras é significativa: comandos específicos e ancorados vêm
    antes dos genéricos, e qualquer coisa que não casar vira CONVERSAR (IA).
    """
    txt = normalizar_texto(texto)
    if not txt:
        return Intencao(Acao.CONVERSAR, {"texto": texto})

    if re.match(CMD_SAUDACAO, txt):
        return Intencao(Acao.SAUDACAO)

    if re.match(CMD_DORMIR, txt):
        return Intencao(Acao.DORMIR)

    if re.match(CMD_ACORDAR, txt):
        return Intencao(Acao.ACORDAR)

    match = re.search(CMD_ALARME, txt)
    if match:
        try:
            segundos, unidade = segundos_do_alarme(match.group(1), match.group(2))
        except ValueError:
            return Intencao(Acao.CONVERSAR, {"texto": texto})
        return Intencao(Acao.ALARME, {"segundos": segundos, "quantidade": int(match.group(1)), "unidade": unidade})

    match = re.match(CMD_NOTA, txt)
    if match:
        return Intencao(Acao.ANOTAR, {"texto": match.group(1).strip()})

    if re.search(CMD_LER_NOTAS, txt):
        return Intencao(Acao.LER_NOTAS)

    match = re.match(CMD_CALCULAR, txt)
    if match:
        return Intencao(Acao.CALCULAR, {"expressao": _primeiro_grupo(match)})

    if re.search(CMD_VER_TELA, txt):
        return Intencao(Acao.VER_TELA)

    if re.search(CMD_LER_TELA, txt):
        return Intencao(Acao.LER_TELA)

    if re.search(CMD_CLIMA, txt):
        cidade_match = re.search(CMD_CIDADE_CLIMA, txt)
        cidade = cidade_match.group(1).strip() if cidade_match else ""
        return Intencao(Acao.CLIMA, {"cidade": cidade})

    if re.search(CMD_HORA, txt):
        return Intencao(Acao.HORA)

    if re.search(CMD_PIADA, txt):
        return Intencao(Acao.PIADA)

    if re.search(CMD_STATUS, txt):
        return Intencao(Acao.STATUS)

    match = re.match(CMD_VOLUME, txt)
    if match:
        return Intencao(Acao.VOLUME, {"nivel": int(match.group(1)) if match.group(1) else None})

    if re.search(CMD_HABILIDADES, txt):
        return Intencao(Acao.HABILIDADES)

    match = re.match(CMD_HABILIDADE_EXTRA, txt)
    if match and habilidades_extras:
        alvo = match.group(1).strip()
        for nome in habilidades_extras:
            if nome in alvo.replace(" ", ""):
                return Intencao(Acao.HABILIDADE_EXTRA, {"nome": nome})

    match = re.match(CMD_MELHORAR, txt)
    if match:
        return Intencao(Acao.MELHORAR, {"alvo": (match.group(1) or "geral").strip() or "geral"})

    match = re.match(CMD_PESQUISAR, txt)
    if match:
        return Intencao(Acao.PESQUISAR, {"query": match.group(1).strip()})

    match = re.match(CMD_ABRIR, txt)
    if match:
        return Intencao(Acao.ABRIR, {"alvo": match.group(1).strip()})

    match = re.match(CMD_FECHAR, txt)
    if match:
        return Intencao(Acao.FECHAR, {"alvo": match.group(1).strip()})

    return Intencao(Acao.CONVERSAR, {"texto": texto})
