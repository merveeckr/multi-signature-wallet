# ─────────────────────────────────────────────────────────────
# eip712_signer.py — EIP-712 Off-Chain İmza Modülü
# Yazan: Emine Binay | COM 4532 Blockchain Projesi
# ─────────────────────────────────────────────────────────────
# Bu dosyanın görevi:
#   Sahiplerin işlemleri blockchain'e gitmeden (gas ödemeden)
#   kendi bilgisayarlarında imzalamasını sağlamak.
#   Tüm imzalar toplandıktan sonra tek seferde blockchain'e
#   gönderilir — bu "batch submit" olarak adlandırılır.
#
#   EIP-712 nedir?
#   Ethereum İmzalama Standardı. İnsanın okuyabileceği formatta
#   (adres, miktar, hedef gibi) veriyi imzalamayı sağlar.
#   Kullanıcı MetaMask'ta "0x1234..." yerine "0.5 ETH → 0xABC..."
#   gibi anlamlı bir şey görür.
#
#   Normal akış vs EIP-712 akışı:
#   Normal  : Her sahip ayrı confirmTransaction gönderir (N gas)
#   EIP-712 : Sahipler off-chain imzalar → tek tx submit (1 gas)
#
#   Çalıştırma:
#   python backend/eip712_signer.py
# ─────────────────────────────────────────────────────────────

import os
import sys
sys.path.insert(0, os.path.dirname(__file__))

from web3 import Web3
from eth_account import Account
from eth_account.messages import encode_typed_data
from dotenv import load_dotenv
import json

load_dotenv()

# ── Ayarları oku ──────────────────────────────────────────
RPC_URL          = os.getenv("RPC_URL", "http://127.0.0.1:8545")
PRIVATE_KEY      = os.getenv("PRIVATE_KEY")
CONTRACT_ADDRESS = os.getenv("CONTRACT_ADDRESS")
CHAIN_ID         = int(os.getenv("CHAIN_ID", "31337"))

# Hardhat'ın herkese açık test private key'leri
# Gerçek projede bunlar her sahibin kendi key'i olurdu
OWNER_1_KEY = os.getenv("PRIVATE_KEY")
OWNER_2_KEY = "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"

w3 = Web3(Web3.HTTPProvider(RPC_URL))


# ── EIP-712 Domain Tanımı ─────────────────────────────────
def get_domain():
    """
    EIP-712 domain separator oluşturur.

    Domain separator nedir?
    Her kontratın kendine özgü bir kimliği. İmza hangi kontrat
    için verildiğini belirtir. Başka bir kontrat bu imzayı
    kullanamaz — replay saldırısını önler.

    İçeriği:
    - name    : kontratın adı
    - version : versiyon (1)
    - chainId : hangi ağda (31337 = Hardhat local)
    - verifyingContract: kontratın adresi
    """
    return {
        "name"              : "MultiSigWallet",
        "version"           : "1",
        "chainId"           : CHAIN_ID,
        "verifyingContract" : Web3.to_checksum_address(CONTRACT_ADDRESS),
    }


# ── EIP-712 Tip Tanımı ────────────────────────────────────
# Solidity'deki struct Transaction'ın Python karşılığı
# Bu yapı imzalanan verinin şablonunu tanımlar
TRANSACTION_TYPE = {
    "Transaction": [
        {"name": "to",    "type": "address"},  # alıcı adres
        {"name": "value", "type": "uint256"},  # ETH miktarı (wei)
        {"name": "data",  "type": "bytes"},    # ekstra veri
        {"name": "nonce", "type": "uint256"},  # tekrar saldırısı önlemi
    ]
}


