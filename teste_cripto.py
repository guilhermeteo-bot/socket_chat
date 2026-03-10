import os
import base64

# ─── Copie as mesmas funções do server.py/client.py ──────
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

CHAVE_AES = b"ChatSeguro2024!!ChatSeguro2024!!"

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

# ─── Testes ───────────────────────────────────────────────

def separador(titulo):
    print(f"\n{'─'*50}")
    print(f"  {titulo}")
    print('─'*50)

erros = 0

# Teste 1 — Mensagem simples
separador("Teste 1: mensagem simples")
msg = "olá mundo"
cifra = criptografar(msg)
decifrada = descriptografar(cifra)
print(f"  Original:         '{msg}'")
print(f"  Criptografado:    {cifra}")
print(f"  Descriptografado: '{decifrada}'")
if msg == decifrada:
    print("  ✅ PASSOU")
else:
    print("  ❌ FALHOU")
    erros += 1

# Teste 2 — Mensagem com caracteres especiais
separador("Teste 2: caracteres especiais / acentos")
msg2 = "João disse: 'Olá, tudo bem? 😊'"
cifra2 = criptografar(msg2)
decifrada2 = descriptografar(cifra2)
print(f"  Original:         '{msg2}'")
print(f"  Criptografado:    {cifra2}")
print(f"  Descriptografado: '{decifrada2}'")
if msg2 == decifrada2:
    print("  ✅ PASSOU")
else:
    print("  ❌ FALHOU")
    erros += 1

# Teste 3 — Duas mensagens iguais geram cifras DIFERENTES (IV aleatório)
separador("Teste 3: IV aleatório — mesma mensagem, cifras diferentes")
msg3 = "senha123"
c1 = criptografar(msg3)
c2 = criptografar(msg3)
print(f"  Mensagem:   '{msg3}'")
print(f"  Cifra 1:    {c1}")
print(f"  Cifra 2:    {c2}")
if c1 != c2:
    print("  ✅ PASSOU — cifras diferentes (IV único por mensagem)")
else:
    print("  ❌ FALHOU — cifras iguais indicam IV fixo (vulnerabilidade!)")
    erros += 1

# Teste 4 — Payload JSON completo (como trafega no socket)
separador("Teste 4: payload JSON completo (formato real do socket)")
import json
pkt = json.dumps({"type": "msg", "text": "Oi, como vai?"})
cifra4 = criptografar(pkt)
decifrada4 = descriptografar(cifra4)
pkt_recuperado = json.loads(decifrada4)
print(f"  JSON original:    {pkt}")
print(f"  Criptografado:    {cifra4}")
print(f"  JSON recuperado:  {pkt_recuperado}")
if pkt_recuperado == json.loads(pkt):
    print("  ✅ PASSOU")
else:
    print("  ❌ FALHOU")
    erros += 1

# Teste 5 — Chave errada deve falhar
separador("Teste 5: chave errada deve gerar erro")
def descriptografar_chave_errada(payload: str) -> str:
    CHAVE_ERRADA = b"ChaveErrada12345ChaveErrada12345"
    iv_b64, cifra_b64 = payload.split(":", 1)
    iv    = base64.b64decode(iv_b64)
    cifra = base64.b64decode(cifra_b64)
    cipher = AES.new(CHAVE_ERRADA, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(cifra), AES.block_size).decode("utf-8")

msg5 = "mensagem secreta"
cifra5 = criptografar(msg5)
try:
    resultado = descriptografar_chave_errada(cifra5)
    print(f"  ❌ FALHOU — conseguiu descriptografar com chave errada: '{resultado}'")
    erros += 1
except Exception as e:
    print(f"  Tentativa com chave errada gerou: {type(e).__name__}")
    print(f"  ✅ PASSOU — chave errada não consegue descriptografar")

# ─── Resultado final ──────────────────────────────────────
print(f"\n{'═'*50}")
if erros == 0:
    print("  🔒 TODOS OS TESTES PASSARAM — criptografia funcionando!")
else:
    print(f"  ⚠️  {erros} teste(s) falharam.")
print('═'*50)
