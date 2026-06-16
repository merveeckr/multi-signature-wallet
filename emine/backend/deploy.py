# ─────────────────────────────────────────────────────────────
# deploy.py — Kontrat Deploy Scripti
# Yazan: Emine Binay | COM 4532 Blockchain Projesi
# ─────────────────────────────────────────────────────────────
# Bu dosyanın görevi:
#   Merve'nin yazdığı MultiSigWallet kontratını Hardhat'ın
#   local blockchain ağına yüklemek (deploy etmek).
#
#   Deploy = kontratı blockchain'e kalıcı olarak yerleştirmek.
#   Bir kez deploy edilir, sonra adresiyle çağrılır.
#
#   Çalıştırma sırası:
#   1. Önce Hardhat node başlatılmalı (ayrı terminalde)
#   2. Sonra bu script çalıştırılır: python backend/deploy.py
#   3. Çıktıdaki CONTRACT_ADDRESS .env'ye yazılır
# ─────────────────────────────────────────────────────────────

import json
import os
from web3 import Web3
from dotenv import load_dotenv

# .env dosyasını oku
load_dotenv()

# ── Ayarları oku ──────────────────────────────────────────
# Tüm gizli bilgileri .env'den alıyoruz
RPC_URL     = os.getenv("RPC_URL", "http://127.0.0.1:8545")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
OWNER_1     = os.getenv("OWNER_1")
OWNER_2     = os.getenv("OWNER_2")
OWNER_3     = os.getenv("OWNER_3")
CHAIN_ID    = int(os.getenv("CHAIN_ID", "31337"))

# ── Blockchain'e bağlan ───────────────────────────────────
# HTTPProvider: Hardhat'ın local node'una HTTP ile bağlanır
w3      = Web3(Web3.HTTPProvider(RPC_URL))

# Private key'den hesap türet — bu hesap deploy işlemini yapacak
account = w3.eth.account.from_key(PRIVATE_KEY)

# Bağlantı kontrolü
print(f"Bağlantı durumu : {w3.is_connected()}")
print(f"Deploy eden     : {account.address}")

# ── Artifact dosyasını oku ────────────────────────────────
# Hardhat kontratı derleyince (compile) artifacts/ klasörüne yazar.
# Bu JSON dosyasında iki önemli şey var:
#   - abi:      kontratın fonksiyon listesi (web3.py için)
#   - bytecode: kontratın makine kodu (blockchain'e bu yüklenir)
artifact_path = os.path.join(
    os.path.dirname(__file__),          # backend/ klasörü
    "..",                                # proje kökü
    "artifacts", "contracts",            # Hardhat'ın çıktı klasörü
    "MultiSigWallet.sol",                # kontrat dosyası adı
    "MultiSigWallet.json"                # derlenmiş artifact
)

# Dosyayı aç ve oku
with open(artifact_path) as f:
    artifact = json.load(f)

# ABI ve bytecode'u ayır
abi      = artifact["abi"]       # fonksiyon listesi
bytecode = artifact["bytecode"]  # makine kodu

# ── Kontratı deploy et ────────────────────────────────────
# Sahip listesi: 3 kişinin adresi
owners = [OWNER_1, OWNER_2, OWNER_3]

# M değeri: kaç onay gerekiyor?
# 2-of-3 → 3 sahibin 2'si onaylamalı
M = 2

print("\nDeploy ediliyor...")
print(f"Sahipler : {owners}")
print(f"Eşik (M) : {M} of {len(owners)}")

# Kontrat nesnesini oluştur (henüz deploy edilmedi)
contract = w3.eth.contract(abi=abi, bytecode=bytecode)

# Deploy işlemini oluştur
# constructor(owners, M) → kontratın başlangıç fonksiyonu
tx = contract.constructor(owners, M).build_transaction({
    "from"    : account.address,
    "nonce"   : w3.eth.get_transaction_count(account.address),
    "gas"     : 3000000,   # deploy için daha fazla gas gerekir
    "chainId" : CHAIN_ID,
})

# İşlemi private key ile imzala
signed = account.sign_transaction(tx)

# İmzalı işlemi blockchain'e gönder
tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

# İşlemin onaylanmasını bekle
print("Onay bekleniyor...")
receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

# Deploy başarılı — kontrat adresi receipt içinde geliyor
contract_address = receipt.contractAddress

print(f"\n✓ Deploy başarılı!")
print(f"✓ TX Hash        : {tx_hash.hex()}")
print(f"✓ Kontrat adresi : {contract_address}")
print(f"\n>>> .env dosyasına şu satırı ekle/güncelle:")
print(f"CONTRACT_ADDRESS={contract_address}")