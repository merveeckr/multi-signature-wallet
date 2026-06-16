# Merve'nin Yaptıkları — İlerleme Raporu

**Proje:** Multi-Signature Wallet · COM4532 · Blockchain  
**Yazar:** Merve Çakır  
**Rapor tarihi:** 25 Mayıs 2026  
**Bu rapor ne için:** Emine ve İrem'in Merve'nin contract tarafında tam olarak ne yaptığını bilmesi için yazılmıştır. Entegrasyon ve testlerde bu bilgiye ihtiyaç duyulacak.

---

## Genel Durum

| Görev | Durum |
|---|---|
| 3 Solidity contract (Hafta 1) | ✅ Tamamlandı |
| Time-lock mekanizması (Hafta 2) | ✅ Tamamlandı |
| emergencyPause (Hafta 2) | ✅ Tamamlandı |
| Replay koruması (Hafta 2) | ✅ Tamamlandı |
| Slither güvenlik audit (Hafta 3) | ✅ Tamamlandı |
| Sepolia deploy script (Hafta 4 hazırlık) | ✅ Hazır — yarın çalıştırılacak |

---

## 1. Dosya Yapısı

```
contracts/
  MultiSigWallet.sol      ← Deploy edilen tek contract
  OwnerManager.sol        ← Abstract — sahip yönetimi
  TransactionManager.sol  ← Abstract — işlem yaşam döngüsü

abi/
  MultiSigWallet.abi.json     ← Emine'nin kullandığı ABI (güncel)
  OwnerManager.abi.json
  TransactionManager.abi.json

scripts/
  deploy.js               ← Yarın Sepolia'ya deploy için
  verify.js               ← Deploy sonrası Etherscan doğrulama için

security_audit.md         ← Slither audit raporu
merve_contract_specs.md   ← Tüm fonksiyon imzaları (Emine & İrem için)
```

**Önemli:** `OwnerManager.sol` ve `TransactionManager.sol` ayrı deploy **edilmez**. `MultiSigWallet` bunları içinde taşır. Emine sadece `MultiSigWallet` ABI'sini kullanır.

---

## 2. Hafta 1 — Temel Kontrat Yapısı

### Ne yapıldı?

3 Solidity dosyası yazıldı ve derlendi. Bu dosyalar projenin tüm çekirdeğini oluşturuyor.

### `OwnerManager.sol` — Sahip Yönetimi

Sahibi (owner) kim olabilir, nasıl eklenir/çıkarılır, onay eşiği nasıl değiştirilir — bunların hepsini bu dosya yönetiyor.

**State değişkenleri:**
- `mapping(address => bool) public isOwner` — adres sahip mi?
- `address[] public owners` — tüm sahipler listesi
- `uint256 public numConfirmationsRequired` — gereken minimum onay sayısı (M)

**Fonksiyonlar (hepsi `onlyWallet` — yani doğrudan çağrılamaz, multisig konsensüsüyle çağrılır):**
- `addOwner(address)` — yeni sahip ekler
- `removeOwner(address)` — sahibi çıkarır; M > N olursa M'i otomatik düşürür
- `replaceOwner(address, address)` — bir sahibi başkasıyla değiştirir
- `changeRequirement(uint256)` — onay eşiğini günceller
- `getOwners()` — tüm sahiplerin listesini döndürür

**`onlyWallet` ne demek?** Bu fonksiyonlara `msg.sender == address(this)` zorunlu. Yani sadece kontrat kendi kendini çağırabilir. Pratikte: önce `submitTransaction` ile teklif oluşturulur, M onay alınır, `executeTransaction` ile yürütülür — o esnada kontrat kendi fonksiyonunu çağırmış olur.

**M ≥ N/2 kuralı:** Onay eşiği sahip sayısının yarısından küçük olamaz. Örn: 3 sahip varsa minimum 2 onay gerekir. Bu kural her sahip ekleme/çıkarma işleminde de kontrol edilir (`validRequirement` modifier).

