import tkinter as tk
from PIL import Image, ImageTk, ImageGrab
import threading, pyttsx3, time, random, os, re, psutil, sys, json, subprocess, webbrowser, shutil, base64, datetime, importlib.util, io, ctypes, argparse
import speech_recognition as sr
from groq import Groq

# --- CONFIGURAÇÃO ---
PASTA_HABILIDADES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "habilidades")
ARQUIVO_MEMORIA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "memoria.json")

# API key via argumento de linha de comando ou variável de ambiente
parser = argparse.ArgumentParser(description="Shimeji - Assistente de voz evolutivo")
parser.add_argument("--api-key", type=str, default=os.environ.get("GROQ_API_KEY", ""), help="Chave da API Groq")
parser.add_argument("--modelo", type=str, default="llama-3.3-70b-versatile", help="Modelo Groq a usar")
parser.add_argument("--sem-voz", action="store_true", help="Desativa TTS (text-to-speech)")
args = parser.parse_args()

CHAVE_GROQ = args.api_key or "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"
client = Groq(api_key=CHAVE_GROQ) if CHAVE_GROQ else None
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

# Saudações para detectar interação
CMD_SAUDACAO = r'^(oi|ola|ol[aá]|hey|bom dia|boa tarde|boa noite|eai|e ai|fala|salve|opa)'


