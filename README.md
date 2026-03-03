

> Cliente e Servidor TCP com interface TUI colorida  
> `Python` • `Socket` • `Threading` • `Rich` • `prompt_toolkit`


Chat em tempo real via TCP utilizando sockets Python. O servidor aceita múltiplos clientes simultaneamente através de threads, autentica usuários com senha hasheada e retransmite mensagens entre todos os participantes. O cliente conta com interface TUI colorida com prompt fixo na tela.

| | |
|---|---|
| **Linguagem** | Python 3.10+ |
| **Protocolo** | TCP — `socket.AF_INET / SOCK_STREAM` |
| **Comunicação** | Mensagens JSON (uma por linha) |
| **Autenticação** | Hash SHA-256 |
| **Interface** | Rich + prompt_toolkit |
| **Persistência** | `usuarios.json` / `historico.json` |

---

## Pré-requisitos

Instale as dependências do cliente:

```bash
pip3 install rich prompt_toolkit
```

O servidor não possui dependências externas — usa apenas a biblioteca padrão do Python.

---

## Como Usar

### 1. Iniciar o Servidor (Linux / Zorin OS)

```bash
python3 server.py
```

Para aceitar conexões de outros computadores na rede, certifique-se de que `HOST = '0.0.0.0'` no `server.py` e libere a porta no firewall:

```bash
sudo ufw allow 12345
sudo ufw enable
```

### 2. Descobrir o IP do Servidor

```bash
hostname -I
```

Anote o IP retornado (ex: `192.168.1.105`).

### 3. Configurar o Cliente

No arquivo `client.py`, altere a variável `HOST`:

```python
HOST = "192.168.1.105"   # IP do computador com o servidor
```

> Se cliente e servidor estiverem na mesma máquina, mantenha `HOST = 'localhost'`.

### 4. Iniciar o Cliente

```bash
python3 client.py
```

O menu de login será exibido automaticamente.

---

## Comandos Disponíveis no Chat

| Comando | Descrição |
|---|---|
| `/usuarios` | Lista todos os usuários online |
| `/historico` | Exibe as últimas 20 mensagens |
| `/sair` | Encerra a conexão |

---

## Segurança

- Senhas armazenadas como hash SHA-256 — nunca em texto puro
- Limite de 5 tentativas de login por sessão
- Detecção de sessão duplicada — mesmo usuário não loga duas vezes
- Escrita atômica nos arquivos JSON (evita corrupção)
- Locks em todas as operações de arquivo e lista de clientes

---

## Arquitetura

### server.py
- Cada cliente roda em uma thread independente
- Protocolo baseado em pacotes JSON por linha
- Broadcast distribui mensagens para todos os clientes online
- Histórico persistido em `historico.json` (máx. 500 mensagens)

### client.py
- Thread de recebimento coloca pacotes em fila — thread principal consome
- `patch_stdout` mantém o prompt fixo na última linha da tela
- `Console` com `force_terminal=True` garante cores corretas dentro do `patch_stdout`
- Fallback automático para modo texto simples sem dependências

---

## Estrutura de Arquivos

```
projeto/
├── server.py          # Servidor TCP
├── client.py          # Cliente com interface TUI
├── usuarios.json      # Criado automaticamente no primeiro uso
└── historico.json     # Criado automaticamente no primeiro uso
```
