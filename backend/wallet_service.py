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
from config import RPC_URL, PRIVATE_KEY, CONTRACT_ADDRESS, ABI_PATH, CHAIN_ID


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
def _send_tx(fn):
    """
    Bir kontrat fonksiyonunu blockchain'e gönderir.

    Neden bu fonksiyon var?
    confirmTransaction, executeTransaction gibi her işlem için
    aynı adımları tekrar tekrar yazmak yerine buraya topladık.

    Adımlar:
    1. İşlemi oluştur (build_transaction)
    2. Private key ile imzala (sign_transaction)
    3. Blockchain'e gönder (send_raw_transaction)
    4. İşlemin tamamlanmasını bekle (wait_for_transaction_receipt)
    5. Makbuzu (receipt) döndür — içinde tx_hash var
    """
    # İşlemi oluştur: from, nonce, gas, chainId gerekli
    # nonce: bu hesabın kaçıncı işlemi olduğu (tekrar saldırısını önler)
    # gas: işlem için ödenecek maksimum ücret (test ağında önemi yok)
    tx = fn.build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gas": 300000,
        "chainId": CHAIN_ID,
    })

    # İşlemi private key ile imzala
    # İmzalanmamış işlem blockchain tarafından reddedilir
    signed = account.sign_transaction(tx)

    # İmzalı işlemi blockchain'e gönder
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)

    # İşlemin onaylanmasını bekle (birkaç saniye sürebilir)
    # receipt: işlemin makbuzu — başarılı mı, gas ne kadar harcandı vs.
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    return receipt


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

    Döndürdüğü format (İrem'in beklediği):
    {
        "balance_eth": 1.25,
        "threshold": 2,
        "total_owners": 3,
        "owner_addresses": ["0x...", "0x...", "0x..."],
        "contract_address": "0x..."
    }
    """
    # Kontratın bakiyesini wei cinsinden al
    # 1 ETH = 10^18 wei (küçük birim, ondalık hatalarını önler)
    balance_wei = w3.eth.get_balance(
        Web3.to_checksum_address(CONTRACT_ADDRESS)
    )

    # Wei'yi ETH'ye çevir (insanın okuyabileceği format)
    balance_eth = float(w3.from_wei(balance_wei, "ether"))

    # Kontrat fonksiyonunu çağır: kaç onay gerekiyor? (M değeri)
    # .call() = sadece oku, blockchain'i değiştirme
    threshold = contract.functions.numConfirmationsRequired().call()

    # Tüm sahiplerin adreslerini al
    owners = contract.functions.getOwners().call()

    return {
        "balance_eth":      balance_eth,       # örn: 1.25
        "threshold":        threshold,          # örn: 2
        "total_owners":     len(owners),        # örn: 3
        "owner_addresses":  owners,             # örn: ["0x...", ...]
        "contract_address": CONTRACT_ADDRESS,   # örn: "0x..."
    }


# ── FONKSİYON 2: Bekleyen İşlemler ───────────────────────
def get_pending_transactions():
    """
    Henüz yürütülmemiş (pending) işlemlerin listesini döner.

    İrem'in arayüzündeki "Bekleyen İşlemler" tablosunu doldurmak için
    kullanılır. Her satır bir işlemi temsil eder.

    Nasıl çalışır?
    1. Toplam işlem sayısını al
    2. Her işlemi tek tek kontrol et
    3. executed=True olanları atla (zaten yapılmış)
    4. Kalanları listeye ekle

    Döndürdüğü format (İrem'in beklediği):
    [
        {
            "id": 0,
            "recipient": "0x...",
            "amount_eth": 0.5,
            "current_confirmations": 1,
            "is_executable": False
        },
        ...
    ]
    """
    # Kontrata kaç işlem gönderildiğini öğren
    total = contract.functions.getTransactionCount().call()

    # Bekleyen işlemleri toplayacağımız liste
    pending = []

    # Her işlemi sırayla kontrol et
    for i in range(total):
        # İşlem detaylarını al
        # getTransaction() şunu döner:
        # (hedef_adres, miktar_wei, data, yapıldı_mı, onay_sayısı)
        to, value, data, executed, num_confirmations = \
            contract.functions.getTransaction(i).call()

        # Zaten yürütülmüşse listeye ekleme, bir sonrakine geç
        if executed:
            continue

        # Kaç onay gerektiğini öğren
        threshold = contract.functions.numConfirmationsRequired().call()

        # Bu işlem hemen yürütülebilir mi?
        # (onay sayısı eşiğe ulaştıysa evet)
        is_executable = num_confirmations >= threshold

        pending.append({
            "id":                    i,
            "recipient":             to,
            # Wei'yi ETH'ye çevir
            "amount_eth":            float(w3.from_wei(value, "ether")),
            "current_confirmations": num_confirmations,
            "is_executable":         is_executable,
        })

    return pending


# ── FONKSİYON 3: İşlem Onaylama ──────────────────────────
def approve_transaction(transaction_id: int):
    """
    Verilen ID'li işlemi onaylar.

    İrem'in arayüzündeki "Onayla" butonuna basılınca çağrılır.
    Blockchain'e gerçek bir işlem gönderir → gas öder (test ağında
    gerçek para değil).

    Parametre:
        transaction_id (int): Onaylanacak işlemin ID'si
                              (örn: 0, 1, 2...)

    Döndürdüğü format (İrem'in beklediği):
        Başarılı: {"status": "success", "tx_hash": "0x..."}
        Hatalı:   {"status": "error",   "message": "hata mesajı"}

    Olası hatalar:
        - Zaten onayladıysak kontrat reddeder (notConfirmed modifier)
        - Sahip değilsek reddeder (onlyOwner modifier)
        - İşlem yoksa reddeder (txExists modifier)
    """
    try:
        # confirmTransaction fonksiyonunu blockchain'e gönder
        # _send_tx yardımcı fonksiyonu imzalama ve gönderme işini yapar
        receipt = _send_tx(
            contract.functions.confirmTransaction(transaction_id)
        )

        # Başarılıysa tx_hash'i döndür
        # tx_hash: işlemin blockchain'deki parmak izi, takip için kullanılır
        return {
            "status":  "success",
            "tx_hash": receipt.transactionHash.hex(),
        }

    except Exception as e:
        # Hata olursa mesajı döndür, programı çökertme
        return {
            "status":  "error",
            "message": str(e),
        }
    

# ── FONKSİYON 4: İşlem Teklifi Oluşturma ─────────────────
def submit_transaction(to: str, amount_eth: float, data: bytes = b""):
    """
    Yeni bir işlem teklifi oluşturur ve pending listeye ekler.

    Bu fonksiyon ne zaman çağrılır?
    Sahiplerden biri "şu adrese şu kadar ETH gönderelim" demek
    istediğinde. İrem'in arayüzündeki "Yeni İşlem" formuna
    gönder butonuna basılınca bu çağrılır.

    Parametreler:
        to (str):          Parayı alacak Ethereum adresi
        amount_eth (float): Gönderilecek ETH miktarı (örn: 0.5)
        data (bytes):      Ekstra veri — düz ETH transferinde boş

    Döndürdüğü format:
        Başarılı: {"status": "success", "tx_index": 0, "tx_hash": "0x..."}
        Hatalı:   {"status": "error", "message": "hata mesajı"}

    Kontrat tarafında ne olur?
    submitTransaction çağrılır → transactions dizisine eklenir →
    SubmitTransaction eventi fırlatılır → txIndex döner
    """
    try:
        # ETH miktarını wei'ye çevir
        # Kontrat her zaman wei cinsinden çalışır
        amount_wei = w3.to_wei(amount_eth, "ether")

        # Hedef adresi checksum formatına çevir
        to_address = Web3.to_checksum_address(to)

        # submitTransaction fonksiyonunu blockchain'e gönder
        receipt = _send_tx(
            contract.functions.submitTransaction(to_address, amount_wei, data)
        )

        # Receipt içinden txIndex'i bul
        # SubmitTransaction eventi txIndex'i içeriyor
        tx_index = None
        try:
            # Event log'undan txIndex'i çek
            logs = contract.events.SubmitTransaction().process_receipt(receipt)
            if logs:
                tx_index = logs[0]["args"]["txIndex"]
        except Exception:
            # Event parse edilemezse receipt'teki log sayısından tahmin et
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
def execute_transaction(transaction_id: int):
    """
    Yeterli onay alan bir işlemi gerçekten yürütür (parayı gönderir).

    Bu fonksiyon ne zaman çağrılır?
    Bir işlem M kadar onay aldıktan sonra, herhangi bir sahip
    "artık yürüt" diyebilir. İrem'in arayüzündeki "Yürüt"
    butonuna basılınca çağrılır.

    Kontrat tarafında ne olur?
    1. executed = true set edilir (CEI pattern — önce state değişir)
    2. Sonra ETH hedef adrese gönderilir
    3. ExecuteTransaction eventi fırlatılır

    Neden önce executed=true?
    Reentrancy saldırısını önlemek için. Önce para gönderilseydi,
    kötü niyetli bir kontrat tekrar executeTransaction çağırabilirdi.

    Parametreler:
        transaction_id (int): Yürütülecek işlemin ID'si

    Döndürdüğü format:
        Başarılı: {"status": "success", "tx_hash": "0x..."}
        Hatalı:   {"status": "error", "message": "hata mesajı"}
    """
    try:
        receipt = _send_tx(
            contract.functions.executeTransaction(transaction_id)
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
def revoke_confirmation(transaction_id: int):
    """
    Daha önce verilen onayı geri çeker.

    Bu fonksiyon ne zaman çağrılır?
    Bir sahip onay verdikten sonra fikrini değiştirirse.
    İşlem henüz yürütülmemiş olmalı — yürütülmüşse geri alınamaz.

    Kontrat tarafında ne olur?
    confirmed[txIndex][msg.sender] = false yapılır →
    numConfirmations 1 azaltılır →
    RevokeConfirmation eventi fırlatılır

    Parametreler:
        transaction_id (int): Onayı geri çekilecek işlemin ID'si

    Döndürdüğü format:
        Başarılı: {"status": "success", "tx_hash": "0x..."}
        Hatalı:   {"status": "error", "message": "hata mesajı"}
    """
    try:
        receipt = _send_tx(
            contract.functions.revokeConfirmation(transaction_id)
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
def get_confirmation_status(transaction_id: int, owner_address: str):
    """
    Belirli bir sahibin belirli bir işlemi onaylayıp onaylamadığını döner.

    Bu fonksiyon ne zaman çağrılır?
    İrem'in arayüzünde her sahip için "onayladı / onaylamadı"
    göstergesi çizmek için. Tablo hücresi gibi düşün.

    Parametreler:
        transaction_id (int):  İşlem ID'si
        owner_address  (str):  Sorgulanacak sahibin adresi

    Döndürür:
        True  → bu sahip onayladı
        False → bu sahip henüz onaylamadı
    """
    return contract.functions.getConfirmationStatus(
        transaction_id,
        Web3.to_checksum_address(owner_address)
    ).call()


# ── FONKSİYON 8: İşlem Yürütülebilir mi? ─────────────────
def is_confirmed(transaction_id: int):
    """
    Bir işlemin yeterli onayı alıp almadığını kontrol eder.

    Bu fonksiyon ne zaman çağrılır?
    İrem'in arayüzünde "Yürüt" butonunun aktif olup olmayacağına
    karar vermek için. Eğer True dönerse buton aktif olur.

    Kontrat tarafında ne olur?
    numConfirmations >= numConfirmationsRequired kontrolü yapar.
    Yani onay sayısı eşiğe (M) ulaştıysa True, ulaşmadıysa False.

    Parametreler:
        transaction_id (int): Kontrol edilecek işlemin ID'si

    Döndürür:
        True  → işlem yürütülebilir (yeterli onay var)
        False → henüz yeterli onay yok
    """
    return contract.functions.isConfirmed(transaction_id).call()


# ── FONKSİYON 9: Yönetim İşlemi Encode Et ────────────────
def encode_management_call(function_name: str, *args):
    """
    Yönetim fonksiyonlarını (addOwner, removeOwner vs.)
    submitTransaction ile göndermek için ABI-encode eder.

    Neden gerekli?
    addOwner, removeOwner, changeRequirement gibi fonksiyonlar
    'onlyWallet' modifier'lı — yani sadece kontratın kendisi
    çağırabilir. Dışarıdan direkt çağrılamaz.

    Bunları çağırmak için şu adımlar izlenir:
    1. Bu fonksiyon ile "ne yapmak istiyorum" bilgisi encode edilir
    2. submitTransaction(_data=encode_edilmiş_veri) ile teklif açılır
    3. M onay alınır
    4. executeTransaction çağrılır
    5. Kontrat kendi kendini çağırır → addOwner çalışır

    Parametreler:
        function_name (str): çağrılacak fonksiyon adı
                             "addOwner", "removeOwner",
                             "replaceOwner", "changeRequirement"
        *args: fonksiyonun parametreleri

    Kullanım örnekleri:
        # Yeni sahip ekle
        data = encode_management_call("addOwner", "0x1234...")
        submit_transaction(to=CONTRACT_ADDRESS, amount_eth=0, data=data)

        # Sahip çıkar
        data = encode_management_call("removeOwner", "0x1234...")
        submit_transaction(to=CONTRACT_ADDRESS, amount_eth=0, data=data)

        # Onay eşiğini değiştir (M=3 yap)
        data = encode_management_call("changeRequirement", 3)
        submit_transaction(to=CONTRACT_ADDRESS, amount_eth=0, data=data)

    Döndürür:
        bytes: ABI-encoded fonksiyon çağrısı
               (submitTransaction'ın _data parametresine verilir)
    """
    # Desteklenen yönetim fonksiyonları
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

    # contract.encodeABI() ile fonksiyon çağrısını byte'a çevir
    # Bu byte'lar submitTransaction'ın _data parametresine gider
    
    # Web3.py 7.x'te encode_abi syntax'ı değişti
    # fn_name yerine abi_element_identifier kullanılıyor
    fn = getattr(contract.functions, function_name)
    encoded = fn(*args).build_transaction({
        "from": account.address,
        "gas": 0,
        "chainId": CHAIN_ID,
        "nonce": 0,
    })["data"]

    print(f"[encode_management_call] {function_name}{args}")
    print(f"  Encoded: {encoded[:20]}...({len(encoded)} byte)")

    return encoded


# ── EVENT LİSTENER ────────────────────────────────────────
def listen_events(callback=None):
    """
    Kontrattan gelen tüm eventleri dinler ve callback'e iletir.

    Event nedir?
    Kontrat bir şey yaptığında blockchain'e kayıt düşer.
    Örneğin yeni işlem gelince SubmitTransaction eventi fırlatılır.
    Biz bu eventi dinleyip İrem'in arayüzünü güncelleyebiliriz.

    Dinlediğimiz 8 event:
    İşlem eventleri:
        SubmitTransaction   → yeni pending işlem geldi
        ConfirmTransaction  → birileri onayladı
        RevokeConfirmation  → biri onayını geri çekti
        ExecuteTransaction  → işlem yürütüldü, para gitti
        Deposit             → cüzdana ETH yatırıldı

    Sahip eventleri:
        OwnerAddition       → yeni sahip eklendi
        OwnerRemoval        → sahip çıkarıldı
        RequirementChange   → M eşiği değişti

    Parametreler:
        callback: Her event geldiğinde çağrılacak fonksiyon.
                  callback(event_name, event_data) şeklinde çağrılır.
                  None ise sadece konsola yazdırır.

    Kullanım örneği:
        def benim_callback(event_name, data):
            print(f"Event geldi: {event_name}")
            print(data)
        listen_events(callback=benim_callback)
    """
    import time

    # Dinleyeceğimiz tüm eventler ve açıklamaları
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

    # Her event için "latest" bloğundan itibaren filtre oluştur
    # fromBlock="latest" → sadece şu andan itibaren gelen eventleri al
    filters = {}
    for event_name, event_class in event_filters.items():
        try:
            filters[event_name] = event_class.create_filter(fromBlock="latest")
        except Exception as e:
            print(f"[UYARI] {event_name} filtresi oluşturulamadı: {e}")

    print("[EVENT LİSTENER] Dinleme başladı. Çıkmak için Ctrl+C")
    print(f"[EVENT LİSTENER] {len(filters)} event dinleniyor...")

    # Sonsuz döngü — yeni eventleri sürekli kontrol et
    while True:
        for event_name, event_filter in filters.items():
            try:
                # Yeni giriş var mı kontrol et
                new_entries = event_filter.get_new_entries()

                for entry in new_entries:
                    # Event verisini düzenli formata çevir
                    event_data = {
                        "event":       event_name,
                        "block":       entry.get("blockNumber"),
                        "tx_hash":     entry.get("transactionHash", b"").hex(),
                        "args":        dict(entry.get("args", {})),
                    }

                    # Konsola yazdır
                    print(f"\n[EVENT] {event_name}")
                    print(f"  Blok    : {event_data['block']}")
                    print(f"  TX Hash : {event_data['tx_hash']}")
                    print(f"  Veriler : {event_data['args']}")

                    # Callback varsa çağır
                    if callback:
                        callback(event_name, event_data)

            except Exception as e:
                print(f"[UYARI] {event_name} okunurken hata: {e}")

        # 2 saniyede bir kontrol et — çok sık sormak gereksiz yük yaratır
        time.sleep(2)