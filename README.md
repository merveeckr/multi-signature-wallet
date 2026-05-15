# Multi-Signature Wallet

COM 4532 — Blockchain Technology and Public Ledgers  
Ankara Üniversitesi · Merve Çakır · Emine Binay · İrem Keskin

---

## Proje Özeti

M-of-N eşik imzası şemasıyla çalışan, Ethereum üzerinde deploy edilen akıllı sözleşme tabanlı çok imzalı cüzdan sistemi. Tek özel anahtar güvenlik açığını ortadan kaldırır; bir işlemin yürütülebilmesi için N sahipten en az M'inin onayı zorunludur.

---

## Sorumluluklar

| Kişi | Alan | Dosyalar |
|---|---|---|
| **Merve** | Smart Contract & Güvenlik | `contracts/`, `abi/` |
| **Emine** | Python Backend & Entegrasyon | `backend/` |
| **İrem** | Frontend & Test | `frontend/`, `tests/` |

---

## Proje Yapısı

```
blockchain-prohe/
├── contracts/
│   ├── MultiSigWallet.sol      ← Deploy edilen ana contract
│   ├── OwnerManager.sol        ← Abstract — sahip yönetimi
│   └── TransactionManager.sol  ← Abstract — tx yaşam döngüsü
│
├── abi/
│   ├── MultiSigWallet.abi.json ← Emine'nin kullandığı ABI
│   ├── OwnerManager.abi.json
│   └── TransactionManager.abi.json
│
├── backend/                    ← Emine (Web3.py servisleri)
│   ├── wallet_service.py
│   ├── deploy.py
│   └── config.py
│
├── frontend/                   ← İrem (Streamlit dashboard)
│   └── app.py
│
├── tests/                      ← İrem (Hardhat + Pytest testleri)
│   ├── test_multisig.js        ← Solidity unit testleri (Hardhat)
│   └── test_wallet_service.py  ← Python integration testleri
│
├── hardhat.config.js
├── package.json
├── requirements.txt
├── .env.example
├── contract_reference.html     ← Teknik referans dokümanı
└── merve_contract_specs.md     ← Contract spesifikasyonları
```

---

## Gereksinimler

- **Node.js** v18 veya üzeri
- **Python** 3.10 veya üzeri
- **Git**

---

## Kurulum

### 1. Repoyu klonla

```bash
git clone <repo-url>
cd blockchain-prohe
```

### 2. Node bağımlılıklarını yükle (Hardhat + OpenZeppelin)

```bash
npm install
```

### 3. Python sanal ortamı oluştur ve bağımlılıkları yükle

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Ortam değişkenlerini ayarla

```bash
cp .env.example .env
```

`.env` dosyasını düzenle:

```env
RPC_URL=http://127.0.0.1:8545       # Hardhat local node
PRIVATE_KEY=0x...                    # Deploy eden hesabın private key'i
OWNER_1=0x...
OWNER_2=0x...
OWNER_3=0x...
CHAIN_ID=31337                       # Hardhat local = 31337, Sepolia = 11155111
```

---

## Çalıştırma

### Local Hardhat node başlat

```bash
npx hardhat node
```

Yeni terminal açarak devam et.

### Contract'ları compile et

```bash
npx hardhat compile
```

`artifacts/` ve `abi/` klasörleri güncellenir.

### Contract'ları deploy et (Emine)

```bash
python backend/deploy.py
```

Deploy adresi konsola yazdırılır — `.env` dosyasına `CONTRACT_ADDRESS=0x...` olarak kaydet.

### Streamlit dashboard başlat (İrem)

```bash
streamlit run frontend/app.py
```

Tarayıcıda `http://localhost:8501` adresini aç.

---

## Test

### Hardhat (Solidity unit testleri — İrem)

```bash
npx hardhat test

# Coverage raporu
npx hardhat coverage
```

Hedef: **%90 üzeri coverage**

### Pytest (Python integration testleri — İrem)

```bash
pytest tests/ -v
```

---

## Testnet Deploy (Hafta 4)

### Sepolia deploy

1. `.env` içinde `RPC_URL`'i Sepolia Infura/Alchemy URL'siyle güncelle
2. `CHAIN_ID=11155111` yap
3. Test ETH al: [Sepolia Faucet](https://sepoliafaucet.com)

```bash
python backend/deploy.py --network sepolia
```

### Etherscan Verify (Merve)

```bash
npx hardhat verify --network sepolia <CONTRACT_ADDRESS> \
  "<OWNER_1>" "<OWNER_2>" "<OWNER_3>" 2
```

---

## Güvenlik Mekanizmaları

| Saldırı | Önlem |
|---|---|
| Reentrancy | `ReentrancyGuard` + CEI pattern |
| Tekrar onay | `confirmed[txIndex][msg.sender]` mapping |
| Quorum manipülasyonu | M ≥ N/2 hard-coded kural |
| Yetkisiz admin | `onlyWallet` modifier (sadece multisig konsensüsüyle) |
| Time-lock | _Hafta 2'de eklenecek_ |
| emergencyPause | _Hafta 2'de eklenecek_ |

---

## Referans Dokümanlar

- **[contract_reference.html](contract_reference.html)** — Emine & İrem için fonksiyon imzaları, events, revert mesajları
- **[merve_contract_specs.md](merve_contract_specs.md)** — Detaylı contract spesifikasyonu
- **[Proje Önerisi (PDF)](21290542_Merve_Cakir_COM4532_Project_Proposal.pdf)**

---

## Takvim

| Hafta | Tarih | Milestone |
|---|---|---|
| 1 | 05–11 Mayıs | Ortam kurulumu, contract iskeletleri, ABI paylaşımı |
| 2 | 12–18 Mayıs | Core logic, EIP-712, unit testler |
| 3 | 19–25 Mayıs | Entegrasyon, güvenlik audit, saldırı testleri |
| 4 | 26 Mayıs–01 Haziran | Testnet deploy, rapor, sunum |
