
import socket
import threading
import json
import sys
import os
import base64
from datetime import datetime

HOST  = 'localhost'
PORTA = 12345

# ─── Criptografia AES-256-CBC ────────────────────────────
# pip install pycryptodome
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# Chave fixa de 32 bytes (AES-256). Deve ser idêntica no server.py.
CHAVE_AES = b"ChatSeguro2024!!ChatSeguro2024!!"  # exatamente 32 bytes

def criptografar(mensagem: str) -> str:
    """
    Criptografa uma string com AES-256-CBC.
    Retorna: "<iv_base64>:<cifra_base64>"
    """
    iv = os.urandom(16)
    cipher = AES.new(CHAVE_AES, AES.MODE_CBC, iv)
    cifra = cipher.encrypt(pad(mensagem.encode("utf-8"), AES.block_size))
    return base64.b64encode(iv).decode() + ":" + base64.b64encode(cifra).decode()

def descriptografar(payload: str) -> str:
    """
    Descriptografa o payload "<iv_base64>:<cifra_base64>" e retorna a string original.
    """
    iv_b64, cifra_b64 = payload.split(":", 1)
    iv    = base64.b64decode(iv_b64)
    cifra = base64.b64decode(cifra_b64)
    cipher = AES.new(CHAVE_AES, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(cifra), AES.block_size).decode("utf-8")

# ─── Dependências opcionais de UI ────────────────────────

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich.theme import Theme
    from rich.prompt import Prompt
    from rich import box
    from prompt_toolkit import PromptSession
    from prompt_toolkit.styles import Style as PTStyle
    from prompt_toolkit.formatted_text import HTML
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

if HAS_RICH:
    TEMA = Theme({
        "sistema": "bold cyan",
        "voce":    "bold green",
        "outro":   "bold yellow",
        "ts":      "dim white",
        "cmd":     "bold magenta",
        "erro":    "bold red",
        "info":    "dim cyan",
        "sucesso": "bold green",
    })

BANNER = """\
 ██████╗██╗  ██╗ █████╗ ████████╗
██╔════╝██║  ██║██╔══██╗╚══██╔══╝
██║     ███████║███████║   ██║   
██║     ██╔══██║██╔══██║   ██║   
╚██████╗██║  ██║██║  ██║   ██║   
 ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝  \
"""


# ─── Envio com criptografia ──────────────────────────────

def enviar(sock, texto):
    """Criptografa o payload JSON e envia pelo socket."""
    raw = json.dumps({"text": texto}, ensure_ascii=False)
    payload = criptografar(raw) + "\n"
    sock.sendall(payload.encode())


# ─── Cliente Simples (fallback sem Rich) ─────────────────

class ClienteSimples:
    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.buf = ""

    def iniciar(self):
        try:
            self.sock.connect((HOST, PORTA))
        except ConnectionRefusedError:
            print("Erro: servidor não encontrado.")
            sys.exit(1)

        threading.Thread(target=self._receber, daemon=True).start()

        try:
            while True:
                msg = input()
                enviar(self.sock, msg)
                if msg.lower() == "/sair":
                    break
        except (EOFError, KeyboardInterrupt):
            pass
        finally:
            self.sock.close()

    def _receber(self):
        while True:
            try:
                dados = self.sock.recv(2048)
                if not dados:
                    break
                self.buf += dados.decode(errors="replace")
                while "\n" in self.buf:
                    linha, _, self.buf = self.buf.partition("\n")
                    linha = linha.strip()
                    if not linha:
                        continue
                    try:
                        decriptado = descriptografar(linha)
                        pkt = json.loads(decriptado)
                        print(pkt.get("text", ""))
                    except Exception:
                        print(linha)
            except OSError:
                break


# ─── Cliente Rich ────────────────────────────────────────

