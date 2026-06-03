# ─────────────────────────────────────────────────────────────
# config.py — Proje Ayarları
# Yazan: Emine Binay | COM 4532 Blockchain Projesi
# ─────────────────────────────────────────────────────────────
# Bu dosyanın görevi:
#   .env dosyasındaki gizli bilgileri (adresler, şifreler) okumak
#   ve diğer Python dosyalarına hazır değişkenler olarak sunmak.
#
#   Neden ayrı bir dosya?
#   Çünkü her dosyada tekrar tekrar os.getenv() yazmak yerine
#   sadece "from config import RPC_URL" diyerek kullanabiliriz.
# ─────────────────────────────────────────────────────────────

import os
from dotenv import load_dotenv

# .env dosyasını oku ve ortam değişkenlerine yükle
# load_dotenv() çağrılmazsa os.getenv() hiçbir şey bulamaz
load_dotenv()

# ── Blockchain Bağlantısı ─────────────────────────────────
# RPC_URL: Python'un blockchain'e konuştuğu adres
# Hardhat local ağı her zaman 8545 portunda çalışır
RPC_URL = os.getenv("RPC_URL", "http://127.0.0.1:8545")

# PRIVATE_KEY: İşlemleri imzalamak için kullanılan gizli anahtar
# Bu Hardhat'ın herkese açık test anahtarı — gerçek para yok!
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

# CHAIN_ID: Hangi ağda olduğumuzu söyler
# 31337 = Hardhat local ağı, 11155111 = Sepolia testnet
CHAIN_ID = int(os.getenv("CHAIN_ID", "31337"))

# ── Sahip Adresleri ───────────────────────────────────────
# Cüzdanı kontrol edecek 3 kişinin Ethereum adresleri
# Kontrat deploy edilirken bunlar "owner" olarak atanır
OWNER_1 = os.getenv("OWNER_1")  # 1. sahip
OWNER_2 = os.getenv("OWNER_2")  # 2. sahip
OWNER_3 = os.getenv("OWNER_3")  # 3. sahip

# ── Kontrat Adresi ────────────────────────────────────────
# deploy.py çalıştırıldıktan sonra bu değer .env'ye yazılır
# Başta boş — deploy olmadan kontrata bağlanamayız
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")

# ── ABI Dosyasının Yolu ───────────────────────────────────
# ABI (Application Binary Interface): Kontratın dışarıya açık
# fonksiyonlarının listesi. Web3.py bunu okuyarak hangi
# fonksiyonu nasıl çağıracağını anlar.
# Merve bu dosyayı hazırladı: abi/MultiSigWallet.abi.json
#
# os.path.dirname(__file__) = bu dosyanın bulunduğu klasör (backend/)
# ".." ile bir üst klasöre (proje kökü) çıkıyoruz
# oradan "abi/MultiSigWallet.abi.json"a ulaşıyoruz


# ABI dosyasının yolu — Hardhat'ın derlediği artifact dosyası
# abi/ klasörü boş, gerçek ABI artifacts/ içinde
ABI_PATH = os.path.join(
    os.path.dirname(__file__),              # backend/ klasörü
    "..",                                    # proje kökü
    "artifacts", "contracts",               # Hardhat artifact klasörü
    "MultiSigWallet.sol",                   # kontrat dosyası adı
    "MultiSigWallet.json"                   # derlenmiş JSON
)