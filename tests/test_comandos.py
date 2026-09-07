"""O interpretador precisa acertar o comando e, principalmente, não inventar um."""

import pytest

from shimeji.comandos import Acao, interpretar, normalizar_texto, segundos_do_alarme


@pytest.mark.parametrize("fala, acao", [
    ("oi shimeji", Acao.SAUDACAO),
    ("Bom dia!", Acao.SAUDACAO),
    ("abre o youtube", Acao.ABRIR),
    ("pesquisa python asyncio", Acao.PESQUISAR),
    ("fecha o firefox", Acao.FECHAR),
    ("que horas são", Acao.HORA),
    ("alarme em 10 minutos", Acao.ALARME),
    ("anota comprar pão", Acao.ANOTAR),
    ("minhas notas", Acao.LER_NOTAS),
    ("conta uma piada", Acao.PIADA),
    ("calcula 2 + 2", Acao.CALCULAR),
    ("clima em São Paulo", Acao.CLIMA),
    ("olha a tela", Acao.VER_TELA),
    ("lê a tela", Acao.LER_TELA),
    ("status do sistema", Acao.STATUS),
    ("volume 50", Acao.VOLUME),
    ("o que você sabe fazer", Acao.HABILIDADES),
    ("dorme", Acao.DORMIR),
    ("acorda", Acao.ACORDAR),
])
def test_reconhece_comandos_nativos(fala, acao):
    assert interpretar(fala).acao is acao


@pytest.mark.parametrize("fala", [
    "me explica o que é um dataframe",
    "quanto tempo leva pra compilar isso",
    "como funciona a memória do python",
    "me fala sobre o sistema operacional linux",
    "vou abrir um pull request amanhã",
    "qual a melhor forma de tratar erro em go",
    "essa API tem rate limit de quanto",
])
def test_conversa_normal_nao_dispara_comando(fala):
    """Regressão: 'dataframe' virava data, 'tempo' virava clima, 'memória' virava status."""
    assert interpretar(fala).acao is Acao.CONVERSAR


def test_alarme_extrai_tempo_em_segundos():
    intencao = interpretar("me avisa em 2 horas")
    assert intencao.acao is Acao.ALARME
    assert intencao["segundos"] == 7200
    assert intencao["unidade"] == "horas"


@pytest.mark.parametrize("quantidade, unidade, segundos", [
    ("30", "segundos", 30), ("5", "min", 300), ("1", "hora", 3600), ("90", "minutos", 5400),
])
def test_conversao_de_unidades(quantidade, unidade, segundos):
    assert segundos_do_alarme(quantidade, unidade)[0] == segundos


@pytest.mark.parametrize("quantidade, unidade", [("0", "minutos"), ("-5", "min"), ("10", "luas")])
def test_alarme_invalido_e_rejeitado(quantidade, unidade):
    with pytest.raises(ValueError):
        segundos_do_alarme(quantidade, unidade)


@pytest.mark.parametrize("fala, esperado", [
    ("anota pra mim: comprar pão", "comprar pão"),
    ("anota aí revisar o PR", "revisar o pr"),
    ("anota: subir o deploy", "subir o deploy"),
    ("lembra que tenho reunião", "tenho reunião"),
])
def test_extrai_o_texto_da_nota(fala, esperado):
    intencao = interpretar(fala)
    assert intencao.acao is Acao.ANOTAR
    assert intencao["texto"] == esperado


def test_clima_extrai_a_cidade():
    assert interpretar("clima em Belo Horizonte")["cidade"] == "belo horizonte"


def test_clima_sem_cidade_fica_vazio():
    assert interpretar("vai chover hoje")["cidade"] == ""


@pytest.mark.parametrize("fala, nivel", [("volume 70", 70), ("volume para 20", 20), ("volume", None)])
def test_volume_extrai_o_nivel(fala, nivel):
    assert interpretar(fala)["nivel"] == nivel


def test_habilidade_extra_so_casa_com_habilidade_existente():
    assert interpretar("executa pomodoro", ("pomodoro",)).acao is Acao.HABILIDADE_EXTRA
    assert interpretar("executa pomodoro", ()).acao is not Acao.HABILIDADE_EXTRA


def test_pesquisa_tem_prioridade_sobre_abrir():
    """'pesquisa X' e 'abre X' são ambos verbos iniciais: a ordem precisa ser estável."""
    assert interpretar("pesquisa como abrir um arquivo em python").acao is Acao.PESQUISAR


def test_texto_vazio_vira_conversa():
    assert interpretar("   ").acao is Acao.CONVERSAR


@pytest.mark.parametrize("entrada, esperado", [
    ("  OI   Shimeji!! ", "oi shimeji"),
    ("Que Horas São?", "que horas são"),
])
def test_normalizacao_do_texto(entrada, esperado):
    assert normalizar_texto(entrada) == esperado


def test_intencao_expoe_parametros_por_indice():
    assert interpretar("abre github")["alvo"] == "github"
