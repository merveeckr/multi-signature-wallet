# ─────────────────────────────────────────────────────────────
# test_wallet_service.py — Backend Fonksiyon Test Scripti
# Yazan: Emine Binay | COM 4532 Blockchain Projesi
# ─────────────────────────────────────────────────────────────
# Bu dosyanın görevi:
#   wallet_service.py içindeki tüm fonksiyonları gerçek
#   Hardhat local ağında çalıştırıp sonuçları kontrol etmek.
#
#   Çalıştırma:
#   1. Hardhat node açık olmalı (npx hardhat node)
#   2. Deploy yapılmış olmalı (python backend/deploy.py)
#   3. .env'de CONTRACT_ADDRESS dolu olmalı
#   Sonra: python backend/test_wallet_service.py
# ─────────────────────────────────────────────────────────────

import sys
import os

# backend/ klasöründen import edebilmek için path'e ekle
sys.path.insert(0, os.path.dirname(__file__))

import wallet_service as ws
from web3 import Web3
from config import OWNER_1, OWNER_2, OWNER_3, CONTRACT_ADDRESS

# ── Yardımcı: renkli çıktı ────────────────────────────────
def basarili(mesaj):
    print(f"  [✓] {mesaj}")

def basarisiz(mesaj):
    print(f"  [✗] {mesaj}")

def baslik(mesaj):
    print(f"\n{'='*55}")
    print(f"  {mesaj}")
    print(f"{'='*55}")

# ── TEST 1: Blockchain bağlantısı ─────────────────────────
baslik("TEST 1 — Blockchain bağlantısı")
try:
    bagli = ws.w3.is_connected()
    if bagli:
        basarili(f"Bağlantı kuruldu: {ws.w3.provider.endpoint_uri}")
    else:
        basarisiz("Bağlantı kurulamadı! Hardhat node çalışıyor mu?")
        sys.exit(1)
except Exception as e:
    basarisiz(f"Hata: {e}")
    sys.exit(1)

# ── TEST 2: Kontrat erişimi ───────────────────────────────
baslik("TEST 2 — Kontrat erişimi")
try:
    adres = CONTRACT_ADDRESS
    print(f"  Kontrat adresi : {adres}")
    # Kontratın blockchain'de gerçekten var olup olmadığını kontrol et
    kod = ws.w3.eth.get_code(Web3.to_checksum_address(adres))
    if len(kod) > 2:  # "0x" den fazlası varsa kontrat var demek
        basarili("Kontrat blockchain'de mevcut")
    else:
        basarisiz("Kontrat bulunamadı! Deploy yapıldı mı?")
        sys.exit(1)
except Exception as e:
    basarisiz(f"Hata: {e}")
    sys.exit(1)

# ── TEST 3: get_wallet_stats() ────────────────────────────
baslik("TEST 3 — get_wallet_stats()")
try:
    sonuc = ws.get_wallet_stats()
    print(f"  Bakiye          : {sonuc['balance_eth']} ETH")
    print(f"  Eşik (M)        : {sonuc['threshold']}")
    print(f"  Toplam sahip    : {sonuc['total_owners']}")
    print(f"  Sahip adresleri :")
    for i, adres in enumerate(sonuc['owner_addresses']):
        print(f"    {i+1}. {adres}")

    # Doğruluk kontrolü
    assert sonuc['threshold'] == 2, "Eşik 2 olmalıydı!"
    assert sonuc['total_owners'] == 3, "3 sahip olmalıydı!"
    basarili("get_wallet_stats() doğru çalışıyor")
except Exception as e:
    basarisiz(f"Hata: {e}")

# ── TEST 4: get_pending_transactions() ───────────────────
baslik("TEST 4 — get_pending_transactions() [başlangıçta boş]")
try:
    bekleyenler = ws.get_pending_transactions()
    print(f"  Bekleyen işlem sayısı: {len(bekleyenler)}")
    if len(bekleyenler) == 0:
        basarili("Başlangıçta bekleyen işlem yok — doğru!")
    else:
        print(f"  Mevcut bekleyen işlemler: {bekleyenler}")
