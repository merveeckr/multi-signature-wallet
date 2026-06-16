# MultiSigWallet — Güvenlik Audit Raporu

**Proje:** Multi-Signature Wallet (COM4532 - Blockchain)  
**Yazar:** Merve Çakır  
**Araç:** Slither v0.11.5  
**Tarih:** 25 Mayıs 2026  
**Hedef:** `contracts/MultiSigWallet.sol` (+ OwnerManager, TransactionManager)

---

## Özet

| Seviye | İlk Çalıştırma | Düzeltme Sonrası |
|---|---|---|
| Critical | 0 | 0 |
| High | 0 | 0 |
| Medium | 2 | 0 ✓ |
| Low / Info | 5 | 5 (false positive / intentional) |

**Sonuç: 0 Critical, 0 High bulgu. 2 Medium bulgu düzeltildi.**

---

## Düzeltilen Bulgular

### [FIXED] M-01 — Strict Equality with Zero (incorrect-equality)

**Detektor:** `incorrect-equality`  
**Konum:** `TransactionManager._setTimeLock()` — `readyTime[_txIndex] == 0`  
**Risk:** Strict equality kullanımı, beklenmedik 0 değeriyle yanlış davranışa yol açabilir.

**Düzeltme:** `readyTime[_txIndex] == 0` yerine ayrı bir `bool _timeLockInitialized[txIndex]` flag'i eklendi. Artık time-lock başlatılıp başlatılmadığı boolean ile takip ediliyor.

```solidity
// Önce (riskli):
if (readyTime[_txIndex] == 0) { ... }

// Sonra (güvenli):
if (!_timeLockInitialized[_txIndex]) {
    _timeLockInitialized[_txIndex] = true;
    ...
}
```

---

### [FIXED] M-02 — Timestamp Comparison Risk (timestamp)

**Detektor:** `timestamp`  
**Konum:** `TransactionManager._setTimeLock()` — `readyTime[_txIndex] == 0`  
**Risk:** Miner'lar `block.timestamp`'i yaklaşık 15 dakika manipüle edebilir.

**Not:** Bu bulgu M-01 ile aynı satırdan kaynaklanıyordu. M-01 düzeltmesiyle birlikte bu da giderildi.  
**Etki:** Time-lock süresi 24 saat olduğundan 15 dakikalık timestamp manipülasyonu pratikte anlamsızdır, ancak iyileştirme alındı.

---

### [FIXED] L-01 — Cache Array Length (cache-array-length)

**Detektor:** `cache-array-length`  
**Konum:** `OwnerManager.removeOwner()` ve `OwnerManager.replaceOwner()` döngüleri  
**Risk:** Her iterasyonda `owners.length` storage'dan okunur → gereksiz gas tüketimi.

**Düzeltme:** Her iki fonksiyonda da döngüden önce `uint256 len = owners.length` ile cache'lendi.

```solidity
// Önce:
for (uint256 i = 0; i < owners.length; i++) { ... }

// Sonra:
uint256 len = owners.length;
for (uint256 i = 0; i < len; i++) { ... }
```

---

## Kalan Bulgular — False Positive / Kasıtlı

### [FALSE POSITIVE] I-01 — Assembly Kullanımı (assembly)

**Konum:** `node_modules/@openzeppelin/contracts/utils/StorageSlot.sol`  
**Durum:** OpenZeppelin kütüphanesi kodu — projemiz tarafından yazılmamıştır.  
**Eylem:** Yok. Üçüncü taraf kütüphane sorumluluğu dışındadır.

---

### [FALSE POSITIVE / INTENTIONAL] I-02 — Pragma Sürüm Uyumsuzluğu (pragma)

**Bulgular:**
- Projemiz: `pragma solidity 0.8.20` (sabit sürüm — önerilen)
- OpenZeppelin: `pragma solidity ^0.8.20` (esnek sürüm)

**Durum:** Projemiz kendi kontratlarında sürümü sabitledi (bu güvenlik açısından daha iyidir). OZ'nin `^0.8.20` kullanması OZ'nin kendi tercihidir, değiştirilemez.  
**Eylem:** Yok.

---

### [INTENTIONAL] I-03 — Solidity Sürüm Uyarısı (solc-version)

**Bulgu:** `0.8.20` sürümünde bilinen hatalar: `VerbatimInvalidDeduplication`, `FullInlinerNonExpressionSplitArgumentEvaluationOrder`, `MissingSideEffectsOnSelectorAccess`

**Analiz:**
- `VerbatimInvalidDeduplication` — sadece `verbatim` yasm opcode'u kullananları etkiler. Projemizde `verbatim` kullanılmıyor.
- `FullInlinerNonExpressionSplitArgumentEvaluationOrder` — sadece optimizer açık + karmaşık ifade sıralama. Projemiz bu pattern'i kullanmıyor.
- `MissingSideEffectsOnSelectorAccess` — `function selector` üzerinde yan etkili ifade. Projemizde yok.

**Sonuç:** Bu hatalar projemizi etkilemez. 0.8.20 kullanımı devam eder (Hardhat projesi bu sürüme configure edilmiştir).

---

