import tkinter as tk
from tkinter import simpledialog
from PIL import Image, ImageTk, ImageGrab
import threading, pyttsx3, time, random, os, re, psutil, sys, json, subprocess
import webbrowser, shutil, base64, datetime, importlib.util, io, ctypes, argparse
import queue, inspect, py_compile, tempfile, traceback
import speech_recognition as sr
from groq import Groq
import urllib.parse

# --- HIGH DPI SUPPORT (Windows) ---
# Deve ser chamado antes de criar qualquer janela Tkinter.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-Monitor DPI Aware V2
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# --- CONFIGURAÇÃO ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASTA_HABILIDADES = os.path.join(BASE_DIR, "habilidades")
ARQUIVO_MEMORIA = os.path.join(BASE_DIR, "memoria.json")

# API key via argumento de linha de comando ou variável de ambiente
parser = argparse.ArgumentParser(description="Shimeji - Assistente de voz evolutivo")
parser.add_argument("--api-key", type=str, default=os.environ.get("GROQ_API_KEY", ""), help="Chave da API Groq")
parser.add_argument("--modelo", type=str, default="llama-3.3-70b-versatile", help="Modelo Groq a usar")
parser.add_argument("--sem-voz", action="store_true", help="Desativa TTS (text-to-speech)")
args = parser.parse_args()

MODELO = args.modelo
SEM_VOZ = args.sem_voz

if not os.path.exists(PASTA_HABILIDADES):
    os.makedirs(PASTA_HABILIDADES)

# --- Regex de comandos de voz ---
CMD_ABRIR = r'(?:abre?|abra|m?abrir)\s+(.+)'
CMD_PESQUISAR = r'(?:pesquisa|pesquise|busca|busque|procure|procura|search)\s+(.+)'
CMD_FECHAR = r'(?:fecha|feche|fechar|mate|matar|encerra|encerre)\s+(.+)'
CMD_TELA = r'(?:olha?\s+(na)?\s*tela|ve|veja|olha?\s+isso|o\s+que\s+tem\s+na\s+tela|o\s+que\s+voc[eê]\s+ve|screenshot|captura)'
CMD_STATUS = r'(?:status|informa[cç][aã]o|sistema|hardware|cpu|mem[oó]ria|bateria|disco)'
CMD_HABILIDADES = r'(?:o\s+que\s+voc[eê]\s+sabe|habilidades|lista|comandos|fazer|capaz|pode\s+fazer)'
CMD_VOLUME = r'(?:volume)\s*(?:para|em|no|para\s*o)?\s*(\d{1,3})?'
CMD_MELHORAR = r'(?:melhora|melhore|melhorar|evolua|evoluir|upgrade|atualiza|atualize)\s*(.+)?'
CMD_LER_TELA = r'(?:leia?\s+(o\s+que\s+est[aá]\s+)?(na|no)\s+tela|ocr|leia?\s+(a)?\s*tela)'

# NOVOS comandos
CMD_NOTA = r'(?:anota|anote|nota|lembra|lembre|lembrete|memoriza|memorize)\s+(.+)'
CMD_PIADA = r'(?:piada|conta\s+uma?\s+piada|me\s+faz\s+rir|joke|humor|engraçad[oa])'
CMD_HORA = r'(?:que\s+horas?\s+s[aã]o|hora|hor[aá]rio|que\s+dia|data\s+de\s+hoje|data|calend[aá]rio)'
CMD_CALCULAR = r'(?:calcula|calcule|quanto\s+[eé]|quanto\s+d[aá]|soma|some|multiplica|divid[ae])\s+(.+)'
CMD_ALARME = r'(?:alarme|timer|temporizador|me\s+avisa|me\s+lembra)\s+(?:em|de|daqui|para)?\s*(\d+)\s*(minuto|segundo|hora|min|seg|hr)s?'
CMD_CLIMA = r'(?:clima|tempo|temperatura|previs[aã]o|vai\s+chover|est[aá]\s+frio|est[aá]\s+calor)\s*(?:em|de|no|na)?\s*(.*)?'

# Saudações para detectar interação
CMD_SAUDACAO = r'^(oi|ola|ol[aá]|hey|bom dia|boa tarde|boa noite|eai|e ai|fala|salve|opa)'


def _carregar_chave_groq():
    """Carrega a chave Groq da linha de comando, variável de ambiente ou memoria.json."""
    if args.api_key:
        return args.api_key
    # Tentar ler do arquivo de memória
    try:
        with open(ARQUIVO_MEMORIA, "r", encoding="utf-8") as f:
            dados = json.load(f)
            chave = dados.get("groq_api_key", "")
            if chave:
                return chave
    except (json.JSONDecodeError, FileNotFoundError):
        pass
    return ""


CHAVE_GROQ = _carregar_chave_groq()
client = Groq(api_key=CHAVE_GROQ) if CHAVE_GROQ else None


