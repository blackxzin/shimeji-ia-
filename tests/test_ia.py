"""O parsing das respostas do modelo é onde texto vira comportamento."""

import pytest

from shimeji.ia import CerebroIA, interpretar_resposta, limpar_tags, montar_prompt_sistema


@pytest.mark.parametrize("bruto, humor", [
    ("[FELIZ] tudo certo", "feliz"),
    ("[BRAVA] isso está errado", "brava"),
    ("[TRISTE] que pena", "triste"),
    ("sem tag nenhuma", None),
])
def test_extrai_o_humor(bruto, humor):
    assert interpretar_resposta(bruto).humor == humor


def test_remove_as_tags_do_texto_falado():
    assert interpretar_resposta("[FELIZ] Oi! Tudo bem?").texto == "Oi! Tudo bem?"


def test_limpar_tags_normaliza_espacos():
    assert limpar_tags("[FELIZ]   muito    espaço  ") == "muito espaço"


def test_extrai_habilidade_a_aprender():
    resposta = interpretar_resposta("[APRENDER] saudar | print('oi'); print('tchau')")
    assert resposta.habilidade == ("saudar", "print('oi'); print('tchau')")


def test_extrai_melhoria_proposta():
    resposta = interpretar_resposta("[MELHORAR] cache_notas | self.cache = {}")
    assert resposta.melhoria == ("cache_notas", "self.cache = {}")


@pytest.mark.parametrize("bruto", [
    "[APRENDER] sem barra vertical",
    "[APRENDER] | corpo sem nome",
    "[APRENDER] nome_sem_corpo |   ",
])
def test_comando_malformado_nao_vira_habilidade(bruto):
    assert interpretar_resposta(bruto).habilidade is None


def test_resposta_vazia_nao_quebra():
    resposta = interpretar_resposta("")
    assert resposta.texto == "" and resposta.humor is None


def test_prompt_inclui_estado_e_notas():
    prompt = montar_prompt_sistema("polar", "Expert", 600, 25, [{"data": "hoje", "texto": "revisar PR"}], True)
    assert "polar" in prompt and "Expert" in prompt and "revisar PR" in prompt
    assert "[MELHORAR]" in prompt


def test_prompt_desencoraja_auto_modificacao_quando_desligada():
    prompt = montar_prompt_sistema("polar", "Aprendiz", 10, 5, [], False)
    assert "desligada" in prompt
    assert "[MELHORAR] nome_da_funcao" not in prompt


def test_cerebro_sem_chave_fica_indisponivel():
    assert CerebroIA().disponivel is False


def test_cerebro_sem_chave_nao_faz_chamada():
    with pytest.raises(RuntimeError, match="não configurado"):
        CerebroIA().conversar("prompt", [], "oi")


def test_conversa_monta_mensagens_com_historico(cliente_falso):
    cliente = cliente_falso(["[FELIZ] beleza!"])
    cerebro = CerebroIA(modelo="modelo-teste", cliente=cliente)
    historico = [{"papel": "user", "texto": "oi"}, {"papel": "assistant", "texto": "olá"}]

    resposta = cerebro.conversar("prompt de sistema", historico, "e aí?")

    mensagens = cliente.chamadas[0]["messages"]
    assert mensagens[0]["role"] == "system"
    assert [m["role"] for m in mensagens[1:]] == ["user", "assistant", "user"]
    assert mensagens[-1]["content"] == "e aí?"
    assert resposta.texto == "beleza!" and resposta.humor == "feliz"


def test_papel_desconhecido_no_historico_vira_user(cliente_falso):
    cliente = cliente_falso()
    CerebroIA(cliente=cliente).conversar("p", [{"papel": "robô", "texto": "x"}], "oi")
    assert cliente.chamadas[0]["messages"][1]["role"] == "user"


def test_historico_e_truncado(cliente_falso):
    cliente = cliente_falso()
    historico = [{"papel": "user", "texto": str(i)} for i in range(50)]
    CerebroIA(cliente=cliente).conversar("p", historico, "oi")
    assert len(cliente.chamadas[0]["messages"]) <= 8


def test_visao_envia_a_imagem_em_base64(cliente_falso):
    cliente = cliente_falso(["vejo um editor de código"])
    cerebro = CerebroIA(modelo_visao="visao-teste", cliente=cliente)

    assert cerebro.descrever_tela("QUJD") == "vejo um editor de código"
    conteudo = cliente.chamadas[0]["messages"][0]["content"]
    assert conteudo[1]["image_url"]["url"] == "data:image/png;base64,QUJD"
    assert cliente.chamadas[0]["model"] == "visao-teste"


def test_trocar_chave_para_vazio_desliga_o_cerebro(cliente_falso):
    cerebro = CerebroIA(cliente=cliente_falso())
    assert cerebro.disponivel is True
    cerebro.trocar_chave("")
    assert cerebro.disponivel is False


def test_codificar_imagem_gera_base64():
    from PIL import Image

    from shimeji.ia import codificar_imagem

    base64_png = codificar_imagem(Image.new("RGB", (3000, 2000), "red"))
    assert isinstance(base64_png, str) and len(base64_png) > 50