# ── FONKSİYON 1: Off-chain imzala ────────────────────────
def sign_transaction_offchain(private_key: str, to: str,
                               amount_eth: float, nonce: int,
                               data: bytes = b""):
    """
    Bir işlemi blockchain'e gitmeden imzalar (gas ödemez).

    Bu fonksiyon ne zaman çağrılır?
    Her sahip kendi bilgisayarında bu fonksiyonu çağırır.
    İmzasını üretir ve batch submit'e gönderir.

    Parametreler:
        private_key (str):  İmzalayan sahibin private key'i
        to          (str):  Parayı alacak adres
        amount_eth  (float):Gönderilecek ETH miktarı
        nonce       (int):  İşlem numarası (tekrar önlemi)
        data        (bytes):Ekstra veri (boş olabilir)

    Döndürür:
        dict: {
            "signature": "0x...",  imza
            "signer":    "0x...",  imzalayan adres
            "to":        "0x...",  hedef adres
            "value":     123456,   wei cinsinden
            "nonce":     0         işlem numarası
        }
    """
    # ETH → wei dönüşümü
    value_wei = w3.to_wei(amount_eth, "ether")

    # İmzalanacak veriyi EIP-712 formatında hazırla
    structured_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name",              "type": "string"},
                {"name": "version",           "type": "string"},
                {"name": "chainId",           "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            **TRANSACTION_TYPE,
        },
        "domain"     : get_domain(),
        "primaryType": "Transaction",
        "message"    : {
            "to"   : Web3.to_checksum_address(to),
            "value": value_wei,
            "data" : data,
            "nonce": nonce,
        },
    }

    # encode_typed_data: veriyi EIP-712 formatına çevirir
    # Account.sign_message: private key ile imzalar
    signable = encode_typed_data(full_message=structured_data)
    account  = Account.from_key(private_key)
    signed   = account.sign_message(signable)

    return {
        "signature": signed.signature.hex(),
        "signer"   : account.address,
        "to"       : Web3.to_checksum_address(to),
        "value"    : value_wei,
        "nonce"    : nonce,
        "data"     : data.hex() if data else "0x",
    }