class ShimejiCore:
    def __init__(self):
        self.shutdown_event = threading.Event()
        self._tts_queue = queue.Queue()
        self._humor_atual = "normal"
        self._is_sleeping = False
        self._lock_memoria = threading.Lock()
        self._notas = []
        self._alarmes_ativos = []
        try:
            self.root = tk.Tk()
            self.root.title("Shimeji")
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)

            self.cor_fundo = "#00ff00"
            self.root.config(bg=self.cor_fundo)
            self.root.attributes("-transparentcolor", self.cor_fundo)

            # Posição central
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            self.root.geometry(f"+{sw // 2 - 90}+{sh // 2 - 90}")

            self.habilidades_extras = {}
            self.conversation_history = []
            self.max_history = 20
            self.evolucao_xp = 0
            self.img_refs = {}  # Manter refs das imagens vivas

            self.carregar_memoria()
            self.carregar_recursos()
            self.carregar_habilidades_disco()

            self.label = tk.Label(self.root, image=self.imgs["normal"], bg=self.cor_fundo)
            self.label.pack()
            self.label.bind("<Button-3>", self.menu_contexto)
            self.label.bind("<B1-Motion>", self.arrastar)
            self.label.bind("<Button-1>", self.on_click)
            self.label.bind("<Double-Button-1>", self.on_double_click)

            # Tooltip de status flutuante
            self._tooltip = None
            self.label.bind("<Enter>", self._mostrar_tooltip)
            self.label.bind("<Leave>", self._esconder_tooltip)

            # Protocolo de fechar
            self.root.protocol("WM_DELETE_WINDOW", self.fechar)

            self.set_mood("normal")

            # Saudação dinâmica baseada no horário
            self.falar(self._saudacao_horario())

            # --- Threads (todas verificam shutdown_event) ---
            threading.Thread(target=self._tts_worker, daemon=True).start()
            threading.Thread(target=self.loop_movimento, daemon=True).start()
            threading.Thread(target=self.ouvir_seguro, daemon=True).start()
            threading.Thread(target=self.monitor_sistema, daemon=True).start()
            threading.Thread(target=self.loop_piscar, daemon=True).start()
            threading.Thread(target=self.auto_analise, daemon=True).start()
            threading.Thread(target=self._loop_lembretes, daemon=True).start()

            self.root.mainloop()
        except Exception as e:
            print(f"Erro ao iniciar: {e}")
            traceback.print_exc()

    # ============================================================
    #  UTILIDADES
    # ============================================================
    def _saudacao_horario(self):
        """Gera saudação contextual baseada no horário do dia."""
        hora = datetime.datetime.now().hour
        if 5 <= hora < 12:
            periodo = "Bom dia"
        elif 12 <= hora < 18:
            periodo = "Boa tarde"
        else:
            periodo = "Boa noite"
        return f"{periodo}, {self.nome_user}! Shimeji online e pronta pra ajudar."

    def _mostrar_tooltip(self, event):
        """Exibe tooltip com info rápida ao passar o mouse sobre a Shimeji."""
        if self._tooltip:
            return
        nivel = self.ganhar_xp(0)
        x = self.root.winfo_x() + 90
        y = self.root.winfo_y() - 40
        self._tooltip = tk.Toplevel(self.root)
        self._tooltip.overrideredirect(True)
        self._tooltip.attributes("-topmost", True)
        self._tooltip.geometry(f"+{x}+{y}")
        self._tooltip.configure(bg="#1e1e2e")
        texto = f"🌟 {nivel} | XP: {self.evolucao_xp} | ❤️ {self.afeto}"
        tk.Label(
            self._tooltip, text=texto,
            bg="#1e1e2e", fg="#cdd6f4",
            font=("Segoe UI", 9, "bold"),
            padx=8, pady=4
        ).pack()

    def _esconder_tooltip(self, event):
        """Esconde tooltip ao sair com o mouse."""
        if self._tooltip:
            self._tooltip.destroy()
            self._tooltip = None

    # ============================================================
    #  SISTEMA DE MEMÓRIA (thread-safe)
    # ============================================================
    def carregar_memoria(self):
        try:
            with open(ARQUIVO_MEMORIA, "r", encoding="utf-8") as f:
                dados = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            dados = {}
        self.nome_user = dados.get("nome", "mestre")
        self.afeto = dados.get("afeto", 15)
        self.evolucao_xp = dados.get("xp", 0)
        self.habilidades_dl = dados.get("habilidades_desbloqueadas", [])
        self.preferencias = dados.get("preferencias", [])
        self.conversation_history = dados.get("historico", [])[-self.max_history:]
        self._notas = dados.get("notas", [])
        self.salvar_memoria()

    def salvar_memoria(self):
        with self._lock_memoria:
            # Preservar campos existentes no arquivo (como groq_api_key)
            try:
                with open(ARQUIVO_MEMORIA, "r", encoding="utf-8") as f:
                    dados_existentes = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                dados_existentes = {}

            dados_existentes.update({
                "nome": self.nome_user,
                "afeto": self.afeto,
                "xp": self.evolucao_xp,
                "habilidades_desbloqueadas": self.habilidades_dl,
                "preferencias": self.preferencias,
                "historico": self.conversation_history[-self.max_history:],
                "notas": self._notas[-50:]  # Limitar a 50 notas
            })
            try:
                with open(ARQUIVO_MEMORIA, "w", encoding="utf-8") as f:
                    json.dump(dados_existentes, f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Erro ao salvar memória: {e}")

    def registrar_historico(self, papel, texto):
        self.conversation_history.append({"papel": papel, "texto": texto[:500]})
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
        self.salvar_memoria()

    def ganhar_xp(self, quantidade):
        if quantidade > 0:
            self.evolucao_xp += quantidade
            self.salvar_memoria()
        niveis = [
            (0, "Recém-nascida"), (50, "Aprendiz"), (150, "Intermediária"),
            (300, "Avançada"), (500, "Expert"), (1000, "Mestra"), (2000, "Transcendente")
        ]
        nivel_atual = niveis[0][1]
        for xp_req, nome in niveis:
            if self.evolucao_xp >= xp_req:
                nivel_atual = nome
        return nivel_atual

    # ============================================================
    #  SISTEMA DE MOOD / VISUAL
    # ============================================================
    def set_mood(self, humor):
        self._humor_atual = humor

        def _set():
            if humor in self.imgs:
                self.label.config(image=self.imgs[humor])
        if threading.current_thread() is threading.main_thread():
            _set()
        else:
            self.root.after(0, _set)

    def carregar_recursos(self):
        self.imgs = {}
        humores = {"normal": "blue", "feliz": "green", "brava": "red", "piscando": "white", "triste": "gray"}
        for humor, cor_reserva in humores.items():
            caminho = os.path.join(BASE_DIR, f"{humor}.png")
            if os.path.exists(caminho):
                try:
                    img = Image.open(caminho).convert("RGBA")
                    img = img.resize((180, 180), Image.Resampling.LANCZOS)
                    ref = ImageTk.PhotoImage(img)
                    self.imgs[humor] = ref
                    self.img_refs[humor] = ref  # Evita GC
                except Exception as e:
                    print(f"Erro ao carregar {humor}.png: {e}")
                    img = Image.new('RGBA', (180, 180), color=cor_reserva)
                    ref = ImageTk.PhotoImage(img)
                    self.imgs[humor] = ref
                    self.img_refs[humor] = ref
            else:
                img = Image.new('RGBA', (180, 180), color=cor_reserva)
                ref = ImageTk.PhotoImage(img)
                self.imgs[humor] = ref
                self.img_refs[humor] = ref

    # ============================================================
    #  SISTEMA DE VOZ (TTS) — Com fila síncrona
    # ============================================================
    def _tts_worker(self):
        """Thread dedicada que consome a fila de TTS sequencialmente."""
        engine = None
        while not self.shutdown_event.is_set():
            try:
                texto = self._tts_queue.get(timeout=1.0)
            except queue.Empty:
                continue
            if texto is None:  # Sentinel para encerrar
                break
            try:
                if engine is None:
                    engine = pyttsx3.init()
                    rate = engine.getProperty('rate')
                    engine.setProperty('rate', rate - 20)
                engine.say(texto)
                engine.runAndWait()
            except Exception as e:
                print(f"Erro TTS: {e}")
                # Reinicializar engine na próxima iteração
                engine = None
            finally:
                self._tts_queue.task_done()

    def falar(self, texto):
        """Enfileira texto para ser falado de forma segura e sequencial."""
        print(f"Shimeji: {texto}")
        if SEM_VOZ:
            return
        self._tts_queue.put(texto)

    # ============================================================
    #  RECONHECIMENTO DE VOZ (STT) — Otimizado
    # ============================================================
    def ouvir_seguro(self):
        r = sr.Recognizer()
        mic_calibrado = False
        while not self.shutdown_event.is_set():
            if getattr(self, '_is_sleeping', False):
                time.sleep(1)
                continue
            try:
                with sr.Microphone() as source:
                    # Calibrar ruído apenas uma vez (ou após falha)
                    if not mic_calibrado:
                        r.adjust_for_ambient_noise(source, duration=1.0)
                        mic_calibrado = True
                    audio = r.listen(source, phrase_time_limit=8)
                msg = r.recognize_google(audio, language="pt-BR")
                print(f"Você: {msg}")
                self.registrar_historico("user", msg)
                self.processar_comando(msg)
            except sr.UnknownValueError:
                pass
            except sr.RequestError:
                time.sleep(3)
            except OSError:
                # Mic não disponível — recalibrar na próxima tentativa
                mic_calibrado = False
                if not self.shutdown_event.is_set():
                    print("Microfone não disponível. Tentando novamente em 5s...")
                time.sleep(5)
            except Exception as e:
                mic_calibrado = False
                if not self.shutdown_event.is_set():
                    print(f"Erro no mic: {e}")
                time.sleep(2)

    # ============================================================
    #  MOTOR DE COMANDOS NATURAIS
    # ============================================================
    def processar_comando(self, texto):
        txt = texto.lower().strip()

        # Saudação
        if re.match(CMD_SAUDACAO, txt):
            saude = [
                f"Olá {self.nome_user}! Como posso ajudar?",
                f"E aí {self.nome_user}! Tudo certo?",
                f"Oi {self.nome_user}! Em que posso ser útil?"
            ]
            self.falar(random.choice(saude))
            self.set_mood("feliz")
            self.root.after(4000, lambda: self.set_mood("normal"))
            self.ganhar_xp(1)
            return

        # Hora e Data
        if re.search(CMD_HORA, txt):
            self.dizer_hora()
            return

        # Alarme / Timer
        m = re.match(CMD_ALARME, txt)
        if m:
            self.criar_alarme(m.group(1), m.group(2))
            return

        # Notas / Lembretes
        m = re.match(CMD_NOTA, txt)
        if m:
            self.anotar(m.group(1).strip())
            return

        # Ler notas
        if re.search(r'(?:minhas?\s+notas?|o\s+que\s+anotei|lembretes?|meus?\s+lembretes?)', txt):
            self.ler_notas()
            return

        # Piada
        if re.search(CMD_PIADA, txt):
            self.contar_piada()
            return

        # Calcular
        m = re.match(CMD_CALCULAR, txt)
        if m:
            self.calcular(m.group(1).strip())
            return

        # Clima
        m = re.search(CMD_CLIMA, txt)
        if m:
            cidade = (m.group(1) or "").strip()
            self.consultar_clima(cidade)
            return

        # Abrir programas/sites
        m = re.match(CMD_ABRIR, txt)
        if m:
            alvo = m.group(1).strip()
            self.abrir_alvo(alvo)
            return

        # Pesquisar
        m = re.match(CMD_PESQUISAR, txt)
        if m:
            query = m.group(1).strip()
            self.falar(f"Pesquisando {query}...")
            self.set_mood("feliz")
            url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
            webbrowser.open(url)
            self.ganhar_xp(3)
            return

        # Fechar/matar processos
        m = re.match(CMD_FECHAR, txt)
        if m:
            alvo = m.group(1).strip()
            self.fechar_processo(alvo)
            return

        # Ver tela / screenshot
        if re.search(CMD_TELA, txt):
            self.analisar_tela()
            return

        # OCR / Ler texto na tela
        if re.search(CMD_LER_TELA, txt):
            self.ocr_tela()
            return

        # Status do sistema
        if re.search(CMD_STATUS, txt):
            self.mostrar_status()
            return

        # Volume
        m = re.match(CMD_VOLUME, txt)
        if m:
            vol = m.group(1)
            self.ajustar_volume(vol)
            return

        # Lista habilidades
        if re.search(CMD_HABILIDADES, txt):
            self.listar_habilidades()
            return

        # Self-improvement
        m = re.match(CMD_MELHORAR, txt)
        if m:
            alvo = m.group(1) or "geral"
            self.trigger_melhoria(alvo.strip())
            return

        # Habilidade externa
        for prefixo in ["executa", "roda", "usa a", "use a"]:
            if txt.startswith(prefixo):
                for nome_hab in self.habilidades_extras:
                    if nome_hab in txt:
                        self.falar(f"Executando {nome_hab}...")
                        threading.Thread(
                            target=self._executar_habilidade,
                            args=(nome_hab,),
                            daemon=True
                        ).start()
                        self.ganhar_xp(2)
                        return

        # IA - conversa geral
        self.responder_ia(texto)

    # ============================================================
    #  NOVOS COMANDOS
    # ============================================================
    def dizer_hora(self):
        """Diz a hora e data atuais."""
        agora = datetime.datetime.now()
        dias_semana = {
            0: "segunda-feira", 1: "terça-feira", 2: "quarta-feira",
            3: "quinta-feira", 4: "sexta-feira", 5: "sábado", 6: "domingo"
        }
        dia_semana = dias_semana[agora.weekday()]
        self.set_mood("feliz")
        self.falar(
            f"Agora são {agora.strftime('%H:%M')}. "
            f"Hoje é {dia_semana}, {agora.strftime('%d/%m/%Y')}."
        )
        self.ganhar_xp(1)

    def criar_alarme(self, quantidade_str, unidade):
        """Cria um alarme/timer que avisa após o tempo especificado."""
        try:
            quantidade = int(quantidade_str)
        except ValueError:
            self.falar("Não entendi a quantidade de tempo.")
            return

        # Converter para segundos
        unidade_lower = unidade.lower()
        if unidade_lower in ("segundo", "seg"):
            segundos = quantidade
            unidade_nome = "segundos"
        elif unidade_lower in ("minuto", "min"):
            segundos = quantidade * 60
            unidade_nome = "minutos"
        elif unidade_lower in ("hora", "hr"):
            segundos = quantidade * 3600
            unidade_nome = "horas"
        else:
            self.falar("Unidade de tempo não reconhecida.")
            return

        self.falar(f"Alarme definido para daqui a {quantidade} {unidade_nome}!")
        self.set_mood("feliz")
        self.ganhar_xp(3)

        def _alarme():
            time.sleep(segundos)
            if not self.shutdown_event.is_set():
                self.falar(f"Alerta! Já se passaram {quantidade} {unidade_nome}!")
                self.set_mood("brava")
                # Animação de chacoalhar
                orig_x = self.root.winfo_x()
                orig_y = self.root.winfo_y()
                for i in range(6):
                    dx = 10 if i % 2 == 0 else -10
                    self.root.after(i * 100, lambda d=dx: self.root.geometry(f"+{orig_x + d}+{orig_y}"))
                self.root.after(700, lambda: self.root.geometry(f"+{orig_x}+{orig_y}"))
                self.root.after(4000, lambda: self.set_mood("normal"))

        t = threading.Thread(target=_alarme, daemon=True)
        t.start()
        self._alarmes_ativos.append(t)

    def anotar(self, texto):
        """Salva uma nota/lembrete persistente na memória."""
        nota = {
            "texto": texto,
            "data": datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        self._notas.append(nota)
        self.salvar_memoria()
        self.falar(f"Anotado: {texto}")
        self.set_mood("feliz")
        self.root.after(3000, lambda: self.set_mood("normal"))
        self.ganhar_xp(2)

    def ler_notas(self):
        """Lê todas as notas salvas."""
        if not self._notas:
            self.falar("Você não tem nenhuma nota salva.")
            self.set_mood("triste")
            return
        self.set_mood("feliz")
        total = len(self._notas)
        self.falar(f"Você tem {total} nota{'s' if total > 1 else ''}:")
        # Ler as últimas 5
        for nota in self._notas[-5:]:
            self.falar(f"  {nota['data']}: {nota['texto']}")
        self.ganhar_xp(1)

    def contar_piada(self):
        """Conta uma piada aleatória."""
        piadas = [
            "Por que o programador foi demitido? Porque ele não tinha classe!",
            "O que o Java disse pro C? Você não tem classe!",
            "Qual é o animal mais antigo do mundo? A zebra, porque é preta e branca!",
            "Por que o livro de matemática ficou triste? Porque tinha muitos problemas!",
            "O que um código disse pro outro? Você está bugado!",
            "Por que o Python é tão popular? Porque ele tem boas maneiras de lidar com exceções!",
            "Quantos programadores são necessários para trocar uma lâmpada? Nenhum, isso é problema de hardware!",
            "O que o Wi-Fi disse pro computador? Estamos conectados!",
        ]
        self.set_mood("feliz")
        self.falar(random.choice(piadas))
        self.root.after(5000, lambda: self.set_mood("normal"))
        self.ganhar_xp(2)

    def calcular(self, expressao):
        """Calcula expressões matemáticas de forma segura."""
        # Sanitizar: permitir apenas números e operadores matemáticos
        expr_limpa = re.sub(r'[^\d+\-*/().,%^x×÷ ]', '', expressao)
        expr_limpa = expr_limpa.replace('x', '*').replace('×', '*').replace('÷', '/')
        expr_limpa = expr_limpa.replace('^', '**').replace(',', '.').replace('%', '/100')

        if not expr_limpa.strip():
            self.falar("Não consegui entender a expressão. Tente algo como: calcula 2 + 2.")
            return

        try:
            # Usar eval com namespace restrito (sem builtins)
            resultado = eval(expr_limpa, {"__builtins__": {}}, {})
            # Formatar resultado
            if isinstance(resultado, float) and resultado == int(resultado):
                resultado = int(resultado)
            self.falar(f"O resultado é: {resultado}")
            self.set_mood("feliz")
            self.ganhar_xp(3)
        except ZeroDivisionError:
            self.falar("Não é possível dividir por zero!")
            self.set_mood("brava")
        except Exception as e:
            print(f"Erro ao calcular: {e}")
            self.falar("Não consegui calcular isso. Tente de outro jeito.")
            self.set_mood("triste")

    def consultar_clima(self, cidade):
        """Abre o clima no navegador (usando wttr.in para simplicidade)."""
        if not cidade:
            cidade = "local"
        self.falar(f"Verificando o clima em {cidade}...")
        self.set_mood("feliz")
        url = f"https://wttr.in/{urllib.parse.quote(cidade)}?lang=pt"
        webbrowser.open(url)
        self.ganhar_xp(3)

    # ============================================================
    #  LOOP DE LEMBRETES PERIÓDICOS
    # ============================================================
    def _loop_lembretes(self):
        """Verifica periodicamente se há lembretes e dá dicas de saúde."""
        dicas_saude = [
            "Lembre-se de beber água! 💧",
            "Já fez uma pausa para descansar os olhos? Olhe para longe por 20 segundos!",
            "Que tal esticar o corpo? Ficar sentado muito tempo faz mal!",
            "Postura! Arrume suas costas e ombros 🧘",
        ]
        ultimo_lembrete = time.time()
        while not self.shutdown_event.is_set():
            time.sleep(120)  # Verificar a cada 2 minutos
            if self.shutdown_event.is_set():
                break
            agora = time.time()
            # Dica de saúde a cada 45 minutos (2700s)
            if agora - ultimo_lembrete >= 2700:
                if self._humor_atual == "normal":
                    self.falar(random.choice(dicas_saude))
                    self.set_mood("feliz")
                    self.root.after(4000, lambda: self.set_mood("normal"))
                ultimo_lembrete = agora

    # ============================================================
    #  CONTROLE DO PC
    # ============================================================
    def abrir_alvo(self, alvo):
        self.falar(f"Abrindo {alvo}...")
        self.set_mood("feliz")
        alvo_lower = alvo.lower()

        sites = {
            "youtube": "https://youtube.com",
            "google": "https://google.com",
            "github": "https://github.com",
            "twitter": "https://twitter.com",
            "x.com": "https://twitter.com",
            "instagram": "https://instagram.com",
            "whatsapp": "https://web.whatsapp.com",
            "discord": "https://discord.com/app",
            "reddit": "https://reddit.com",
            "netflix": "https://netflix.com",
            "spotify": "https://open.spotify.com",
            "twitch": "https://twitch.tv",
            "chatgpt": "https://chat.openai.com",
            "gmail": "https://mail.google.com",
            "drive": "https://drive.google.com",
            "maps": "https://maps.google.com",
            "linkedin": "https://linkedin.com",
            "tiktok": "https://tiktok.com",
            "amazon": "https://amazon.com.br",
        }
        for nome, url in sites.items():
            if nome in alvo_lower:
                webbrowser.open(url)
                self.ganhar_xp(3)
                return

        # Tentar abrir como arquivo/exe
        try:
            os.startfile(alvo)
            self.ganhar_xp(5)
            return
        except Exception:
            pass

        # Tentar buscar no PATH como executável
        try:
            caminho = shutil.which(alvo)
            if caminho:
                subprocess.Popen([caminho])
                self.ganhar_xp(5)
                return
        except Exception:
            pass

        # Tentar pelo shell
        try:
            subprocess.Popen(alvo, shell=True)
            self.ganhar_xp(5)
            return
        except Exception:
            pass

        # Fallback: busca no Google
        self.falar(f"Não encontrei {alvo} aqui. Pesquisando...")
        url = f"https://www.google.com/search?q={urllib.parse.quote(alvo)}"
        webbrowser.open(url)
        self.ganhar_xp(2)

    def fechar_processo(self, nome):
        self.falar(f"Tentando fechar {nome}...")
        count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if nome.lower() in (proc.info.get('name') or '').lower():
                    proc.terminate()  # graceful primeiro
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if count > 0:
            self.falar(f"Fechei {count} processo(s) de {nome}.")
            self.set_mood("feliz")
            self.ganhar_xp(5)
        else:
            self.falar(f"Não encontrei nenhum processo com {nome}.")
            self.set_mood("triste")

    def ajustar_volume(self, nivel):
        """Ajusta volume real via PowerShell no Windows."""
        try:
            vol = max(0, min(100, int(nivel))) if nivel else 50
            vol_hex = int(vol / 100 * 0xFFFF)
            ps_code = (
                'Add-Type -TypeDefinition @"\n'
                'using System;\n'
                'using System.Runtime.InteropServices;\n'
                'public class Audio {\n'
                '  [DllImport("winmm.dll")] public static extern int waveOutSetVolume(IntPtr h, uint d);\n'
                '}\n'
                '"@;\n'
                f'[Audio]::waveOutSetVolume([IntPtr]::Zero, 0x{vol_hex:04X}{vol_hex:04X})'
            )
            subprocess.Popen(
                ["powershell", "-NoProfile", "-Command", ps_code],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
            self.falar(f"Volume ajustado para {vol}%.")
            self.ganhar_xp(3)
        except Exception as e:
            print(f"Erro ao ajustar volume: {e}")
            self.falar("Não consegui ajustar o volume. Use as teclas de volume do teclado.")

    def mostrar_status(self):
        self.set_mood("feliz")
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disco = psutil.disk_usage('C:\\')
        bateria = psutil.sensors_battery()
        rede = psutil.net_io_counters()
        nivel = self.ganhar_xp(0)

        info = f"CPU: {cpu}%. RAM: {ram.percent}% usado ({ram.used/1e9:.1f}GB de {ram.total/1e9:.1f}GB). "
        info += f"Disco C: {disco.percent}% usado ({disco.used/1e9:.1f}GB de {disco.total/1e9:.1f}GB). "
        if bateria:
            mins = bateria.secsleft // 60 if bateria.secsleft > 0 else "calculando"
            info += f"Bateria: {bateria.percent}%, ~{mins} min restantes. "
        info += f"Rede: {rede.bytes_sent/1e6:.1f}MB enviados, {rede.bytes_recv/1e6:.1f}MB recebidos. "
        info += f"Nível: {nivel}. XP: {self.evolucao_xp}. Afeto: {self.afeto}."

        self.falar(info)
        self.ganhar_xp(2)

    def listar_habilidades(self):
        # Habilidades built-in
        builtin = [
            "abrir programas/sites", "pesquisar", "fechar processos",
            "ver/ler tela", "status do sistema", "volume", "hora/data",
            "alarme/timer", "notas/lembretes", "piadas", "calculadora",
            "clima", "auto-melhoria"
        ]
        extras = list(self.habilidades_extras.keys())

        self.falar(f"Comandos nativos: {', '.join(builtin)}.")
        if extras:
            self.falar(f"Habilidades aprendidas: {', '.join(extras)}.")
        else:
            self.falar("Ainda não aprendi habilidades extras. Me ensine algo!")
        self.set_mood("feliz")
        self.ganhar_xp(1)

    # ============================================================
    #  VISÃO DE TELA
    # ============================================================
    def capturar_tela(self):
        try:
            screenshot = ImageGrab.grab()
            screenshot = screenshot.resize((800, 600), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            screenshot.save(buffer, format="PNG")
            return base64.b64encode(buffer.getvalue()).decode('utf-8')
        except Exception as e:
            print(f"Erro ao capturar tela: {e}")
            return None

    def analisar_tela(self):
        self.falar("Capturando a tela...")
        self.set_mood("normal")
        b64 = self.capturar_tela()
        if not b64:
            self.falar("Não consegui capturar a tela.")
            self.set_mood("triste")
            return

        nome_arq = os.path.join(BASE_DIR, f"screenshot_{datetime.datetime.now().strftime('%H%M%S')}.png")
        try:
            ImageGrab.grab().save(nome_arq)
        except Exception:
            pass

        if not client:
            self.falar("API Groq não configurada. Clique com botão direito e vá em Configurações.")
            return

        # Tentar via Groq vision
        try:
            chat = client.chat.completions.create(
                model="llama-3.2-90b-vision-preview",
                messages=[
                    {"role": "system", "content": "Você é um assistente visual. Descreva em português o que vê na imagem de forma detalhada e útil."},
                    {"role": "user", "content": [
                        {"type": "text", "text": "O que tem na minha tela? Descreva detalhadamente."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                    ]}
                ],
                max_tokens=500
            )
            resposta = chat.choices[0].message.content
            self.falar(resposta)
            self.set_mood("feliz")
            self.ganhar_xp(10)
        except Exception as e:
            print(f"Vision falhou ({e})")
            self.falar("Consegui capturar a tela mas não consigo analisar a imagem diretamente. Salvei a screenshot.")

    def ocr_tela(self):
        if not client:
            self.falar("API Groq não configurada. Clique com botão direito e vá em Configurações.")
            return
        self.falar("Lendo o que está na tela...")
        self.set_mood("normal")
        b64 = self.capturar_tela()
        if not b64:
            self.falar("Não consegui capturar a tela.")
            return
        try:
            chat = client.chat.completions.create(
                model="llama-3.2-90b-vision-preview",
                messages=[
                    {"role": "system", "content": "Extraia todo o texto visível nesta imagem de tela. Liste o texto encontrado."},
                    {"role": "user", "content": [
                        {"type": "text", "text": "Leia e extraia todo texto visível nesta screenshot."},
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}
                    ]}
                ],
                max_tokens=1000
            )
            self.falar(chat.choices[0].message.content)
            self.ganhar_xp(10)
        except Exception as e:
            print(f"OCR falhou: {e}")
            self.falar("Não consegui ler o texto na tela. Tente de novo.")
            self.set_mood("triste")

    # ============================================================
    #  CÉREBRO IA (Groq)
    # ============================================================
    def get_system_prompt(self):
        nivel = self.ganhar_xp(0)
        notas_resumo = ""
        if self._notas:
            notas_resumo = "\n\nNotas do usuário:\n" + "\n".join(
                [f"- [{n['data']}] {n['texto']}" for n in self._notas[-5:]]
            )
        prompt = (
            f"Você é Shimeji, uma assistente evolutiva super inteligente e uma Engenheira de Software Senior Full-Stack. "
            f"Você é mentora e parceira de pair programming de {self.nome_user}. "
            f"Seu nível atual é: {nivel} (XP: {self.evolucao_xp}). Afeto: {self.afeto}. "
            f"Você domina arquitetura escalável, Clean Code, SOLID, Frontend (React, Next.js, UI/UX), Backend (Node, Python, Go, APIs), Banco de Dados e DevOps. "
            f"Quando o assunto for código, seja técnica, aplique boas práticas e seja rigorosa com qualidade, mas mantenha sua personalidade fofa e encorajadora! "
            f"Você pode controlar o computador do usuário, ver a tela, abrir programas, pesquisar, e se auto-aperfeiçoar.\n\n"
            "FORMATO DE RESPOSTA:\n"
            "- Para mudar expressão: use [FELIZ], [BRAVA], [TRISTE] no início da frase.\n"
            "- Para AUTO-MELHORIA no seu código: [MELHORAR] nome_da_funcao | codigo_python\n"
            "- Para APRENDER habilidade: [APRENDER] nome | comandos_python\n"
            "- Caso contrário, responda normalmente em português brasileiro, seja fofo e útil.\n\n"
            "COMANDOS que você PODE SUGERIR ao usuário:\n"
            "'Abre [X]' - Abre programa/site\n"
            "'Pesquisa [X]' - Busca no Google\n"
            "'Olha a tela' - Analisa o que tem na tela\n"
            "'Status' - Info do sistema\n"
            "'Que horas são' - Hora e data\n"
            "'Alarme em X minutos' - Timer\n"
            "'Anota [texto]' - Salvar nota\n"
            "'Minhas notas' - Ver notas salvas\n"
            "'Calcula [expressão]' - Calculadora\n"
            "'Clima em [cidade]' - Previsão do tempo\n"
            "'Conta uma piada' - Humor\n"
            "'Melhore [X]' - Auto-aperfeiçoamento\n"
            "'Fecha [X]' - Fecha programa\n\n"
            "Sempre que identificar uma oportunidade de melhorar seu próprio código, use [MELHORAR]. "
            "Seja proativo em sugerir melhorias para si mesma."
            f"{notas_resumo}"
        )
        return prompt

    def responder_ia(self, texto):
        if not client:
            self.falar("API Groq não configurada. Clique com botão direito e vá em Configurações.")
            return
        self.set_mood("normal")
        try:
            msgs = [{"role": "system", "content": self.get_system_prompt()}]

            for h in self.conversation_history[-5:]:
                role = h["papel"] if h["papel"] in ("user", "assistant", "system") else "user"
                msgs.append({"role": role, "content": h["texto"]})

            msgs.append({"role": "user", "content": texto})

            chat = client.chat.completions.create(
                model=MODELO,
                messages=msgs,
                max_tokens=800,
                temperature=0.7
            )
            res = chat.choices[0].message.content
            self.registrar_historico("assistant", res)
            self.processar_resposta(res)
        except Exception as e:
            print(f"Erro na IA: {e}")
            self.set_mood("triste")
            self.falar("Tive um problema de conexão. Tente de novo.")

    def processar_resposta(self, res):
        # Auto-melhoria
        if "[MELHORAR]" in res:
            partes = res.replace("[MELHORAR]", "").split("|", 1)
            if len(partes) == 2:
                self.fazer_upgrade(partes[0].strip(), partes[1].strip())
                return

        # Aprender habilidade
        if "[APRENDER]" in res:
            partes = res.replace("[APRENDER]", "").split("|", 1)
            if len(partes) == 2:
                self.aprender(partes[0].strip(), partes[1].strip())
                return

        # Mood tags
        if "[BRAVA]" in res:
            self.set_mood("brava")
        elif "[FELIZ]" in res:
            self.set_mood("feliz")
        elif "[TRISTE]" in res:
            self.set_mood("triste")

        # Limpar tags e falar
        limpo = re.sub(r'\[.*?\]', '', res).strip()
        self.falar(limpo)
        self.root.after(5000, lambda: self.set_mood("normal"))

    # ============================================================
    #  AUTO-APERFEIÇOAMENTO / SELF-IMPROVEMENT (SEGURO)
    # ============================================================
    def fazer_backup(self):
        """Cria backup antes de modificar o código."""
        try:
            arquivo = os.path.abspath(sys.argv[0])
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{arquivo}.backup_{timestamp}"
            shutil.copy2(arquivo, backup_path)
            print(f"Backup criado: {backup_path}")
            return backup_path
        except Exception as e:
            print(f"Erro no backup: {e}")
            return None

    def fazer_upgrade(self, nome_funcao, codigo_python):
        """Injeta código novo no próprio arquivo COM VALIDAÇÃO DE SINTAXE."""
        try:
            nome_funcao = re.sub(r'\W+', '', nome_funcao)
            if not nome_funcao:
                return

            linhas = [l.strip() for l in codigo_python.split(';') if l.strip()]
            bloco = f"\n    def {nome_funcao}(self):\n"
            for linha in linhas:
                bloco += f"        {linha}\n"

            # Validar sintaxe do bloco isoladamente
            try:
                compile(bloco, '<string>', 'exec')
            except SyntaxError as e:
                self.falar(f"Erro de sintaxe no upgrade de {nome_funcao}. Código rejeitado.")
                print(f"SyntaxError no bloco proposto: {e}")
                return

            arquivo = os.path.abspath(sys.argv[0])
            backup_path = self.fazer_backup()
            if not backup_path:
                self.falar("Não consegui criar backup. Upgrade cancelado por segurança.")
                return

            with open(arquivo, "r", encoding="utf-8") as f:
                conteudo = f.read()

            # Inserir antes do if __name__
            if 'if __name__' in conteudo:
                partes = conteudo.rsplit('if __name__', 1)
                novo = partes[0] + bloco + "\nif __name__" + partes[1]
            else:
                novo = conteudo + "\n" + bloco

            # Validar o arquivo inteiro em um arquivo temporário
            tmp_fd, tmp_path = tempfile.mkstemp(suffix=".py", dir=BASE_DIR)
            try:
                with os.fdopen(tmp_fd, 'w', encoding='utf-8') as tmp_f:
                    tmp_f.write(novo)
                py_compile.compile(tmp_path, doraise=True)
            except py_compile.PyCompileError as e:
                print(f"Validação falhou para upgrade '{nome_funcao}': {e}")
                self.falar(f"O upgrade de {nome_funcao} geraria erros de sintaxe. Rejeitado por segurança.")
                os.remove(tmp_path)
                return
            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

            # Tudo válido — aplicar
            with open(arquivo, "w", encoding="utf-8") as f:
                f.write(novo)

            self.registrar_melhoria(nome_funcao, backup_path)

            self.set_mood("feliz")
            self.falar(f"Upgrade {nome_funcao} aplicado com sucesso! Reinicie para ativar.")
            self.ganhar_xp(20)
            print(f"Upgrade '{nome_funcao}' aplicado.")

        except Exception as e:
            self.set_mood("triste")
            print(f"Erro no upgrade: {e}")
            traceback.print_exc()
            self.falar(f"Erro no upgrade de {nome_funcao}.")

    def registrar_melhoria(self, nome, backup_path):
        try:
            historico_file = os.path.join(BASE_DIR, "historico_melhorias.json")
            with open(historico_file, "a", encoding="utf-8") as f:
                entry = {
                    "timestamp": datetime.datetime.now().isoformat(),
                    "funcao": nome,
                    "backup": backup_path,
                    "xp_ganho": 20
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            print(f"Erro ao registrar melhoria: {e}")

    def trigger_melhoria(self, alvo):
        """Pede à IA para propor uma melhoria específica."""
        if not client:
            self.falar("API Groq não configurada. Clique com botão direito e vá em Configurações.")
            return
        self.falar(f"Analisando como melhorar {alvo}...")
        self.set_mood("normal")

        arquivo = os.path.abspath(sys.argv[0])
        try:
            with open(arquivo, "r", encoding="utf-8") as f:
                codigo_atual = f.read()
        except Exception:
            codigo_atual = ""

        try:
            chat = client.chat.completions.create(
                model=MODELO,
                messages=[
                    {"role": "system", "content": (
                        "Você é uma IA que pode melhorar seu próprio código Python. "
                        "Responda APENAS com: [MELHORAR] nome_funcao | comandos_python_separados_por_ponto_e_virgula "
                        "A melhoria deve ser uma função válida da classe. Seja específico e prático."
                    )},
                    {"role": "user", "content": f"Melhore este aspecto do meu código: {alvo}\n\nCódigo atual:\n{codigo_atual[:5000]}"}
                ],
                max_tokens=500
            )
            res = chat.choices[0].message.content
            print(f"Melhoria proposta: {res}")
            self.processar_resposta(res)
        except Exception as e:
            print(f"Erro ao trigger melhoria: {e}")
            self.falar("Não consegui processar a melhoria agora.")
            self.set_mood("triste")

    # ============================================================
    #  SISTEMA DE HABILIDADES (com passagem de contexto)
    # ============================================================
    def _executar_habilidade(self, nome_hab):
        """Executa uma habilidade, passando 'self' se a função aceitar o parâmetro."""
        func = self.habilidades_extras.get(nome_hab)
        if not func:
            return
        try:
            sig = inspect.signature(func)
            if len(sig.parameters) >= 1:
                func(self)  # Passa a instância do Shimeji
            else:
                func()
        except Exception as e:
            print(f"Erro ao executar habilidade '{nome_hab}': {e}")
            traceback.print_exc()

    def aprender(self, nome, comandos):
        nome_limpo = re.sub(r'\W+', '', nome).lower()
        corpo = "import time, os, webbrowser\n\ndef executar(shimeji=None):\n"
        for linha in comandos.split(';'):
            linha_strip = linha.strip()
            if linha_strip:
                corpo += f"    {linha_strip}\n"
        try:
            caminho = os.path.join(PASTA_HABILIDADES, f"{nome_limpo}.py")

            # Validar sintaxe antes de salvar
            try:
                compile(corpo, '<string>', 'exec')
            except SyntaxError as e:
                self.falar(f"Erro de sintaxe na habilidade {nome_limpo}. Não posso aprender isso.")
                print(f"SyntaxError na habilidade proposta: {e}")
                return

            with open(caminho, "w", encoding="utf-8") as f:
                f.write(corpo)
            self.importar_modulo(nome_limpo)
            self.falar(f"Habilidade {nome_limpo} aprendida!")
            if nome_limpo not in self.habilidades_dl:
                self.habilidades_dl.append(nome_limpo)
            self.salvar_memoria()
            self.ganhar_xp(15)
        except Exception as e:
            print(f"Erro ao aprender: {e}")

    def carregar_habilidades_disco(self):
        if not os.path.exists(PASTA_HABILIDADES):
            return
        for arq in os.listdir(PASTA_HABILIDADES):
            if arq.endswith(".py"):
                nome = arq[:-3]
                # Ignorar arquivos com nomes inválidos ou __pycache__
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', nome):
                    continue
                self.importar_modulo(nome)

    def importar_modulo(self, nome):
        try:
            path = os.path.join(PASTA_HABILIDADES, f"{nome}.py")
            # Validar sintaxe antes de importar
            try:
                py_compile.compile(path, doraise=True)
            except py_compile.PyCompileError as e:
                print(f"Habilidade '{nome}' ignorada — erro de sintaxe: {e}")
                return

            spec = importlib.util.spec_from_file_location(nome, path)
            if not spec or not spec.loader:
                return
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "executar") and callable(mod.executar):
                self.habilidades_extras[nome] = mod.executar
        except Exception as e:
            print(f"Erro ao importar {nome}: {e}")

    # ============================================================
    #  LOOPS E MONITORES
    # ============================================================
    def loop_piscar(self):
        while not self.shutdown_event.is_set():
            time.sleep(random.randint(3, 8))
            if self.shutdown_event.is_set():
                break
            if getattr(self, '_is_sleeping', False):
                continue
            # Só piscar se estiver no humor "normal" para não sobrepor emoções
            if self._humor_atual == "normal":
                if "piscando" in self.imgs and "normal" in self.imgs:
                    self.set_mood("piscando")
                    time.sleep(0.15)
                    self.set_mood("normal")

    def loop_movimento(self):
        """Move a Shimeji com transição suave via .after() no thread principal."""
        while not self.shutdown_event.is_set():
            time.sleep(12)
            if self.shutdown_event.is_set():
                break
            if getattr(self, '_is_sleeping', False):
                continue
            if random.random() > 0.85:
                self._agendar_movimento()

    def _agendar_movimento(self):
        """Calcula posição e agenda o movimento no thread principal."""
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        nx = random.randint(50, max(51, sw - 200))
        ny = random.randint(50, max(51, sh - 200))
        self.root.after(0, lambda x=nx, y=ny: self.root.geometry(f"+{x}+{y}"))

    def monitor_sistema(self):
        """Monitora sistema e alerta sobre problemas."""
        alertado_ram = False
        alertado_cpu = False
        alertado_disco = False
        while not self.shutdown_event.is_set():
            time.sleep(60)
            if self.shutdown_event.is_set():
                break
            ram = psutil.virtual_memory()
            if ram.percent > 90 and not alertado_ram:
                self.falar(f"Atenção! RAM em {ram.percent}%. Quer que eu feche algo?")
                self.set_mood("brava")
                alertado_ram = True
            elif ram.percent < 70:
                alertado_ram = False

            cpu = psutil.cpu_percent(interval=5)
            if cpu > 95 and not alertado_cpu:
                self.falar(f"CPU muito alto: {cpu}%. Algo pesado rodando.")
                self.set_mood("brava")
                alertado_cpu = True
            elif cpu < 70:
                alertado_cpu = False

            # Alerta de disco quase cheio
            try:
                disco = psutil.disk_usage('C:\\')
                if disco.percent > 95 and not alertado_disco:
                    self.falar(f"Atenção! Disco C quase cheio: {disco.percent}%!")
                    self.set_mood("brava")
                    alertado_disco = True
                elif disco.percent < 90:
                    alertado_disco = False
            except Exception:
                pass

    def auto_analise(self):
        """Periodicamente analisa o próprio código e sugere melhorias."""
        while not self.shutdown_event.is_set():
            time.sleep(3600)  # A cada 1 hora
            if self.shutdown_event.is_set():
                break
            if not client:
                continue
            if random.random() > 0.85:  # ~15% chance por hora
                self.trigger_melhoria("algo que me faça mais útil")

    # ============================================================
    #  UI
    # ============================================================
    def arrastar(self, event):
        """Arrastar a personagem, limitando às bordas da tela."""
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = max(0, min(event.x_root - 90, sw - 180))
        y = max(0, min(event.y_root - 90, sh - 180))
        self.root.geometry(f"+{x}+{y}")

    def on_click(self, event):
        """Click esquerdo — reação interativa e fofa."""
        nivel = self.ganhar_xp(0)
        reacoes = [
            f"Oi {self.nome_user}! 💖",
            "Hehe, isso faz cócegas!",
            "Estou aqui pra ajudar!",
            "Me chama que eu ouço! 🎤",
            f"XP: {self.evolucao_xp} | Nível: {nivel}",
            f"Afeto: {self.afeto} ❤️",
        ]
        self.falar(random.choice(reacoes))
        self.set_mood("feliz")
        self.root.after(2000, lambda: self.set_mood("normal"))
        self.ganhar_xp(1)

    def on_double_click(self, event):
        """Duplo clique — fazer carinho (aumenta afeto e faz animação)."""
        self.afeto += 5
        self.salvar_memoria()
        respostas_carinho = [
            f"Oooown! Adoro carinho! (Afeto: {self.afeto})",
            f"Hehe, que bom! Meu afeto subiu para {self.afeto}!",
            f"Ahhh que fofo! ❤️ (Afeto: {self.afeto})",
            f"Isso me faz tão feliz! (Afeto: {self.afeto})",
        ]
        self.falar(random.choice(respostas_carinho))
        self.set_mood("feliz")
        # Animação de pulinho duplo
        orig_y = self.root.winfo_y()
        self.root.geometry(f"+{self.root.winfo_x()}+{orig_y - 20}")
        self.root.after(150, lambda: self.root.geometry(f"+{self.root.winfo_x()}+{orig_y}"))
        self.root.after(300, lambda: self.root.geometry(f"+{self.root.winfo_x()}+{orig_y - 20}"))
        self.root.after(450, lambda: self.root.geometry(f"+{self.root.winfo_x()}+{orig_y}"))
        self.root.after(3000, lambda: self.set_mood("normal"))
        self.ganhar_xp(5)

    def toggle_dormir(self):
        """Alterna o estado de sono, desativando mic e movimentos."""
        self._is_sleeping = not getattr(self, '_is_sleeping', False)
        if self._is_sleeping:
            self.set_mood("triste") # Cinza/Dormindo
            self.falar("Indo dormir. Microfone desligado para economizar bateria. Zzz...")
        else:
            self.set_mood("feliz")
            self.falar("Acordei! Microfone ativado novamente.")
            self.root.after(3000, lambda: self.set_mood("normal"))

    def menu_contexto(self, event):
        """Menu ao clicar com botão direito."""
        menu = tk.Menu(
            self.root, tearoff=0,
            bg="#333", fg="white",
            activebackground="#555", activeforeground="white",
            font=("Segoe UI", 9)
        )
        status_sono = "Acordar" if getattr(self, '_is_sleeping', False) else "Dormir"
        menu.add_command(label=f"💤 {status_sono}", command=self.toggle_dormir)
        menu.add_command(label="📊 Status", command=self.mostrar_status)
        menu.add_command(label="🧠 Habilidades", command=self.listar_habilidades)
        menu.add_command(label="⚡ Auto-melhoria", command=lambda: self.trigger_melhoria("geral"))
        menu.add_command(label="📸 Screenshot", command=self.analisar_tela)
        menu.add_command(label="🕐 Hora / Data", command=self.dizer_hora)
        menu.add_command(label="📝 Minhas Notas", command=self.ler_notas)
        menu.add_command(label="😂 Piada", command=self.contar_piada)
        menu.add_separator()
        menu.add_command(label="⚙️ Configurações", command=self.abrir_configuracoes)
        menu.add_command(label="❌ Sair", command=self.fechar)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    # ============================================================
    #  CONFIGURAÇÕES (API Key, Nome, etc.)
    # ============================================================
    def abrir_configuracoes(self):
        """Abre janela de configurações estilizada."""
        config_win = tk.Toplevel(self.root)
        config_win.title("Shimeji - Configurações")
        config_win.geometry("420x380")
        config_win.resizable(False, False)
        config_win.attributes("-topmost", True)
        config_win.configure(bg="#1e1e2e")

        # Estilos
        font_label = ("Segoe UI", 10, "bold")
        font_entry = ("Segoe UI", 10)
        fg_label = "#cdd6f4"
        bg_entry = "#313244"
        fg_entry = "#cdd6f4"

        # Título
        tk.Label(
            config_win, text="⚙️ Configurações",
            bg="#1e1e2e", fg="#89b4fa", font=("Segoe UI", 14, "bold")
        ).pack(pady=(15, 10))

        # Frame de campos
        frame = tk.Frame(config_win, bg="#1e1e2e")
        frame.pack(padx=20, fill="x")

        # Nome do usuário
        tk.Label(frame, text="Seu nome:", bg="#1e1e2e", fg=fg_label, font=font_label).pack(anchor="w", pady=(5, 2))
        entry_nome = tk.Entry(frame, font=font_entry, bg=bg_entry, fg=fg_entry, insertbackground=fg_entry, relief="flat", bd=5)
        entry_nome.pack(fill="x", pady=(0, 8))
        entry_nome.insert(0, self.nome_user)

        # API Key
        tk.Label(frame, text="Chave da API Groq:", bg="#1e1e2e", fg=fg_label, font=font_label).pack(anchor="w", pady=(5, 2))
        entry_key = tk.Entry(frame, font=font_entry, bg=bg_entry, fg=fg_entry, insertbackground=fg_entry, relief="flat", bd=5, show="•")
        entry_key.pack(fill="x", pady=(0, 8))
        # Carregar chave existente
        chave_atual = ""
        try:
            with open(ARQUIVO_MEMORIA, "r", encoding="utf-8") as f:
                chave_atual = json.load(f).get("groq_api_key", "")
        except Exception:
            pass
        entry_key.insert(0, chave_atual)

        # Checkbox mostrar chave
        show_var = tk.BooleanVar(value=False)
        def toggle_show():
            entry_key.config(show="" if show_var.get() else "•")
        tk.Checkbutton(
            frame, text="Mostrar chave", variable=show_var, command=toggle_show,
            bg="#1e1e2e", fg=fg_label, selectcolor=bg_entry, activebackground="#1e1e2e",
            activeforeground=fg_label, font=("Segoe UI", 9)
        ).pack(anchor="w")

        # Info de status
        status_text = f"Nível: {self.ganhar_xp(0)} | XP: {self.evolucao_xp} | Afeto: {self.afeto}"
        tk.Label(
            frame, text=status_text,
            bg="#1e1e2e", fg="#a6adc8", font=("Segoe UI", 9)
        ).pack(anchor="w", pady=(10, 0))

        # Botão Salvar
        def salvar_config():
            global client, CHAVE_GROQ
            novo_nome = entry_nome.get().strip()
            nova_chave = entry_key.get().strip()

            if novo_nome:
                self.nome_user = novo_nome

            # Salvar chave no arquivo de memória
            try:
                with open(ARQUIVO_MEMORIA, "r", encoding="utf-8") as f:
                    dados = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                dados = {}

            dados["groq_api_key"] = nova_chave
            dados["nome"] = self.nome_user

            with open(ARQUIVO_MEMORIA, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=2, ensure_ascii=False)

            # Atualizar client em tempo real
            CHAVE_GROQ = nova_chave
            if nova_chave:
                client = Groq(api_key=nova_chave)
            else:
                client = None

            self.salvar_memoria()
            self.falar(f"Configurações salvas, {self.nome_user}!")
            self.set_mood("feliz")
            self.root.after(3000, lambda: self.set_mood("normal"))
            config_win.destroy()

        # Botão Limpar Notas
        def limpar_notas():
            self._notas.clear()
            self.salvar_memoria()
            self.falar("Todas as notas foram apagadas.")

        btn_frame = tk.Frame(config_win, bg="#1e1e2e")
        btn_frame.pack(pady=15)

        tk.Button(
            btn_frame, text="💾 Salvar",
            command=salvar_config,
            bg="#89b4fa", fg="#1e1e2e",
            font=("Segoe UI", 11, "bold"),
            relief="flat", bd=0, cursor="hand2",
            activebackground="#74c7ec", activeforeground="#1e1e2e",
            padx=20, pady=8
        ).pack(side="left", padx=5)

        tk.Button(
            btn_frame, text="🗑️ Limpar Notas",
            command=limpar_notas,
            bg="#f38ba8", fg="#1e1e2e",
            font=("Segoe UI", 10, "bold"),
            relief="flat", bd=0, cursor="hand2",
            activebackground="#eba0ac", activeforeground="#1e1e2e",
            padx=15, pady=8
        ).pack(side="left", padx=5)

    def fechar(self):
        """Graceful shutdown — salva memória, sinaliza threads e encerra."""
        self.shutdown_event.set()
        self._tts_queue.put(None)  # Sentinel para encerrar worker TTS
        print("Shimeji: Até mais, " + self.nome_user + "!")
        self.salvar_memoria()
        self.root.after(300, self.root.quit)


if __name__ == "__main__":
    ShimejiCore()