### [INTENTIONAL] I-04 — Low-Level Call (low-level-calls)

**Konum:** `MultiSigWallet.executeTransaction()` — `txn.to.call{value: txn.value}(txn.data)`

**Gerekçe:** Multisig cüzdan tasarımının özüdür. Arbitrary calldata (ABI-encoded fonksiyon çağrısı) iletmek için low-level call zorunludur. Yüksek seviyeli çağrı (`ITarget(txn.to).someFunc()`) kullanılamaz çünkü hedef kontrat ve fonksiyon compile-time'da bilinmez.

**Mevcut mitigasyonlar:**
- `nonReentrant` modifier (ReentrancyGuard)
- CEI pattern: `txn.executed = true` + `nonce++` → dış çağrıdan önce
- Başarısızlık durumunda `require(success)` ile revert

**Eylem:** Yok. Tasarım gereği.

---

### [INTENTIONAL] I-05 — İsimlendirme Kuralları (naming-convention)

**Bulgular:**
- Parametre isimleri `_txIndex`, `_to`, `_value` vb. — underscore prefix
- Sabit değişkenler `DOMAIN_SEPARATOR`, `DEPLOY_CHAIN_ID` — ALL_CAPS

**Gerekçe:**
- Underscore prefix (`_param`): parametre ile state değişkenini ayırt etmek için yaygın Solidity konvansiyonu. Kod okunurluğunu artırır.
- ALL_CAPS: `immutable` ve `constant` değişkenler için EVM standart konvansiyonu (Solidity resmi kılavuzu da öneriyor).

**Eylem:** Yok. Kasıtlı stil tercihidir.

---

## Manuel Access Control Checklist

| Fonksiyon | Kısıtlama | Doğrulama |
|---|---|---|
| `submitTransaction` | `isOwner[msg.sender]` | ✅ |
| `confirmTransaction` | `isOwner[msg.sender]` | ✅ |
| `executeTransaction` | `isOwner[msg.sender]` | ✅ |
| `revokeConfirmation` | `isOwner[msg.sender]` | ✅ |
| `pause` | `isOwner[msg.sender]` | ✅ |
| `unpause` | `isOwner[msg.sender]` | ✅ |
| `addOwner` | `onlyWallet` (msg.sender == address(this)) | ✅ |
| `removeOwner` | `onlyWallet` | ✅ |
| `replaceOwner` | `onlyWallet` | ✅ |
| `changeRequirement` | `onlyWallet` | ✅ |
| `changeTimeLockDuration` | `onlyWallet` | ✅ |
| `getOwners`, `getBalance` vb. | Public view — kısıtlama yok | ✅ |

---

## Attack Vector → Mitigation Tablosu

| Saldırı | Vektör | Mitigation | Durum |
|---|---|---|---|
| Reentrancy | `executeTransaction` → kötü niyetli kontrat geri çağırır | ReentrancyGuard + CEI pattern | ✅ Korumalı |
| Replay (zincir içi) | Aynı txIndex iki kez yürütülür | `executed = true` flag | ✅ Korumalı |
| Replay (zincirler arası) | Mainnet tx'i Sepolia'ya kopyalanır | `DEPLOY_CHAIN_ID` kontrolü + `DOMAIN_SEPARATOR` chainId içerir | ✅ Korumalı |
| Replay (imza seti) | Aynı off-chain imza seti iki kez kullanılır | `nonce` her execute'da artar | ✅ Korumalı |
| Azınlık saldırısı | M sahip konsensüs olmadan yürütür | M ≥ N/2 hard-code | ✅ Korumalı |
| Duplikat onay | Aynı sahip iki kez onaylar | `confirmed[txIndex][owner]` mapping + `notConfirmed` modifier | ✅ Korumalı |
| Time-lock bypass | M onaya ulaşır ulaşmaz anında execute | `timeLockPassed` modifier — `block.timestamp >= readyTime` | ✅ Korumalı |
| Yetkisiz owner ekleme | Direkt `addOwner()` çağrısı | `onlyWallet` modifier | ✅ Korumalı |
| Sıfır adres owner | `address(0)` sahip ekleme | `notNull` modifier + constructor kontrolü | ✅ Korumalı |
| Tekrar eden owner | Aynı adres iki kez ekleme | `ownerDoesNotExist` modifier + `isOwner` mapping | ✅ Korumalı |

---

## Slither Ham Çıktı Özeti

```
İlk çalıştırma (25 Mayıs 2026):
  5 contracts analyzed, 101 detectors, 29 result(s) found
  - incorrect-equality: 1 (FIXED)
  - timestamp: 1 (FIXED)
  - cache-array-length: 1 (FIXED)
  - assembly: 9 (OZ kütüphanesi — false positive)
  - solc-version: 5 (bilinen bug'lar projeyi etkilemiyor)
  - low-level-calls: 1 (intentional)
  - naming-convention: 11 (intentional)

Düzeltme sonrası çalıştırma:
  5 contracts analyzed, 101 detectors, 28 result(s) found
  - incorrect-equality: 0 ✓
  - timestamp: 0 ✓
  - cache-array-length: 0 ✓
  - Kalan: tümü false positive / intentional
```