---

### `TransactionManager.sol` — İşlem Yaşam Döngüsü

İşlem verilerini tutan struct, state değişkenleri ve view fonksiyonlar burada.

**Transaction struct:**
```solidity
struct Transaction {
    address to;               // Hedef adres
    uint256 value;            // Gönderilecek ETH (wei)
    bytes data;               // ABI-encoded fonksiyon çağrısı (boş da olabilir)
    bool executed;            // Yürütüldü mü?
    uint256 numConfirmations; // Kaç onay var?
}
```

**State:**
- `Transaction[] internal transactions` — tüm işlem geçmişi
- `mapping(uint256 => mapping(address => bool)) public confirmed` — kim hangi işlemi onayladı

**View fonksiyonlar:**
- `getTransaction(txIndex)` — bir işlemin tüm detaylarını döndürür
- `getTransactionCount()` — toplam işlem sayısı
- `getConfirmationStatus(txIndex, ownerAddress)` — belirli bir sahip o işlemi onayladı mı?

---

### `MultiSigWallet.sol` — Ana Kontrat

Yukarıdaki iki abstract kontratı miras alan, deploy edilen tek kontrat.

**Constructor:**
```
MultiSigWallet(address[] owners, uint256 numConfirmationsRequired)
```
- Owner listesini ve M değerini alır
- M ≥ N/2 kuralını zorunlu kılar
- Tekrar eden veya sıfır adres kabul etmez

**Core fonksiyonlar:**
- `submitTransaction(to, value, data)` → işlem teklifi oluşturur, txIndex döndürür
- `confirmTransaction(txIndex)` → sahip işlemi onaylar
- `executeTransaction(txIndex)` → M onay alınmışsa işlemi zincirde yürütür
- `revokeConfirmation(txIndex)` → verilen onayı geri çeker
- `getBalance()` → cüzdanın ETH bakiyesi

**receive():** ETH gönderilince otomatik çalışır, `Deposit` event yayınlar.

---

## 3. Hafta 2 — Güvenlik Mekanizmaları

### 3.1 Time-lock (24 Saat Bekleme)

**Ne yapar:** Bir işlem M onaya ulaşınca otomatik 24 saatlik bir sayaç başlar. Bu 24 saat dolmadan `executeTransaction` çağrılamaz.

**Neden gerekli:** Büyük miktarlı işlemlerde, onaylar toplandıktan sonra da sahiplere "dur bir düşünelim" şansı tanır. Fark edilmeyen kötü amaçlı bir işlemi durdurmak için zaman kazandırır.

**Nasıl çalışır (teknik):**

