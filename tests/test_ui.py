"""Testes da camada visual. Exigem sessão gráfica; são pulados sem ela."""

import threading
import tkinter as tk

import pytest

from tests.conftest import precisa_de_tela

pytestmark = precisa_de_tela


@pytest.fixture
def root():
    janela = tk.Tk()
    janela.withdraw()
    yield janela
    try:
        janela.destroy()
    except tk.TclError:
        pass


@pytest.fixture
def sprites(root):
    from shimeji.ui import carregar_sprites

    return carregar_sprites()


def test_carrega_todos_os_humores(sprites):
    from shimeji.config import HUMORES

    assert set(sprites) == set(HUMORES)


def test_sprite_de_reserva_quando_falta_arquivo(root, tmp_path):
    from shimeji.config import HUMORES
    from shimeji.ui import carregar_sprites

    assert set(carregar_sprites(str(tmp_path))) == set(HUMORES)


def test_recorte_de_transparencia():
    from PIL import Image

    from shimeji.ui import recortar_transparencia

    imagem = Image.new("RGBA", (100, 100), (0, 0, 0, 0))
    imagem.paste((255, 0, 0, 255), (40, 40, 60, 60))
    assert recortar_transparencia(imagem).size == (20, 20)


def test_recorte_de_imagem_totalmente_transparente():
    from PIL import Image

    from shimeji.ui import recortar_transparencia

    vazia = Image.new("RGBA", (10, 10), (0, 0, 0, 0))
    assert recortar_transparencia(vazia).size == (10, 10)


def test_despachante_roda_na_thread_da_interface(root):
    from shimeji.ui import Despachante

    despachante = Despachante(root, intervalo_ms=5)
    despachante.iniciar()
    threads_vistas = []

    def de_outra_thread():
        despachante.publicar(lambda: threads_vistas.append(threading.current_thread()))

    thread = threading.Thread(target=de_outra_thread)
    thread.start()
    thread.join()

    root.after(120, root.quit)
    root.mainloop()

    assert threads_vistas == [threading.main_thread()]


def test_despachante_isola_erro_de_tarefa(root):
    from shimeji.ui import Despachante

    despachante = Despachante(root, intervalo_ms=5)
    despachante.iniciar()
    executadas = []

    despachante.publicar(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    despachante.publicar(lambda: executadas.append("depois"))

    root.after(120, root.quit)
    root.mainloop()
    assert executadas == ["depois"]


def test_personagem_limita_a_posicao_na_tela(root, sprites):
    from shimeji.ui import Personagem

    personagem = Personagem(root, sprites)
    personagem.mover_para(-500, -500)
    assert personagem.posicao() == (0, 0)

    personagem.mover_para(99999, 99999)
    x, y = personagem.posicao()
    assert x <= personagem.largura_tela and y <= personagem.altura_tela


def test_personagem_troca_de_humor(root, sprites):
    from shimeji.ui import Personagem

    personagem = Personagem(root, sprites)
    personagem.definir_humor("feliz")
    assert personagem.humor == "feliz"

    personagem.definir_humor("humor_inexistente")
    assert personagem.humor == "feliz"


def test_posicao_aleatoria_fica_dentro_da_tela(root, sprites):
    from shimeji.ui import Personagem

    personagem = Personagem(root, sprites)
    for _ in range(30):
        x, y = personagem.posicao_aleatoria()
        assert 0 <= x <= personagem.largura_tela
        assert 0 <= y <= personagem.altura_tela


def test_animacao_volta_para_a_posicao_inicial(root, sprites):
    from shimeji.ui import Personagem

    personagem = Personagem(root, sprites)
    personagem.mover_para(300, 300)
    personagem.pular(vezes=1, duracao_ms=10)

    root.after(120, root.quit)
    root.mainloop()
    assert personagem.posicao() == (300, 300)


def test_tooltip_abre_e_fecha_uma_vez(root):
    from shimeji.ui import Tooltip

    tooltip = Tooltip(root)
    tooltip.mostrar("status", 10, 10)
    primeira = tooltip._janela
    tooltip.mostrar("outro", 20, 20)
    assert tooltip._janela is primeira

    tooltip.esconder()
    assert tooltip._janela is None
    tooltip.esconder()  # esconder duas vezes não pode explodir


def test_menu_com_separador(root):
    from shimeji.ui import construir_menu

    menu = construir_menu(root, [("A", lambda: None), ("", None), ("B", lambda: None)])
    assert menu.index("end") == 2


# --- janela de configurações ----------------------------------------------
@pytest.fixture
def config_win(root):
    from shimeji.ui import JanelaConfiguracoes

    salvos = []
    limpezas = []
    janela = JanelaConfiguracoes(
        root, nome_atual="polar", chave_atual="gsk_antiga", status="Nível: Aprendiz",
        ao_salvar=lambda nome, chave: salvos.append((nome, chave)),
        ao_limpar_notas=lambda: limpezas.append(True),
    )
    janela.salvos = salvos
    janela.limpezas = limpezas
    yield janela
    janela.fechar()


def test_campos_vem_preenchidos(config_win):
    assert config_win.entrada_nome.get() == "polar"
    assert config_win.entrada_chave.get() == "gsk_antiga"


def test_chave_comeca_oculta(config_win):
    assert config_win.entrada_chave.cget("show") == "•"


def test_alternar_mostrar_chave(config_win):
    config_win.mostrar_chave.set(True)
    config_win._alternar_chave()
    assert config_win.entrada_chave.cget("show") == ""

    config_win.mostrar_chave.set(False)
    config_win._alternar_chave()
    assert config_win.entrada_chave.cget("show") == "•"


def test_salvar_entrega_os_valores_e_fecha(config_win):
    config_win.entrada_nome.delete(0, "end")
    config_win.entrada_nome.insert(0, "  novo nome  ")
    config_win._salvar()
    assert config_win.salvos == [("novo nome", "gsk_antiga")]


def test_limpar_notas_chama_o_callback(config_win):
    config_win._limpar()
    assert config_win.limpezas == [True]


def test_fechar_duas_vezes_nao_explode(config_win):
    config_win.fechar()
    config_win.fechar()


def test_despachante_parado_ignora_novas_tarefas(root):
    from shimeji.ui import Despachante

    despachante = Despachante(root, intervalo_ms=5)
    despachante.iniciar()
    despachante.parar()

    executadas = []
    despachante.publicar(lambda: executadas.append(1))
    root.after(60, root.quit)
    root.mainloop()
    assert executadas == []


def test_publicar_depois_agenda_com_atraso(root, sprites):
    from shimeji.ui import Despachante, Personagem

    personagem = Personagem(root, sprites)
    despachante = Despachante(root, intervalo_ms=5)
    despachante.iniciar()

    despachante.publicar_depois(20, lambda: personagem.definir_humor("brava"))
    root.after(30, root.quit)
    root.mainloop()
    assert personagem.humor == "brava"


def test_tremer_volta_a_origem(root, sprites):
    from shimeji.ui import Personagem

    personagem = Personagem(root, sprites)
    personagem.mover_para(200, 200)
    personagem.tremer(vezes=4, duracao_ms=5)

    root.after(80, root.quit)
    root.mainloop()
    assert personagem.posicao() == (200, 200)


def test_sincronizar_posicao_le_a_janela(root, sprites):
    from shimeji.ui import Personagem

    personagem = Personagem(root, sprites)
    personagem.sincronizar_posicao()
    assert isinstance(personagem.posicao(), tuple)
