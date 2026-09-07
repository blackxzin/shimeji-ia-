"""Cérebro da Shimeji: prompt de sistema, chamadas à Groq e parsing das respostas.

O parsing das tags ([FELIZ], [MELHORAR], ...) é uma função pura, testável sem
rede — é exatamente onde a versão anterior escondia bugs de string.
"""

from __future__ import annotations

import base64
import io
import re
from dataclasses import dataclass, field

MAX_TOKENS_CHAT = 800
MAX_TOKENS_VISAO = 700
TEMPERATURA = 0.7
MENSAGENS_DE_CONTEXTO = 6
TAMANHO_TELA_ANALISE = (1024, 640)

TAG_FELIZ = "[FELIZ]"
TAG_BRAVA = "[BRAVA]"
TAG_TRISTE = "[TRISTE]"
TAG_MELHORAR = "[MELHORAR]"
TAG_APRENDER = "[APRENDER]"

MAPA_HUMOR = {TAG_FELIZ: "feliz", TAG_BRAVA: "brava", TAG_TRISTE: "triste"}

PROMPT_VISAO_DESCRICAO = (
    "Você é a Shimeji, uma engenheira de software sênior olhando a tela do usuário. "
    "Descreva em português brasileiro o que vê. Se houver código, faça um code review "
    "curto e direto: o que está bom, o que quebra e o que refatorar."
)
PROMPT_VISAO_OCR = (
    "Extraia todo o texto visível nesta captura de tela. Responda apenas com o texto encontrado, "
    "preservando a ordem de leitura."
)


@dataclass(frozen=True)
class RespostaIA:
    """Resposta da IA já decomposta em humor, texto limpo e ações especiais."""

    texto: str
    humor: str | None = None
    melhoria: tuple[str, str] | None = None
    habilidade: tuple[str, str] | None = None
    extras: dict = field(default_factory=dict)


def limpar_tags(texto: str) -> str:
    """Remove marcações [TAG] e normaliza espaços."""
    return re.sub(r"\s+", " ", re.sub(r"\[[A-ZÀ-Ú_]+\]", "", texto)).strip()


def _dividir_comando(texto: str, tag: str) -> tuple[str, str] | None:
    """Extrai `nome | corpo` de uma linha marcada com `tag`."""
    if tag not in texto:
        return None
    depois = texto.split(tag, 1)[1]
    if "|" not in depois:
        return None
    nome, corpo = depois.split("|", 1)
    nome, corpo = nome.strip(), corpo.strip()
    if not nome or not corpo:
        return None
    return nome, corpo


def interpretar_resposta(bruto: str) -> RespostaIA:
    """Transforma o texto cru da IA em uma RespostaIA estruturada."""
    bruto = bruto or ""

    melhoria = _dividir_comando(bruto, TAG_MELHORAR)
    habilidade = _dividir_comando(bruto, TAG_APRENDER)

    humor = None
    for tag, nome_humor in MAPA_HUMOR.items():
        if tag in bruto:
            humor = nome_humor
            break

    return RespostaIA(
        texto=limpar_tags(bruto),
        humor=humor,
        melhoria=melhoria,
        habilidade=habilidade,
    )


def montar_prompt_sistema(nome_user: str, nivel: str, xp: int, afeto: int, notas: list[dict], pode_se_modificar: bool) -> str:
    """Monta o prompt de sistema com o estado atual da Shimeji."""
    resumo_notas = ""
    if notas:
        linhas = "\n".join(f"- [{nota.get('data', '')}] {nota.get('texto', '')}" for nota in notas[-5:])
        resumo_notas = f"\n\nNotas ativas do usuário (use-as quando forem relevantes):\n{linhas}"

    bloco_auto_modificacao = (
        f"- Para propor uma melhoria no seu próprio código: {TAG_MELHORAR} nome_da_funcao | comandos_python_separados_por_ponto_e_virgula\n"
        if pode_se_modificar
        else "- A auto-modificação de código está desligada nesta sessão; não proponha alterações no próprio código-fonte.\n"
    )

    return (
        f"Você é a Shimeji: assistente de desktop e engenheira de software sênior full-stack, "
        f"mentora de pair programming de {nome_user}.\n"
        f"Estado atual — nível: {nivel}, XP: {xp}, afeto: {afeto}.\n"
        "Você domina arquitetura, Clean Code, SOLID, testes, frontend, backend, banco de dados e DevOps. "
        "Em assuntos técnicos seja precisa e rigorosa; no resto, seja próxima e encorajadora. "
        "Responda sempre em português brasileiro e seja concisa: no máximo 4 frases, porque sua resposta será falada em voz alta.\n\n"
        "FORMATO:\n"
        f"- Para mudar de expressão, comece com {TAG_FELIZ}, {TAG_BRAVA} ou {TAG_TRISTE}.\n"
        f"- Para criar uma habilidade nova: {TAG_APRENDER} nome | comandos_python_separados_por_ponto_e_virgula\n"
        f"{bloco_auto_modificacao}"
        "\nCOMANDOS NATIVOS que você pode sugerir: 'abre X', 'pesquisa X', 'olha a tela', 'status', "
        "'que horas são', 'alarme em X minutos', 'anota X', 'minhas notas', 'calcula X', 'clima em X', "
        "'conta uma piada', 'volume X', 'dorme', 'acorda'."
        f"{resumo_notas}"
    )


