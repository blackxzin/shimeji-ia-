# Shimeji — Assistente Evolutiva & Mentora de Código

Shimeji é uma assistente virtual de desktop construída em Python (Tkinter) que roda na sua tela como um "pet virtual". Mais do que fofa, ela é integrada com IA Avançada (API Groq - modelo Llama 3) e agora atua como uma **Engenheira de Software Senior Full-Stack** para te ajudar no dia a dia.

## 🚀 O que há de novo na última versão?

Esta versão traz uma reestruturação profunda (Thread-Safe e assíncrona) e introduz as seguintes **novas funcionalidades nativas**:

### 🧠 Cérebro Avançado (Dev Senior)
- A IA da Shimeji agora tem a persona de uma Mentora Senior de Programação (Clean Code, SOLID, Full-Stack).
- **Pair Programming Visual:** Basta mostrar o código na tela e dizer *"Olha a tela e analisa esse código"*, ela fará um Code Review completo da sua arquitetura usando Visão Computacional.

### 💤 Modo Hibernação (Dormir / Acordar)
- Clique com o botão direito nela e escolha **"💤 Dormir"**. Ela desliga completamente o microfone (consumo de CPU cai para 0%) e para de se mover para poupar a bateria do seu notebook.
- Para voltar ao trabalho, clique em **"💤 Acordar"**.

### 📝 Memória e Lembretes Persistentes
- A Shimeji nunca esquece! Fale *"anota pra mim: comprar pão"* e a nota ficará salva. As suas notas são embutidas no cérebro dela (Contexto da IA), então ela sempre estará ciente do que você tem a fazer.
- Você pode gerenciar/limpar notas pelo menu de *Configurações*.

### ⏱️ Alarmes e Temporizadores
- Precisa de foco ou tem um compromisso? Diga *"alarme em 10 minutos"*. A Shimeji roda isso em background e vai dar uns pulos na tela e te avisar na hora exata!

### 💖 Carinho (Duplo Clique) e Gamificação
- Dê um duplo clique na Shimeji para fazer carinho nela! O seu nível de Afeto subirá e ela ficará toda feliz, dando pulinhos duplos.
- **Tooltip Flutuante:** Passe o mouse (hover) sem clicar para ver o Status rápido (Nível, XP, Afeto) em um balão flutuante elegante.

### 🛠️ Outras Funcionalidades
- **Calculadora Segura:** Diga *"calcula 25 x 4"* e ela fará a conta em um ambiente blindado de segurança.
- **Clima e Previsão do Tempo:** Diga *"clima em São Paulo"*.
- **Data e Hora Dinâmica:** Diga *"que horas são"*.
- **Saudação Inteligente:** Bom dia, boa tarde ou boa noite de acordo com o horário que você inicia o programa.
- **Piadas Tech:** Ela tem um arsenal de piadas sobre bugs e códigos para levantar seu ânimo.

---

## 💻 Requisitos e Execução

### Bibliotecas Necessárias
```bash
pip install tk Pillow psutil speechrecognition pyttsx3 groq
```

*Nota para Windows:* Você vai precisar do `PyAudio` para o SpeechRecognition funcionar. (Se falhar no pip, baixe o .whl).

### Como Rodar
Você deve ter uma chave da API da **Groq** (para o cérebro dela funcionar). 

1. Inicie o programa:
```bash
python3 shimeji.py
```

### Opções de linha de comando

| Flag | Padrão | Descrição |
|------|--------|-----------|
| `--api-key CHAVE` | env `GROQ_API_KEY` ou `memoria.json` | Chave da API Groq |
| `--modelo NOME` | `llama-3.3-70b-versatile` | Modelo Groq para texto/chat |
| `--modelo-visao NOME` | `llama-3.2-90b-vision-preview` | Modelo Groq para visão/OCR de tela |
| `--sem-voz` | `False` | Desativa TTS (text-to-speech) |

Exemplo:
```bash
python3 shimeji.py --modelo-visao meta-llama/llama-4-scout-17b-16e-instruct --sem-voz
```
2. Na primeira vez, clique com o botão direito na Shimeji, vá em **⚙️ Configurações** e cole sua Chave de API lá, além de definir o seu nome. (Isso ficará salvo no `memoria.json`).

## 🧠 Como adicionar novas habilidades
A Shimeji possui uma pasta `habilidades/`. Qualquer arquivo `.py` lá dentro é carregado dinamicamente.
A Shimeji tem a funcionalidade de **Auto-Melhoria** e **Aprender**: você pode pedir a ela mesma que gere código Python para novas funcionalidades. Ela testará a sintaxe em background e aplicará em si mesma sem que você precise fechar o programa!
