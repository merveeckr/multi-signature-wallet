// SPDX-License-Identifier: MIT
pragma solidity 0.8.20;

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
 *  KURAL: M >= N/2  (numConfirmationsRequired >= owners.length / 2)
 *  Bu kural hem constructor'da hem de validRequirement modifier'ında zorlanır.
 * ────────────────────────────────────────────────────────────────────
 *
 *  HAFTA 2 EKLEMELERİ:
 *  ─ Time-lock  : M onaya ulaşan işlem, timeLockDuration (24 saat) geçmeden yürütülemez.
 *  ─ Pause      : Herhangi bir sahip cüzdanı durdurabilir / açabilir.
 *  ─ Replay     : DOMAIN_SEPARATOR + nonce ile zincir-arası imza tekrarı önlenir (EIP-712 desteği).
 *  ─ Chain check: executeTransaction, kontratın deploy edildiği zinciri doğrular.
 * ────────────────────────────────────────────────────────────────────
 */
contract MultiSigWallet is ReentrancyGuard, OwnerManager, TransactionManager {
    // ─── State ────────────────────────────────────────────────────────────────

    /// @notice true ise tüm işlem fonksiyonları dondurulmuştur.
    bool public paused;

    /**
     * @notice Her başarılı executeTransaction'da 1 artırılır.
     * @dev Emine'nin EIP-712 off-chain imzalarında replay'i önlemek için kullanılır.
     *      İmza struct'ı bu nonce'u içerdiğinden aynı imza seti iki kez geçerli olmaz.
     */
    uint256 public nonce;

    /**
     * @notice EIP-712 domain separator — Emine'nin off-chain imzalarında kullanılır.
     * @dev chainId + address(this) içerir; farklı chain/kontrat adresinde geçersiz kalır.
     */
    bytes32 public immutable DOMAIN_SEPARATOR;

    /// @dev Deploy sırasındaki chainId — executeTransaction'da zincir doğrulaması için.
    uint256 private immutable DEPLOY_CHAIN_ID;

    // ─── Events ───────────────────────────────────────────────────────────────

    /**
     * @notice Cüzdana ETH yatırıldığında yayınlanır.
     */
    event Deposit(address indexed sender, uint256 amount, uint256 balance);

    /// @notice Bir sahip cüzdanı acil durdurduğunda yayınlanır.
    event EmergencyPaused(address indexed triggeredBy);

    /// @notice Bir sahip duraklatmayı kaldırdığında yayınlanır.
    event EmergencyUnpaused(address indexed triggeredBy);

    // ─── Modifiers ────────────────────────────────────────────────────────────

    /// @dev Cüzdan dondurulmuşsa revert atar.
    modifier whenNotPaused() {
        require(!paused, "MultiSigWallet: cuzcdan durduruldu");
        _;
    }

    // ─── Constructor ──────────────────────────────────────────────────────────

    /**
     * @notice Cüzdanı başlatır; sahip listesini, onay eşiğini ve EIP-712 domain separator'ını ayarlar.
     *
     * @param _owners                  N adet yetkili sahip adresi (tekrarsız, sıfır adres içermemeli).
     * @param _numConfirmationsRequired İşlem için gereken minimum onay sayısı M. Koşul: M >= N/2.
     */
    constructor(address[] memory _owners, uint256 _numConfirmationsRequired) {
        require(_owners.length > 0, "MultiSigWallet: en az 1 sahip gerekli");
        require(
            _numConfirmationsRequired > 0 &&
                _numConfirmationsRequired <= _owners.length &&
                _numConfirmationsRequired * 2 >= _owners.length,
            "MultiSigWallet: gecersiz M veya N degeri (M >= N/2 sarti)"
        );

        for (uint256 i = 0; i < _owners.length; i++) {
            address owner = _owners[i];
            require(owner != address(0), "MultiSigWallet: sifir adres");
            require(!isOwner[owner], "MultiSigWallet: sahip adresi tekrarlanamaz");
            isOwner[owner] = true;
            owners.push(owner);
        }

        numConfirmationsRequired = _numConfirmationsRequired;

        // EIP-712 domain separator — chainId + kontrat adresi ile zincire özgü
        DEPLOY_CHAIN_ID = block.chainid;
        DOMAIN_SEPARATOR = keccak256(abi.encode(
            keccak256("EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"),
            keccak256(bytes("MultiSigWallet")),
            keccak256(bytes("1")),
            block.chainid,
            address(this)
        ));
    }

    // ─── Fallback / Receive ───────────────────────────────────────────────────

    receive() external payable {
        emit Deposit(msg.sender, msg.value, address(this).balance);
    }

    // ─── Core Multisig Functions ──────────────────────────────────────────────

    /**
     * @notice Yeni bir işlem teklifi oluşturur.
     * @param _to    Hedef adres.
     * @param _value Transfer edilecek ETH miktarı (wei).
     * @param _data  ABI-encoded fonksiyon çağrısı.
     * @return txIndex Oluşturulan işlemin dizin numarası.
     */
    function submitTransaction(
        address _to,
        uint256 _value,
        bytes memory _data
    )
        public
        nonReentrant
        whenNotPaused
        returns (uint256 txIndex)
    {
        require(isOwner[msg.sender], "MultiSigWallet: sadece sahip cagirir");
        require(_to != address(0), "MultiSigWallet: sifir hedef adres");

        txIndex = _addTransaction(_to, _value, _data);
    }

    /**
     * @notice Sahip, belirli bir bekleyen işlemi onaylar.
     * @dev Onay sayısı M'e ulaşırsa time-lock başlatılır.
     * @param _txIndex Onaylanacak işlemin dizin numarası.
     */
    function confirmTransaction(uint256 _txIndex)
        public
        nonReentrant
        whenNotPaused
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

        // M onaya ilk kez ulaşıldığında time-lock başlat
        if (transactions[_txIndex].numConfirmations >= numConfirmationsRequired) {
            _setTimeLock(_txIndex);
        }
    }

    /**
     * @notice Yeterli onay alındıysa ve time-lock süresi dolduysa işlemi zincirde yürütür.
     * @dev Replay koruması: zincir doğrulaması + nonce artışı (CEI sırasında). EIP-712 uyumlu.
     * @param _txIndex Yürütülecek işlemin dizin numarası.
     */
    function executeTransaction(uint256 _txIndex)
        public
        nonReentrant
        whenNotPaused
        txExists(_txIndex)
        notExecuted(_txIndex)
        timeLockPassed(_txIndex)
    {
        require(isOwner[msg.sender], "MultiSigWallet: sadece sahip cagirir");
        require(
            transactions[_txIndex].numConfirmations >= numConfirmationsRequired,
            "MultiSigWallet: yetersiz onay sayisi"
        );
        // Chain fork / cross-chain replay koruması
        require(block.chainid == DEPLOY_CHAIN_ID, "MultiSigWallet: yanlis zincir");

        Transaction storage txn = transactions[_txIndex];
        txn.executed = true; // CEI: durum önce güncellenir
        nonce++;              // off-chain imza setini geçersiz kılar

        (bool success, ) = txn.to.call{value: txn.value}(txn.data);
        require(success, "MultiSigWallet: islem yurutme basarisiz");

        emit ExecuteTransaction(_txIndex, msg.sender);
    }

    /**
     * @notice Sahip, daha önce verdiği onayı geri çeker.
     * @param _txIndex Onayı geri çekilecek işlemin dizin numarası.
     */
    function revokeConfirmation(uint256 _txIndex)
        public
        whenNotPaused
        txExists(_txIndex)
        notExecuted(_txIndex)
        alreadyConfirmed(_txIndex)
    {
        require(isOwner[msg.sender], "MultiSigWallet: sadece sahip cagirir");

        confirmed[_txIndex][msg.sender] = false;
        transactions[_txIndex].numConfirmations -= 1;

        emit RevokeConfirmation(_txIndex, msg.sender);
    }

    // ─── Emergency Pause ─────────────────────────────────────────────────────

    /**
     * @notice Cüzdanı acil olarak dondurur. Herhangi bir sahip çağırabilir.
     * @dev Dondurulunca submit/confirm/execute/revoke çalışmaz.
     */
    function pause() public {
        require(isOwner[msg.sender], "MultiSigWallet: sadece sahip cagirir");
        require(!paused, "MultiSigWallet: zaten durduruldu");
        paused = true;
        emit EmergencyPaused(msg.sender);
    }

    /**
     * @notice Duraklatmayı kaldırır. Herhangi bir sahip çağırabilir.
     * @dev onlyWallet kullanılmadı: pause sırasında executeTransaction çalışmaz → deadlock.
     */
    function unpause() public {
        require(isOwner[msg.sender], "MultiSigWallet: sadece sahip cagirir");
        require(paused, "MultiSigWallet: zaten aktif");
        paused = false;
        emit EmergencyUnpaused(msg.sender);
    }

    // ─── Time-lock Yönetimi ───────────────────────────────────────────────────

    /**
     * @notice Time-lock süresini günceller. Sadece multisig konsensüsüyle çağrılabilir.
     * @param _duration Yeni süre (saniye). 0 = time-lock devre dışı bırakır (önerilmez).
     */
    function changeTimeLockDuration(uint256 _duration) public onlyWallet {
        timeLockDuration = _duration;
        emit TimeLockDurationChanged(_duration);
    }

    // ─── View / Helper ────────────────────────────────────────────────────────

    /**
     * @notice İşlemin gereken onay sayısına ulaşıp ulaşmadığını döndürür.
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

    /// @notice Cüzdan ETH bakiyesini döndürür (wei).
    function getBalance() public view returns (uint256) {
        return address(this).balance;
    }

    /**
     * @notice Mevcut zincir ID'sini döndürür.
     * @dev Emine'nin EIP-712 domain separator hesabında kullanılır.
     */
    function getChainId() public view returns (uint256) {
        return block.chainid;
    }

    /**
     * @notice EIP-712 uyumlu işlem hash'ini hesaplar.
     * @dev Emine off-chain imza toplarken bu hash'i kullanır; nonce replay'i önler.
     * @param _txIndex İşlem dizin numarası.
     * @return İmzalanacak EIP-712 mesaj hash'i.
     */
    function getTransactionHash(uint256 _txIndex)
        public
        view
        txExists(_txIndex)
        returns (bytes32)
    {
        Transaction storage txn = transactions[_txIndex];
        return keccak256(abi.encodePacked(
            "\x19\x01",
            DOMAIN_SEPARATOR,
            keccak256(abi.encode(
                keccak256("Transaction(address to,uint256 value,bytes data,uint256 txIndex,uint256 nonce)"),
                txn.to,
                txn.value,
                keccak256(txn.data),
                _txIndex,
                nonce
            ))
        ));
    }
}
