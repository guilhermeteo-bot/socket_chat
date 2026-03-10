
import socket
import threading
import json
import os
import hashlib
import base64
from datetime import datetime

# ─── Criptografia AES-256-CBC ────────────────────────────
# pip install pycryptodome
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

# Chave fixa de 32 bytes (AES-256). Deve ser idêntica no client.py.
# Em produção, use variável de ambiente ou troca de chave via DH.
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

# ─── Configurações gerais ────────────────────────────────

HOST = 'localhost'
PORTA = 12345
ARQUIVO_USUARIOS = "usuarios.json"
ARQUIVO_HISTORICO = "historico.json"
MAX_TENTATIVAS = 5

LOCK_USUARIOS  = threading.Lock()
LOCK_HISTORICO = threading.Lock()
LOCK_CLIENTES  = threading.Lock()

clientes_online = {}  # {username: conexao}


def _iniciar_arquivo(path, padrao):
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump(padrao, f)

_iniciar_arquivo(ARQUIVO_USUARIOS, {})
_iniciar_arquivo(ARQUIVO_HISTORICO, [])


def gerar_hash(senha):
    return hashlib.sha256(senha.encode()).hexdigest()


def carregar_json(path, lock):
    with lock:
        with open(path) as f:
            return json.load(f)


def salvar_json(path, dados, lock):
    tmp = path + ".tmp"
    with lock:
        with open(tmp, "w") as f:
            json.dump(dados, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)


def salvar_mensagem(remetente, texto):
    hist = carregar_json(ARQUIVO_HISTORICO, LOCK_HISTORICO)
    hist.append({"ts": ts(), "de": remetente, "msg": texto})
    salvar_json(ARQUIVO_HISTORICO, hist[-500:], LOCK_HISTORICO)


def ts():
    return datetime.now().strftime("%H:%M")


# ─── Envio / Recepção com criptografia ──────────────────

def enviar(conexao, tipo, texto):
    """Serializa em JSON, criptografa e envia pelo socket."""
    raw = json.dumps({"type": tipo, "text": texto}, ensure_ascii=False)
    payload = criptografar(raw) + "\n"
    conexao.sendall(payload.encode())


def receber_linha(conexao, buf):
    """Lê até '\\n', retorna (linha_descriptografada, buf_restante)."""
    while "\n" not in buf:
        dados = conexao.recv(2048)
        if not dados:
            raise ConnectionResetError
        buf += dados.decode(errors="replace")
    linha, _, buf = buf.partition("\n")
    linha = linha.strip()
    if linha:
        linha = descriptografar(linha)
    return linha, buf


def recv_input(conexao, buf):
    """Aguarda uma linha de input do cliente e retorna (texto, buf)."""
    linha, buf = receber_linha(conexao, buf)
    try:
        pkt = json.loads(linha)
        return pkt.get("text", "").strip(), buf
    except json.JSONDecodeError:
        return linha.strip(), buf

# ─── Broadcast ──────────────────────────────────────────

def broadcast(remetente, texto):
    salvar_mensagem(remetente, texto)
    hora = ts()
    with LOCK_CLIENTES:
        mortos = []
        for nome, conn in clientes_online.items():
            if nome == remetente:
                continue
            try:
                enviar(conn, "msg", f"[{hora}] {remetente}: {texto}")
            except OSError:
                mortos.append(nome)
        for nome in mortos:
            clientes_online.pop(nome, None)


def lista_online():
    with LOCK_CLIENTES:
        nomes = list(clientes_online.keys())
    return "Online: " + ", ".join(nomes) if nomes else "Nenhum usuário online."


def historico_recente(n=20):
    hist = carregar_json(ARQUIVO_HISTORICO, LOCK_HISTORICO)
    if not hist:
        return "Sem histórico ainda."
    return "\n".join(f"[{m['ts']}] {m['de']}: {m['msg']}" for m in hist[-n:])


# ─── Autenticação ────────────────────────────────────────

