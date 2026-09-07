"""Integração com o sistema operacional: abrir, fechar, volume e telemetria.

Esta camada substitui o `subprocess.Popen(alvo, shell=True)` da versão anterior,
que executava texto ditado por voz direto no shell — qualquer frase com `;` ou
`&&` virava um comando arbitrário. Agora só há três caminhos permitidos: sites
conhecidos, abertura pelo handler do desktop e executáveis achados no PATH.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import urllib.parse
import webbrowser
from dataclasses import dataclass

import psutil

SITES_CONHECIDOS = {
    "youtube": "https://youtube.com",
    "google": "https://google.com",
    "github": "https://github.com",
    "gitlab": "https://gitlab.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "twitter": "https://twitter.com",
    "instagram": "https://instagram.com",
    "whatsapp": "https://web.whatsapp.com",
    "discord": "https://discord.com/app",
    "reddit": "https://reddit.com",
    "netflix": "https://netflix.com",
    "spotify": "https://open.spotify.com",
    "twitch": "https://twitch.tv",
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai",
    "gmail": "https://mail.google.com",
    "drive": "https://drive.google.com",
    "maps": "https://maps.google.com",
    "linkedin": "https://linkedin.com",
    "tiktok": "https://tiktok.com",
    "amazon": "https://amazon.com.br",
    "notion": "https://notion.so",
    "figma": "https://figma.com",
}

# Nunca encerrar por voz: derrubaria a própria Shimeji ou a sessão gráfica.
PROCESSOS_PROTEGIDOS = frozenset({
    "python", "python3", "pythonw", "systemd", "init", "kernel", "kthreadd",
    "explorer.exe", "winlogon.exe", "csrss.exe", "services.exe", "lsass.exe",
    "gnome-shell", "kwin", "kwin_wayland", "xorg", "wayland", "sshd", "dbus-daemon",
})

URL_CLIMA = "https://wttr.in/{cidade}?lang=pt"
URL_BUSCA = "https://www.google.com/search?q={query}"


class ErroDeSistema(RuntimeError):
    """Falha ao interagir com o sistema operacional."""


@dataclass(frozen=True)
class StatusSistema:
    cpu: float
    ram_percentual: float
    ram_usada_gb: float
    ram_total_gb: float
    disco_percentual: float
    disco_usado_gb: float
    disco_total_gb: float
    bateria_percentual: float | None
    bateria_minutos: int | None

    def descrever(self) -> str:
        partes = [
            f"CPU em {self.cpu:.0f} por cento.",
            f"RAM em {self.ram_percentual:.0f} por cento, {self.ram_usada_gb:.1f} de {self.ram_total_gb:.1f} gigas.",
            f"Disco em {self.disco_percentual:.0f} por cento, {self.disco_usado_gb:.1f} de {self.disco_total_gb:.1f} gigas.",
        ]
        if self.bateria_percentual is not None:
            texto = f"Bateria em {self.bateria_percentual:.0f} por cento"
            if self.bateria_minutos:
                texto += f", cerca de {self.bateria_minutos} minutos restantes"
            partes.append(texto + ".")
        return " ".join(partes)


def caminho_do_disco() -> str:
    return "C:\\" if sys.platform == "win32" else "/"


def coletar_status() -> StatusSistema:
    """Fotografa CPU, RAM, disco e bateria."""
    ram = psutil.virtual_memory()
    disco = psutil.disk_usage(caminho_do_disco())
    bateria = psutil.sensors_battery() if hasattr(psutil, "sensors_battery") else None

    bateria_percentual = bateria.percent if bateria else None
    bateria_minutos = None
    if bateria and bateria.secsleft is not None and bateria.secsleft > 0:
        bateria_minutos = bateria.secsleft // 60

    return StatusSistema(
        cpu=psutil.cpu_percent(interval=0.5),
        ram_percentual=ram.percent,
        ram_usada_gb=ram.used / 1e9,
        ram_total_gb=ram.total / 1e9,
        disco_percentual=disco.percent,
        disco_usado_gb=disco.used / 1e9,
        disco_total_gb=disco.total / 1e9,
        bateria_percentual=bateria_percentual,
        bateria_minutos=bateria_minutos,
    )


def resolver_site(alvo: str) -> str | None:
    """Devolve a URL de um site conhecido, ou a própria URL se o alvo já for uma."""
    alvo_normalizado = alvo.lower().strip()
    if alvo_normalizado.startswith(("http://", "https://")):
        return alvo_normalizado
    for nome, url in SITES_CONHECIDOS.items():
        if nome in alvo_normalizado:
            return url
    return None


def abrir_no_navegador(url: str) -> None:
    webbrowser.open(url)


def pesquisar(query: str) -> str:
    url = URL_BUSCA.format(query=urllib.parse.quote(query))
    abrir_no_navegador(url)
    return url


def abrir_clima(cidade: str) -> str:
    destino = cidade.strip() or ""
    url = URL_CLIMA.format(cidade=urllib.parse.quote(destino))
    abrir_no_navegador(url)
    return url


def _abrir_com_desktop(caminho: str) -> bool:
    """Entrega o caminho ao handler do sistema. Sempre lista de args, nunca shell."""
    if not os.path.exists(caminho):
        return False
    try:
        if sys.platform == "win32":
            os.startfile(caminho)  # noqa: S606 - API dedicada do Windows, sem shell
        elif sys.platform == "darwin":
            subprocess.Popen(["open", caminho])
        else:
            subprocess.Popen(["xdg-open", caminho])
        return True
    except OSError:
        return False


def _abrir_executavel(alvo: str) -> bool:
    """Procura o alvo no PATH e executa sem interpretação de shell."""
    # Um alvo com metacaracteres nunca é um nome de programa legítimo.
    if any(caractere in alvo for caractere in ";|&$`><\n"):
        return False
    executavel = shutil.which(alvo)
    if not executavel:
        return False
    try:
        subprocess.Popen([executavel])
        return True
    except OSError:
        return False


def abrir_alvo(alvo: str) -> str:
    """Abre site, arquivo ou programa. Cai para busca no Google se não achar.

    Retorna um rótulo do caminho usado: "site", "arquivo", "programa" ou "busca".
    """
    alvo = alvo.strip()
    if not alvo:
        raise ErroDeSistema("nada para abrir")

    url = resolver_site(alvo)
    if url:
        abrir_no_navegador(url)
        return "site"

    if _abrir_com_desktop(os.path.expanduser(alvo)):
        return "arquivo"

    if _abrir_executavel(alvo):
        return "programa"

    pesquisar(alvo)
    return "busca"


def processo_protegido(nome: str) -> bool:
    base = os.path.basename(nome or "").lower()
    sem_extensao = base.rsplit(".", 1)[0]
    return base in PROCESSOS_PROTEGIDOS or sem_extensao in PROCESSOS_PROTEGIDOS


def encerrar_processos(nome_alvo: str, pid_proprio: int | None = None) -> tuple[int, int]:
    """Encerra processos cujo nome contenha `nome_alvo`.

    Retorna (encerrados, protegidos_ignorados). O próprio processo da Shimeji e a
    lista de processos críticos do sistema nunca são tocados.
    """
    alvo = (nome_alvo or "").strip().lower()
    if len(alvo) < 3:
        raise ErroDeSistema("nome curto demais para encerrar com segurança")

    pid_proprio = os.getpid() if pid_proprio is None else pid_proprio
    encerrados = 0
    protegidos = 0

    for processo in psutil.process_iter(["pid", "name"]):
        try:
            nome = (processo.info.get("name") or "").lower()
            if alvo not in nome:
                continue
            if processo.info.get("pid") == pid_proprio:
                protegidos += 1
                continue
            if processo_protegido(nome):
                protegidos += 1
                continue
            processo.terminate()
            encerrados += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    return encerrados, protegidos


def ajustar_volume(nivel: int | None) -> int:
    """Define o volume principal (0-100). Retorna o valor aplicado."""
    volume = 50 if nivel is None else max(0, min(100, int(nivel)))

    if sys.platform == "win32":
        _volume_windows(volume)
    else:
        _volume_unix(volume)
    return volume


def _volume_windows(volume: int) -> None:
    valor = int(volume / 100 * 0xFFFF)
    codigo = (
        'Add-Type -TypeDefinition @"\n'
        "using System;\nusing System.Runtime.InteropServices;\n"
        "public class Audio {\n"
        '  [DllImport("winmm.dll")] public static extern int waveOutSetVolume(IntPtr h, uint d);\n'
        "}\n"
        '"@;\n'
        f"[Audio]::waveOutSetVolume([IntPtr]::Zero, 0x{valor:04X}{valor:04X})"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", codigo],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False,
        )
    except (OSError, subprocess.SubprocessError) as erro:
        raise ErroDeSistema(f"falha ao ajustar o volume no Windows: {erro}") from erro


def _volume_unix(volume: int) -> None:
    tentativas = (
        ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"],
        ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{volume / 100:.2f}"],
        ["amixer", "-q", "set", "Master", f"{volume}%"],
        ["osascript", "-e", f"set volume output volume {volume}"],
    )
    for comando in tentativas:
        if not shutil.which(comando[0]):
            continue
        try:
            resultado = subprocess.run(
                comando, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False
            )
            if resultado.returncode == 0:
                return
        except (OSError, subprocess.SubprocessError):
            continue
    raise ErroDeSistema("nenhum controlador de áudio disponível (pactl, wpctl, amixer)")
