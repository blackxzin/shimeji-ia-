"""Testes de integração do orquestrador, com Tk real e IA/áudio dublados."""

import threading
import time
import tkinter as tk

import pytest

from shimeji.comandos import Acao
from shimeji.config import Config
from tests.conftest import precisa_de_tela

pytestmark = precisa_de_tela


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Uma Shimeji completa, isolada do disco do usuário e sem falar de verdade."""
    from shimeji import app as modulo_app

    monkeypatch.setattr(modulo_app, "ARQUIVO_MEMORIA", str(tmp_path / "memoria.json"))
    pasta_habilidades = tmp_path / "habilidades"
    pasta_habilidades.mkdir()
    monkeypatch.setattr(modulo_app, "PASTA_HABILIDADES", str(pasta_habilidades))

    root = tk.Tk()
    root.withdraw()
    aplicacao = modulo_app.ShimejiApp(Config(sem_voz=True, sem_microfone=True), root=root)

    falas = []
    aplicacao.locutor._eco = falas.append
    aplicacao.falas = falas

    yield aplicacao

    aplicacao.parar_evento.set()
    try:
        root.destroy()
    except tk.TclError:
        pass


def rodar_pendencias(app, ms=120):
    """Deixa o laço do Tk drenar o despachante."""
    app.root.after(ms, app.root.quit)
    app.root.mainloop()


# --- roteamento de comandos ------------------------------------------------
def test_calculo_responde_com_o_resultado(app):
    app.processar("calcula 25 vezes 4")
    assert any("100" in fala for fala in app.falas)


def test_calculo_invalido_nao_derruba_a_aplicacao(app):
    app.processar("calcula abacaxi mais laranja")
    assert any("não consegui calcular" in fala.lower() for fala in app.falas)


def test_anotar_e_ler_notas(app):
    app.processar("anota pra mim: revisar o PR")
    assert app.memoria.notas[-1]["texto"] == "revisar o pr"

    app.falas.clear()
    app.processar("minhas notas")
    assert any("revisar o pr" in fala for fala in app.falas)


def test_ler_notas_vazias(app):
    app.processar("minhas notas")
    assert any("ainda não tem notas" in fala for fala in app.falas)


def test_hora_menciona_o_relogio(app):
    app.processar("que horas são")
    assert any(":" in fala for fala in app.falas)


def test_piada_sempre_fala_algo(app):
    app.processar("conta uma piada")
    assert len(app.falas) == 1 and len(app.falas[0]) > 10


def test_saudacao_usa_o_nome_do_usuario(app):
    app.memoria.definir_nome("polar")
    app.processar("oi")
    assert any("polar" in fala for fala in app.falas)


def test_conversa_sem_chave_avisa_o_usuario(app):
    app.processar("me explica o que é um dataframe")
    rodar_pendencias(app)
    assert any("groq" in fala.lower() for fala in app.falas)


def test_comando_desconhecido_vira_conversa(app):
    assert app.processar("qual a melhor forma de tratar erro em go").acao is Acao.CONVERSAR


# --- ganho de XP -----------------------------------------------------------
def test_comandos_dao_xp(app):
    inicial = app.memoria.xp
    app.processar("conta uma piada")
    assert app.memoria.xp > inicial


def test_xp_persiste_no_disco(app):
    from shimeji.memoria import Memoria

    app.processar("calcula 1 + 1")
    assert Memoria(app.memoria.caminho).xp == app.memoria.xp


# --- sono ------------------------------------------------------------------
def test_dormir_e_acordar(app):
    app.processar("dorme")
    assert app.dormindo is True

    app.processar("acorda")
    assert app.dormindo is False


def test_alternar_sono_pelo_menu(app):
    app.alternar_sono()
    assert app.dormindo is True


# --- segurança -------------------------------------------------------------
def test_fechar_processo_protegido_e_recusado(app, monkeypatch):
    from shimeji import sistema

    class ProcessoFalso:
        info = {"pid": 1, "name": "systemd"}

        def terminate(self):
            raise AssertionError("nunca deveria encerrar um processo protegido")

    monkeypatch.setattr(sistema.psutil, "process_iter", lambda _: [ProcessoFalso()])
    app.processar("fecha o systemd")
    assert any("protegido" in fala for fala in app.falas)


def test_auto_melhoria_recusada_por_padrao(app):
    app._propor_melhoria("geral")
    assert any("desligada" in fala for fala in app.falas)


def test_melhoria_vinda_da_ia_e_rejeitada_sem_permissao(app):
    from shimeji.ia import RespostaIA

    app._aplicar_resposta(RespostaIA(texto="", melhoria=("nova", "self.x = 1")))
    assert any("rejeitei" in fala.lower() for fala in app.falas)


# --- IA dublada ------------------------------------------------------------
def test_conversa_com_ia_fala_a_resposta(app, cliente_falso):
    from shimeji.ia import CerebroIA

    app.cerebro = CerebroIA(modelo="m", cliente=cliente_falso(["[FELIZ] Bora refatorar isso!"]))
    app._conversar("como melhoro esse código?")
    assert "Bora refatorar isso!" in app.falas


def test_resposta_da_ia_entra_no_historico(app, cliente_falso):
    from shimeji.ia import CerebroIA

    app.cerebro = CerebroIA(modelo="m", cliente=cliente_falso(["Resposta da IA"]))
    app._conversar("pergunta")
    assert app.memoria.historico[-1] == {"papel": "assistant", "texto": "Resposta da IA"}


def test_falha_da_ia_nao_derruba_a_aplicacao(app):
    class ClienteQuebrado:
        chat = property(lambda self: self)

        @property
        def completions(self):
            return self

        def create(self, **_):
            raise RuntimeError("rede caiu")

    from shimeji.ia import CerebroIA

    app.cerebro = CerebroIA(cliente=ClienteQuebrado())
    app._conversar("oi")
    assert any("problema de conexão" in fala for fala in app.falas)


def test_aprende_habilidade_proposta_pela_ia(app):
    from shimeji.ia import RespostaIA

    app._aplicar_resposta(RespostaIA(texto="", habilidade=("saudar", "print('oi')")))
    assert "saudar" in app.habilidades
    assert "saudar" in app.memoria.habilidades_desbloqueadas


def test_habilidade_invalida_da_ia_e_recusada(app):
    from shimeji.ia import RespostaIA

    app._aplicar_resposta(RespostaIA(texto="", habilidade=("ruim", "print('sem fechar'")))
    assert "ruim" not in app.habilidades
    assert any("não consegui aprender" in fala.lower() for fala in app.falas)


# --- threads e desligamento ------------------------------------------------
def test_humor_pode_ser_trocado_de_outra_thread(app):
    app.despachante.iniciar()

    thread = threading.Thread(target=lambda: app.humor("brava", voltar_em_ms=None))
    thread.start()
    thread.join()
    rodar_pendencias(app)

    assert app.personagem.humor == "brava"


def test_humor_volta_ao_normal_sozinho(app):
    app.despachante.iniciar()
    app.humor("feliz", voltar_em_ms=30)
    rodar_pendencias(app, ms=200)
    assert app.personagem.humor == "normal"


def test_alarme_dispara_e_e_cancelado_no_encerramento(app):
    app.processar("me avisa em 1 segundo")
    assert len(app._alarmes) == 1

    app.encerrar()
    assert app._alarmes == []


def test_encerrar_e_idempotente(app):
    app.encerrar()
    app.encerrar()  # a segunda chamada não pode explodir
    assert app.parar_evento.is_set()


def test_encerrar_salva_a_memoria(app):
    from shimeji.memoria import Memoria

    app.memoria.definir_nome("polar")
    app.processar("calcula 2+2")
    app.encerrar()
    assert Memoria(app.memoria.caminho).nome_user == "polar"


def test_lacos_de_fundo_param_no_encerramento(app):
    app.parar_evento.set()
    assert app._dormir_interrompivel(0.01) is False


# --- interação com o mouse -------------------------------------------------
def test_clique_dá_xp_e_fala(app):
    inicial = app.memoria.xp
    app._ao_clicar(None)
    assert app.memoria.xp > inicial and len(app.falas) == 1


def test_carinho_aumenta_o_afeto(app):
    inicial = app.memoria.afeto
    app._ao_dar_carinho(None)
    assert app.memoria.afeto == inicial + 5


def test_resumo_de_status_tem_os_numeros(app):
    resumo = app.resumo_status()
    assert str(app.memoria.xp) in resumo and app.memoria.nivel in resumo


def test_salvar_configuracoes_troca_nome_e_chave(app):
    app._salvar_configuracoes("polar", "gsk_teste")
    assert app.memoria.nome_user == "polar"
    assert app.config.api_key == "gsk_teste"


def test_limpar_notas_pelo_menu(app):
    app.processar("anota teste")
    app.falas.clear()
    app._limpar_notas()
    assert app.memoria.notas == []
    assert any("apaguei" in fala.lower() for fala in app.falas)


# --- laços de fundo --------------------------------------------------------
def test_laco_de_piscar_para_no_encerramento(app, monkeypatch):
    import shimeji.app as modulo

    monkeypatch.setattr(modulo, "INTERVALO_PISCAR", (0, 0))
    monkeypatch.setattr(modulo, "DURACAO_PISCADA", 0.001)

    thread = threading.Thread(target=app._laco_piscar, daemon=True)
    thread.start()
    app.parar_evento.set()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_laco_de_movimento_publica_novo_lugar(app, monkeypatch):
    import shimeji.app as modulo

    monkeypatch.setattr(modulo, "INTERVALO_MOVIMENTO", 0.01)
    monkeypatch.setattr(modulo, "CHANCE_MOVIMENTO", 1.0)
    app.despachante.iniciar()

    thread = threading.Thread(target=app._laco_movimento, daemon=True)
    thread.start()
    rodar_pendencias(app, ms=150)
    app.parar_evento.set()
    thread.join(timeout=2)

    assert app.personagem.posicao() != (0, 0)


def test_monitor_alerta_uma_unica_vez_por_pico(app, monkeypatch):
    import shimeji.app as modulo
    from shimeji.sistema import StatusSistema

    monkeypatch.setattr(modulo, "INTERVALO_MONITOR", 0.01)
    critico = StatusSistema(cpu=5, ram_percentual=99, ram_usada_gb=16, ram_total_gb=16,
                            disco_percentual=10, disco_usado_gb=1, disco_total_gb=10,
                            bateria_percentual=None, bateria_minutos=None)
    monkeypatch.setattr(modulo.sistema, "coletar_status", lambda: critico)

    thread = threading.Thread(target=app._laco_monitor, daemon=True)
    thread.start()
    time.sleep(0.15)
    app.parar_evento.set()
    thread.join(timeout=2)

    alertas = [fala for fala in app.falas if "RAM" in fala]
    assert len(alertas) == 1


def test_monitor_sobrevive_a_falha_do_psutil(app, monkeypatch):
    import shimeji.app as modulo

    monkeypatch.setattr(modulo, "INTERVALO_MONITOR", 0.01)

    def explodir():
        raise RuntimeError("psutil caiu")

    monkeypatch.setattr(modulo.sistema, "coletar_status", explodir)

    thread = threading.Thread(target=app._laco_monitor, daemon=True)
    thread.start()
    time.sleep(0.08)
    app.parar_evento.set()
    thread.join(timeout=2)
    assert not thread.is_alive()


def test_dicas_de_saude_respeitam_o_intervalo(app, monkeypatch):
    import shimeji.app as modulo

    monkeypatch.setattr(modulo, "INTERVALO_TICK_LEMBRETE", 0.01)
    monkeypatch.setattr(modulo, "INTERVALO_DICA_SAUDE", 0.02)

    thread = threading.Thread(target=app._laco_lembretes, daemon=True)
    thread.start()
    time.sleep(0.15)
    app.parar_evento.set()
    thread.join(timeout=2)
    assert app.falas


# --- visão -----------------------------------------------------------------
def test_olhar_a_tela_sem_chave_avisa(app):
    app._analisar_tela()
    assert any("groq" in fala.lower() for fala in app.falas)


def test_olhar_a_tela_com_ia(app, monkeypatch, cliente_falso):
    from PIL import Image

    from shimeji import tela as modulo_tela
    from shimeji.ia import CerebroIA

    monkeypatch.setattr(modulo_tela, "capturar", lambda: Image.new("RGB", (40, 30), "blue"))
    app.cerebro = CerebroIA(modelo_visao="v", cliente=cliente_falso(["vejo um editor aberto"]))

    app._analisar_tela()
    assert "vejo um editor aberto" in app.falas


def test_falha_na_captura_e_comunicada(app, monkeypatch, cliente_falso):
    from shimeji import tela as modulo_tela
    from shimeji.ia import CerebroIA

    def explodir():
        raise modulo_tela.ErroDeCaptura("sem grim nem scrot")

    monkeypatch.setattr(modulo_tela, "capturar", explodir)
    app.cerebro = CerebroIA(cliente=cliente_falso())

    app._analisar_tela()
    assert any("sem grim nem scrot" in fala for fala in app.falas)


def test_ler_a_tela_usa_o_modelo_de_visao(app, monkeypatch, cliente_falso):
    from PIL import Image

    from shimeji import tela as modulo_tela
    from shimeji.ia import CerebroIA

    monkeypatch.setattr(modulo_tela, "capturar", lambda: Image.new("RGB", (20, 20)))
    cliente = cliente_falso(["texto extraído da tela"])
    app.cerebro = CerebroIA(modelo_visao="visao", cliente=cliente)

    app._ler_tela()
    assert "texto extraído da tela" in app.falas
    assert cliente.chamadas[0]["model"] == "visao"


# --- outros caminhos -------------------------------------------------------
def test_abrir_site_conhecido(app, monkeypatch):
    from shimeji import sistema

    abertas = []
    monkeypatch.setattr(sistema, "abrir_no_navegador", abertas.append)
    app.processar("abre o youtube")
    assert abertas == ["https://youtube.com"]


def test_pesquisar_abre_o_google(app, monkeypatch):
    from shimeji import sistema

    abertas = []
    monkeypatch.setattr(sistema, "abrir_no_navegador", abertas.append)
    app.processar("pesquisa clean architecture")
    assert "google.com/search" in abertas[0]


def test_clima_abre_o_wttr(app, monkeypatch):
    from shimeji import sistema

    abertas = []
    monkeypatch.setattr(sistema, "abrir_no_navegador", abertas.append)
    app.processar("clima em Curitiba")
    assert abertas[0].startswith("https://wttr.in/curitiba")


def test_volume_relata_o_valor_aplicado(app, monkeypatch):
    from shimeji import sistema

    monkeypatch.setattr(sistema, "_volume_unix", lambda _: None)
    monkeypatch.setattr(sistema, "_volume_windows", lambda _: None)
    app.processar("volume 35")
    assert any("35" in fala for fala in app.falas)


def test_volume_sem_controlador_avisa(app, monkeypatch):
    from shimeji import sistema

    def explodir(_):
        raise sistema.ErroDeSistema("nenhum controlador de áudio")

    monkeypatch.setattr(sistema, "_volume_unix", explodir)
    monkeypatch.setattr(sistema, "_volume_windows", explodir)
    app.processar("volume 35")
    assert any("não consegui mudar o volume" in fala.lower() for fala in app.falas)


def test_listar_habilidades_sem_extras(app):
    app.processar("o que você sabe fazer")
    assert any("ainda não aprendi habilidades extras" in fala.lower() for fala in app.falas)


def test_listar_habilidades_com_extras(app):
    app.habilidades.salvar_nova("teste", "pass")
    app.falas.clear()
    app.processar("o que você sabe fazer")
    assert any("teste" in fala for fala in app.falas)


def test_executar_habilidade_extra(app):
    app.habilidades.salvar_nova("motivar", "pass")
    app.falas.clear()
    intencao = app.processar("executa motivar")
    assert intencao.acao is Acao.HABILIDADE_EXTRA
    assert any("motivar" in fala for fala in app.falas)


def test_habilidade_que_falha_e_comunicada(app, monkeypatch):
    from shimeji.habilidades import ErroDeHabilidade

    def explodir(nome, instancia=None):
        raise ErroDeHabilidade("boom")

    monkeypatch.setattr(app.habilidades, "executar", explodir)
    app._executar_habilidade_segura("qualquer")
    assert any("boom" in fala for fala in app.falas)


def test_status_do_sistema_e_falado(app):
    app._dizer_status()
    assert any("CPU" in fala for fala in app.falas)


def test_saudacao_do_horario_muda_com_a_hora(app, monkeypatch):
    import datetime as dt

    class DataFalsa(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 9, 6, 8, 0)

    monkeypatch.setattr("shimeji.app.datetime.datetime", DataFalsa)
    assert app.saudacao_do_horario().startswith("Bom dia")


def test_erro_inesperado_no_manipulador_nao_derruba(app, monkeypatch):
    def explodir(_):
        raise RuntimeError("falha interna")

    monkeypatch.setattr(app, "_contar_piada", lambda: explodir(None))
    app.processar("conta uma piada")
    assert any("algo deu errado" in fala.lower() for fala in app.falas)


def test_roteiro_de_demo_so_tem_comandos_offline(app):
    from shimeji.comandos import interpretar
    from shimeji.textos import roteiro_demo

    for _, comando in roteiro_demo():
        assert interpretar(comando, ("motivacao",)).acao is not Acao.CONVERSAR


def test_passo_de_demo_sem_chave_nao_chama_a_ia(app):
    app._passo_demo("me explica recursão")
    assert any("modo demo" in fala for fala in app.falas)


def test_melhoria_aplicada_quando_permitida(app, monkeypatch, tmp_path):
    from shimeji import evolucao
    from shimeji.config import Config
    from shimeji.ia import RespostaIA

    alvo = tmp_path / "alvo.py"
    alvo.write_text("class C:\n    pass\n", encoding="utf-8")
    monkeypatch.setattr(evolucao, "ARQUIVO_MELHORIAS", str(tmp_path / "log.jsonl"))
    monkeypatch.setattr(evolucao, "aplicar_melhoria",
                        lambda caminho, nome, cmd, permitido: "nova_funcao")

    app.config = Config(sem_voz=True, permitir_auto_modificacao=True)
    app._aplicar_resposta(RespostaIA(texto="", melhoria=("nova", "self.x = 1")))
    assert any("nova_funcao" in fala for fala in app.falas)


def test_propor_melhoria_com_permissao_consulta_a_ia(app, monkeypatch, cliente_falso):
    from shimeji.config import Config
    from shimeji.ia import CerebroIA

    app.config = Config(sem_voz=True, permitir_auto_modificacao=True)
    cliente = cliente_falso(["[MELHORAR] cache | self.cache = {}"])
    app.cerebro = CerebroIA(modelo="m", cliente=cliente)

    app._propor_melhoria("desempenho")
    assert cliente.chamadas, "a IA deveria ter sido consultada"


def test_prompt_reflete_a_permissao_de_auto_modificacao(app):
    from shimeji.config import Config

    assert "desligada" in app._prompt_sistema()
    app.config = Config(permitir_auto_modificacao=True)
    assert "[MELHORAR]" in app._prompt_sistema()


def test_menu_de_contexto_abre_e_fecha(app):
    class EventoFalso:
        x_root = 10
        y_root = 10

    app._abrir_menu(EventoFalso())


def test_arrastar_move_o_personagem(app):
    class EventoFalso:
        x_root = 400
        y_root = 300

    app._ao_arrastar(EventoFalso())
    x, y = app.personagem.posicao()
    assert (x, y) == app.personagem.limitar(400 - 90, 300 - 90)


def test_tooltip_aparece_ao_passar_o_mouse(app):
    app._ao_entrar_mouse(None)
    assert app.tooltip._janela is not None
    app.tooltip.esconder()


def test_abrir_configuracoes(app):
    app.abrir_configuracoes()  # não pode explodir


# --- contrato público usado pelas habilidades ------------------------------
def test_api_de_plugin_ganhar_xp_recebe_numero(app):
    inicial = app.memoria.xp
    nivel = app.ganhar_xp(7)
    assert app.memoria.xp == inicial + 7
    assert nivel == app.memoria.nivel


def test_api_de_plugin_set_mood(app):
    app.despachante.iniciar()
    app.set_mood("brava", voltar_em_ms=None)
    rodar_pendencias(app)
    assert app.personagem.humor == "brava"


def test_api_de_plugin_pular_e_tremer(app):
    app.despachante.iniciar()
    app.personagem.mover_para(250, 250)
    app.pular()
    app.tremer(vezes=2)
    rodar_pendencias(app, ms=250)
    assert app.personagem.posicao() == (250, 250)


def test_api_de_plugin_anotar(app):
    app.anotar("nota vinda de um plugin")
    assert app.memoria.notas[-1]["texto"] == "nota vinda de um plugin"


def test_habilidades_incluidas_usam_a_api_publica(app, tmp_path):
    """As habilidades que vêm no repositório precisam rodar contra a API atual."""
    import os
    import shutil

    from shimeji.habilidades import RegistroDeHabilidades

    origem = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "habilidades")
    destino = tmp_path / "hab"
    shutil.copytree(origem, destino, ignore=shutil.ignore_patterns("__pycache__"))

    registro = RegistroDeHabilidades(str(destino))
    carregadas = registro.carregar_tudo()
    assert carregadas, "nenhuma habilidade foi carregada"

    app.despachante.iniciar()
    for nome in carregadas:
        registro.executar(nome, app)  # não pode levantar
    rodar_pendencias(app)
