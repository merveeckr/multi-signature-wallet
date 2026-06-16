# ─────────────────────────────────────────────────────────────
# wallet_service.py — Backend Servis Katmanı
# Yazan: Emine Binay | COM 4532 Blockchain Projesi
# ─────────────────────────────────────────────────────────────
# Bu dosyanın görevi:
#   Merve'nin Solidity kontratıyla Python arasında köprü kurmak.
#   İrem'in Streamlit arayüzü bu dosyadaki fonksiyonları çağırır,
#   bu dosya da blockchain'e gidip veriyi alır ve geri döner.
#
#   Katman yapısı:
#   İrem (Streamlit UI) → Emine (wallet_service.py) → Merve (Kontrat)
# ─────────────────────────────────────────────────────────────

import json
from web3 import Web3

# config.py'den ayarları import et
# Böylece RPC_URL, PRIVATE_KEY gibi şeyleri tekrar yazmak zorunda kalmayız
from backend.config import RPC_URL, PRIVATE_KEY, CONTRACT_ADDRESS, ABI_PATH, CHAIN_ID

# ── Blockchain Bağlantısı ─────────────────────────────────
# Web3.HTTPProvider: Python'un blockchain node'una HTTP üzerinden
# bağlanmasını sağlar. Tıpkı bir web sitesine istek atmak gibi.
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Hesabı private key'den türet
# Bu hesap işlemleri imzalamak için kullanılacak
# İmza = "bu işlemi ben onaylıyorum" demek
account = w3.eth.account.from_key(PRIVATE_KEY)

# ABI dosyasını oku (Merve'nin hazırladığı JSON dosyası)
# ABI olmadan web3.py kontratın fonksiyonlarını bilemez

# ABI dosyasını oku
# Hardhat'ın artifact JSON'u tüm kontrat bilgisini içerir
# Biz sadece "abi" anahtarındaki listeyi alıyoruz
with open(ABI_PATH) as f:
    artifact = json.load(f)
    abi = artifact["abi"]  # sadece abi listesini al, tüm dosyayı değil


# Kontrat nesnesini oluştur
# Bu nesne üzerinden contract.functions.xxx() şeklinde çağrı yaparız
contract = w3.eth.contract(
    address=Web3.to_checksum_address(CONTRACT_ADDRESS),
    abi=abi
)


# ── Yardımcı Fonksiyon ────────────────────────────────────
def _send_tx(fn, private_key: str = None):
    """
    Bir kontrat fonksiyonunu blockchain'e gönderir.
    private_key verilirse o hesap kullanılır, verilmezse modül düzeyindeki account.
    """
    try:
        act = w3.eth.account.from_key(private_key) if private_key else account
        tx = fn.build_transaction({
            "from": act.address,
            "nonce": w3.eth.get_transaction_count(act.address),
            "gas": 300000,
            "chainId": CHAIN_ID,
        })
        signed = act.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

        # İşlemin onaylanmasını bekle
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        return receipt
    except Exception:
        raise


# ── FONKSİYON 1: Cüzdan Genel Bilgileri ──────────────────
def get_wallet_stats():
    """
    Cüzdanın genel durumunu döner.

    İrem'in dashboard'undaki şu bilgileri doldurmak için kullanılır:
    - Cüzdandaki toplam ETH miktarı
    - Bir işlem için kaç onay gerektiği (threshold/M)
    - Toplam sahip sayısı
    - Sahiplerin adresleri
    - Kontratın adresi

    Blockchain'e sadece "okuma" isteği gönderir → gas ödemez.
    (Sadece veri değiştiren işlemler gas öder)
    """
    balance_wei = w3.eth.get_balance(
        Web3.to_checksum_address(CONTRACT_ADDRESS)
    )
    balance_eth = float(w3.from_wei(balance_wei, "ether"))
    threshold = contract.functions.numConfirmationsRequired().call()
    owners = contract.functions.getOwners().call()

    return {
        "balance_eth":      balance_eth,
        "threshold":        threshold,
        "total_owners":     len(owners),
        "owner_addresses":  owners,
        "contract_address": CONTRACT_ADDRESS,
    }


