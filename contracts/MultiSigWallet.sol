// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
import "./OwnerManager.sol";
import "./TransactionManager.sol";

/**
 * @title MultiSigWallet
 * @author COM4532 - Merve Çakır
 * @notice M-of-N çoklu imzalı cüzdan. Her işlem yürütülmeden önce en az M sahip onayı gerektirir.
 * @dev OwnerManager ve TransactionManager'ı miras alır. ReentrancyGuard reentrancy saldırılarına karşı koruma sağlar.
 *
 * ────────────────────────────────────────────────────────────────────
 *  ÖNEMLİ KURAL: M >= N/2  (numConfirmationsRequired >= owners.length / 2)
 *  Bu kural hem constructor'da hem de validRequirement modifier'ında zorlanır.
 *  Amaç: azınlık saldırısını önlemek ve oy çoğunluğunu garanti altına almak.
 * ────────────────────────────────────────────────────────────────────
 */
contract MultiSigWallet is ReentrancyGuard, OwnerManager, TransactionManager {
    // ─── Events ───────────────────────────────────────────────────────────────

    /**
     * @notice Cüzdana ETH yatırıldığında yayınlanır.
     * @param sender  Gönderen adres.
     * @param amount  Yatırılan ETH miktarı (wei).
     * @param balance İşlem sonrası cüzdan bakiyesi (wei).
     */
    event Deposit(
        address indexed sender,
        uint256 amount,
        uint256 balance
    );

    // ─── Constructor ──────────────────────────────────────────────────────────

    /**
     * @notice Cüzdanı başlatır; sahip listesini ve onay eşiğini ayarlar.
     * @dev M >= N/2 hard-code kuralı burada doğrulanır.
     *
     * @param _owners                  N adet yetkili sahip adresi (tekrarsız, sıfır adres içermemeli).
     * @param _numConfirmationsRequired İşlem için gereken minimum onay sayısı M.
     *                                  Koşul: M >= N/2  ve  1 <= M <= N.
     *
     * @custom:throws "gecersiz M veya N degeri"   _owners boşsa veya M/N kuralı bozuluyorsa.
     * @custom:throws "sahip adresi tekrarlanamaz" Aynı adres birden fazla kez verilmişse.
     * @custom:throws "sifir adres"                address(0) verilmişse.
     */
    constructor(address[] memory _owners, uint256 _numConfirmationsRequired) {
        // ── Temel geçerlilik kontrolü ──────────────────────────────────────
        require(_owners.length > 0, "MultiSigWallet: en az 1 sahip gerekli");
        require(
            _numConfirmationsRequired > 0 &&
                _numConfirmationsRequired <= _owners.length &&
                _numConfirmationsRequired * 2 >= _owners.length, // ← M >= N/2 hard-code
            "MultiSigWallet: gecersiz M veya N degeri (M >= N/2 sarti)"
        );

        // ── Sahipleri kaydet ──────────────────────────────────────────────
        for (uint256 i = 0; i < _owners.length; i++) {
            address owner = _owners[i];
            require(owner != address(0), "MultiSigWallet: sifir adres");
            require(!isOwner[owner], "MultiSigWallet: sahip adresi tekrarlanamaz");

            isOwner[owner] = true;
            owners.push(owner);
        }

        numConfirmationsRequired = _numConfirmationsRequired;
    }

    // ─── Fallback / Receive ───────────────────────────────────────────────────

    /**
     * @notice Doğrudan ETH transferlerini kabul eder ve Deposit event'i yayınlar.
     */
    receive() external payable {
        emit Deposit(msg.sender, msg.value, address(this).balance);
    }

    // ─── Core Multisig Functions ──────────────────────────────────────────────

    /**
     * @notice Yeni bir işlem teklifi oluşturur.
     * @dev Yalnızca kayıtlı sahipler çağırabilir. nonReentrant reentrancy'ye karşı koruma sağlar.
     *
     * @param _to    Hedef adres (alıcı ya da çağrılacak kontrat).
     * @param _value Transfer edilecek ETH miktarı (wei). Saf token transferlerinde 0 olabilir.
     * @param _data  ABI-encoded fonksiyon çağrısı. ETH transferinde boş bytes gönderilebilir.
     * @return txIndex Oluşturulan işlemin dizin numarası.
     */
    function submitTransaction(
        address _to,
        uint256 _value,
        bytes memory _data
    )
        public
        nonReentrant
        returns (uint256 txIndex)
    {
        require(isOwner[msg.sender], "MultiSigWallet: sadece sahip cagirir");
        require(_to != address(0), "MultiSigWallet: sifir hedef adres");

        txIndex = _addTransaction(_to, _value, _data);
    }

    /**
     * @notice Sahip, belirli bir bekleyen işlemi onaylar.
     * @dev Yalnızca sahipler çağırabilir; işlem var olmalı, yürütülmemiş olmalı ve daha önce onaylanmamış olmalı.
     *
     * @param _txIndex Onaylanacak işlemin dizin numarası.
     */
    function confirmTransaction(uint256 _txIndex)
        public
        nonReentrant
        txExists(_txIndex)
        notExecuted(_txIndex)
        notConfirmed(_txIndex)
    {
        require(isOwner[msg.sender], "MultiSigWallet: sadece sahip cagirir");

        confirmed[_txIndex][msg.sender] = true;
        transactions[_txIndex].numConfirmations += 1;

        emit ConfirmTransaction(
            _txIndex,
            msg.sender,
            transactions[_txIndex].numConfirmations
        );
    }

    /**
     * @notice Yeterli onay alındıysa işlemi zincirde yürütür.
     * @dev nonReentrant ile reentrancy korumalı. Yürütme başarısız olursa revert atar.
     *
     * @param _txIndex Yürütülecek işlemin dizin numarası.
     */
    function executeTransaction(uint256 _txIndex)
        public
        nonReentrant
        txExists(_txIndex)
        notExecuted(_txIndex)
    {
        require(isOwner[msg.sender], "MultiSigWallet: sadece sahip cagirir");
        require(
            transactions[_txIndex].numConfirmations >= numConfirmationsRequired,
            "MultiSigWallet: yetersiz onay sayisi"
        );

        Transaction storage txn = transactions[_txIndex];
        txn.executed = true;

        (bool success, ) = txn.to.call{value: txn.value}(txn.data);
        require(success, "MultiSigWallet: islem yurutme basarisiz");

        emit ExecuteTransaction(_txIndex, msg.sender);
    }

    /**
     * @notice Sahip, daha önce verdiği onayı geri çeker.
     * @dev İşlem yürütülmemişse onay geri alınabilir.
     *
     * @param _txIndex Onayı geri çekilecek işlemin dizin numarası.
     */
    function revokeConfirmation(uint256 _txIndex)
        public
        txExists(_txIndex)
        notExecuted(_txIndex)
        alreadyConfirmed(_txIndex)
    {
        require(isOwner[msg.sender], "MultiSigWallet: sadece sahip cagirir");

        confirmed[_txIndex][msg.sender] = false;
        transactions[_txIndex].numConfirmations -= 1;

        emit RevokeConfirmation(_txIndex, msg.sender);
    }

    // ─── View Overrides ───────────────────────────────────────────────────────

    /**
     * @notice İşlemin gereken onay sayısına ulaşıp ulaşmadığını döndürür.
     * @param _txIndex İşlem dizin numarası.
     * @return true ↔ onay sayısı >= numConfirmationsRequired.
     */
    function isConfirmed(uint256 _txIndex)
        public
        view
        override
        txExists(_txIndex)
        returns (bool)
    {
        return transactions[_txIndex].numConfirmations >= numConfirmationsRequired;
    }

    /**
     * @notice Cüzdan ETH bakiyesini döndürür (wei cinsinden).
     * @return Güncel kontrat bakiyesi.
     */
    function getBalance() public view returns (uint256) {
        return address(this).balance;
    }
}