def autenticar(conexao):
    buf = ""
    tentativas = {}

    while True:
        enviar(conexao, "menu", "")

        try:
            opcao, buf = recv_input(conexao, buf)
        except (ConnectionResetError, OSError):
            return None

        usuarios = carregar_json(ARQUIVO_USUARIOS, LOCK_USUARIOS)

        if opcao == "1":
            enviar(conexao, "prompt", "Usuário")
            usuario, buf = recv_input(conexao, buf)

            bloqueios = tentativas.get(usuario, 0)
            if bloqueios >= MAX_TENTATIVAS:
                enviar(conexao, "erro", "Muitas tentativas. Tente mais tarde.")
                continue

            enviar(conexao, "prompt_senha", "Senha")
            senha, buf = recv_input(conexao, buf)

            if usuario in usuarios and usuarios[usuario] == gerar_hash(senha):
                with LOCK_CLIENTES:
                    if usuario in clientes_online:
                        enviar(conexao, "erro", "Usuário já conectado em outro lugar.")
                        continue
                enviar(conexao, "ok", f"Bem-vindo, {usuario}!")
                return usuario
            else:
                tentativas[usuario] = bloqueios + 1
                restantes = MAX_TENTATIVAS - tentativas[usuario]
                enviar(conexao, "erro", f"Credenciais inválidas. Tentativas restantes: {restantes}")

        elif opcao == "2":
            enviar(conexao, "prompt", "Novo usuário")
            usuario, buf = recv_input(conexao, buf)

            if len(usuario) < 3:
                enviar(conexao, "erro", "Nome deve ter ao menos 3 caracteres.")
                continue
            if usuario in usuarios:
                enviar(conexao, "erro", "Usuário já existe.")
                continue

            enviar(conexao, "prompt_senha", "Nova senha (mín. 6 chars)")
            senha, buf = recv_input(conexao, buf)

            if len(senha) < 6:
                enviar(conexao, "erro", "Senha muito curta.")
                continue

            usuarios[usuario] = gerar_hash(senha)
            salvar_json(ARQUIVO_USUARIOS, usuarios, LOCK_USUARIOS)
            enviar(conexao, "sucesso", "Conta criada com sucesso! Faça login.")

        elif opcao == "3":
            enviar(conexao, "sair", "Até logo!")
            return None


# ─── Handler do cliente ──────────────────────────────────

def lidar_com_cliente(conexao, endereco):
    print(f"[+] {endereco} conectado")

    usuario = autenticar(conexao)
    if not usuario:
        conexao.close()
        return

    with LOCK_CLIENTES:
        clientes_online[usuario] = conexao

    broadcast("Sistema", f"{usuario} entrou. {lista_online()}")
    print(f"[✓] {usuario} autenticado")

    buf = ""
    try:
        while True:
            try:
                linha, buf = receber_linha(conexao, buf)
            except (ConnectionResetError, OSError):
                break

            if not linha:
                continue

            try:
                pkt = json.loads(linha)
                texto = pkt.get("text", "").strip()
            except json.JSONDecodeError:
                texto = linha.strip()

            if not texto:
                continue

            if texto.startswith("/"):
                cmd = texto.lower()
                if cmd == "/sair":
                    enviar(conexao, "sair", "Até logo!")
                    break
                elif cmd == "/usuarios":
                    enviar(conexao, "info", lista_online())
                elif cmd == "/historico":
                    enviar(conexao, "info", historico_recente())
                else:
                    enviar(conexao, "erro", "Comando desconhecido. Use /usuarios, /historico ou /sair")
            else:
                hora = ts()
                enviar(conexao, "voce", f"[{hora}] Você: {texto}")
                broadcast(usuario, texto)

    except Exception as e:
        print(f"[!] Erro com {usuario}: {e}")
    finally:
        with LOCK_CLIENTES:
            clientes_online.pop(usuario, None)
        broadcast("Sistema", f"{usuario} saiu. {lista_online()}")
        conexao.close()
        print(f"[-] {usuario} desconectado")


def main():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORTA))
    srv.listen()
    print(f"🚀 Servidor rodando em {HOST}:{PORTA}  [AES-256-CBC ativo]")
    try:
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=lidar_com_cliente, args=(conn, addr), daemon=True).start()
    except KeyboardInterrupt:
        print("\n[!] Servidor encerrado.")
    finally:
        srv.close()

if __name__ == "__main__":
    main()
