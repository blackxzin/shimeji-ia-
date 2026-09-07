"""Camada visual em Tkinter: janela, sprites, animações e diálogos.

Regra de ouro deste módulo: **todo widget só é tocado na thread principal**.
As threads de fundo publicam callables no `Despachante`, que os drena dentro do
laço do Tk. A versão anterior chamava `root.after()` direto das threads de voz e
de alarme, o que é uma corrida contra o interpretador do Tcl.
"""

from __future__ import annotations

import os
import queue
import random
import tkinter as tk
from typing import Callable

from .config import CORES_RESERVA, HUMORES, PASTA_ASSETS, TAMANHO_SPRITE

INTERVALO_DRENAGEM_MS = 40
COR_CHROMA = "#00ff00"
COR_FUNDO_ESCURO = "#1e1e2e"
COR_TEXTO = "#cdd6f4"
COR_DESTAQUE = "#89b4fa"
COR_PERIGO = "#f38ba8"
COR_CAMPO = "#313244"
COR_SECUNDARIA = "#a6adc8"
FONTE = "Segoe UI"
MARGEM_TELA = 20
ALTURA_PULO = 20
PASSO_TREMOR = 12


class Despachante:
    """Ponte entre threads de fundo e a thread da interface."""

    def __init__(self, root: tk.Misc, intervalo_ms: int = INTERVALO_DRENAGEM_MS):
        self._root = root
        self._intervalo = intervalo_ms
        self._fila: queue.Queue[Callable[[], None]] = queue.Queue()
        self._ativo = True

    def publicar(self, funcao: Callable[[], None]) -> None:
        """Agenda `funcao` para rodar na thread da interface. Seguro de qualquer thread."""
        if self._ativo:
            self._fila.put(funcao)

    def publicar_depois(self, atraso_ms: int, funcao: Callable[[], None]) -> None:
        """Agenda com atraso, sempre a partir da thread da interface."""
        self.publicar(lambda: self._root.after(atraso_ms, funcao))

    def iniciar(self) -> None:
        self._drenar()

    def parar(self) -> None:
        self._ativo = False

    def _drenar(self) -> None:
        while True:
            try:
                funcao = self._fila.get_nowait()
            except queue.Empty:
                break
            try:
                funcao()
            except tk.TclError:
                return  # janela já destruída
            except Exception as erro:
                print(f"[ui] erro em tarefa agendada: {erro}")
        if self._ativo:
            try:
                self._root.after(self._intervalo, self._drenar)
            except tk.TclError:
                self._ativo = False


def recortar_transparencia(imagem):
    """Corta o excesso transparente ao redor do sprite.

    No Linux o Tk não tem `-transparentcolor`, então sobra uma moldura da cor
    chroma em volta do personagem. Recortar pela caixa do canal alfa reduz essa
    moldura ao mínimo possível sem depender de extensões do X.
    """
    if imagem.mode != "RGBA":
        return imagem
    caixa = imagem.getbbox()
    return imagem.crop(caixa) if caixa else imagem


def carregar_sprites(pasta: str = PASTA_ASSETS, tamanho: int = TAMANHO_SPRITE) -> dict:
    """Carrega os PNGs de humor. Gera um sprite sólido de reserva se faltar arquivo."""
    from PIL import Image, ImageTk

    sprites = {}
    for humor in HUMORES:
        caminho = os.path.join(pasta, f"{humor}.png")
        imagem = None
        if os.path.isfile(caminho):
            try:
                imagem = recortar_transparencia(Image.open(caminho).convert("RGBA"))
                imagem.thumbnail((tamanho, tamanho), Image.Resampling.LANCZOS)
            except Exception as erro:
                print(f"[ui] falha ao carregar {humor}.png: {erro}")
                imagem = None
        if imagem is None:
            imagem = Image.new("RGBA", (tamanho, tamanho), CORES_RESERVA[humor])
        sprites[humor] = ImageTk.PhotoImage(imagem)
    return sprites


class Tooltip:
    """Balão de status que aparece ao passar o mouse."""

    def __init__(self, root: tk.Misc):
        self._root = root
        self._janela: tk.Toplevel | None = None

    def mostrar(self, texto: str, x: int, y: int) -> None:
        if self._janela is not None:
            return
        self._janela = tk.Toplevel(self._root)
        self._janela.overrideredirect(True)
        self._janela.attributes("-topmost", True)
        self._janela.geometry(f"+{x}+{y}")
        self._janela.configure(bg=COR_FUNDO_ESCURO)
        tk.Label(
            self._janela, text=texto, bg=COR_FUNDO_ESCURO, fg=COR_TEXTO,
            font=(FONTE, 9, "bold"), padx=10, pady=5, justify="left",
        ).pack()

    def esconder(self) -> None:
        if self._janela is not None:
            try:
                self._janela.destroy()
            except tk.TclError:
                pass
            self._janela = None