# ── FONKSİYON 2: Bekleyen İşlemler ───────────────────────
def get_pending_transactions():
    """
    Henüz yürütülmemiş (pending) işlemlerin listesini döner.

    İrem'in arayüzündeki "Bekleyen İşlemler" tablosunu doldurmak için
    kullanılır. Her satır bir işlemi temsil eder.
    """
    total = contract.functions.getTransactionCount().call()
    threshold = contract.functions.numConfirmationsRequired().call()
    pending = []

    for i in range(total):
        to, value, _, executed, num_confirmations = \
            contract.functions.getTransaction(i).call()

        if executed:
            continue

        pending.append({
            "id":                    i,
            "recipient":             to,
            "amount_eth":            float(w3.from_wei(value, "ether")),
            "current_confirmations": num_confirmations,
            "is_executable":         num_confirmations >= threshold,
        })

    return pending


# ── FONKSİYON 3: İşlem Onaylama ──────────────────────────
def approve_transaction(transaction_id: int, private_key: str = None):
    """
    Verilen ID'li işlemi onaylar.
    """
    try:
        receipt = _send_tx(
            contract.functions.confirmTransaction(transaction_id),
            private_key=private_key,
        )
        return {
            "status":  "success",
            "tx_hash": receipt.transactionHash.hex(),
        }
    except Exception as e:
        return {
            "status":  "error",
            "message": str(e),
        }
    

# ── FONKSİYON 4: İşlem Teklifi Oluşturma ─────────────────
def submit_transaction(to: str, amount_eth: float, private_key: str = None, data: bytes = b""):
    """
    Yeni bir işlem teklifi oluşturur ve pending listeye ekler.
    """
    try:
        amount_wei = w3.to_wei(amount_eth, "ether")
        to_address = Web3.to_checksum_address(to)

        receipt = _send_tx(
            contract.functions.submitTransaction(to_address, amount_wei, data),
            private_key=private_key,
        )

        tx_index = None
        try:
            logs = contract.events.SubmitTransaction().process_receipt(receipt)
            if logs:
                tx_index = logs[0]["args"]["txIndex"]
        except Exception:
            tx_index = len(receipt.logs) - 1

        return {
            "status":   "success",
            "tx_index": tx_index,
            "tx_hash":  receipt.transactionHash.hex(),
        }
    except Exception as e:
        return {
            "status":  "error",
            "message": str(e),
        }


# ── FONKSİYON 5: İşlemi Yürütme ──────────────────────────
def execute_transaction(transaction_id: int, private_key: str = None):
    """
    Yeterli onay alan bir işlemi gerçekten yürütür (parayı gönderir).
    """
    try:
        receipt = _send_tx(
            contract.functions.executeTransaction(transaction_id),
            private_key=private_key,
        )
        return {
            "status":  "success",
            "tx_hash": receipt.transactionHash.hex(),
        }
    except Exception as e:
        return {
            "status":  "error",
            "message": str(e),
        }


# ── FONKSİYON 6: Onay Geri Çekme ─────────────────────────
def revoke_confirmation(transaction_id: int, private_key: str = None):
    """
    Daha önce verilen onayı geri çeker.
    """
    try:
        receipt = _send_tx(
            contract.functions.revokeConfirmation(transaction_id),
            private_key=private_key,
        )
        return {
            "status":  "success",
            "tx_hash": receipt.transactionHash.hex(),
        }
    except Exception as e:
        return {
            "status":  "error",
            "message": str(e),
        }


# ── FONKSİYON 7: Onay Durumu Sorgula ─────────────────────
def get_active_address(private_key: str = None) -> str:
    """Aktif hesabın adresini döner. Key verilmezse .env'deki varsayılan kullanılır."""
    if private_key:
        return w3.eth.account.from_key(private_key).address
    return account.address


def get_paused_status() -> bool:
    """Cüzdanın dondurulup dondurulmadığını döner."""
    try:
        return contract.functions.paused().call()
    except Exception:
        return False