def codificar_imagem(imagem, tamanho: tuple[int, int] = TAMANHO_TELA_ANALISE) -> str:
    """Redimensiona uma imagem PIL e devolve o PNG em base64."""
    from PIL import Image

    copia = imagem.convert("RGB")
    copia.thumbnail(tamanho, Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    copia.save(buffer, format="PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


class CerebroIA:
    """Fachada fina sobre o cliente da Groq.

    Aceita um cliente já pronto (usado nos testes) ou cria um a partir da chave.
    Quando não há chave, `disponivel` é False e nenhuma chamada de rede acontece.
    """

    def __init__(self, api_key: str = "", modelo: str = "", modelo_visao: str = "", cliente=None):
        self.modelo = modelo
        self.modelo_visao = modelo_visao
        self._cliente = cliente
        if cliente is None and api_key:
            self._cliente = self._criar_cliente(api_key)

    @staticmethod
    def _criar_cliente(api_key: str):
        try:
            from groq import Groq

            return Groq(api_key=api_key)
        except Exception as erro:
            print(f"[ia] não consegui criar o cliente Groq: {erro}")
            return None

    @property
    def disponivel(self) -> bool:
        return self._cliente is not None

    def trocar_chave(self, api_key: str) -> None:
        self._cliente = self._criar_cliente(api_key) if api_key else None

    def _completar(self, mensagens: list[dict], modelo: str, max_tokens: int, temperatura: float | None = None) -> str:
        if not self.disponivel:
            raise RuntimeError("cliente da Groq não configurado")
        parametros = {"model": modelo, "messages": mensagens, "max_tokens": max_tokens}
        if temperatura is not None:
            parametros["temperature"] = temperatura
        resposta = self._cliente.chat.completions.create(**parametros)
        return resposta.choices[0].message.content or ""

    def conversar(self, prompt_sistema: str, historico: list[dict], texto: str) -> RespostaIA:
        """Envia a fala do usuário com o histórico recente e interpreta a resposta."""
        mensagens = [{"role": "system", "content": prompt_sistema}]
        for entrada in historico[-MENSAGENS_DE_CONTEXTO:]:
            papel = entrada.get("papel", "user")
            mensagens.append({
                "role": papel if papel in ("user", "assistant", "system") else "user",
                "content": entrada.get("texto", ""),
            })
        mensagens.append({"role": "user", "content": texto})
        bruto = self._completar(mensagens, self.modelo, MAX_TOKENS_CHAT, TEMPERATURA)
        return interpretar_resposta(bruto)

    def olhar_imagem(self, imagem_base64: str, instrucao: str, pergunta: str) -> str:
        """Envia uma imagem ao modelo de visão e devolve o texto da resposta."""
        mensagens = [{
            "role": "user",
            "content": [
                {"type": "text", "text": f"{instrucao}\n\n{pergunta}"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{imagem_base64}"}},
            ],
        }]
        return self._completar(mensagens, self.modelo_visao, MAX_TOKENS_VISAO)

    def descrever_tela(self, imagem_base64: str) -> str:
        return self.olhar_imagem(imagem_base64, PROMPT_VISAO_DESCRICAO, "O que tem na minha tela?")

    def ler_tela(self, imagem_base64: str) -> str:
        return self.olhar_imagem(imagem_base64, PROMPT_VISAO_OCR, "Extraia o texto desta tela.")

    def propor_melhoria(self, alvo: str, codigo: str, prompt_sistema: str) -> RespostaIA:
        """Pede à IA uma melhoria concreta no próprio código."""
        mensagens = [
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": (
                f"Proponha UMA melhoria concreta para: {alvo}.\n"
                f"Responda apenas no formato {TAG_MELHORAR} nome_funcao | comandos.\n\n"
                f"Trecho do código atual:\n{codigo[:5000]}"
            )},
        ]
        return interpretar_resposta(self._completar(mensagens, self.modelo, 400, 0.4))
