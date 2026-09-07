"""Orquestrador da Shimeji: costura interface, voz, IA, memória e habilidades."""

from __future__ import annotations

import datetime
import os
import random
import threading
import tkinter as tk

from . import evolucao, sistema, tela
from .calculadora import ErroDeCalculo, calcular, formatar
from .comandos import Acao, Intencao, interpretar
from .config import (
    ARQUIVO_MEMORIA, BASE_DIR, CHANCE_MOVIMENTO, Config, DURACAO_PISCADA,
    INTERVALO_DICA_SAUDE, INTERVALO_MONITOR, INTERVALO_MOVIMENTO, INTERVALO_PISCAR,
    INTERVALO_TICK_LEMBRETE, LIMITE_ALERTA_CPU, LIMITE_ALERTA_DISCO, LIMITE_ALERTA_RAM,
    PASTA_HABILIDADES, carregar_config, ler_chave_do_arquivo,
)
from .evolucao import ErroDeEvolucao
from .habilidades import ErroDeHabilidade, RegistroDeHabilidades
from .ia import CerebroIA, codificar_imagem, montar_prompt_sistema
from .memoria import Memoria, xp_para_proximo_nivel
from .textos import DICAS_SAUDE, PIADAS, REACOES_CARINHO, REACOES_CLIQUE, SAUDACOES, roteiro_demo
from .ui import Despachante, JanelaConfiguracoes, Personagem, Tooltip, carregar_sprites, construir_menu
from .voz import Locutor, Ouvinte

DIAS_DA_SEMANA = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
                  "sexta-feira", "sábado", "domingo")

XP = {
    "saudacao": 1, "abrir": 3, "pesquisar": 3, "fechar": 5, "hora": 1, "alarme": 3,
    "anotar": 2, "ler_notas": 1, "piada": 2, "calcular": 3, "clima": 3, "visao": 10,
    "status": 2, "volume": 3, "habilidades": 1, "melhoria": 20, "clique": 1, "carinho": 5,
    "habilidade_extra": 2,
}

DURACAO_HUMOR_MS = 4000
DURACAO_HUMOR_CURTA_MS = 2000
NOTAS_LIDAS_EM_VOZ = 5