`TransactionManager.sol`'a eklenenler:
- `uint256 public timeLockDuration = 24 hours` — bekleme süresi (saniye cinsinden, varsayılan 86400)
- `mapping(uint256 => uint256) public readyTime` — her işlem için "ne zaman execute edilebilir" timestamp'i
- `mapping(uint256 => bool) private _timeLockInitialized` — sayaç başlatıldı mı? (güvenlik fix'i için ayrıldı)

`MultiSigWallet.confirmTransaction`'da:
```
M. onay verilince → _setTimeLock(txIndex) çağrılır
→ readyTime[txIndex] = block.timestamp + 24 saat
→ TimeLockTriggered event yayınlanır
```

`MultiSigWallet.executeTransaction`'da:
- `timeLockPassed` modifier eklendi → `block.timestamp >= readyTime[txIndex]` olmadan revert atar

**Emine'ye not:** `readyTime(txIndex)` fonksiyonunu çağırarak bir işlemin ne zaman yürütülebileceğini öğrenebilirsin. `TimeLockTriggered` event'ini dinlersen UI'da "X saat sonra yürütülebilir" gösterebilirsin.

**İrem'e not:** `"TransactionManager: time-lock suresi dolmadi"` revert mesajını test et.

**Time-lock süresi değiştirilebilir mi?** Evet ama sadece multisig konsensüsüyle: `changeTimeLockDuration(saniye)` fonksiyonu `onlyWallet` korumalı.

---

### 3.2 emergencyPause (Acil Durdurma)

**Ne yapar:** Herhangi bir sahip cüzdanı tek başına dondurabilir. Dondurulunca `submitTransaction`, `confirmTransaction`, `executeTransaction`, `revokeConfirmation` — hiçbiri çalışmaz. Herhangi bir sahip yeniden açabilir.

**Neden gerekli:** Bir güvenlik açığı fark edilince, anında müdahale için tek onay yeterli olsun. Büyük tutarlar tehlikedeyken çok-sahip konsensüsü beklemeye zaman yok.

**Neden unpause de tek sahiple açılıyor?** Teknik bir zorunluluk: cüzdan dondurulunca `executeTransaction` çalışmıyor. Eğer `unpause` için "multisig konsensüsü gereksin" desek, açmak için execute gerekir ama execute çalışmıyor — kilitlenme (deadlock) olurdu. Bu yüzden bilinçli olarak tek sahip kararıyla açılabiliyor.

**Eklenen kodlar:**
- `bool public paused` — durum değişkeni
- `modifier whenNotPaused()` — 4 işlem fonksiyonuna eklendi
- `pause()` — sahip çağırır, `EmergencyPaused` event
- `unpause()` — sahip çağırır, `EmergencyUnpaused` event

**İrem'e not:** Şu 4 revert mesajını test et:
- `"MultiSigWallet: cuzcdan durduruldu"` — paused iken işlem yapmaya çalışınca
- `"MultiSigWallet: zaten durduruldu"` — zaten paused iken `pause()` çağrılırsa
- `"MultiSigWallet: zaten aktif"` — paused değilken `unpause()` çağrılırsa
- Sahip olmayan `pause()` çağırırsa: `"MultiSigWallet: sadece sahip cagirir"`

---

### 3.3 Replay Koruması (EIP-712 + Chain ID)

**Replay saldırısı ne demek?** Birisi daha önce geçerli olan bir işlem setini (veya imzaları) alıp "tekrar oynatmaya" çalışması. İki senaryo:

1. **Zincirler arası:** Sepolia'da geçerli olan bir işlemi Mainnet'e kopyalama
2. **İmza seti replay:** Emine'nin topladığı off-chain imzaları ikinci kez kullanma

**Ne eklendi?**

Constructor'da oluşturulan `DOMAIN_SEPARATOR`:
```
DOMAIN_SEPARATOR = hash(
    "EIP712Domain(...)",
    "MultiSigWallet",   ← kontrat adı
    "1",                ← versiyon
    chainId,            ← hangi zincir
    address(this)       ← hangi kontrat adresi
)
```
Bu değer her kontrat adresinde ve her zincirde farklı çıkar. Sepolia'daki imza seti Mainnet'te geçersiz olur.

`executeTransaction`'da:
```solidity
require(block.chainid == DEPLOY_CHAIN_ID, "MultiSigWallet: yanlis zincir");
txn.executed = true;
nonce++;   // ← her execute'da 1 artar
```
`nonce` artışı: Emine off-chain imza toplarken bu nonce'u imza struct'ına dahil eder. İşlem execute edildikten sonra nonce değişir, eski imza seti artık geçersizdir.

**Emine'ye not — EIP-712 imza için:**
```python
# Kontraktan oku:
domain_separator = contract.functions.DOMAIN_SEPARATOR().call()
nonce = contract.functions.nonce().call()
tx_hash = contract.functions.getTransactionHash(tx_index).call()

# tx_hash'i sahiplere imzalat, imzaları topla, sonra confirmTransaction çağır
```

**Yeni view fonksiyonlar:**
- `getTransactionHash(txIndex)` → EIP-712 uyumlu imzalanacak hash
- `getChainId()` → mevcut chain ID

---

## 4. Hafta 3 — Slither Güvenlik Audit

Slither, Solidity kontratlarını otomatik analiz eden bir güvenlik aracı. `pip install slither-analyzer` ile kuruldu, kontratlar üzerinde çalıştırıldı.

### Sonuçlar

| Önem | İlk çalıştırma | Düzeltme sonrası |
|---|---|---|
| Critical | 0 | 0 |
| High | 0 | 0 |
| Medium | 2 | **0 ✅** |
| Low/Info | 5 | 5 (false positive) |

**0 Critical, 0 High bulgu.**

### Düzeltilen Sorunlar

**Sorun 1 — Strict equality (Medium):**  
`readyTime[txIndex] == 0` ifadesi Slither tarafından riskli bulundu. Eğer timestamp manipülasyonu olursa 0 değeri beklenmedik davranış yaratabilir. Düzeltme: ayrı bir `bool _timeLockInitialized[txIndex]` eklendi, `== 0` kontrolü kaldırıldı.

**Sorun 2 — Gas israfı (Low):**  
`OwnerManager.sol`'daki döngüler her adımda `owners.length`'i storage'dan okuyordu. Düzeltme: döngüden önce `uint256 len = owners.length` ile cache'lendi. Böylece storage okuma işlemi bir kereden fazla yapılmıyor, gas tasarrufu sağlandı.

**Kalan "sorunlar" neden düzeltilmedi:**
- `assembly` kullanımı → OpenZeppelin'in kendi kodu, bizim yazdığımız değil
- `low-level-calls` → Multisig cüzdan olduğu için kaçınılmaz; hedef kontrat compile-time'da belli değil
- `naming-convention` → `_parametre` prefix'i Solidity'de yaygın, `DOMAIN_SEPARATOR` gibi ALL_CAPS sabitler için de standart

Detaylı analiz: `security_audit.md` dosyasında.

---

## 5. Hafta 4 Hazırlığı — Sepolia Deploy

Yarın (26 Mayıs) ortak oturumda yapılacak. Teknik altyapı hazır.

### Hazır olanlar

- `scripts/deploy.js` → Node.js ile çalışır, Sepolia'ya deploy eder, adresi kaydeder
- `scripts/verify.js` → Etherscan doğrulama talimatlarını verir
- `hardhat.config.js` → Sepolia ağı tanımlandı

### Yarın ne yapılacak

1. Emine ve İrem'den MetaMask adresleri alınır
2. `.env` dosyası oluşturulur (`.env.example`'dan kopyalanır)
3. [sepoliafaucet.com](https://sepoliafaucet.com)'dan test ETH alınır
4. `node scripts/deploy.js` çalıştırılır → contract adresi çıkar
5. `node scripts/verify.js` → Etherscan'de doğrulanır

### `.env` dosyasında ne doldurulacak

```
SEPOLIA_RPC_URL   → Infura veya Alchemy'den (ücretsiz hesap)
PRIVATE_KEY       → Merve'nin MetaMask private key'i
OWNER_1           → Merve'nin adresi
OWNER_2           → Emine'nin adresi (yarın alınacak)
OWNER_3           → İrem'in adresi (yarın alınacak)
ETHERSCAN_API_KEY → etherscan.io'dan ücretsiz
```

---

## 6. Şu An Geçerli Olan Tüm Revert Mesajları

İrem'in testleri için tam liste:

| Senaryo | Revert Mesajı |
|---|---|
| Boş owners dizisi | `"MultiSigWallet: en az 1 sahip gerekli"` |
| M < N/2 veya M=0 | `"MultiSigWallet: gecersiz M veya N degeri (M >= N/2 sarti)"` |
| address(0) owner | `"MultiSigWallet: sifir adres"` |
| Tekrar eden owner | `"MultiSigWallet: sahip adresi tekrarlanamaz"` |
| Sahip olmayan çağırır | `"MultiSigWallet: sadece sahip cagirir"` |
| Sıfır hedef adres | `"MultiSigWallet: sifir hedef adres"` |
| Olmayan txIndex | `"TransactionManager: islem bulunamadi"` |
| Zaten yürütülmüş | `"TransactionManager: islem zaten yurutuldu"` |
| Aynı sahip 2 kez onay | `"TransactionManager: zaten onaylanmis"` |
| Onayı olmayan revoke | `"TransactionManager: onay bulunamadi"` |
| Yetersiz onay ile execute | `"MultiSigWallet: yetersiz onay sayisi"` |
| Time-lock dolmadan execute | `"TransactionManager: time-lock suresi dolmadi"` |
| Paused iken işlem | `"MultiSigWallet: cuzcdan durduruldu"` |
| Zaten paused iken pause | `"MultiSigWallet: zaten durduruldu"` |
| Paused değilken unpause | `"MultiSigWallet: zaten aktif"` |
| addOwner direkt çağrılırsa | `"OwnerManager: sadece kontrat cagirabilir"` |
| Yanlış zincirde execute | `"MultiSigWallet: yanlis zincir"` |
| Execute başarısız olursa | `"MultiSigWallet: islem yurutme basarisiz"` |

---

## 7. Güncel ABI Fonksiyon Listesi

`abi/MultiSigWallet.abi.json` içinde olan her şey (Emine'nin kullanabileceği):

**İşlem fonksiyonları:**
- `submitTransaction(address, uint256, bytes)` → `uint256 txIndex`
- `confirmTransaction(uint256)`
- `executeTransaction(uint256)`
- `revokeConfirmation(uint256)`

**Sahip yönetimi (onlyWallet — multisig konsensüsüyle):**
- `addOwner(address)`
- `removeOwner(address)`
- `replaceOwner(address, address)`
- `changeRequirement(uint256)`
- `changeTimeLockDuration(uint256)` ← yeni

**Pause:**
- `pause()` ← yeni
- `unpause()` ← yeni

**View fonksiyonlar:**
- `getTransaction(uint256)` → `(address, uint256, bytes, bool, uint256)`
- `getTransactionCount()` → `uint256`
- `getConfirmationStatus(uint256, address)` → `bool`
- `getOwners()` → `address[]`
- `isConfirmed(uint256)` → `bool`
- `getBalance()` → `uint256`
- `getChainId()` → `uint256` ← yeni
- `getTransactionHash(uint256)` → `bytes32` ← yeni

**Public state okuma:**
- `isOwner(address)` → `bool`
- `owners(uint256)` → `address`
- `numConfirmationsRequired()` → `uint256`
- `confirmed(uint256, address)` → `bool`
- `paused()` → `bool` ← yeni
- `nonce()` → `uint256` ← yeni
- `DOMAIN_SEPARATOR()` → `bytes32` ← yeni
- `timeLockDuration()` → `uint256` ← yeni
- `readyTime(uint256)` → `uint256` ← yeni

**Events:**
- `Deposit(address indexed, uint256, uint256)`
- `SubmitTransaction(uint256 indexed, address indexed, address indexed, uint256, bytes)`
- `ConfirmTransaction(uint256 indexed, address indexed, uint256)`
- `RevokeConfirmation(uint256 indexed, address indexed)`
- `ExecuteTransaction(uint256 indexed, address indexed)`
- `TimeLockTriggered(uint256 indexed, uint256)` ← yeni
- `TimeLockDurationChanged(uint256)` ← yeni
- `EmergencyPaused(address indexed)` ← yeni
- `EmergencyUnpaused(address indexed)` ← yeni
- `OwnerAddition(address indexed)`
- `OwnerRemoval(address indexed)`
- `RequirementChange(uint256)`
