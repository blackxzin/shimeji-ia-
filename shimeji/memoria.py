"""Persistência da memória da Shimeji (perfil, XP, notas, histórico).

Escritas são atômicas (arquivo temporário + `os.replace`) e serializadas por um
lock, para que um desligamento no meio de um save não deixe um JSON corrompido.
"""

from __future__ import annotations

import datetime
import json
import os
import tempfile
import threading

from .config import ARQUIVO_MEMORIA, MAX_HISTORICO, MAX_NOTAS, MAX_TAMANHO_NOTA

NIVEIS = (
    (0, "Recém-nascida"),
    (50, "Aprendiz"),
    (150, "Intermediária"),
    (300, "Avançada"),
    (500, "Expert"),
    (1000, "Mestra"),
    (2000, "Transcendente"),
)

CAMPOS_PRESERVADOS = ("groq_api_key",)


def nivel_para_xp(xp: int) -> str:
    """Traduz XP acumulado no nome do nível correspondente."""
    nome = NIVEIS[0][1]
    for xp_necessario, rotulo in NIVEIS:
        if xp >= xp_necessario:
            nome = rotulo
    return nome


def xp_para_proximo_nivel(xp: int) -> int | None:
    """Quanto falta para o próximo nível, ou None se já está no topo."""
    for xp_necessario, _ in NIVEIS:
        if xp < xp_necessario:
            return xp_necessario - xp
    return None


class Memoria:
    """Estado persistente da Shimeji. Seguro para uso entre threads."""

    def __init__(self, caminho: str = ARQUIVO_MEMORIA, salvar_automaticamente: bool = True):
        self.caminho = caminho
        self._salvar_automaticamente = salvar_automaticamente
        self._lock = threading.RLock()
        self.nome_user = "mestre"
        self.afeto = 15
        self.xp = 0
        self.habilidades_desbloqueadas: list[str] = []
        self.preferencias: list[str] = []
        self.historico: list[dict] = []
        self.notas: list[dict] = []
        self.carregar()

    # --- leitura ---------------------------------------------------------
    def _ler_arquivo(self) -> dict:
        try:
            with open(self.caminho, "r", encoding="utf-8") as arquivo:
                dados = json.load(arquivo)
            return dados if isinstance(dados, dict) else {}
        except (json.JSONDecodeError, FileNotFoundError, OSError):
            return {}

    def carregar(self) -> None:
        dados = self._ler_arquivo()
        with self._lock:
            self.nome_user = str(dados.get("nome") or "mestre")
            self.afeto = int(dados.get("afeto", 15) or 0)
            self.xp = int(dados.get("xp", 0) or 0)
            self.habilidades_desbloqueadas = list(dados.get("habilidades_desbloqueadas") or [])
            self.preferencias = list(dados.get("preferencias") or [])
            self.historico = list(dados.get("historico") or [])[-MAX_HISTORICO:]
            self.notas = list(dados.get("notas") or [])[-MAX_NOTAS:]

    # --- escrita ---------------------------------------------------------
    def como_dicionario(self) -> dict:
        with self._lock:
            return {
                "nome": self.nome_user,
                "afeto": self.afeto,
                "xp": self.xp,
                "habilidades_desbloqueadas": list(self.habilidades_desbloqueadas),
                "preferencias": list(self.preferencias),
                "historico": list(self.historico[-MAX_HISTORICO:]),
                "notas": list(self.notas[-MAX_NOTAS:]),
            }

    def salvar(self) -> bool:
        """Grava a memória de forma atômica. Retorna False se falhar."""
        with self._lock:
            dados = self._ler_arquivo()
            dados.update(self.como_dicionario())
            try:
                self._escrever_atomico(dados)
                return True
            except OSError as erro:
                print(f"[memoria] não consegui salvar: {erro}")
                return False

    def _escrever_atomico(self, dados: dict) -> None:
        diretorio = os.path.dirname(os.path.abspath(self.caminho)) or "."
        os.makedirs(diretorio, exist_ok=True)
        descritor, temporario = tempfile.mkstemp(dir=diretorio, suffix=".tmp")
        try:
            with os.fdopen(descritor, "w", encoding="utf-8") as arquivo:
                json.dump(dados, arquivo, indent=2, ensure_ascii=False)
                arquivo.flush()
                os.fsync(arquivo.fileno())
            os.replace(temporario, self.caminho)
        except BaseException:
            if os.path.exists(temporario):
                os.remove(temporario)
            raise

    def _talvez_salvar(self) -> None:
        if self._salvar_automaticamente:
            self.salvar()

    # --- operações de domínio -------------------------------------------
    def ganhar_xp(self, quantidade: int) -> str:
        """Soma XP (se positivo) e devolve o nível atual."""
        with self._lock:
            if quantidade > 0:
                self.xp += quantidade
                self._talvez_salvar()
            return nivel_para_xp(self.xp)

    @property
    def nivel(self) -> str:
        return nivel_para_xp(self.xp)

    def ganhar_afeto(self, quantidade: int = 5) -> int:
        with self._lock:
            self.afeto += quantidade
            self._talvez_salvar()
            return self.afeto

    def registrar_historico(self, papel: str, texto: str) -> None:
        with self._lock:
            self.historico.append({"papel": papel, "texto": texto[:MAX_TAMANHO_NOTA]})
            self.historico = self.historico[-MAX_HISTORICO:]
            self._talvez_salvar()

    def adicionar_nota(self, texto: str, agora: datetime.datetime | None = None) -> dict:
        agora = agora or datetime.datetime.now()
        nota = {"texto": texto[:MAX_TAMANHO_NOTA], "data": agora.strftime("%d/%m/%Y %H:%M")}
        with self._lock:
            self.notas.append(nota)
            self.notas = self.notas[-MAX_NOTAS:]
            self._talvez_salvar()
        return nota

    def limpar_notas(self) -> int:
        with self._lock:
            total = len(self.notas)
            self.notas = []
            self._talvez_salvar()
            return total

    def desbloquear_habilidade(self, nome: str) -> None:
        with self._lock:
            if nome not in self.habilidades_desbloqueadas:
                self.habilidades_desbloqueadas.append(nome)
                self._talvez_salvar()

    def definir_nome(self, nome: str) -> None:
        with self._lock:
            if nome.strip():
                self.nome_user = nome.strip()
                self._talvez_salvar()

    def salvar_api_key(self, chave: str) -> None:
        """Guarda a chave da Groq sem tocar no resto da memória."""
        with self._lock:
            dados = self._ler_arquivo()
            dados.update(self.como_dicionario())
            dados["groq_api_key"] = chave
            try:
                self._escrever_atomico(dados)
            except OSError as erro:
                print(f"[memoria] não consegui salvar a chave: {erro}")
