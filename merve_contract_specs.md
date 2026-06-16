# Merve'nin Paylaşacakları — Contract Teknik Spesifikasyonları

**Proje:** Multi-Signature Wallet (COM4532 - Blockchain)
**Mimari:** M-of-N Threshold Consensus | Solidity ^0.8.20 | Ethereum
**Son güncelleme:** Hafta 2 tamamlandı — Time-lock + emergencyPause eklendi

---

## Mimari Not (Emine & İrem için)

Bu projede **3 ayrı deploy edilen contract YOK**. Bunun yerine:

- `OwnerManager.sol` ve `TransactionManager.sol` birer **abstract (soyut) base contract**
- `MultiSigWallet.sol` bu ikisini **inherit** ederek tek bir contract halinde deploy ediliyor
- Yani deploy edilen **tek contract: `MultiSigWallet`**

```
MultiSigWallet
  ├── is ReentrancyGuard   (OpenZeppelin)
  ├── is OwnerManager      (abstract — sahip yönetimi)
  └── is TransactionManager (abstract — tx yaşam döngüsü + time-lock state)
```

---

## 1. `MultiSigWallet.sol` — Deploy Edilen Contract

### Constructor

```solidity
constructor(
    address[] memory _owners,             // Başlangıç sahiplerinin adresleri (N adet)
    uint256 _numConfirmationsRequired     // Gereken minimum onay sayısı (M değeri)
)
```

**Kurallar:**
- `_owners` boş olamaz
- `M >= N/2` hard-coded zorunlu (`_numConfirmationsRequired * 2 >= _owners.length`)
- Tekrar eden adres veya sıfır adres kabul edilmez

**Revert mesajları:**
- `"MultiSigWallet: en az 1 sahip gerekli"`
- `"MultiSigWallet: gecersiz M veya N degeri (M >= N/2 sarti)"`
- `"MultiSigWallet: sifir adres"`
- `"MultiSigWallet: sahip adresi tekrarlanamaz"`

---

### Fonksiyon İmzaları

```solidity
// Yeni işlem teklifi oluşturur → txIndex döndürür
function submitTransaction(
    address _to,
    uint256 _value,
    bytes memory _data
) public nonReentrant whenNotPaused returns (uint256 txIndex);

// Sahip belirli bir işlemi onaylar; M'e ulaşıldığında time-lock başlar
function confirmTransaction(uint256 _txIndex)
    public nonReentrant whenNotPaused;

// Time-lock süresi dolduktan sonra işlemi zincirde yürütür
function executeTransaction(uint256 _txIndex)
    public nonReentrant whenNotPaused;

// Sahip daha önce verdiği onayı geri çeker
function revokeConfirmation(uint256 _txIndex)
    public whenNotPaused;

// İşlemin yeterli onaya ulaşıp ulaşmadığını döndürür
function isConfirmed(uint256 _txIndex)
    public view returns (bool);

// Cüzdan ETH bakiyesini döndürür (wei)
function getBalance() public view returns (uint256);
```

**receive() — Doğrudan ETH transferi kabul eder, Deposit event yayınlar.**

---

### ★ YENİ — Emergency Pause Fonksiyonları

```solidity
// Cüzdanı dondurur — herhangi bir sahip çağırabilir (hız öncelikli)
function pause() public;

// Duraklatmayı kaldırır — herhangi bir sahip çağırabilir (deadlock önlenir)
function unpause() public;

// Durum okuma
bool public paused;
```

**Tasarım kararı:** `unpause()` `onlyWallet` değil, `onlyOwner` gerektirir.
Sebebi: cüzdan dondurulduğunda `executeTransaction` çalışmaz → `onlyWallet`
kullansaydık açmak imkânsız olurdu (deadlock).

---

### ★ YENİ — Time-lock Fonksiyonu

```solidity
// Time-lock süresini değiştirir — sadece multisig konsensüsüyle (onlyWallet)
function changeTimeLockDuration(uint256 _duration) public onlyWallet;

// Durum okuma
uint256 public timeLockDuration;           // varsayılan: 86400 (24 saat)
mapping(uint256 => uint256) public readyTime; // txIndex → unlock timestamp
```

**Akış:**
1. `confirmTransaction` ile M onaya ulaşıldığında → `readyTime[txIndex]` set edilir
2. `block.timestamp >= readyTime[txIndex]` olmadan `executeTransaction` revert atar
3. `readyTime` bir kez set edilince sıfırlanmaz (onay geri çekilip yeniden verilse bile timer sıfırlanmaz)

---

### Events (MultiSigWallet)

```solidity
event Deposit(address indexed sender, uint256 amount, uint256 balance);
event EmergencyPaused(address indexed triggeredBy);    // ★ YENİ
event EmergencyUnpaused(address indexed triggeredBy);  // ★ YENİ
```

### Events (TransactionManager — MultiSigWallet'ta da yayınlanır)

```solidity
event SubmitTransaction(uint256 indexed txIndex, address indexed submitter, address indexed to, uint256 value, bytes data);
event ConfirmTransaction(uint256 indexed txIndex, address indexed confirmer, uint256 confirmationCount);
event RevokeConfirmation(uint256 indexed txIndex, address indexed revoker);
event ExecuteTransaction(uint256 indexed txIndex, address indexed executor);
event TimeLockTriggered(uint256 indexed txIndex, uint256 unlockTime);  // ★ YENİ
event TimeLockDurationChanged(uint256 newDuration);                    // ★ YENİ
```