class ShimejiApp:
    """A aplicação inteira. Construir não inicia o laço: chame `executar()`."""

    def __init__(self, config: Config | None = None, root: tk.Tk | None = None):
        self.config = config or Config()
        self.parar_evento = threading.Event()
        self._dormindo = False
        self._alarmes: list[threading.Timer] = []

        self.memoria = Memoria(ARQUIVO_MEMORIA)
        self.habilidades = RegistroDeHabilidades(PASTA_HABILIDADES)
        self.habilidades.carregar_tudo()
        self.cerebro = CerebroIA(
            api_key=self.config.api_key,
            modelo=self.config.modelo,
            modelo_visao=self.config.modelo_visao,
        )

        self.root = root or tk.Tk()
        self.personagem = Personagem(self.root, carregar_sprites())
        self.despachante = Despachante(self.root)
        self.tooltip = Tooltip(self.root)
        self.locutor = Locutor(ativo=not self.config.sem_voz)

        self._ligar_eventos()
        self.root.protocol("WM_DELETE_WINDOW", self.encerrar)

    # ================================================================
    #  Ciclo de vida
    # ================================================================
    def executar(self) -> None:
        """Sobe as threads de fundo e entra no laço da interface."""
        self.despachante.iniciar()
        self.locutor.iniciar()
        self.falar(self.saudacao_do_horario())

        for alvo, nome in (
            (self._laco_piscar, "piscar"),
            (self._laco_movimento, "movimento"),
            (self._laco_monitor, "monitor"),
            (self._laco_lembretes, "lembretes"),
        ):
            threading.Thread(target=alvo, name=nome, daemon=True).start()

        if not self.config.sem_microfone:
            Ouvinte(self.ao_ouvir, self.parar_evento, lambda: self._dormindo).iniciar()
        elif not self.config.demo:
            print("[app] microfone desligado; use o menu do botão direito.")

        if self.config.demo:
            self._agendar_demo()

        try:
            self.root.mainloop()
        finally:
            self.parar_evento.set()

    def encerrar(self) -> None:
        """Desligamento gracioso: cancela alarmes, salva memória e fecha a janela."""
        if self.parar_evento.is_set():
            return
        self.parar_evento.set()
        for alarme in self._alarmes:
            alarme.cancel()
        self._alarmes.clear()
        self.despachante.parar()
        self.locutor.parar()
        self.memoria.salvar()
        print(f"Shimeji: até mais, {self.memoria.nome_user}!")
        try:
            self.root.quit()
            self.root.destroy()
        except tk.TclError:
            pass

    # ================================================================
    #  Atalhos de apresentação
    # ================================================================
    def falar(self, texto: str) -> None:
        self.locutor.falar(texto)

    def humor(self, nome: str, voltar_em_ms: int | None = DURACAO_HUMOR_MS) -> None:
        """Troca a expressão a partir de qualquer thread, com retorno automático."""
        self.despachante.publicar(lambda: self.personagem.definir_humor(nome))
        if voltar_em_ms:
            self.despachante.publicar_depois(voltar_em_ms, lambda: self.personagem.definir_humor("normal"))

    def animar(self, nome_animacao: str, **kwargs) -> None:
        animacao = getattr(self.personagem, nome_animacao, None)
        if animacao:
            self.despachante.publicar(lambda: animacao(**kwargs))

    def _premiar(self, chave: str) -> None:
        """XP interno por comando, usando a tabela XP."""
        self.memoria.ganhar_xp(XP.get(chave, 1))

    # ================================================================
    #  API pública para habilidades (plugins)
    # ================================================================
    # Uma habilidade recebe esta instância como argumento. O que está abaixo é
    # o contrato estável: qualquer coisa fora daqui pode mudar entre versões.

    def ganhar_xp(self, quantidade: int = 1) -> str:
        """Concede XP a partir de uma habilidade. Devolve o nível atual."""
        return self.memoria.ganhar_xp(int(quantidade))

    def set_mood(self, humor: str, voltar_em_ms: int | None = DURACAO_HUMOR_MS) -> None:
        """Troca a expressão. Pode ser chamada de qualquer thread."""
        self.humor(humor, voltar_em_ms)

    def pular(self, vezes: int = 1) -> None:
        """Anima um pulinho com segurança de thread."""
        self.animar("pular", vezes=vezes)

    def tremer(self, vezes: int = 6) -> None:
        """Anima um tremor com segurança de thread."""
        self.animar("tremer", vezes=vezes)

    def anotar(self, texto: str) -> None:
        """Guarda uma nota persistente a partir de uma habilidade."""
        self._anotar(texto)

    def saudacao_do_horario(self) -> str:
        hora = datetime.datetime.now().hour
        periodo = "Bom dia" if 5 <= hora < 12 else "Boa tarde" if 12 <= hora < 18 else "Boa noite"
        return f"{periodo}, {self.memoria.nome_user}! Shimeji online."

    def resumo_status(self) -> str:
        faltando = xp_para_proximo_nivel(self.memoria.xp)
        linha_extra = f"\nFaltam {faltando} XP para o próximo nível" if faltando else "\nNível máximo alcançado"
        return (f"🌟 {self.memoria.nivel}   ·   XP {self.memoria.xp}   ·   ❤️ {self.memoria.afeto}"
                f"{linha_extra}\n📝 {len(self.memoria.notas)} notas   ·   🧠 {len(self.habilidades)} habilidades")

    # ================================================================
    #  Entrada de comandos
    # ================================================================
    def ao_ouvir(self, texto: str) -> None:
        """Chamado pela thread do microfone."""
        print(f"Você: {texto}")
        self.memoria.registrar_historico("user", texto)
        self.processar(texto)

    def processar(self, texto: str) -> Intencao:
        """Interpreta e executa uma fala. Retorna a intenção detectada."""
        intencao = interpretar(texto, self.habilidades.nomes)
        manipulador = self._manipuladores().get(intencao.acao)
        if manipulador is None:
            self._conversar(texto)
            return intencao
        try:
            manipulador(intencao)
        except Exception as erro:
            print(f"[app] falha ao executar {intencao.acao}: {erro}")
            self.humor("triste")
            self.falar("Algo deu errado aqui. Tenta de novo?")
        return intencao

    def _manipuladores(self) -> dict:
        return {
            Acao.SAUDACAO: lambda i: self._saudar(),
            Acao.ABRIR: lambda i: self._abrir(i["alvo"]),
            Acao.PESQUISAR: lambda i: self._pesquisar(i["query"]),
            Acao.FECHAR: lambda i: self._fechar_programa(i["alvo"]),
            Acao.HORA: lambda i: self._dizer_hora(),
            Acao.ALARME: lambda i: self._criar_alarme(i["segundos"], i["quantidade"], i["unidade"]),
            Acao.ANOTAR: lambda i: self._anotar(i["texto"]),
            Acao.LER_NOTAS: lambda i: self._ler_notas(),
            Acao.PIADA: lambda i: self._contar_piada(),
            Acao.CALCULAR: lambda i: self._calcular(i["expressao"]),
            Acao.CLIMA: lambda i: self._clima(i["cidade"]),
            Acao.VER_TELA: lambda i: self._rodar_em_thread(self._analisar_tela),
            Acao.LER_TELA: lambda i: self._rodar_em_thread(self._ler_tela),
            Acao.STATUS: lambda i: self._rodar_em_thread(self._dizer_status),
            Acao.VOLUME: lambda i: self._volume(i["nivel"]),
            Acao.HABILIDADES: lambda i: self._listar_habilidades(),
            Acao.MELHORAR: lambda i: self._rodar_em_thread(self._propor_melhoria, i["alvo"]),
            Acao.DORMIR: lambda i: self._definir_sono(True),
            Acao.ACORDAR: lambda i: self._definir_sono(False),
            Acao.HABILIDADE_EXTRA: lambda i: self._rodar_habilidade(i["nome"]),
            Acao.CONVERSAR: lambda i: self._rodar_em_thread(self._conversar, i["texto"]),
        }

    def _rodar_em_thread(self, funcao, *argumentos) -> None:
        """Trabalho lento (rede, disco, psutil) nunca bloqueia a interface."""
        threading.Thread(target=funcao, args=argumentos, daemon=True).start()

    # ================================================================
    #  Comandos
    # ================================================================
    def _saudar(self) -> None:
        self.falar(random.choice(SAUDACOES).format(nome=self.memoria.nome_user))
        self.humor("feliz")
        self._premiar("saudacao")

    def _abrir(self, alvo: str) -> None:
        self.humor("feliz")
        try:
            resultado = sistema.abrir_alvo(alvo)
        except sistema.ErroDeSistema as erro:
            self.humor("triste")
            self.falar(f"Não consegui abrir: {erro}")
            return
        mensagens = {
            "site": f"Abrindo {alvo}.",
            "arquivo": f"Abrindo {alvo}.",
            "programa": f"Iniciando {alvo}.",
            "busca": f"Não achei {alvo} aqui, então pesquisei na web.",
        }
        self.falar(mensagens[resultado])
        self._premiar("abrir")

    def _pesquisar(self, query: str) -> None:
        self.falar(f"Pesquisando {query}.")
        self.humor("feliz")
        sistema.pesquisar(query)
        self._premiar("pesquisar")

    def _fechar_programa(self, alvo: str) -> None:
        try:
            encerrados, protegidos = sistema.encerrar_processos(alvo)
        except sistema.ErroDeSistema as erro:
            self.humor("triste")
            self.falar(f"Não vou fazer isso: {erro}.")
            return

        if encerrados:
            self.falar(f"Fechei {encerrados} processo de {alvo}." if encerrados == 1
                       else f"Fechei {encerrados} processos de {alvo}.")
            self.humor("feliz")
            self._premiar("fechar")
        elif protegidos:
            self.falar(f"Encontrei {alvo}, mas é um processo protegido. Não vou encerrar.")
            self.humor("brava")
        else:
            self.falar(f"Não achei nenhum processo chamado {alvo}.")
            self.humor("triste")

    def _dizer_hora(self) -> None:
        agora = datetime.datetime.now()
        self.humor("feliz")
        self.falar(f"São {agora.strftime('%H:%M')}. Hoje é {DIAS_DA_SEMANA[agora.weekday()]}, "
                   f"{agora.strftime('%d/%m/%Y')}.")
        self._premiar("hora")

    def _criar_alarme(self, segundos: int, quantidade: int, unidade: str) -> None:
        self.falar(f"Alarme marcado para daqui a {quantidade} {unidade}.")
        self.humor("feliz")
        self._premiar("alarme")

        def disparar() -> None:
            if self.parar_evento.is_set():
                return
            self.falar(f"O tempo acabou! Passaram {quantidade} {unidade}.")
            self.humor("brava")
            self.animar("tremer")

        temporizador = threading.Timer(segundos, disparar)
        temporizador.daemon = True
        temporizador.start()
        self._alarmes = [t for t in self._alarmes if t.is_alive()] + [temporizador]

    def _anotar(self, texto: str) -> None:
        self.memoria.adicionar_nota(texto)
        self.falar(f"Anotado: {texto}")
        self.humor("feliz", DURACAO_HUMOR_CURTA_MS)
        self._premiar("anotar")

    def _ler_notas(self) -> None:
        if not self.memoria.notas:
            self.humor("triste")
            self.falar("Você ainda não tem notas salvas.")
            return
        total = len(self.memoria.notas)
        self.humor("feliz")
        self.falar(f"Você tem {total} nota." if total == 1 else f"Você tem {total} notas.")
        for nota in self.memoria.notas[-NOTAS_LIDAS_EM_VOZ:]:
            self.falar(f"{nota['data']}: {nota['texto']}")
        self._premiar("ler_notas")

    def _contar_piada(self) -> None:
        self.humor("feliz", 5000)
        self.falar(random.choice(PIADAS))
        self._premiar("piada")

    def _calcular(self, expressao: str) -> None:
        try:
            resultado = calcular(expressao)
        except ErroDeCalculo as erro:
            self.humor("triste")
            self.falar(f"Não consegui calcular: {erro}.")
            return
        self.humor("feliz")
        self.falar(f"O resultado é {formatar(resultado)}.")
        self._premiar("calcular")

    def _clima(self, cidade: str) -> None:
        self.humor("feliz")
        self.falar(f"Vendo o clima em {cidade}." if cidade else "Abrindo a previsão do tempo.")
        sistema.abrir_clima(cidade)
        self._premiar("clima")

    def _volume(self, nivel: int | None) -> None:
        try:
            aplicado = sistema.ajustar_volume(nivel)
        except sistema.ErroDeSistema as erro:
            self.humor("triste")
            self.falar(f"Não consegui mudar o volume: {erro}.")
            return
        self.falar(f"Volume em {aplicado} por cento.")
        self._premiar("volume")

    def _listar_habilidades(self) -> None:
        self.humor("feliz")
        self.falar("Sei abrir programas e sites, pesquisar, fechar processos, olhar e ler a sua tela, "
                   "dar o status do sistema, controlar o volume, dizer as horas, criar alarmes, "
                   "guardar notas, calcular, ver o clima e contar piadas.")
        extras = self.habilidades.nomes
        self.falar(f"Habilidades aprendidas: {', '.join(extras)}." if extras
                   else "Ainda não aprendi habilidades extras. Me ensine alguma!")
        self._premiar("habilidades")

    def _rodar_habilidade(self, nome: str) -> None:
        self.falar(f"Executando {nome}.")
        self._premiar("habilidade_extra")
        self._rodar_em_thread(self._executar_habilidade_segura, nome)

    def _executar_habilidade_segura(self, nome: str) -> None:
        try:
            self.habilidades.executar(nome, self)
        except ErroDeHabilidade as erro:
            self.humor("triste")
            self.falar(f"A habilidade {nome} falhou: {erro}.")

    def _definir_sono(self, dormir: bool) -> None:
        self._dormindo = dormir
        if dormir:
            self.humor("triste", voltar_em_ms=None)
            self.falar("Vou dormir. Microfone desligado para economizar bateria.")
        else:
            self.humor("feliz")
            self.falar("Acordei! Microfone ligado de novo.")

    def alternar_sono(self) -> None:
        self._definir_sono(not self._dormindo)

    @property
    def dormindo(self) -> bool:
        return self._dormindo

    # ================================================================
    #  Visão e IA
    # ================================================================
    def _capturar_para_ia(self) -> str | None:
        try:
            imagem = tela.capturar()
        except tela.ErroDeCaptura as erro:
            self.humor("triste")
            self.falar(f"Não consegui capturar a tela: {erro}")
            return None
        try:
            tela.salvar(imagem, BASE_DIR)
        except OSError:
            pass
        return codificar_imagem(imagem)

    def _exigir_cerebro(self) -> bool:
        if self.cerebro.disponivel:
            return True
        self.humor("triste")
        self.falar("Minha chave da Groq não está configurada. Abra as configurações no botão direito.")
        return False

    def _analisar_tela(self) -> None:
        if not self._exigir_cerebro():
            return
        self.falar("Olhando a sua tela.")
        imagem = self._capturar_para_ia()
        if imagem is None:
            return
        try:
            self.falar(self.cerebro.descrever_tela(imagem))
            self.humor("feliz")
            self._premiar("visao")
        except Exception as erro:
            print(f"[app] visão falhou: {erro}")
            self.humor("triste")
            self.falar("Capturei a tela, mas não consegui analisar a imagem.")

    def _ler_tela(self) -> None:
        if not self._exigir_cerebro():
            return
        self.falar("Lendo o texto da tela.")
        imagem = self._capturar_para_ia()
        if imagem is None:
            return
        try:
            self.falar(self.cerebro.ler_tela(imagem))
            self._premiar("visao")
        except Exception as erro:
            print(f"[app] OCR falhou: {erro}")
            self.humor("triste")
            self.falar("Não consegui ler o texto da tela.")

    def _dizer_status(self) -> None:
        self.humor("feliz")
        status = sistema.coletar_status()
        self.falar(f"{status.descrever()} Nível {self.memoria.nivel}, {self.memoria.xp} de experiência.")
        self._premiar("status")

    def _prompt_sistema(self) -> str:
        return montar_prompt_sistema(
            nome_user=self.memoria.nome_user,
            nivel=self.memoria.nivel,
            xp=self.memoria.xp,
            afeto=self.memoria.afeto,
            notas=self.memoria.notas,
            pode_se_modificar=self.config.permitir_auto_modificacao,
        )

    def _conversar(self, texto: str) -> None:
        if not self._exigir_cerebro():
            return
        try:
            resposta = self.cerebro.conversar(self._prompt_sistema(), self.memoria.historico, texto)
        except Exception as erro:
            print(f"[app] IA falhou: {erro}")
            self.humor("triste")
            self.falar("Tive um problema de conexão. Tenta de novo?")
            return
        self._aplicar_resposta(resposta)

    def _aplicar_resposta(self, resposta) -> None:
        if resposta.habilidade:
            self._aprender_habilidade(*resposta.habilidade)
            return
        if resposta.melhoria:
            self._aplicar_melhoria(*resposta.melhoria)
            return
        if resposta.humor:
            self.humor(resposta.humor, 5000)
        if resposta.texto:
            self.memoria.registrar_historico("assistant", resposta.texto)
            self.falar(resposta.texto)

    def _aprender_habilidade(self, nome: str, comandos: str) -> None:
        try:
            nome_final = self.habilidades.salvar_nova(nome, comandos)
        except ErroDeHabilidade as erro:
            self.humor("triste")
            self.falar(f"Não consegui aprender essa habilidade: {erro}.")
            return
        self.memoria.desbloquear_habilidade(nome_final)
        self.memoria.ganhar_xp(15)
        self.humor("feliz")
        self.falar(f"Aprendi a habilidade {nome_final}! Diga 'executa {nome_final}' para usar.")

    def _aplicar_melhoria(self, nome: str, comandos: str) -> None:
        try:
            nome_final = evolucao.aplicar_melhoria(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py"),
                nome, comandos, self.config.permitir_auto_modificacao,
            )
        except ErroDeEvolucao as erro:
            self.humor("triste")
            self.falar(f"Rejeitei essa melhoria: {erro}.")
            return
        self.memoria.ganhar_xp(XP["melhoria"])
        self.humor("feliz")
        self.falar(f"Apliquei a melhoria {nome_final}. Me reinicie para ativar.")

    def _propor_melhoria(self, alvo: str) -> None:
        if not self.config.permitir_auto_modificacao:
            self.falar("A auto-modificação está desligada. Suba com --permitir-auto-modificacao se quiser liberar.")
            return
        if not self._exigir_cerebro():
            return
        self.falar(f"Pensando em como melhorar {alvo}.")
        try:
            with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py"), encoding="utf-8") as arquivo:
                codigo = arquivo.read()
            resposta = self.cerebro.propor_melhoria(alvo, codigo, self._prompt_sistema())
        except Exception as erro:
            print(f"[app] proposta de melhoria falhou: {erro}")
            self.humor("triste")
            self.falar("Não consegui pensar em uma melhoria agora.")
            return
        self._aplicar_resposta(resposta)

    # ================================================================
    #  Laços de fundo
    # ================================================================
    def _dormir_interrompivel(self, segundos: float) -> bool:
        """Espera respeitando o pedido de desligamento. False se é hora de parar."""
        return not self.parar_evento.wait(segundos)

    def _laco_piscar(self) -> None:
        while self._dormir_interrompivel(random.randint(*INTERVALO_PISCAR)):
            if self._dormindo or self.personagem.humor != "normal":
                continue
            self.humor("piscando", voltar_em_ms=None)
            if not self._dormir_interrompivel(DURACAO_PISCADA):
                return
            self.humor("normal", voltar_em_ms=None)

    def _laco_movimento(self) -> None:
        while self._dormir_interrompivel(INTERVALO_MOVIMENTO):
            if self._dormindo or random.random() > CHANCE_MOVIMENTO:
                continue
            self.despachante.publicar(
                lambda: self.personagem.mover_para(*self.personagem.posicao_aleatoria())
            )

    def _laco_monitor(self) -> None:
        alertado = {"ram": False, "cpu": False, "disco": False}
        while self._dormir_interrompivel(INTERVALO_MONITOR):
            try:
                status = sistema.coletar_status()
            except Exception as erro:
                print(f"[app] monitor falhou: {erro}")
                continue
            for chave, valor, limite, mensagem in (
                ("ram", status.ram_percentual, LIMITE_ALERTA_RAM, "A memória RAM está em {:.0f} por cento."),
                ("cpu", status.cpu, LIMITE_ALERTA_CPU, "A CPU está em {:.0f} por cento."),
                ("disco", status.disco_percentual, LIMITE_ALERTA_DISCO, "O disco está em {:.0f} por cento."),
            ):
                if valor > limite and not alertado[chave]:
                    self.falar(mensagem.format(valor) + " Quer que eu feche alguma coisa?")
                    self.humor("brava")
                    alertado[chave] = True
                elif valor < limite - 20:
                    alertado[chave] = False

    def _laco_lembretes(self) -> None:
        ultimo = 0.0
        decorrido = 0.0
        while self._dormir_interrompivel(INTERVALO_TICK_LEMBRETE):
            decorrido += INTERVALO_TICK_LEMBRETE
            if self._dormindo or decorrido - ultimo < INTERVALO_DICA_SAUDE:
                continue
            ultimo = decorrido
            if self.personagem.humor == "normal":
                self.falar(random.choice(DICAS_SAUDE))
                self.humor("feliz")

    # ================================================================
    #  Interação com o mouse
    # ================================================================
    def _ligar_eventos(self) -> None:
        rotulo = self.personagem.label
        rotulo.bind("<Button-1>", self._ao_clicar)
        rotulo.bind("<Double-Button-1>", self._ao_dar_carinho)
        rotulo.bind("<B1-Motion>", self._ao_arrastar)
        rotulo.bind("<Button-3>", self._abrir_menu)
        rotulo.bind("<Enter>", self._ao_entrar_mouse)
        rotulo.bind("<Leave>", lambda evento: self.tooltip.esconder())

    def _ao_clicar(self, evento) -> None:
        self.falar(random.choice(REACOES_CLIQUE).format(
            nome=self.memoria.nome_user, xp=self.memoria.xp,
            nivel=self.memoria.nivel, afeto=self.memoria.afeto))
        self.humor("feliz", DURACAO_HUMOR_CURTA_MS)
        self._premiar("clique")

    def _ao_dar_carinho(self, evento) -> None:
        afeto = self.memoria.ganhar_afeto()
        self.falar(random.choice(REACOES_CARINHO).format(afeto=afeto))
        self.humor("feliz")
        self.personagem.pular(vezes=2)
        self._premiar("carinho")

    def _ao_arrastar(self, evento) -> None:
        metade = self.personagem.tamanho // 2
        self.personagem.mover_para(evento.x_root - metade, evento.y_root - metade)

    def _ao_entrar_mouse(self, evento) -> None:
        x, y = self.personagem.posicao()
        self.tooltip.mostrar(self.resumo_status(), x + self.personagem.tamanho + 8, y)

    def _abrir_menu(self, evento) -> None:
        self.tooltip.esconder()
        rotulo_sono = "☀️  Acordar" if self._dormindo else "💤  Dormir"
        menu = construir_menu(self.root, [
            (rotulo_sono, self.alternar_sono),
            ("📊  Status do sistema", lambda: self._rodar_em_thread(self._dizer_status)),
            ("🧠  Habilidades", self._listar_habilidades),
            ("👀  Olhar a tela", lambda: self._rodar_em_thread(self._analisar_tela)),
            ("📖  Ler a tela", lambda: self._rodar_em_thread(self._ler_tela)),
            ("🕐  Hora e data", self._dizer_hora),
            ("📝  Minhas notas", self._ler_notas),
            ("😂  Piada", self._contar_piada),
            ("", None),
            ("⚡  Auto-melhoria", lambda: self._rodar_em_thread(self._propor_melhoria, "geral")),
            ("⚙️  Configurações", self.abrir_configuracoes),
            ("", None),
            ("❌  Sair", self.encerrar),
        ])
        try:
            menu.tk_popup(evento.x_root, evento.y_root)
        finally:
            menu.grab_release()

    def abrir_configuracoes(self) -> None:
        JanelaConfiguracoes(
            self.root,
            nome_atual=self.memoria.nome_user,
            chave_atual=ler_chave_do_arquivo(),
            status=self.resumo_status(),
            ao_salvar=self._salvar_configuracoes,
            ao_limpar_notas=self._limpar_notas,
        )

    def _salvar_configuracoes(self, nome: str, chave: str) -> None:
        if nome:
            self.memoria.definir_nome(nome)
        self.memoria.salvar_api_key(chave)
        self.config = self.config.com_api_key(chave)
        self.cerebro.trocar_chave(chave)
        self.humor("feliz")
        self.falar(f"Configurações salvas, {self.memoria.nome_user}!")

    def _limpar_notas(self) -> None:
        total = self.memoria.limpar_notas()
        self.falar("Não havia notas para apagar." if total == 0 else f"Apaguei {total} notas.")

    # ================================================================
    #  Modo demonstração
    # ================================================================
    def _agendar_demo(self) -> None:
        """Executa um roteiro fixo, sem microfone e sem rede, para gravar a demo."""
        atraso = 1500
        for espera, comando in roteiro_demo():
            atraso += espera
            self.root.after(atraso, lambda c=comando: self._passo_demo(c))
        self.root.after(atraso + 4000, self.encerrar)

    def _passo_demo(self, comando: str) -> None:
        print(f"\n[demo] Você: {comando}")
        intencao = interpretar(comando, self.habilidades.nomes)
        if intencao.acao is Acao.CONVERSAR and not self.cerebro.disponivel:
            self.falar("(modo demo: sem chave da Groq, esta pergunta iria para a IA)")
            return
        self.processar(comando)


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada da aplicação."""
    import sys

    config = carregar_config(argv if argv is not None else sys.argv[1:])
    try:
        aplicacao = ShimejiApp(config)
    except tk.TclError as erro:
        print(f"Não consegui abrir a janela: {erro}\nA Shimeji precisa de uma sessão gráfica.")
        return 1
    aplicacao.executar()
    return 0


    def cache(self):
        """Método gerado automaticamente pela auto-evolução."""
        self.cache = {}


    def cache(self):
        """Método gerado automaticamente pela auto-evolução."""
        self.cache = {}


    def cache(self):
        """Método gerado automaticamente pela auto-evolução."""
        self.cache = {}


    def cache(self):
        """Método gerado automaticamente pela auto-evolução."""
        self.cache = {}