class ShimejiCore:
    def __init__(self):
        self.shutdown_event = threading.Event()
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
            self.max_history = 10
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

            # Protocolo de fechar
            self.root.protocol("WM_DELETE_WINDOW", self.fechar)

            self.set_mood("normal")
            self.falar("Shimeji online. Pronta para evoluir.")

            # --- Threads (todas verificam shutdown_event) ---
            threading.Thread(target=self.loop_movimento, daemon=True).start()
            threading.Thread(target=self.ouvir_seguro, daemon=True).start()
            threading.Thread(target=self.monitor_sistema, daemon=True).start()
            threading.Thread(target=self.loop_piscar, daemon=True).start()
            threading.Thread(target=self.auto_analise, daemon=True).start()

            self.root.mainloop()
        except Exception as e:
            print(f"Erro ao iniciar: {e}")

    # ============================================================
    #  SISTEMA DE MEMÓRIA
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
        self.salvar_memoria()

    def salvar_memoria(self):
        dados = {
            "nome": self.nome_user,
            "afeto": self.afeto,
            "xp": self.evolucao_xp,
            "habilidades_desbloqueadas": self.habilidades_dl,
            "preferencias": self.preferencias,
            "historico": self.conversation_history[-self.max_history:]
        }
        try:
            with open(ARQUIVO_MEMORIA, "w", encoding="utf-8") as f:
                json.dump(dados, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Erro ao salvar memória: {e}")

    def registrar_historico(self, papel, texto):
        self.conversation_history.append({"papel": papel, "texto": texto[:500]})
        if len(self.conversation_history) > self.max_history:
            self.conversation_history = self.conversation_history[-self.max_history:]
        self.salvar_memoria()

    def ganhar_xp(self, quantidade):
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
        base_dir = os.path.dirname(os.path.abspath(__file__))
        for humor, cor_reserva in humores.items():
            caminho = os.path.join(base_dir, f"{humor}.png")
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
    #  SISTEMA DE VOZ
    # ============================================================
    def falar(self, texto):
        print(f"Shimeji: {texto}")
        if SEM_VOZ:
            return
        def _f():
            try:
                engine = pyttsx3.init()
                rate = engine.getProperty('rate')
                engine.setProperty('rate', rate - 20)
                engine.say(texto)
                engine.runAndWait()
            except Exception as e:
                print(f"Erro TTS: {e}")
        threading.Thread(target=_f, daemon=True).start()

    def ouvir_seguro(self):
        r = sr.Recognizer()
        while not self.shutdown_event.is_set():
            try:
                with sr.Microphone() as source:
                    r.adjust_for_ambient_noise(source, duration=0.6)
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
                # Mic não disponível
                if not self.shutdown_event.is_set():
                    print("Microfone não disponível. Tente com outro dispositivo.")
                time.sleep(5)
            except Exception as e:
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
            url = f"https://www.google.com/search?q={webbrowser.quote(query)}"
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
                        threading.Thread(target=self.habilidades_extras[nome_hab], daemon=True).start()
                        self.ganhar_xp(2)
                        return

        # IA - conversa geral
        self.responder_ia(texto)

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
        url = f"https://www.google.com/search?q={webbrowser.quote(alvo)}"
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
            # PowerShell: ajusta o master volume
            ps_code = (
                f'Add-Type -TypeDefinition @"\n'
                'using System;\n'
                'using System.Runtime.InteropServices;\n'
                'public class Audio {{\n'
                '  [DllImport("winmm.dll")] public static extern int waveOutSetVolume(IntPtr h, uint d);\n'
                '}}\n'
                '"@;\n'
                f'[Audio]::waveOutSetVolume([IntPtr]::Zero, {int(vol/100*0xFFFF):X}{int(vol/100*0xFFFF):X})'
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

        info = f"CPU: {cpu}%. RAM: {ram.percent}% usado ({ram.used/1e9:.1f}GB de {ram.total/1e9:.1f}GB). "
        info += f"Disco C: {disco.percent}% usado ({disco.used/1e9:.1f}GB de {disco.total/1e9:.1f}GB). "
        if bateria:
            mins = bateria.secsleft // 60 if bateria.secsleft > 0 else "calculando"
            info += f"Bateria: {bateria.percent}%, ~{mins} min restantes. "
        info += f"Rede: {rede.bytes_sent/1e6:.1f}MB enviados, {rede.bytes_recv/1e6:.1f}MB recebidos. "
        info += f"XP de evolução: {self.evolucao_xp}."

        self.falar(info)
        self.ganhar_xp(2)

    def listar_habilidades(self):
        habilidades = list(self.habilidades_extras.keys())
        if habilidades:
            lista = ", ".join(habilidades)
            self.falar(f"Eu sei fazer: {lista}.")
        else:
            self.falar("Ainda não aprendi habilidades extras. Me ensine algo!")
        self.set_mood("feliz")

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

        nome_arq = f"screenshot_{datetime.datetime.now().strftime('%H%M%S')}.png"
        try:
            ImageGrab.grab().save(nome_arq)
        except Exception:
            pass

        if not client:
            self.falar("API Groq não configurada. Use --api-key ou defina GROQ_API_KEY.")
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
            self.falar("API Groq não configurada. Use --api-key ou defina GROQ_API_KEY.")
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
        prompt = (
            f"Você é Shimeji, uma assistente evolutiva super inteligente, assistente pessoal de {self.nome_user}. "
            f"Seu nível atual é: {nivel} (XP: {self.evolucao_xp}). "
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
            "'Melhore [X]' - Auto-aperfeiçoamento\n"
            "'Fecha [X]' - Fecha programa\n\n"
            "Sempre que identificar uma oportunidade de melhorar seu próprio código, use [MELHORAR]. "
            "Seja proativo em sugerir melhorias para si mesma."
        )
        return prompt

    def responder_ia(self, texto):
        if not client:
            self.falar("API Groq não configurada. Inicie com --api-key SUA_CHAVE ou defina GROQ_API_KEY.")
            return
        self.set_mood("normal")
        try:
            msgs = [{"role": "system", "content": self.get_system_prompt()}]

            for h in self.conversation_history[-5:]:
                msgs.append({"role": h["papel"], "content": h["texto"]})

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
    #  AUTO-APERFEIÇOAMENTO / SELF-IMPROVEMENT
    # ============================================================
    def fazer_backup(self):
        """Cria backup antes de modificar o código."""
        try:
            arquivo = sys.argv[0]
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = f"{arquivo}.backup_{timestamp}"
            shutil.copy2(arquivo, backup_path)
            print(f"Backup criado: {backup_path}")
            return backup_path
        except Exception as e:
            print(f"Erro no backup: {e}")
            return None

    def fazer_upgrade(self, nome_funcao, codigo_python):
        """Injeta código novo no próprio arquivo com segurança."""
        try:
            nome_funcao = re.sub(r'\W+', '', nome_funcao)
            if not nome_funcao:
                return

            linhas = [l.strip() for l in codigo_python.split(';') if l.strip()]
            bloco = f"\n    def {nome_funcao}(self):\n"
            for linha in linhas:
                bloco += f"        {linha}\n"

            # Validar sintaxe
            compile(bloco, '<string>', 'exec')

            arquivo = sys.argv[0]
            backup_path = self.fazer_backup()

            with open(arquivo, "r", encoding="utf-8") as f:
                conteudo = f.read()

            # Inserir antes do if __name__
            if 'if __name__' in conteudo:
                partes = conteudo.rsplit('if __name__', 1)
                novo = partes[0] + bloco + "\nif __name__" + partes[1]
            else:
                novo = conteudo + "\n" + bloco

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
            self.falar(f"Erro no upgrade de {nome_funcao}.")

    def registrar_melhoria(self, nome, backup_path):
        try:
            historico_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "historico_melhorias.json")
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
            self.falar("API Groq não configurada.")
            return
        self.falar(f"Analisando como melhorar {alvo}...")
        self.set_mood("normal")

        arquivo = sys.argv[0]
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
    #  SISTEMA DE HABILIDADES
    # ============================================================
    def aprender(self, nome, comandos):
        nome_limpo = re.sub(r'\W+', '', nome).lower()
        corpo = "import time, os, webbrowser\n\ndef executar():\n"
        for linha in comandos.split(';'):
            corpo += f"    {linha.strip()}\n"
        try:
            caminho = os.path.join(PASTA_HABILIDADES, f"{nome_limpo}.py")
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(corpo)
            self.importar_modulo(nome_limpo)
            self.falar(f"Habilidade {nome_limpo} aprendida!")
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
                # Ignorar arquivos com nomes inválidos
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', nome):
                    continue
                self.importar_modulo(nome)

    def importar_modulo(self, nome):
        try:
            path = os.path.join(PASTA_HABILIDADES, f"{nome}.py")
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
            # Usar referências mantidas vivas
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
            if random.random() > 0.85:
                # Agendar movimento no thread principal
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
        self.root.geometry(f"+{event.x_root-90}+{event.y_root-90}")

    def on_click(self, event):
        """Click esquerdo — interação simples."""
        pass  # Pode ser expandido

    def menu_contexto(self, event):
        """Menu ao clicar com botão direito."""
        menu = tk.Menu(self.root, tearoff=0, bg="#333", fg="white", activebackground="#555", activeforeground="white")
        menu.add_command(label="Status", command=self.mostrar_status)
        menu.add_command(label="Habilidades", command=self.listar_habilidades)
        menu.add_command(label="Auto-melhoria", command=lambda: self.trigger_melhoria("geral"))
        menu.add_command(label="Screenshot", command=self.analisar_tela)
        menu.add_separator()
        menu.add_command(label="Sair", command=self.fechar)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def fechar(self):
        """Graceful shutdown — salva memória e encerra threads."""
        self.shutdown_event.set()
        self.falar("Até mais, " + self.nome_user + "!")
        self.salvar_memoria()
        self.root.after(500, self.root.quit)


if __name__ == "__main__":
    ShimejiCore()