---

## 2. `OwnerManager.sol` — Abstract Base Contract (değişiklik yok)

> Ayrı deploy **edilmez**. MultiSigWallet içinde miras alınır.

### State Değişkenleri

```solidity
mapping(address => bool) public isOwner;
address[] public owners;
uint256 public numConfirmationsRequired;
```

### Fonksiyon İmzaları

```solidity
function addOwner(address owner) public virtual;        // onlyWallet
function removeOwner(address owner) public virtual;     // onlyWallet
function replaceOwner(address owner, address newOwner) public virtual; // onlyWallet
function changeRequirement(uint256 _required) public virtual;          // onlyWallet
function getOwners() public view returns (address[] memory);
```

### Events

```solidity
event OwnerAddition(address indexed owner);
event OwnerRemoval(address indexed owner);
event RequirementChange(uint256 required);
```

---

## 3. `TransactionManager.sol` — Abstract Base Contract

> Ayrı deploy **edilmez**. MultiSigWallet içinde miras alınır.

### Transaction Struct

```solidity
struct Transaction {
    address to;
    uint256 value;
    bytes data;
    bool executed;
    uint256 numConfirmations;
}
```

### State Değişkenleri

```solidity
Transaction[] internal transactions;
mapping(uint256 => mapping(address => bool)) public confirmed;
mapping(uint256 => uint256) public readyTime;   // ★ YENİ — time-lock
uint256 public timeLockDuration = 24 hours;     // ★ YENİ — varsayılan 24 saat
```

### Fonksiyon İmzaları

```solidity
function getTransaction(uint256 _txIndex) public view returns (address to, uint256 value, bytes memory data, bool executed, uint256 numConfirmations);
function getTransactionCount() public view returns (uint256);
function getConfirmationStatus(uint256 _txIndex, address _owner) public view returns (bool);
function isConfirmed(uint256 _txIndex) public view virtual returns (bool);
```

---

## ABI Dosyaları

- `abi/MultiSigWallet.abi.json` — **GÜNCELLENDİ** (yeni fonksiyonlar + eventler dahil)
- `abi/OwnerManager.abi.json`
- `abi/TransactionManager.abi.json` — **GÜNCELLENDİ**

---

## Deploy Bilgisi

```python
owners = [addr1, addr2, addr3]
num_confirmations_required = 2  # M >= N/2

MultiSigWallet.deploy(owners, num_confirmations_required)
# timeLockDuration varsayılan olarak 24 saat (86400 saniye) başlar
```

---

## Tüm Revert Mesajları (İrem için — güncellenmiş)

| Senaryo | Revert Mesajı |
|---|---|
| M < N/2 veya M=0 | `"MultiSigWallet: gecersiz M veya N degeri (M >= N/2 sarti)"` |
| Boş owners dizisi | `"MultiSigWallet: en az 1 sahip gerekli"` |
| Tekrar eden sahip | `"MultiSigWallet: sahip adresi tekrarlanamaz"` |
| address(0) owner | `"MultiSigWallet: sifir adres"` |
| Sahip olmayan çağırır | `"MultiSigWallet: sadece sahip cagirir"` |
| Olmayan txIndex | `"TransactionManager: islem bulunamadi"` |
| Zaten yürütülmüş tx | `"TransactionManager: islem zaten yurutuldu"` |
| Aynı sahip 2 kez onaylar | `"TransactionManager: zaten onaylanmis"` |
| Yetersiz onay ile execute | `"MultiSigWallet: yetersiz onay sayisi"` |
| Onayı olmayan revoke | `"TransactionManager: onay bulunamadi"` |
| addOwner direkt çağrılır | `"OwnerManager: sadece kontrat cagirabilir"` |
| Time-lock dolmadan execute | `"TransactionManager: time-lock suresi dolmadi"` ★ YENİ |
| Paused iken işlem yapmak | `"MultiSigWallet: cuzcdan durduruldu"` ★ YENİ |
| Zaten paused iken pause | `"MultiSigWallet: zaten durduruldu"` ★ YENİ |
| Paused değilken unpause | `"MultiSigWallet: zaten aktif"` ★ YENİ |

---

## Güvenlik Mekanizmaları — Güncel Durum

| Mekanizma | Durum | Detay |
|---|---|---|
| M >= N/2 hard-code | ✅ | Constructor + `validRequirement` modifier |
| ReentrancyGuard | ✅ | `submit`, `confirm`, `execute` — nonReentrant |
| CEI Pattern | ✅ | `txn.executed = true` → sonra `.call{}()` |
| Duplikat onay engeli | ✅ | `notConfirmed` modifier |
| Yürütülmüş tx koruması | ✅ | `notExecuted` modifier |
| Sıfır adres kontrolü | ✅ | Constructor + `notNull` modifier |
| Time-lock (24 saat) | ✅ | M onaya ulaşınca timer başlar; dolmadan execute revert |
| emergencyPause | ✅ | Herhangi bir sahip dondurur/açar |