def pause_wallet(private_key: str = None):
    """Cüzdanı acil olarak dondurur. Sadece owner çağırabilir."""
    try:
        receipt = _send_tx(contract.functions.pause(), private_key=private_key)
        return {"status": "success", "tx_hash": receipt.transactionHash.hex()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def unpause_wallet(private_key: str = None):
    """Dondurulmuş cüzdanı yeniden açar. Sadece owner çağırabilir."""
    try:
        receipt = _send_tx(contract.functions.unpause(), private_key=private_key)
        return {"status": "success", "tx_hash": receipt.transactionHash.hex()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_confirmation_status(transaction_id: int, owner_address: str):
    """
    Belirli bir sahibin belirli bir işlemi onaylayıp onaylamadığını döner.
    """
    try:
        return contract.functions.getConfirmationStatus(
            transaction_id,
            Web3.to_checksum_address(owner_address)
        ).call()
    except Exception:
        return False


# ── FONKSİYON 8: İşlem Yürütülebilir mi? ─────────────────
def is_confirmed(transaction_id: int):
    """
    Bir işlemin yeterli onayı alıp almadığını kontrol eder.
    """
    try:
        return contract.functions.isConfirmed(transaction_id).call()
    except Exception:
        return False


# ── FONKSİYON 9: Yönetim İşlemi Encode Et ────────────────
def encode_management_call(function_name: str, *args):
    """
    Yönetim fonksiyonlarını (addOwner, removeOwner vs.)
    submitTransaction ile göndermek için ABI-encode eder.
    """
    desteklenen = [
        "addOwner",
        "removeOwner",
        "replaceOwner",
        "changeRequirement"
    ]

    if function_name not in desteklenen:
        raise ValueError(
            f"Desteklenmeyen fonksiyon: {function_name}\n"
            f"Desteklenenler: {desteklenen}"
        )

    fn = getattr(contract.functions, function_name)
    encoded = fn(*args).build_transaction({
        "from": account.address,
        "gas": 0,
        "chainId": CHAIN_ID,
        "nonce": 0,
    })["data"]

    print(f"[encode_management_call] {function_name}{args}")
    print(f"   Encoded: {str(encoded)[:20]}...({len(encoded)} byte)")

    return encoded


# ── EVENT LİSTENER ────────────────────────────────────────
def listen_events(callback=None):
    """
    Kontrattan gelen tüm eventleri dinler ve callback'e iletir.
    """
    import time

    event_filters = {
        "SubmitTransaction":  contract.events.SubmitTransaction,
        "ConfirmTransaction": contract.events.ConfirmTransaction,
        "RevokeConfirmation": contract.events.RevokeConfirmation,
        "ExecuteTransaction": contract.events.ExecuteTransaction,
        "Deposit":            contract.events.Deposit,
        "OwnerAddition":      contract.events.OwnerAddition,
        "OwnerRemoval":       contract.events.OwnerRemoval,
        "RequirementChange":  contract.events.RequirementChange,
    }

    filters = {}
    for event_name, event_class in event_filters.items():
        try:
            filters[event_name] = event_class.create_filter(fromBlock="latest")
        except Exception as e:
            print(f"[UYARI] {event_name} filtresi oluşturulamadı: {e}")

    print("[EVENT LİSTENER] Dinleme başladı. Çıkmak için Ctrl+C")
    print(f"[EVENT LİSTENER] {len(filters)} event dinleniyor...")

    while True:
        for event_name, event_filter in filters.items():
            try:
                new_entries = event_filter.get_new_entries()

                for entry in new_entries:
                    event_data = {
                        "event":       event_name,
                        "block":       entry.get("blockNumber"),
                        "tx_hash":     entry.get("transactionHash", b"").hex(),
                        "args":        dict(entry.get("args", {})),
                    }

                    print(f"\n[EVENT] {event_name}")
                    print(f"   Blok    : {event_data['block']}")
                    print(f"   TX Hash : {event_data['tx_hash']}")
                    print(f"   Veriler : {event_data['args']}")

                    if callback:
                        callback(event_name, event_data)

            except Exception as e:
                print(f"[UYARI] {event_name} okunurken hata: {e}")

        time.sleep(2)