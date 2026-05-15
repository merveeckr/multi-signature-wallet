// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title OwnerManager
 * @author COM4532 - Merve Çakır
 * @notice Sahibi (owner) yönetimi: ekleme, çıkarma, değiştirme ve onay eşiği kontrolü.
 * @dev Soyut temel kontrat — MultiSigWallet tarafından miras alınır.
 *      M >= N/2 kuralı MultiSigWallet constructor'ında uygulanır.
 */
abstract contract OwnerManager {
    // ─── State ────────────────────────────────────────────────────────────────

    /// @notice Adresin sahip olup olmadığını döndürür.
    mapping(address => bool) public isOwner;

    /// @notice Sahip adreslerinin sıralı listesi.
    address[] public owners;

    /// @notice İşlemin yürütülebilmesi için gereken minimum onay sayısı (M).
    uint256 public numConfirmationsRequired;

    // ─── Events ───────────────────────────────────────────────────────────────

    /// @notice Yeni bir sahip eklendiğinde yayınlanır.
    /// @param owner Eklenen sahibin adresi.
    event OwnerAddition(address indexed owner);

    /// @notice Bir sahip listeden çıkarıldığında yayınlanır.
    /// @param owner Çıkarılan sahibin adresi.
    event OwnerRemoval(address indexed owner);

    /// @notice Onay eşiği değiştiğinde yayınlanır.
    /// @param required Yeni onay sayısı (M).
    event RequirementChange(uint256 required);

    // ─── Modifiers ────────────────────────────────────────────────────────────

    modifier onlyWallet() {
        require(msg.sender == address(this), "OwnerManager: sadece kontrat cagirabilir");
        _;
    }

    modifier ownerExists(address _owner) {
        require(isOwner[_owner], "OwnerManager: sahip bulunamadi");
        _;
    }

    modifier ownerDoesNotExist(address _owner) {
        require(!isOwner[_owner], "OwnerManager: zaten sahip");
        _;
    }

    modifier notNull(address _address) {
        require(_address != address(0), "OwnerManager: sifir adres");
        _;
    }

    /// @dev M >= N/2 geçerliliğini doğrular (onay sayısı sahip sayısının yarısından az olamaz).
    modifier validRequirement(uint256 _ownerCount, uint256 _required) {
        require(
            _required != 0 &&
                _ownerCount != 0 &&
                _required <= _ownerCount &&
                _required * 2 >= _ownerCount, // M >= N/2 hard-code kuralı
            "OwnerManager: gecersiz M veya N degeri (M >= N/2 sarti)"
        );
        _;
    }

    // ─── Functions ────────────────────────────────────────────────────────────

    /**
     * @notice Sisteme yeni bir sahip ekler.
     * @dev Yalnızca multisig onayıyla (address(this)) çağrılabilir.
     * @param owner Eklenecek yeni sahibin Ethereum adresi.
     */
    function addOwner(address owner)
        public
        virtual
        onlyWallet
        ownerDoesNotExist(owner)
        notNull(owner)
        validRequirement(owners.length + 1, numConfirmationsRequired)
    {
        isOwner[owner] = true;
        owners.push(owner);
        emit OwnerAddition(owner);
    }

    /**
     * @notice Mevcut bir sahibi listeden çıkarır.
     * @dev Yalnızca multisig onayıyla çağrılabilir. Silme sonrası M >= N/2 hâlâ sağlanmalıdır.
     * @param owner Çıkarılacak sahibin adresi.
     */
    function removeOwner(address owner)
        public
        virtual
        onlyWallet
        ownerExists(owner)
    {
        isOwner[owner] = false;

        // owners dizisinden çıkar
        for (uint256 i = 0; i < owners.length - 1; i++) {
            if (owners[i] == owner) {
                owners[i] = owners[owners.length - 1];
                break;
            }
        }
        owners.pop();

        // Sahip sayısı düştüyse eşiği otomatik ayarla (M >= N/2 kuralı koruyarak)
        if (numConfirmationsRequired > owners.length) {
            changeRequirement(owners.length);
        }

        emit OwnerRemoval(owner);
    }

    /**
     * @notice Mevcut bir sahibi yeni bir adresle değiştirir.
     * @dev Yalnızca multisig onayıyla çağrılabilir.
     * @param owner    Değiştirilecek mevcut sahip adresi.
     * @param newOwner Yeni sahip adresi.
     */
    function replaceOwner(address owner, address newOwner)
        public
        virtual
        onlyWallet
        ownerExists(owner)
        ownerDoesNotExist(newOwner)
        notNull(newOwner)
    {
        for (uint256 i = 0; i < owners.length; i++) {
            if (owners[i] == owner) {
                owners[i] = newOwner;
                break;
            }
        }
        isOwner[owner] = false;
        isOwner[newOwner] = true;

        emit OwnerRemoval(owner);
        emit OwnerAddition(newOwner);
    }

    /**
     * @notice Gereken minimum onay sayısını (M) günceller.
     * @dev Yalnızca multisig onayıyla çağrılabilir. M >= N/2 zorunlu.
     * @param _required Yeni onay eşiği.
     */
    function changeRequirement(uint256 _required)
        public
        virtual
        onlyWallet
        validRequirement(owners.length, _required)
    {
        numConfirmationsRequired = _required;
        emit RequirementChange(_required);
    }

    /**
     * @notice Tüm sahip adreslerini döndürür.
     * @return Sahip adres dizisi.
     */
    function getOwners() public view returns (address[] memory) {
        return owners;
    }
}