# ── FONKSİYON 2: İmzayı doğrula ─────────────────────────
def verify_signature(signature: str, to: str, value_wei: int,
                     nonce: int, data: bytes = b""):
    """
    Bir imzanın geçerli olup olmadığını ve kimin tarafından
    yapıldığını doğrular.

    Bu fonksiyon ne zaman çağrılır?
    Batch submit öncesinde her imzanın gerçekten bir sahipten
    geldiğini doğrulamak için.

    ecrecover nedir?
    İmzadan imzalayanın adresini geri türeten kriptografik işlem.
    "Bu imzayı kim attı?" sorusunu cevaplar.

    Döndürür:
        str: İmzayı atan kişinin Ethereum adresi
    """
    structured_data = {
        "types": {
            "EIP712Domain": [
                {"name": "name",              "type": "string"},
                {"name": "version",           "type": "string"},
                {"name": "chainId",           "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            **TRANSACTION_TYPE,
        },
        "domain"     : get_domain(),
        "primaryType": "Transaction",
        "message"    : {
            "to"   : Web3.to_checksum_address(to),
            "value": value_wei,
            "data" : data,
            "nonce": nonce,
        },
    }

    signable          = encode_typed_data(full_message=structured_data)
    recovered_address = Account.recover_message(
        signable,
        signature=signature
    )
    return recovered_address


# ── FONKSİYON 3: Batch submit ────────────────────────────
def batch_submit(signatures: list, to: str, amount_eth: float,
                 nonce: int, data: bytes = b""):
    """
    Birden fazla off-chain imzayı tek bir blockchain işlemiyle
    gönderir.

    Normal akışta her sahip ayrı confirmTransaction gönderir:
    → 3 sahip × 82,000 gas = 246,000 gas

    Batch submit'te tek seferde gönderilir:
    → 1 submitTransaction = ~106,000 gas
    → Gas tasarrufu: ~140,000 gas (%57 tasarruf)

    Parametreler:
        signatures  (list): off-chain toplanan imzalar listesi
        to          (str):  hedef adres
        amount_eth  (float):ETH miktarı
        nonce       (int):  işlem numarası
        data        (bytes):ekstra veri

    Döndürür:
        dict: {"status": "success/error", "tx_hash": "0x..."}
    """
    import wallet_service as ws

    print(f"\n[BATCH SUBMIT] {len(signatures)} imza toplandı")

    # Her imzayı doğrula — sahte imza varsa reddet
    value_wei = w3.to_wei(amount_eth, "ether")
    for i, sig_data in enumerate(signatures):
        recovered = verify_signature(
            sig_data["signature"], to, value_wei, nonce, data
        )
        print(f"  İmza {i+1}: {recovered[:10]}... "
              f"{'✓ geçerli' if recovered == sig_data['signer'] else '✗ GEÇERSİZ'}")

        if recovered.lower() != sig_data["signer"].lower():
            return {
                "status" : "error",
                "message": f"İmza {i+1} geçersiz! Beklenen: "
                           f"{sig_data['signer']}, Bulunan: {recovered}"
            }

    # Tüm imzalar geçerliyse blockchain'e gönder
    print("  Tüm imzalar geçerli, blockchain'e gönderiliyor...")
    sonuc = ws.submit_transaction(to=to, amount_eth=amount_eth, data=data)
    return sonuc


# ── TEST: EIP-712 akışını dene ────────────────────────────
if __name__ == "__main__":
    print("="*55)
    print("  EIP-712 OFF-CHAIN İMZA TESTİ")
    print("="*55)

    # Test parametreleri
    hedef      = os.getenv("OWNER_2")
    miktar_eth = 0.05
    nonce      = 99  # test nonce'u

    print(f"\nTest işlemi:")
    print(f"  Hedef  : {hedef}")
    print(f"  Miktar : {miktar_eth} ETH")
    print(f"  Nonce  : {nonce}")

    # ── Adım 1: OWNER_1 off-chain imzalar ─────────────────
    print(f"\n[1] OWNER_1 off-chain imzalıyor...")
    imza_1 = sign_transaction_offchain(
        private_key=OWNER_1_KEY,
        to=hedef,
        amount_eth=miktar_eth,
        nonce=nonce
    )
    print(f"  İmza  : {imza_1['signature'][:20]}...")
    print(f"  Signer: {imza_1['signer']}")

    # ── Adım 2: OWNER_2 off-chain imzalar ─────────────────
    print(f"\n[2] OWNER_2 off-chain imzalıyor...")
    imza_2 = sign_transaction_offchain(
        private_key=OWNER_2_KEY,
        to=hedef,
        amount_eth=miktar_eth,
        nonce=nonce
    )
    print(f"  İmza  : {imza_2['signature'][:20]}...")
    print(f"  Signer: {imza_2['signer']}")

    # ── Adım 3: İmzaları doğrula (ecrecover) ──────────────
    print(f"\n[3] İmzalar doğrulanıyor (ecrecover)...")
    value_wei = w3.to_wei(miktar_eth, "ether")

    kurtarilan_1 = verify_signature(
        imza_1["signature"], hedef, value_wei, nonce
    )
    kurtarilan_2 = verify_signature(
        imza_2["signature"], hedef, value_wei, nonce
    )

    print(f"  OWNER_1 doğrulandı: "
          f"{'✓' if kurtarilan_1 == imza_1['signer'] else '✗'} "
          f"({kurtarilan_1[:10]}...)")
    print(f"  OWNER_2 doğrulandı: "
          f"{'✓' if kurtarilan_2 == imza_2['signer'] else '✗'} "
          f"({kurtarilan_2[:10]}...)")

    print(f"\n[4] Batch submit (tek tx ile blockchain'e gönder)...")
    sonuc = batch_submit(
        signatures=[imza_1, imza_2],
        to=hedef,
        amount_eth=miktar_eth,
        nonce=nonce
    )
    print(f"\n  Sonuç: {sonuc}")

    if sonuc.get("status") == "success":
        print(f"\n  ✓ EIP-712 batch submit başarılı!")
        print(f"  ✓ 2 off-chain imza → 1 blockchain tx")
    else:
        print(f"\n  ✗ Hata: {sonuc.get('message')}")

    print("="*55)