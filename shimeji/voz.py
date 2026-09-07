"""Fala (TTS) e escuta (STT) em threads dedicadas.

O TTS roda numa única thread consumidora de fila: `pyttsx3` não é reentrante e a
versão anterior chamava `runAndWait()` de várias threads, o que travava o motor.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Callable

TIMEOUT_FILA = 0.5
AJUSTE_VELOCIDADE = -20
LIMITE_FRASE = 8
DURACAO_CALIBRACAO = 1.0
ESPERA_APOS_ERRO_REDE = 3
ESPERA_SEM_MICROFONE = 5
IDIOMA_PADRAO = "pt-BR"


class Locutor:
    """Fila de fala consumida por uma única thread."""

    def __init__(self, ativo: bool = True, eco: Callable[[str], None] | None = None):
        self.ativo = ativo
        self._eco = eco or (lambda texto: print(f"Shimeji: {texto}"))
        self._fila: queue.Queue[str | None] = queue.Queue()
        self._parar = threading.Event()
        self._thread: threading.Thread | None = None
        self._motor = None

    def iniciar(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._consumir, name="tts", daemon=True)
        self._thread.start()

    def falar(self, texto: str) -> None:
        """Enfileira o texto. Sempre ecoa no terminal, mesmo com a voz desligada."""
        texto = (texto or "").strip()
        if not texto:
            return
        self._eco(texto)
        if self.ativo and not self._parar.is_set():
            self._fila.put(texto)

    def parar(self) -> None:
        self._parar.set()
        self._fila.put(None)

    @property
    def pendentes(self) -> int:
        return self._fila.qsize()

    def _criar_motor(self):
        import pyttsx3

        motor = pyttsx3.init()
        motor.setProperty("rate", motor.getProperty("rate") + AJUSTE_VELOCIDADE)
        return motor

    def _consumir(self) -> None:
        while not self._parar.is_set():
            try:
                texto = self._fila.get(timeout=TIMEOUT_FILA)
            except queue.Empty:
                continue
            if texto is None:
                break
            try:
                if self._motor is None:
                    self._motor = self._criar_motor()
                self._motor.say(texto)
                self._motor.runAndWait()
            except Exception as erro:
                print(f"[voz] falha no TTS: {erro}")
                self._motor = None  # força recriação na próxima frase
            finally:
                self._fila.task_done()


class Ouvinte:
    """Escuta o microfone e entrega as transcrições ao callback informado."""

    def __init__(
        self,
        ao_ouvir: Callable[[str], None],
        parar_evento: threading.Event,
        esta_dormindo: Callable[[], bool] = lambda: False,
        idioma: str = IDIOMA_PADRAO,
    ):
        self.ao_ouvir = ao_ouvir
        self.parar_evento = parar_evento
        self.esta_dormindo = esta_dormindo
        self.idioma = idioma
        self.microfone_disponivel = True

    def iniciar(self) -> threading.Thread:
        thread = threading.Thread(target=self.rodar, name="stt", daemon=True)
        thread.start()
        return thread

    def rodar(self) -> None:
        try:
            import speech_recognition as sr
        except ImportError as erro:
            print(f"[voz] reconhecimento de fala indisponível: {erro}")
            self.microfone_disponivel = False
            return

        reconhecedor = sr.Recognizer()
        calibrado = False

        while not self.parar_evento.is_set():
            if self.esta_dormindo():
                time.sleep(1)
                continue
            try:
                with sr.Microphone() as fonte:
                    if not calibrado:
                        reconhecedor.adjust_for_ambient_noise(fonte, duration=DURACAO_CALIBRACAO)
                        calibrado = True
                    audio = reconhecedor.listen(fonte, phrase_time_limit=LIMITE_FRASE)
                texto = reconhecedor.recognize_google(audio, language=self.idioma)
            except sr.UnknownValueError:
                continue
            except sr.RequestError:
                time.sleep(ESPERA_APOS_ERRO_REDE)
                continue
            except (OSError, AttributeError):
                calibrado = False
                self.microfone_disponivel = False
                if not self.parar_evento.is_set():
                    print("[voz] microfone indisponível; tentando de novo em alguns segundos")
                time.sleep(ESPERA_SEM_MICROFONE)
                continue
            except Exception as erro:
                calibrado = False
                if not self.parar_evento.is_set():
                    print(f"[voz] erro no microfone: {erro}")
                time.sleep(2)
                continue

            self.microfone_disponivel = True
            if texto and not self.parar_evento.is_set():
                self.ao_ouvir(texto)