except Exception as e:
    basarisiz(f"Hata: {e}")

# ── TEST 5: submit_transaction() ─────────────────────────
baslik("TEST 5 — submit_transaction() [yeni işlem teklifi]")
try:
    # OWNER_2'ye 0.1 ETH gönder teklifi oluştur
    hedef = OWNER_2
    miktar = 0.1
    print(f"  Hedef   : {hedef}")
    print(f"  Miktar  : {miktar} ETH")

    sonuc = ws.submit_transaction(to=hedef, amount_eth=miktar)
    print(f"  Sonuç   : {sonuc}")

    if sonuc['status'] == 'success':
        basarili(f"submit_transaction() başarılı — TX index: {sonuc.get('tx_index')}")
        tx_index = sonuc.get('tx_index', 0)
    else:
        basarisiz(f"Hata: {sonuc['message']}")
        tx_index = 0
except Exception as e:
    basarisiz(f"Hata: {e}")
    tx_index = 0

# ── TEST 6: get_pending_transactions() [şimdi dolu] ───────
baslik("TEST 6 — get_pending_transactions() [submit sonrası]")
try:
    bekleyenler = ws.get_pending_transactions()
    print(f"  Bekleyen işlem sayısı: {len(bekleyenler)}")
    for tx in bekleyenler:
        print(f"  ID: {tx['id']} | Alıcı: {tx['recipient'][:10]}... "
              f"| Miktar: {tx['amount_eth']} ETH "
              f"| Onaylar: {tx['current_confirmations']} "
              f"| Yürütülebilir: {tx['is_executable']}")

    if len(bekleyenler) > 0:
        basarili("Bekleyen işlem listelendi")
    else:
        basarisiz("İşlem listelenmedi!")
except Exception as e:
    basarisiz(f"Hata: {e}")

# ── TEST 7: approve_transaction() ────────────────────────
baslik("TEST 7 — approve_transaction() [onay ver]")
try:
    print(f"  İşlem ID {tx_index} onaylanıyor...")
    sonuc = ws.approve_transaction(tx_index)
    print(f"  Sonuç: {sonuc}")

    if sonuc['status'] == 'success':
        basarili(f"approve_transaction() başarılı")
    else:
        basarisiz(f"Hata: {sonuc['message']}")
except Exception as e:
    basarisiz(f"Hata: {e}")

# ── TEST 8: get_confirmation_status() ────────────────────
baslik("TEST 8 — get_confirmation_status() [kim onayladı?]")
try:
    # OWNER_1 onayladı mı? (deploy eden = OWNER_1)
    durum = ws.get_confirmation_status(tx_index, OWNER_1)
    print(f"  OWNER_1 onayladı mı? : {durum}")
    if durum:
        basarili("get_confirmation_status() doğru çalışıyor")
    else:
        basarisiz("OWNER_1 onaylamış olmalıydı!")
except Exception as e:
    basarisiz(f"Hata: {e}")

# ── TEST 9: revoke_confirmation() ────────────────────────
baslik("TEST 9 — revoke_confirmation() [onay geri çek]")
try:
    print(f"  İşlem ID {tx_index} onayı geri çekiliyor...")
    sonuc = ws.revoke_confirmation(tx_index)
    print(f"  Sonuç: {sonuc}")

    if sonuc['status'] == 'success':
        basarili("revoke_confirmation() başarılı")
    else:
        basarisiz(f"Hata: {sonuc['message']}")
except Exception as e:
    basarisiz(f"Hata: {e}")

# ── ÖZET ─────────────────────────────────────────────────
print(f"\n{'='*55}")
print(f"  TEST TAMAMLANDI")
print(f"  Tüm [✓] işaretleri varsa backend hazır!")
print(f"  [✗] varsa o satırdaki hatayı çöz.")
print(f"{'='*55}\n")