"""A memória é o único estado que sobrevive ao fechamento: precisa ser confiável."""

import json
import threading

import pytest

from shimeji.memoria import Memoria, nivel_para_xp, xp_para_proximo_nivel


def test_valores_padrao_sem_arquivo(caminho_memoria):
    memoria = Memoria(caminho_memoria)
    assert memoria.nome_user == "mestre"
    assert memoria.xp == 0
    assert memoria.notas == []


def test_persiste_entre_instancias(caminho_memoria):
    primeira = Memoria(caminho_memoria)
    primeira.definir_nome("polar")
    primeira.ganhar_xp(120)
    primeira.adicionar_nota("revisar o PR")

    segunda = Memoria(caminho_memoria)
    assert segunda.nome_user == "polar"
    assert segunda.xp == 120
    assert segunda.notas[-1]["texto"] == "revisar o PR"


def test_arquivo_corrompido_nao_derruba_o_carregamento(caminho_memoria):
    with open(caminho_memoria, "w", encoding="utf-8") as arquivo:
        arquivo.write("{isso não é json")
    assert Memoria(caminho_memoria).nome_user == "mestre"


def test_preserva_a_chave_da_api_ao_salvar(caminho_memoria):
    """Regressão: um save comum não pode apagar a groq_api_key gravada antes."""
    with open(caminho_memoria, "w", encoding="utf-8") as arquivo:
        json.dump({"groq_api_key": "gsk_secreta", "nome": "polar"}, arquivo)

    memoria = Memoria(caminho_memoria)
    memoria.ganhar_xp(10)

    with open(caminho_memoria, encoding="utf-8") as arquivo:
        assert json.load(arquivo)["groq_api_key"] == "gsk_secreta"


def test_salvar_api_key_sem_perder_o_resto(caminho_memoria):
    memoria = Memoria(caminho_memoria)
    memoria.adicionar_nota("nota importante")
    memoria.salvar_api_key("gsk_nova")

    with open(caminho_memoria, encoding="utf-8") as arquivo:
        dados = json.load(arquivo)
    assert dados["groq_api_key"] == "gsk_nova"
    assert dados["notas"][0]["texto"] == "nota importante"


def test_escrita_e_atomica(caminho_memoria, tmp_path):
    """Nenhum arquivo temporário pode sobrar após o save."""
    memoria = Memoria(caminho_memoria)
    memoria.ganhar_xp(5)
    assert [p.name for p in tmp_path.iterdir()] == ["memoria.json"]


@pytest.mark.parametrize("xp, nivel", [
    (0, "Recém-nascida"), (49, "Recém-nascida"), (50, "Aprendiz"),
    (300, "Avançada"), (2000, "Transcendente"), (999999, "Transcendente"),
])
def test_niveis_por_xp(xp, nivel):
    assert nivel_para_xp(xp) == nivel


def test_xp_para_proximo_nivel():
    assert xp_para_proximo_nivel(0) == 50
    assert xp_para_proximo_nivel(2000) is None


def test_ganhar_xp_ignora_valores_nao_positivos(memoria):
    memoria.ganhar_xp(10)
    memoria.ganhar_xp(0)
    memoria.ganhar_xp(-5)
    assert memoria.xp == 10


def test_historico_respeita_o_limite(memoria):
    for indice in range(50):
        memoria.registrar_historico("user", f"mensagem {indice}")
    assert len(memoria.historico) == 20
    assert memoria.historico[-1]["texto"] == "mensagem 49"


def test_notas_respeitam_o_limite(memoria):
    for indice in range(80):
        memoria.adicionar_nota(f"nota {indice}")
    assert len(memoria.notas) == 50


def test_limpar_notas_retorna_quantas_apagou(memoria):
    memoria.adicionar_nota("a")
    memoria.adicionar_nota("b")
    assert memoria.limpar_notas() == 2
    assert memoria.notas == []


def test_habilidade_desbloqueada_nao_duplica(memoria):
    memoria.desbloquear_habilidade("pomodoro")
    memoria.desbloquear_habilidade("pomodoro")
    assert memoria.habilidades_desbloqueadas == ["pomodoro"]


def test_nome_vazio_e_ignorado(memoria):
    memoria.definir_nome("   ")
    assert memoria.nome_user == "mestre"


def test_escritas_concorrentes_nao_perdem_xp(caminho_memoria):
    """Quatro threads somando XP ao mesmo tempo devem somar exatamente 400."""
    memoria = Memoria(caminho_memoria)
    threads = [threading.Thread(target=lambda: [memoria.ganhar_xp(1) for _ in range(100)]) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert memoria.xp == 400
    assert Memoria(caminho_memoria).xp == 400
