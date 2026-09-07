"""Configuração central: caminhos, constantes e parsing de linha de comando."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, replace

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA_HABILIDADES = os.path.join(BASE_DIR, "habilidades")
PASTA_ASSETS = os.path.join(BASE_DIR, "assets")
ARQUIVO_MEMORIA = os.path.join(BASE_DIR, "memoria.json")
ARQUIVO_MELHORIAS = os.path.join(BASE_DIR, "historico_melhorias.jsonl")

MODELO_PADRAO = "llama-3.3-70b-versatile"
MODELO_VISAO_PADRAO = "meta-llama/llama-4-scout-17b-16e-instruct"

TAMANHO_SPRITE = 180
MAX_HISTORICO = 20
MAX_NOTAS = 50
MAX_TAMANHO_NOTA = 500

INTERVALO_PISCAR = (3, 8)
DURACAO_PISCADA = 0.15
INTERVALO_MOVIMENTO = 12
CHANCE_MOVIMENTO = 0.15
INTERVALO_MONITOR = 60
INTERVALO_DICA_SAUDE = 2700
INTERVALO_TICK_LEMBRETE = 120

LIMITE_ALERTA_RAM = 90
LIMITE_ALERTA_CPU = 95
LIMITE_ALERTA_DISCO = 95

HUMORES = ("normal", "feliz", "brava", "triste", "piscando")
CORES_RESERVA = {
    "normal": "#5b8dd6",
    "feliz": "#5bd68d",
    "brava": "#d65b5b",
    "piscando": "#d6d6d6",
    "triste": "#8d8d9c",
}


@dataclass(frozen=True)
class Config:
    """Configuração imutável da aplicação."""

    api_key: str = ""
    modelo: str = MODELO_PADRAO
    modelo_visao: str = MODELO_VISAO_PADRAO
    sem_voz: bool = False
    demo: bool = False
    sem_microfone: bool = False
    permitir_auto_modificacao: bool = False

    def com_api_key(self, api_key: str) -> "Config":
        """Retorna uma nova Config com a chave trocada (sem mutar a original)."""
        return replace(self, api_key=api_key)


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="shimeji",
        description="Shimeji - assistente de desktop evolutiva com IA",
    )
    parser.add_argument("--api-key", default="", help="Chave da API Groq")
    parser.add_argument("--modelo", default=MODELO_PADRAO, help="Modelo Groq para texto")
    parser.add_argument("--modelo-visao", default=MODELO_VISAO_PADRAO, help="Modelo Groq para visão")
    parser.add_argument("--sem-voz", action="store_true", help="Desativa a síntese de voz (TTS)")
    parser.add_argument("--demo", action="store_true", help="Modo demonstração: sem microfone, sem IA, roteiro automático")
    parser.add_argument("--sem-microfone", action="store_true", help="Não abre o microfone (só menu e cliques)")
    parser.add_argument(
        "--permitir-auto-modificacao",
        action="store_true",
        help="Permite que a IA reescreva o próprio código-fonte (desligado por padrão)",
    )
    return parser


def ler_chave_do_arquivo(caminho: str = ARQUIVO_MEMORIA) -> str:
    """Lê a chave da Groq salva no arquivo de memória. Retorna '' se ausente."""
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo).get("groq_api_key", "") or ""
    except (json.JSONDecodeError, FileNotFoundError, OSError):
        return ""


def resolver_api_key(cli_key: str = "", ambiente: dict | None = None, caminho_memoria: str = ARQUIVO_MEMORIA) -> str:
    """Resolve a chave da API na ordem: linha de comando, ambiente, arquivo de memória."""
    if cli_key:
        return cli_key
    ambiente = os.environ if ambiente is None else ambiente
    do_ambiente = ambiente.get("GROQ_API_KEY", "")
    if do_ambiente:
        return do_ambiente
    return ler_chave_do_arquivo(caminho_memoria)


def carregar_config(argv: list[str] | None = None, ambiente: dict | None = None) -> Config:
    """Constrói a Config a partir dos argumentos de linha de comando.

    Diferente da versão anterior, o parsing NÃO acontece na importação do módulo,
    o que permite importar o pacote em testes e em outras ferramentas.
    """
    args = construir_parser().parse_args(argv if argv is not None else [])
    return Config(
        api_key=resolver_api_key(args.api_key, ambiente),
        modelo=args.modelo,
        modelo_visao=args.modelo_visao,
        sem_voz=args.sem_voz or args.demo,
        demo=args.demo,
        sem_microfone=args.sem_microfone or args.demo,
        permitir_auto_modificacao=args.permitir_auto_modificacao,
    )