class ClienteRich:
    def __init__(self):
        self.console = Console(theme=TEMA, highlight=False, file=sys.__stdout__, force_terminal=True)
        self.sock    = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.rodando = True
        self.buf     = ""
        self.session = PromptSession()
        self.pt_style = PTStyle.from_dict({"prompt": "ansicyan bold"})

        self._fila_lock = threading.Lock()
        self._fila = []
        self._evento = threading.Event()

    def conectar(self):
        try:
            self.sock.connect((HOST, PORTA))
        except ConnectionRefusedError:
            self.console.print("[erro]  Servidor não encontrado.[/]")
            sys.exit(1)

    def _receber(self):
        """Lê bytes do socket, descriptografa e enfileira pacotes."""
        while self.rodando:
            try:
                dados = self.sock.recv(2048)
                if not dados:
                    break
                self.buf += dados.decode(errors="replace")
                while "\n" in self.buf:
                    linha, _, self.buf = self.buf.partition("\n")
                    linha = linha.strip()
                    if not linha:
                        continue
                    try:
                        decriptado = descriptografar(linha)
                        pkt = json.loads(decriptado)
                    except Exception:
                        pkt = {"type": "info", "text": linha}
                    with self._fila_lock:
                        self._fila.append(pkt)
                    self._evento.set()
            except OSError:
                break

        if self.rodando:
            with self._fila_lock:
                self._fila.append({"type": "desconectado", "text": ""})
            self._evento.set()

    def _proximo_pacote(self, timeout=None):
        self._evento.wait(timeout)
        with self._fila_lock:
            if self._fila:
                pkt = self._fila.pop(0)
                if not self._fila:
                    self._evento.clear()
                return pkt
        return None

    def limpar(self):
        os.system("cls" if os.name == "nt" else "clear")

    def cabecalho(self):
        self.console.print(Panel(
            Text(BANNER, style="bold cyan", justify="center"),
            border_style="blue",
            box=box.DOUBLE,
        ))

    def imprimir_pkt(self, pkt):
        tipo  = pkt.get("type", "info")
        texto = pkt.get("text", "")

        if tipo == "msg":
            if "] Sistema:" in texto:
                partes = texto.split("] Sistema:", 1)
                hora = partes[0].lstrip("[")
                self.console.print(f"[ts][{hora}][/] [sistema]⚙ Sistema:[/] [info]{partes[1].strip()}[/]")
            else:
                try:
                    ts_part, resto = texto.split("] ", 1)
                    hora = ts_part.lstrip("[")
                    nome, msg = resto.split(": ", 1)
                    self.console.print(f"[ts][{hora}][/] [outro]{nome}:[/] {msg}")
                except ValueError:
                    self.console.print(texto)

        elif tipo == "voce":
            try:
                ts_part, resto = texto.split("] ", 1)
                hora = ts_part.lstrip("[")
                _, msg = resto.split(": ", 1)
                self.console.print(f"[ts][{hora}][/] [voce]Você:[/] {msg}")
            except ValueError:
                self.console.print(texto)

        elif tipo == "erro":
            self.console.print(f"[erro]  {texto}[/]")

        elif tipo == "sucesso":
            self.console.print(f"[sucesso]  {texto}[/]")

        elif tipo in ("info", "ok"):
            self.console.print(f"[info]{texto}[/]")

        elif tipo == "sair":
            self.console.print(f"[sistema]  {texto}[/]")

        elif tipo == "desconectado":
            self.console.print("[erro]Conexão encerrada pelo servidor.[/]")

    def _prompt(self, label, senha=False):
        try:
            if senha:
                import getpass
                self.console.print(f"[cmd]{label}:[/] ", end="")
                return getpass.getpass("")
            else:
                return self.session.prompt(
                    HTML(f"<ansicyan><b>{label}: </b></ansicyan>"),
                    style=self.pt_style,
                )
        except (EOFError, KeyboardInterrupt):
            return "/sair"

    def fase_login(self):
        while True:
            pkt = self._proximo_pacote(timeout=10)
            if pkt is None:
                continue

            tipo  = pkt.get("type")
            texto = pkt.get("text", "")

            if tipo == "menu":
                self.console.print()
                self.console.print(Panel(
                    "[bold white]\\[1][/] Login\n[bold white]\\[2][/] Criar conta\n[bold white]\\[3][/] Sair",
                    title="[bold cyan]Chat Seguro v2.0[/]",
                    border_style="blue",
                    box=box.ROUNDED,
                    width=30,
                ))
                opcao = self._prompt("Escolha")
                enviar(self.sock, opcao)

            elif tipo == "prompt":
                resp = self._prompt(texto)
                enviar(self.sock, resp)

            elif tipo == "prompt_senha":
                resp = self._prompt(texto, senha=True)
                enviar(self.sock, resp)

            elif tipo == "erro":
                self.console.print(f"[erro] {texto}[/]")

            elif tipo == "sucesso":
                self.console.print(f"[sucesso] {texto}[/]")

            elif tipo == "ok":
                self.console.print(f"[sucesso]  {texto}[/]")
                try:
                    username = texto.split("Bem-vindo,")[1].strip().rstrip("!").split()[0]
                except Exception:
                    username = "usuário"
                return username

            elif tipo == "sair":
                self.console.print(f"[sistema]  {texto}[/]")
                return None

            elif tipo == "desconectado":
                return None

    def fase_chat(self, username):
        from prompt_toolkit.patch_stdout import patch_stdout

        self.console.rule(f"[sistema] Chat — {username} [/]")
        self.console.print("[info]Comandos: [cmd]/usuarios[/]  [cmd]/historico[/]  [cmd]/sair[/][/]\n")

        def _exibir():
            while self.rodando:
                pkt = self._proximo_pacote(timeout=0.2)
                if pkt:
                    tipo = pkt.get("type")
                    if tipo in ("sair", "desconectado"):
                        self.imprimir_pkt(pkt)
                        self.rodando = False
                        break
                    if tipo != "voce":
                        self.imprimir_pkt(pkt)

        threading.Thread(target=_exibir, daemon=True).start()

        try:
            with patch_stdout():
                while self.rodando:
                    try:
                        entrada = self.session.prompt(
                            HTML(f"<ansicyan><b>› </b></ansicyan>"),
                            style=self.pt_style,
                        )
                    except (EOFError, KeyboardInterrupt):
                        entrada = "/sair"

                    if not entrada or not entrada.strip():
                        continue

                    enviar(self.sock, entrada.strip())

                    if entrada.strip().lower() == "/sair":
                        self.rodando = False
                        break
        except Exception:
            pass

    def iniciar(self):
        self.conectar()
        self.limpar()
        self.cabecalho()
        self.console.print(Panel(
            f"[info]Conectado a [bold]{HOST}:{PORTA}[/bold]  🔒 AES-256-CBC[/]",
            border_style="cyan",
            box=box.ROUNDED,
        ))

        threading.Thread(target=self._receber, daemon=True).start()

        username = self.fase_login()

        if username:
            self.fase_chat(username)

        self.rodando = False
        try:
            self.sock.close()
        except OSError:
            pass
        self.console.print("\n[info]Até logo! 👋[/]")


def main():
    if HAS_RICH:
        ClienteRich().iniciar()
    else:
        print("⚠  Rich/prompt_toolkit não instalados. Usando modo simples.")
        print("   Instale com:  pip3 install rich prompt_toolkit\n")
        ClienteSimples().iniciar()

if __name__ == "__main__":
    main()