class Personagem:
    """A janela do personagem: sprite, posição e animações."""

    def __init__(self, root: tk.Tk, sprites: dict, tamanho: int = TAMANHO_SPRITE):
        self.root = root
        self.sprites = sprites
        self.tamanho = tamanho
        self.humor = "normal"
        self._x = 0
        self._y = 0
        self._configurar_janela()
        self.label = tk.Label(root, image=sprites["normal"], bg=self.cor_fundo, bd=0)
        self.label.pack()

    def _configurar_janela(self) -> None:
        self.root.title("Shimeji")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.cor_fundo = COR_CHROMA
        self.root.config(bg=self.cor_fundo)
        try:
            self.root.attributes("-transparentcolor", self.cor_fundo)
        except tk.TclError:
            # Sem chroma key (Linux/macOS): o fundo vira preto translúcido.
            self.cor_fundo = COR_FUNDO_ESCURO
            self.root.config(bg=self.cor_fundo)
            for atributo, valor in (("-alpha", 0.92), ("-type", "splash")):
                try:
                    self.root.attributes(atributo, valor)
                except tk.TclError:
                    pass
        self.centralizar()

    # --- posição ---------------------------------------------------------
    @property
    def largura_tela(self) -> int:
        return self.root.winfo_screenwidth()

    @property
    def altura_tela(self) -> int:
        return self.root.winfo_screenheight()

    def posicao(self) -> tuple[int, int]:
        """Posição atual. Usa o estado interno porque `winfo_x` mente antes do mapeamento."""
        return self._x, self._y

    def mover_para(self, x: int, y: int) -> None:
        x, y = self.limitar(x, y)
        self._x, self._y = x, y
        try:
            self.root.geometry(f"+{x}+{y}")
        except tk.TclError:
            pass

    def sincronizar_posicao(self) -> None:
        """Realinha o estado interno com a janela real (após arrastar com o mouse)."""
        try:
            self._x, self._y = self.root.winfo_x(), self.root.winfo_y()
        except tk.TclError:
            pass

    def limitar(self, x: int, y: int) -> tuple[int, int]:
        """Mantém o personagem inteiramente visível dentro da tela."""
        limite_x = max(0, self.largura_tela - self.tamanho)
        limite_y = max(0, self.altura_tela - self.tamanho)
        return max(0, min(x, limite_x)), max(0, min(y, limite_y))

    def centralizar(self) -> None:
        self.mover_para(self.largura_tela // 2 - self.tamanho // 2, self.altura_tela // 2 - self.tamanho // 2)

    def posicao_aleatoria(self) -> tuple[int, int]:
        return (
            random.randint(MARGEM_TELA, max(MARGEM_TELA + 1, self.largura_tela - self.tamanho - MARGEM_TELA)),
            random.randint(MARGEM_TELA, max(MARGEM_TELA + 1, self.altura_tela - self.tamanho - MARGEM_TELA)),
        )

    # --- aparência -------------------------------------------------------
    def definir_humor(self, humor: str) -> None:
        if humor not in self.sprites:
            return
        self.humor = humor
        try:
            self.label.config(image=self.sprites[humor])
        except tk.TclError:
            pass

    # --- animações (sempre na thread da interface) -----------------------
    def pular(self, vezes: int = 1, altura: int = ALTURA_PULO, duracao_ms: int = 150) -> None:
        x, y = self.posicao()
        for repeticao in range(vezes):
            base = repeticao * duracao_ms * 2
            self.root.after(base, lambda: self.mover_para(x, y - altura))
            self.root.after(base + duracao_ms, lambda: self.mover_para(x, y))

    def tremer(self, vezes: int = 6, duracao_ms: int = 90) -> None:
        x, y = self.posicao()
        for passo in range(vezes):
            deslocamento = PASSO_TREMOR if passo % 2 == 0 else -PASSO_TREMOR
            self.root.after(passo * duracao_ms, lambda d=deslocamento: self.mover_para(x + d, y))
        self.root.after(vezes * duracao_ms, lambda: self.mover_para(x, y))


def construir_menu(root: tk.Misc, itens: list[tuple[str, Callable | None]]) -> tk.Menu:
    """Monta o menu de contexto. Um rótulo None vira separador."""
    menu = tk.Menu(
        root, tearoff=0, bg="#2a2a3a", fg="white",
        activebackground=COR_DESTAQUE, activeforeground=COR_FUNDO_ESCURO, font=(FONTE, 9),
    )
    for rotulo, comando in itens:
        if comando is None:
            menu.add_separator()
        else:
            menu.add_command(label=rotulo, command=comando)
    return menu


class JanelaConfiguracoes:
    """Diálogo de configurações: nome, chave da API e limpeza de notas."""

    def __init__(self, root: tk.Misc, nome_atual: str, chave_atual: str, status: str,
                 ao_salvar: Callable[[str, str], None], ao_limpar_notas: Callable[[], None]):
        self.ao_salvar = ao_salvar
        self.ao_limpar_notas = ao_limpar_notas

        self.janela = tk.Toplevel(root)
        self.janela.title("Shimeji — Configurações")
        self.janela.geometry("440x360")
        self.janela.resizable(False, False)
        self.janela.attributes("-topmost", True)
        self.janela.configure(bg=COR_FUNDO_ESCURO)

        tk.Label(self.janela, text="⚙️  Configurações", bg=COR_FUNDO_ESCURO, fg=COR_DESTAQUE,
                 font=(FONTE, 15, "bold")).pack(pady=(18, 12))

        quadro = tk.Frame(self.janela, bg=COR_FUNDO_ESCURO)
        quadro.pack(padx=24, fill="x")

        self.entrada_nome = self._campo(quadro, "Como devo te chamar:", nome_atual)
        self.entrada_chave = self._campo(quadro, "Chave da API Groq:", chave_atual, oculto=True)

        self.mostrar_chave = tk.BooleanVar(value=False)
        tk.Checkbutton(
            quadro, text="Mostrar chave", variable=self.mostrar_chave, command=self._alternar_chave,
            bg=COR_FUNDO_ESCURO, fg=COR_TEXTO, selectcolor=COR_CAMPO, activebackground=COR_FUNDO_ESCURO,
            activeforeground=COR_TEXTO, font=(FONTE, 9), bd=0, highlightthickness=0,
        ).pack(anchor="w")

        tk.Label(quadro, text=status, bg=COR_FUNDO_ESCURO, fg=COR_SECUNDARIA,
                 font=(FONTE, 9)).pack(anchor="w", pady=(14, 0))

        botoes = tk.Frame(self.janela, bg=COR_FUNDO_ESCURO)
        botoes.pack(pady=18)
        self._botao(botoes, "💾  Salvar", COR_DESTAQUE, self._salvar)
        self._botao(botoes, "🗑️  Limpar notas", COR_PERIGO, self._limpar)

    def _campo(self, pai: tk.Misc, rotulo: str, valor: str, oculto: bool = False) -> tk.Entry:
        tk.Label(pai, text=rotulo, bg=COR_FUNDO_ESCURO, fg=COR_TEXTO,
                 font=(FONTE, 10, "bold")).pack(anchor="w", pady=(8, 3))
        entrada = tk.Entry(
            pai, font=(FONTE, 10), bg=COR_CAMPO, fg=COR_TEXTO, insertbackground=COR_TEXTO,
            relief="flat", bd=6, show="•" if oculto else "",
        )
        entrada.pack(fill="x")
        entrada.insert(0, valor or "")
        return entrada

    def _botao(self, pai: tk.Misc, texto: str, cor: str, comando: Callable) -> None:
        tk.Button(
            pai, text=texto, command=comando, bg=cor, fg=COR_FUNDO_ESCURO,
            font=(FONTE, 10, "bold"), relief="flat", bd=0, cursor="hand2",
            activebackground=cor, activeforeground=COR_FUNDO_ESCURO, padx=18, pady=8,
        ).pack(side="left", padx=6)

    def _alternar_chave(self) -> None:
        self.entrada_chave.config(show="" if self.mostrar_chave.get() else "•")

    def _salvar(self) -> None:
        self.ao_salvar(self.entrada_nome.get().strip(), self.entrada_chave.get().strip())
        self.fechar()

    def _limpar(self) -> None:
        self.ao_limpar_notas()

    def fechar(self) -> None:
        try:
            self.janela.destroy()
        except tk.TclError:
            pass
