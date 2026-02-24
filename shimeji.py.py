import tkinter as tk
from PIL import Image, ImageTk
import threading, pyttsx3, time, random, os, re, psutil, importlib.util, sys
import speech_recognition as sr
from groq import Groq

# --- CONFIGURAÇÃO ---
CHAVE_GROQ = "" 
client = Groq(api_key=CHAVE_GROQ)
MODELO = "llama-3.3-70b-versatile"
PASTA_HABILIDADES = "habilidades"
ARQUIVO_ATUAL = sys.argv[0]

if not os.path.exists(PASTA_HABILIDADES):
    os.makedirs(PASTA_HABILIDADES)

class ShimejiEvolutiva:
    def __init__(self):
        try:
            self.root = tk.Tk()
            self.root.title("Shimeji AI")
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", True)
            
            # Cor de transparência (Verde limão)
            # Se suas imagens sumirem, mude para uma cor que não exista no desenho
            self.cor_fundo = "#00ff00" 
            self.root.config(bg=self.cor_fundo)
            self.root.attributes("-transparentcolor", self.cor_fundo)
            
            self.habilidades_extras = {}
            self.carregar_recursos()
            self.carregar_habilidades_disco()
            
            self.label = tk.Label(self.root, image=self.imgs["normal"], bg=self.cor_fundo)
            self.label.pack()
            self.label.bind("<B1-Motion>", self.arrastar)

            # --- INICIAR SISTEMAS ---
            threading.Thread(target=self.loop_movimento, daemon=True).start()
            threading.Thread(target=self.ouvir_seguro, daemon=True).start()
            threading.Thread(target=self.monitor_ram, daemon=True).start()
            threading.Thread(target=self.loop_piscar, daemon=True).start()
            
            self.falar("Núcleo evolutivo carregado. Estou pronta!")
            self.root.mainloop()
        except Exception as e:
            print(f"Erro ao iniciar: {e}")

    # --- ÁREA DE AUTO-UPGRADE ---
    # [ESPAÇO PARA UPGRADES]

    def fazer_upgrade(self, nome_funcao, comandos_python):
        """Injeta novas funções no próprio arquivo de código."""
        try:
            nome_funcao = re.sub(r'\W+', '', nome_funcao)
            bloco_codigo = f"\n    def {nome_funcao}(self):\n"
            for linha in comandos_python.split(';'):
                bloco_codigo += f"        {linha.strip()}\n"

            # Valida sintaxe antes de salvar
            compile(bloco_codigo, '<string>', 'exec')
            
            with open(ARQUIVO_ATUAL, "r", encoding="utf-8") as f:
                conteudo = f.read()

            marcador = "# [ESPAÇO PARA UPGRADES]"
            if marcador in conteudo:
                novo_conteudo = conteudo.replace(marcador, f"{marcador}\n{bloco_codigo}")
                with open(ARQUIVO_ATUAL, "w", encoding="utf-8") as f:
                    f.write(novo_conteudo)
                self.falar(f"Upgrade {nome_funcao} salvo no meu núcleo. Reinicie para aplicar!")
                self.label.config(image=self.imgs["feliz"])
        except Exception as e:
            self.label.config(image=self.imgs["triste"])
            print(f"Erro no upgrade: {e}")
            self.falar("Houve um erro no código do upgrade.")

    def carregar_recursos(self):
        """Carrega as imagens ou usa cores se falhar."""
        self.imgs = {}
        humores = {
            "normal": "blue", 
            "feliz": "green", 
            "brava": "red", 
            "piscando": "white", 
            "triste": "gray"
        }
        
        for humor, cor_reserva in humores.items():
            caminho = f"{humor}.png"
            if os.path.exists(caminho):
                try:
                    img = Image.open(caminho).convert("RGBA")
                    img = img.resize((180, 180), Image.Resampling.LANCZOS)
                    self.imgs[humor] = ImageTk.PhotoImage(img)
                except:
                    img = Image.new('RGBA', (180, 180), color=cor_reserva)
                    self.imgs[humor] = ImageTk.PhotoImage(img)
            else:
                img = Image.new('RGBA', (180, 180), color=cor_reserva)
                self.imgs[humor] = ImageTk.PhotoImage(img)

    def falar(self, texto):
        print(f"AI: {texto}")
        def _f():
            try:
                engine = pyttsx3.init()
                engine.say(texto)
                engine.runAndWait()
            except: pass
        threading.Thread(target=_f, daemon=True).start()

    def loop_piscar(self):
        """Ciclo vital para ela piscar os olhos sozinha."""
        while True:
            time.sleep(random.randint(3, 8))
            original = self.label.cget("image")
            self.label.config(image=self.imgs["piscando"])
            time.sleep(0.15)
            self.label.config(image=original)

    def ouvir_seguro(self):
        r = sr.Recognizer()
        while True:
            try:
                with sr.Microphone() as source:
                    r.adjust_for_ambient_noise(source, duration=0.6)
                    audio = r.listen(source, phrase_time_limit=6)
                    msg = r.recognize_google(audio, language="pt-BR")
                    print(f"Você: {msg}")
                    self.responder(msg)
            except:
                time.sleep(2)

    def responder(self, texto):
        try:
            prompt = (
                "Você é uma Shimeji evolutiva fofa. "
                "Se pedirem upgrade no núcleo: [UPGRADE] nome_funcao | cod_python. "
                "Se pedirem habilidade externa: [APRENDER] nome | comandos. "
                "Caso contrário, use [FELIZ], [BRAVA] ou [TRISTE] no texto e fale português."
            )
            chat = client.chat.completions.create(
                model=MODELO,
                messages=[{"role": "system", "content": prompt}, {"role": "user", "content": texto}]
            )
            res = chat.choices[0].message.content

            # Lógica de Expressão Visual baseada no texto da IA
            if "[BRAVA]" in res: self.label.config(image=self.imgs["brava"])
            elif "[FELIZ]" in res: self.label.config(image=self.imgs["feliz"])
            elif "[TRISTE]" in res: self.label.config(image=self.imgs["triste"])

            if "[UPGRADE]" in res:
                partes = res.replace("[UPGRADE]", "").split("|")
                self.fazer_upgrade(partes[0].strip(), partes[1].strip())
            elif "[APRENDER]" in res:
                partes = res.replace("[APRENDER]", "").split("|")
                self.aprender(partes[0].strip(), partes[1].strip())
            else:
                limpo = re.sub(r'\[.*?\]', '', res).strip()
                self.falar(limpo)
                self.root.after(4000, lambda: self.label.config(image=self.imgs["normal"]))
        except: pass

    def aprender(self, nome, comandos):
        nome_limpo = re.sub(r'\W+', '', nome).lower()
        corpo = "import time, os, pyautogui, webbrowser\ndef executar():\n"
        for linha in comandos.split(';'):
            corpo += f"    {linha.strip()}\n"
        try:
            caminho = os.path.join(PASTA_HABILIDADES, f"{nome_limpo}.py")
            with open(caminho, "w", encoding="utf-8") as f:
                f.write(corpo)
            self.importar_modulo(nome_limpo)
            self.falar(f"Habilidade {nome_limpo} aprendida!")
        except: pass

    def carregar_habilidades_disco(self):
        if not os.path.exists(PASTA_HABILIDADES): return
        for arq in os.listdir(PASTA_HABILIDADES):
            if arq.endswith(".py"):
                self.importar_modulo(arq[:-3])

    def importar_modulo(self, nome):
        try:
            path = os.path.join(PASTA_HABILIDADES, f"{nome}.py")
            spec = importlib.util.spec_from_file_location(nome, path)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "executar"):
                self.habilidades_extras[nome] = mod.executar
        except: pass

    def monitor_ram(self):
        while True:
            time.sleep(30)

    def arrastar(self, event):
        self.root.geometry(f"+{event.x_root-90}+{event.y_root-90}")

    def loop_movimento(self):
        while True:
            if random.random() > 0.8:
                nx, ny = random.randint(50, 1000), random.randint(50, 600)
                self.root.geometry(f"+{nx}+{ny}")
            time.sleep(15)

if __name__ == "__main__":
    ShimejiEvolutiva()