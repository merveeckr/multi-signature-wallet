// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

/**
 * @title TransactionManager
 * @author COM4532 - Merve Çakır
 * @notice İşlem (transaction) yaşam döngüsünü yönetir: oluşturma, onaylama, iptal ve sorgulama.
 * @dev Soyut temel kontrat — MultiSigWallet tarafından miras alınır.
 *      Yürütme (execute) mantığı MultiSigWallet'ta; burada yalnızca state ve view fonksiyonları.
 */
abstract contract TransactionManager {
    // ─── Structs ──────────────────────────────────────────────────────────────

    /// @notice Bir multisig işleminin tam kaydı.
    struct Transaction {
        address to;               // Hedef adres (alıcı ya da kontrat)
        uint256 value;            // Transfer edilecek ETH miktarı (wei)
        bytes data;               // Çağrılacak fonksiyon verisi (ABI encoded)
        bool executed;            // İşlem zincirde yürütüldü mü?
        uint256 numConfirmations; // Mevcut onay sayısı
    }

    // ─── State ────────────────────────────────────────────────────────────────

    /// @notice Tüm işlem kayıtları; txIndex → Transaction.
    Transaction[] internal transactions;

    /// @notice txIndex → sahip adresi → onayladı mı?
    mapping(uint256 => mapping(address => bool)) public confirmed;

    /// @notice İşlem zincirde yürütülebilir hale gelme zamanı (unix timestamp).
    mapping(uint256 => uint256) public readyTime;

    /// @notice execute öncesi beklenmesi gereken süre (saniye). Varsayılan: 24 saat.
    uint256 public timeLockDuration = 5 minutes;

    /// @dev readyTime set edildi mi? Slither incorrect-equality uyarısını önler.
    mapping(uint256 => bool) private _timeLockInitialized;

    // ─── Events ───────────────────────────────────────────────────────────────

    /**
     * @notice Yeni bir işlem teklifi oluşturulduğunda yayınlanır.
     * @param txIndex   İşlem dizin numarası.
     * @param submitter Teklifi gönderen sahip.
     * @param to        Hedef adres.
     * @param value     ETH miktarı (wei).
     * @param data      Çağrı verisi.
     */
    event SubmitTransaction(
        uint256 indexed txIndex,
        address indexed submitter,
        address indexed to,
        uint256 value,
        bytes data
    );

    /**
     * @notice Bir sahip işlemi onayladığında yayınlanır.
     * @param txIndex          İşlem dizin numarası.
     * @param confirmer        Onaylayan sahip.
     * @param confirmationCount Güncel toplam onay sayısı.
     */
    event ConfirmTransaction(
        uint256 indexed txIndex,
        address indexed confirmer,
        uint256 confirmationCount
    );

    /**
     * @notice Bir sahip daha önce verdiği onayı geri aldığında yayınlanır.
     * @param txIndex  İşlem dizin numarası.
     * @param revoker  Onayı geri alan sahip.
     */
    event RevokeConfirmation(
        uint256 indexed txIndex,
        address indexed revoker
    );

    /**
     * @notice İşlem yeterli onayı alarak zincirde yürütüldüğünde yayınlanır.
     * @param txIndex  İşlem dizin numarası.
     * @param executor Yürütmeyi tetikleyen sahip.
     */
    event ExecuteTransaction(
        uint256 indexed txIndex,
        address indexed executor
    );

    /**
     * @notice İşlem ilk kez M onaya ulaşıp time-lock'a girdiğinde yayınlanır.
     * @param txIndex    İşlem dizin numarası.
     * @param unlockTime execute için gereken en erken unix timestamp.
     */
    event TimeLockTriggered(uint256 indexed txIndex, uint256 unlockTime);

    /// @notice Time-lock süresi değiştiğinde yayınlanır.
    /// @param newDuration Yeni süre (saniye). 0 = time-lock devre dışı.
    event TimeLockDurationChanged(uint256 newDuration);

    // ─── Modifiers ────────────────────────────────────────────────────────────

    modifier txExists(uint256 _txIndex) {
        require(_txIndex < transactions.length, "TransactionManager: islem bulunamadi");
        _;
    }

    modifier notExecuted(uint256 _txIndex) {
        require(!transactions[_txIndex].executed, "TransactionManager: islem zaten yurutuldu");
        _;
    }

    modifier notConfirmed(uint256 _txIndex) {
        require(!confirmed[_txIndex][msg.sender], "TransactionManager: zaten onaylanmis");
        _;
    }

    modifier alreadyConfirmed(uint256 _txIndex) {
        require(confirmed[_txIndex][msg.sender], "TransactionManager: onay bulunamadi");
        _;
    }

    /// @dev Time-lock başlatılmış ve bekleme süresi dolmuş olmalı.
    modifier timeLockPassed(uint256 _txIndex) {
        require(
            _timeLockInitialized[_txIndex] && block.timestamp >= readyTime[_txIndex],
            "TransactionManager: time-lock suresi dolmadi"
        );
        _;
    }

    // ─── Internal Helpers ─────────────────────────────────────────────────────

    /**
     * @dev Yeni işlem ekler; txIndex döndürür.
     */
    function _addTransaction(
        address _to,
        uint256 _value,
        bytes memory _data
    ) internal returns (uint256 txIndex) {
        txIndex = transactions.length;
        transactions.push(
            Transaction({
                to: _to,
                value: _value,
                data: _data,
                executed: false,
                numConfirmations: 0
            })
        );
        emit SubmitTransaction(txIndex, msg.sender, _to, _value, _data);
    }

    /**
     * @dev İşlem ilk kez M onaya ulaştığında time-lock'ı başlatır.
     *      _timeLockInitialized flag'i ile tekrar yazılması önlenir.
     *      Onay geri çekilip yeniden verilse bile timer sıfırlanmaz.
     */
    function _setTimeLock(uint256 _txIndex) internal {
        if (!_timeLockInitialized[_txIndex]) {
            _timeLockInitialized[_txIndex] = true;
            uint256 unlockTime = block.timestamp + timeLockDuration;
            readyTime[_txIndex] = unlockTime;
            emit TimeLockTriggered(_txIndex, unlockTime);
        }
    }

    // ─── View Functions ───────────────────────────────────────────────────────

    /**
     * @notice Belirli bir işlemin tüm alanlarını döndürür.
     * @param _txIndex İşlem dizin numarası.
     * @return to              Hedef adres.
     * @return value           ETH miktarı (wei).
     * @return data            Çağrı verisi.
     * @return executed        Yürütülme durumu.
     * @return numConfirmations Mevcut onay sayısı.
     */
    function getTransaction(uint256 _txIndex)
        public
        view
        txExists(_txIndex)
        returns (
            address to,
            uint256 value,
            bytes memory data,
            bool executed,
            uint256 numConfirmations
        )
    {
        Transaction storage txn = transactions[_txIndex];
        return (txn.to, txn.value, txn.data, txn.executed, txn.numConfirmations);
    }

    /**
     * @notice Toplam işlem sayısını döndürür.
     * @return Toplam kayıtlı işlem adedi.
     */
    function getTransactionCount() public view returns (uint256) {
        return transactions.length;
    }

    /**
     * @notice Belirli bir sahibin belirli işlemi onaylayıp onaylamadığını döndürür.
     * @param _txIndex İşlem dizin numarası.
     * @param _owner   Sorgulanacak sahip adresi.
     * @return Onay durumu.
     */
    function getConfirmationStatus(uint256 _txIndex, address _owner)
        public
        view
        txExists(_txIndex)
        returns (bool)
    {
        return confirmed[_txIndex][_owner];
    }

    /**
     * @notice Bir işlemin yeterli onaya ulaşıp ulaşmadığını kontrol eder.
     * @dev numConfirmationsRequired soyut olduğu için override edilecek.
     * @param _txIndex İşlem dizin numarası.
     * @return true ↔ yeterli onay var.
     */
    function isConfirmed(uint256 _txIndex)
        public
        view
        virtual
        returns (bool);
}
