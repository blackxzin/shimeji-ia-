"""Voz: o TTS não é reentrante, então a fila e a thread única precisam de teste."""

import threading
import time

import pytest

from shimeji.voz import Locutor, Ouvinte


class MotorFalso:
    """Dublê do pyttsx3: registra o que foi falado e conta as inicializações."""

    criados = 0

    def __init__(self, falhar_em=()):
        MotorFalso.criados += 1
        self.ditos = []
        self.falhar_em = set(falhar_em)
        self.propriedades = {"rate": 200}

    def getProperty(self, nome):
        return self.propriedades[nome]

    def setProperty(self, nome, valor):
        self.propriedades[nome] = valor

    def say(self, texto):
        if texto in self.falhar_em:
            raise RuntimeError("motor travou")
        self.ditos.append(texto)

    def runAndWait(self):
        pass


@pytest.fixture(autouse=True)
def zerar_contador():
    MotorFalso.criados = 0


def aguardar(condicao, limite=3.0):
    inicio = time.time()
    while time.time() - inicio < limite:
        if condicao():
            return True
        time.sleep(0.01)
    return False


def test_eco_sempre_acontece_mesmo_com_voz_desligada():
    falas = []
    locutor = Locutor(ativo=False, eco=falas.append)
    locutor.falar("oi")
    assert falas == ["oi"] and locutor.pendentes == 0


@pytest.mark.parametrize("vazio", ["", "   ", "\n"])
def test_texto_vazio_e_ignorado(vazio):
    falas = []
    Locutor(ativo=False, eco=falas.append).falar(vazio)
    assert falas == []


def test_fila_e_consumida_na_ordem(monkeypatch):
    motor = MotorFalso()
    locutor = Locutor(ativo=True, eco=lambda _: None)
    monkeypatch.setattr(locutor, "_criar_motor", lambda: motor)
    locutor.iniciar()

    for frase in ("primeira", "segunda", "terceira"):
        locutor.falar(frase)

    assert aguardar(lambda: len(motor.ditos) == 3)
    assert motor.ditos == ["primeira", "segunda", "terceira"]
    locutor.parar()


def test_usa_uma_unica_instancia_do_motor(monkeypatch):
    """Regressão: o motor era recriado a cada fala e travava o pyttsx3."""
    locutor = Locutor(ativo=True, eco=lambda _: None)
    monkeypatch.setattr(locutor, "_criar_motor", MotorFalso)
    locutor.iniciar()

    for indice in range(5):
        locutor.falar(f"frase {indice}")

    assert aguardar(lambda: MotorFalso.criados >= 1)
    time.sleep(0.2)
    assert MotorFalso.criados == 1
    locutor.parar()


def test_motor_e_recriado_apos_falha(monkeypatch):
    locutor = Locutor(ativo=True, eco=lambda _: None)
    monkeypatch.setattr(locutor, "_criar_motor", lambda: MotorFalso(falhar_em={"quebra"}))
    locutor.iniciar()

    locutor.falar("quebra")
    locutor.falar("depois")

    assert aguardar(lambda: MotorFalso.criados >= 2)
    locutor.parar()


def test_parar_encerra_a_thread(monkeypatch):
    locutor = Locutor(ativo=True, eco=lambda _: None)
    monkeypatch.setattr(locutor, "_criar_motor", MotorFalso)
    locutor.iniciar()
    locutor.parar()

    assert aguardar(lambda: not locutor._thread.is_alive())


def test_falar_apos_parar_nao_enfileira(monkeypatch):
    locutor = Locutor(ativo=True, eco=lambda _: None)
    monkeypatch.setattr(locutor, "_criar_motor", MotorFalso)
    locutor.parar()
    pendentes_antes = locutor.pendentes
    locutor.falar("tarde demais")
    assert locutor.pendentes == pendentes_antes


def test_iniciar_duas_vezes_cria_uma_thread(monkeypatch):
    locutor = Locutor(ativo=True, eco=lambda _: None)
    monkeypatch.setattr(locutor, "_criar_motor", MotorFalso)
    locutor.iniciar()
    primeira = locutor._thread
    locutor.iniciar()
    assert locutor._thread is primeira
    locutor.parar()


# --- Ouvinte ---------------------------------------------------------------
class ReconhecimentoFalso:
    """Dublê mínimo do módulo speech_recognition."""

    class UnknownValueError(Exception):
        pass

    class RequestError(Exception):
        pass

    class Microphone:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    def __init__(self, transcricoes):
        self.transcricoes = list(transcricoes)

    def Recognizer(self):
        modulo = self

        class Reconhecedor:
            def adjust_for_ambient_noise(self, fonte, duration=1.0):
                pass

            def listen(self, fonte, phrase_time_limit=None):
                return "audio"

            def recognize_google(self, audio, language=None):
                if not modulo.transcricoes:
                    raise modulo.UnknownValueError()
                valor = modulo.transcricoes.pop(0)
                if isinstance(valor, Exception):
                    raise valor
                return valor

        return Reconhecedor()


def instalar_reconhecimento_falso(monkeypatch, transcricoes):
    import sys

    falso = ReconhecimentoFalso(transcricoes)
    monkeypatch.setitem(sys.modules, "speech_recognition", falso)
    return falso


def test_ouvinte_entrega_a_transcricao(monkeypatch):
    instalar_reconhecimento_falso(monkeypatch, ["abre o youtube"])
    ouvidas = []
    parar = threading.Event()

    def registrar(texto):
        ouvidas.append(texto)
        parar.set()

    Ouvinte(registrar, parar).rodar()
    assert ouvidas == ["abre o youtube"]


def test_ouvinte_pula_audio_incompreensivel(monkeypatch):
    falso = instalar_reconhecimento_falso(monkeypatch, [])
    ouvidas = []
    parar = threading.Event()

    def ouvir():
        Ouvinte(ouvidas.append, parar).rodar()

    thread = threading.Thread(target=ouvir, daemon=True)
    thread.start()
    time.sleep(0.05)
    parar.set()
    thread.join(timeout=2)
    assert ouvidas == []


def test_ouvinte_ignora_o_microfone_enquanto_dorme(monkeypatch):
    instalar_reconhecimento_falso(monkeypatch, ["não deveria ouvir"])
    ouvidas = []
    parar = threading.Event()

    thread = threading.Thread(
        target=lambda: Ouvinte(ouvidas.append, parar, esta_dormindo=lambda: True).rodar(),
        daemon=True,
    )
    thread.start()
    time.sleep(0.1)
    parar.set()
    thread.join(timeout=2)
    assert ouvidas == []


def test_ouvinte_sem_biblioteca_desiste_sem_travar(monkeypatch):
    import builtins

    original = builtins.__import__

    def importar(nome, *args, **kwargs):
        if nome == "speech_recognition":
            raise ImportError("sem PyAudio")
        return original(nome, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", importar)
    ouvinte = Ouvinte(lambda _: None, threading.Event())
    ouvinte.rodar()
    assert ouvinte.microfone_disponivel is False
