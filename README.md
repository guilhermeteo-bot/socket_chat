# 💬 Chat Seguro — TCP + AES-256-CBC

Chat em tempo real cliente-servidor com **criptografia AES-256-CBC** em todas as mensagens.

---

## Arquitetura

```
┌─────────────┐        TCP Socket (porta 12345)        ┌─────────────┐
│  client.py  │ ◄────── JSON criptografado (AES) ──────► │  server.py  │
└─────────────┘                                         └─────────────┘
                                                              │
                                                    ┌─────────┴─────────┐
                                                    │  usuarios.json    │
                                                    │  historico.json   │
                                                    └───────────────────┘
```

- O **servidor** aceita múltiplos clientes em threads independentes.
- **Todo pacote** trafegado no socket (login, senha, comandos, mensagens) é criptografado antes de sair do remetente e descriptografado ao chegar no destinatário.
- As mensagens são salvas **em texto plano** no histórico local do servidor (proteção apenas do transporte).

---

## Criptografia

### Algoritmo: AES-256-CBC

| Parâmetro | Valor |
|-----------|-------|
| Algoritmo | AES |
| Modo | CBC (Cipher Block Chaining) |
| Tamanho da chave | 256 bits (32 bytes) |
| IV | 16 bytes aleatórios por mensagem (`os.urandom(16)`) |
| Padding | PKCS7 |
| Encoding do payload | Base64 |

### Formato do payload no socket

```
<iv_base64>:<cifra_base64>\n
```

Cada mensagem usa um **IV (vetor de inicialização) único e aleatório**, garantindo que duas mensagens idênticas produzam cifras diferentes.

### Funções implementadas

```python
def criptografar(mensagem: str) -> str:
    iv = os.urandom(16)
    cipher = AES.new(CHAVE_AES, AES.MODE_CBC, iv)
    cifra = cipher.encrypt(pad(mensagem.encode("utf-8"), AES.block_size))
    return base64.b64encode(iv).decode() + ":" + base64.b64encode(cifra).decode()

def descriptografar(payload: str) -> str:
    iv_b64, cifra_b64 = payload.split(":", 1)
    iv    = base64.b64decode(iv_b64)
    cifra = base64.b64decode(cifra_b64)
    cipher = AES.new(CHAVE_AES, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(cifra), AES.block_size).decode("utf-8")
```

### Chave compartilhada

A chave AES de 32 bytes está definida em ambos os arquivos:

```python
CHAVE_AES = b"ChatSeguro2024!!ChatSeguro2024!!"
```

> ⚠️ Em produção, nunca deixe a chave no código-fonte. Use variáveis de ambiente ou uma troca de chaves como Diffie-Hellman.

---

## Funcionalidades

- 🔐 Autenticação com usuário e senha (hash SHA-256)
- 💬 Broadcast de mensagens para todos os clientes online
- 📜 Histórico das últimas 20 mensagens (`/historico`)
- 👥 Lista de usuários online (`/usuarios`)
- 🛡️ Bloqueio após 5 tentativas de login inválidas
- 🔒 Criptografia AES-256-CBC em **todos** os pacotes

---

## Instalação

```bash
# Clone o repositório
git clone https://github.com/seu-usuario/chat-seguro.git
cd chat-seguro

# Instale as dependências
pip install pycryptodome rich prompt_toolkit
```

---

## Execução

**Terminal 1 — Servidor:**
```bash
python server.py
```

**Terminal 2+ — Clientes:**
```bash
python client.py
```

---

## Dependências

| Biblioteca | Uso |
|------------|-----|
| `pycryptodome` | Criptografia AES-256-CBC |
| `rich` | Interface colorida no terminal (opcional) |
| `prompt_toolkit` | Input interativo com histórico (opcional) |

Sem `rich` e `prompt_toolkit`, o cliente funciona em modo texto simples.

---

## Estrutura de arquivos

```
chat-seguro/
├── server.py          # Servidor TCP multi-cliente
├── client.py          # Cliente com interface Rich
├── usuarios.json      # Banco de usuários (criado automaticamente)
├── historico.json     # Histórico de mensagens (criado automaticamente)
└── README.md
```
