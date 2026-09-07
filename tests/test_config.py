"""A configuração é lida na chamada, nunca na importação do módulo."""

import json

import pytest

from shimeji.config import (Config, MODELO_PADRAO, MODELO_VISAO_PADRAO, carregar_config,
                            ler_chave_do_arquivo, resolver_api_key)


def test_padroes_sem_argumentos():
    config = carregar_config([])
    assert config.modelo == MODELO_PADRAO
    assert config.modelo_visao == MODELO_VISAO_PADRAO
    assert config.sem_voz is False
    assert config.permitir_auto_modificacao is False


def test_importar_o_pacote_nao_consome_argv():
    """Regressão: o argparse rodava no import e quebrava pytest e qualquer import."""
    import subprocess
    import sys

    resultado = subprocess.run(
        [sys.executable, "-c", "import shimeji.app; print('ok')", "--flag-que-nao-existe"],
        capture_output=True, text=True,
    )
    assert resultado.returncode == 0 and "ok" in resultado.stdout


def test_flags_de_linha_de_comando():
    config = carregar_config(["--modelo", "m1", "--modelo-visao", "m2", "--sem-voz",
                              "--permitir-auto-modificacao"])
    assert (config.modelo, config.modelo_visao) == ("m1", "m2")
    assert config.sem_voz is True and config.permitir_auto_modificacao is True


def test_modo_demo_desliga_voz_e_microfone():
    config = carregar_config(["--demo"])
    assert config.demo is True and config.sem_voz is True and config.sem_microfone is True


def test_prioridade_da_chave_cli_sobre_ambiente(tmp_path):
    assert resolver_api_key("gsk_cli", {"GROQ_API_KEY": "gsk_env"}, str(tmp_path / "m.json")) == "gsk_cli"


def test_prioridade_do_ambiente_sobre_arquivo(tmp_path):
    arquivo = tmp_path / "m.json"
    arquivo.write_text(json.dumps({"groq_api_key": "gsk_arquivo"}), encoding="utf-8")
    assert resolver_api_key("", {"GROQ_API_KEY": "gsk_env"}, str(arquivo)) == "gsk_env"


def test_usa_o_arquivo_quando_nao_ha_cli_nem_ambiente(tmp_path):
    arquivo = tmp_path / "m.json"
    arquivo.write_text(json.dumps({"groq_api_key": "gsk_arquivo"}), encoding="utf-8")
    assert resolver_api_key("", {}, str(arquivo)) == "gsk_arquivo"


@pytest.mark.parametrize("conteudo", ["{isso não é json", "{}", '{"outra": 1}'])
def test_arquivo_sem_chave_valida_retorna_vazio(tmp_path, conteudo):
    arquivo = tmp_path / "m.json"
    arquivo.write_text(conteudo, encoding="utf-8")
    assert ler_chave_do_arquivo(str(arquivo)) == ""


def test_config_e_imutavel():
    with pytest.raises(Exception):
        Config().modelo = "outro"


def test_com_api_key_devolve_nova_instancia():
    original = Config(api_key="antiga")
    nova = original.com_api_key("nova")
    assert original.api_key == "antiga" and nova.api_key == "nova"
