"""
MultiSigWallet — Otomatik Test Paketi
COM 4532 Blockchain Projesi | Merve Çakır

Çalıştırma:
  1. Hardhat local node başlat:  npx hardhat node
  2. Deploy:                      npx hardhat run scripts/deploy.js --network localhost
  3. Testleri çalıştır:          pytest test/test_multisig.py -v
"""

import json
import os
import time
import pytest
from web3 import Web3

# ── Bağlantı ────────────────────────────────────────────────────────────────
RPC_URL = "http://127.0.0.1:8545"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

# Hardhat'ın default test hesapları (private key'ler herkese açık, gerçek para yok)
def _acct(addr, key):
    return {"address": Web3.to_checksum_address(addr), "key": key}

ACCOUNTS = [
    _acct("0xf39Fd6e51aad88F6f4ce6aB8827279cffFb92266",
          "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"),
    _acct("0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
          "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d"),
    _acct("0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
          "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a"),
    _acct("0x90F79bf6EB2c4f870365E785982E1f101E93b906",
          "0x7c852118294e51e653712a81e05800f419141751be58f605c371e15141b007a6"),
    _acct("0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
          "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926b"),
]

OWNER1 = ACCOUNTS[0]
OWNER2 = ACCOUNTS[1]
OWNER3 = ACCOUNTS[2]
NON_OWNER = ACCOUNTS[3]
RECIPIENT = ACCOUNTS[4]

# ── ABI & Bytecode ───────────────────────────────────────────────────────────
ABI_PATH = os.path.join(
    os.path.dirname(__file__), "..",
    "artifacts", "contracts", "MultiSigWallet.sol", "MultiSigWallet.json"
)

with open(ABI_PATH) as f:
    artifact = json.load(f)
    ABI = artifact["abi"]
    BYTECODE = artifact["bytecode"]


# ── Yardımcı fonksiyon ───────────────────────────────────────────────────────
def deploy_wallet(owners, threshold):
    """Yeni bir MultiSigWallet deploy eder ve kontrat nesnesini döner."""
    acct = w3.eth.account.from_key(OWNER1["key"])
    ContractFactory = w3.eth.contract(abi=ABI, bytecode=BYTECODE)
    tx = ContractFactory.constructor(owners, threshold).build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "gas": 3_000_000,
        "chainId": w3.eth.chain_id,
    })
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return w3.eth.contract(address=receipt.contractAddress, abi=ABI)


def send(contract_fn, sender_key, value=0):
    """Kontrat fonksiyonunu imzalayıp gönderir; receipt döner."""
    acct = w3.eth.account.from_key(sender_key)
    tx = contract_fn.build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "gas": 300_000,
        "chainId": w3.eth.chain_id,
        "value": value,
    })
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(tx_hash)


def fund(contract, amount_eth, sender_key=None):
    """Kontrata ETH gönderir."""
    sender_key = sender_key or OWNER1["key"]
    acct = w3.eth.account.from_key(sender_key)
    tx = {
        "to": contract.address,
        "value": w3.to_wei(amount_eth, "ether"),
        "gas": 50_000,
        "gasPrice": w3.eth.gas_price,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "chainId": w3.eth.chain_id,
    }
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(tx_hash)


# ── Fixture ──────────────────────────────────────────────────────────────────
@pytest.fixture
def wallet():
    """Her test için temiz bir 2-of-3 wallet deploy eder ve 1 ETH yükler."""
    c = deploy_wallet([OWNER1["address"], OWNER2["address"], OWNER3["address"]], 2)
    fund(c, 1.0)
    return c


# ════════════════════════════════════════════════════════════════════════════
# BÖLÜM 1: DEPLOY TESTLERİ
# ════════════════════════════════════════════════════════════════════════════

class TestDeploy:

    def test_owners_correct(self, wallet):
        owners = wallet.functions.getOwners().call()
        assert owners == [OWNER1["address"], OWNER2["address"], OWNER3["address"]]

    def test_threshold_correct(self, wallet):
        assert wallet.functions.numConfirmationsRequired().call() == 2

    def test_initial_balance(self, wallet):
        bal = w3.eth.get_balance(wallet.address)
        assert bal == w3.to_wei(1.0, "ether")

    def test_deploy_empty_owners_fails(self):
        with pytest.raises(Exception):
            deploy_wallet([], 1)

    def test_deploy_threshold_exceeds_owners_fails(self):
        with pytest.raises(Exception):
            deploy_wallet([OWNER1["address"], OWNER2["address"]], 3)

    def test_deploy_threshold_zero_fails(self):
        with pytest.raises(Exception):
            deploy_wallet([OWNER1["address"], OWNER2["address"]], 0)

    def test_deploy_duplicate_owner_fails(self):
        with pytest.raises(Exception):
            deploy_wallet([OWNER1["address"], OWNER1["address"], OWNER2["address"]], 2)


# ════════════════════════════════════════════════════════════════════════════
# BÖLÜM 2: SUBMIT TESTLERİ
# ════════════════════════════════════════════════════════════════════════════

class TestSubmitTransaction:

    def test_owner_can_submit(self, wallet):
        receipt = send(
            wallet.functions.submitTransaction(RECIPIENT["address"], 100, b""),
            OWNER1["key"]
        )
        assert receipt.status == 1

    def test_non_owner_cannot_submit(self, wallet):
        with pytest.raises(Exception):
            send(
                wallet.functions.submitTransaction(RECIPIENT["address"], 100, b""),
                NON_OWNER["key"]
            )

    def test_tx_count_increases(self, wallet):
        send(wallet.functions.submitTransaction(RECIPIENT["address"], 100, b""), OWNER1["key"])
        assert wallet.functions.getTransactionCount().call() == 1

    def test_submit_emits_event(self, wallet):
        receipt = send(
            wallet.functions.submitTransaction(RECIPIENT["address"], 100, b""),
            OWNER1["key"]
        )
        logs = wallet.events.SubmitTransaction().process_receipt(receipt)
        assert len(logs) == 1
        assert logs[0]["args"]["txIndex"] == 0


# ════════════════════════════════════════════════════════════════════════════
# BÖLÜM 3: CONFIRM TESTLERİ
# ════════════════════════════════════════════════════════════════════════════

class TestConfirmTransaction:

    @pytest.fixture(autouse=True)
    def submit_tx(self, wallet):
        self.wallet = wallet
        send(wallet.functions.submitTransaction(RECIPIENT["address"], 100, b""), OWNER1["key"])

    def test_owner_can_confirm(self):
        receipt = send(self.wallet.functions.confirmTransaction(0), OWNER1["key"])
        assert receipt.status == 1

    def test_non_owner_cannot_confirm(self):
        with pytest.raises(Exception):
            send(self.wallet.functions.confirmTransaction(0), NON_OWNER["key"])

    def test_double_confirm_fails(self):
        send(self.wallet.functions.confirmTransaction(0), OWNER1["key"])
        with pytest.raises(Exception):
            send(self.wallet.functions.confirmTransaction(0), OWNER1["key"])

    def test_invalid_tx_index_fails(self):
        with pytest.raises(Exception):
            send(self.wallet.functions.confirmTransaction(99), OWNER1["key"])

    def test_confirmation_count_increases(self):
        send(self.wallet.functions.confirmTransaction(0), OWNER1["key"])
        send(self.wallet.functions.confirmTransaction(0), OWNER2["key"])
        _, _, _, _, num_conf = self.wallet.functions.getTransaction(0).call()
        assert num_conf == 2


# ════════════════════════════════════════════════════════════════════════════
# BÖLÜM 4: EXECUTE TESTLERİ
# ════════════════════════════════════════════════════════════════════════════

class TestExecuteTransaction:

    @pytest.fixture(autouse=True)
    def setup(self, wallet):
        self.wallet = wallet
        amount = w3.to_wei(0.1, "ether")
        send(wallet.functions.submitTransaction(RECIPIENT["address"], amount, b""), OWNER1["key"])
        send(wallet.functions.confirmTransaction(0), OWNER1["key"])
        send(wallet.functions.confirmTransaction(0), OWNER2["key"])

    def test_execute_success(self):
        receipt = send(self.wallet.functions.executeTransaction(0), OWNER1["key"])
        assert receipt.status == 1

    def test_recipient_receives_funds(self):
        before = w3.eth.get_balance(RECIPIENT["address"])
        send(self.wallet.functions.executeTransaction(0), OWNER1["key"])
        after = w3.eth.get_balance(RECIPIENT["address"])
        assert after - before == w3.to_wei(0.1, "ether")

    def test_double_execute_fails(self):
        send(self.wallet.functions.executeTransaction(0), OWNER1["key"])
        with pytest.raises(Exception):
            send(self.wallet.functions.executeTransaction(0), OWNER1["key"])

    def test_execute_without_enough_confirmations_fails(self):
        amount = w3.to_wei(0.1, "ether")
        send(self.wallet.functions.submitTransaction(RECIPIENT["address"], amount, b""), OWNER1["key"])
        send(self.wallet.functions.confirmTransaction(1), OWNER1["key"])
        with pytest.raises(Exception):
            send(self.wallet.functions.executeTransaction(1), OWNER1["key"])

    def test_executed_flag_set_to_true(self):
        send(self.wallet.functions.executeTransaction(0), OWNER1["key"])
        _, _, _, executed, _ = self.wallet.functions.getTransaction(0).call()
        assert executed is True


# ════════════════════════════════════════════════════════════════════════════
# BÖLÜM 5: REVOKE TESTLERİ
# ════════════════════════════════════════════════════════════════════════════

class TestRevokeConfirmation:

    @pytest.fixture(autouse=True)
    def setup(self, wallet):
        self.wallet = wallet
        send(wallet.functions.submitTransaction(RECIPIENT["address"], 100, b""), OWNER1["key"])
        send(wallet.functions.confirmTransaction(0), OWNER1["key"])

    def test_owner_can_revoke(self):
        receipt = send(self.wallet.functions.revokeConfirmation(0), OWNER1["key"])
        assert receipt.status == 1

    def test_unconfirmed_owner_cannot_revoke(self):
        with pytest.raises(Exception):
            send(self.wallet.functions.revokeConfirmation(0), OWNER2["key"])

    def test_revoke_prevents_execute(self):
        send(self.wallet.functions.confirmTransaction(0), OWNER2["key"])
        send(self.wallet.functions.revokeConfirmation(0), OWNER1["key"])
        with pytest.raises(Exception):
            send(self.wallet.functions.executeTransaction(0), OWNER1["key"])

    def test_confirmation_count_decreases(self):
        send(self.wallet.functions.revokeConfirmation(0), OWNER1["key"])
        _, _, _, _, num_conf = self.wallet.functions.getTransaction(0).call()
        assert num_conf == 0


# ════════════════════════════════════════════════════════════════════════════
# BÖLÜM 6: GÜVENLİK / SALDIRI SİMÜLASYONLARI
# ════════════════════════════════════════════════════════════════════════════

class TestSecurityAttacks:

    def test_replay_attack_tx0_approval_does_not_apply_to_tx1(self, wallet):
        """TX0 onayı TX1'e geçmez — replay koruması."""
        send(wallet.functions.submitTransaction(RECIPIENT["address"], 100, b""), OWNER1["key"])
        send(wallet.functions.submitTransaction(RECIPIENT["address"], 200, b""), OWNER1["key"])
        send(wallet.functions.confirmTransaction(0), OWNER1["key"])
        _, _, _, _, conf1 = wallet.functions.getTransaction(1).call()
        assert conf1 == 0

    def test_unauthorized_execute_fails(self, wallet):
        """Non-owner execute edemez."""
        send(wallet.functions.submitTransaction(RECIPIENT["address"], 100, b""), OWNER1["key"])
        send(wallet.functions.confirmTransaction(0), OWNER1["key"])
        send(wallet.functions.confirmTransaction(0), OWNER2["key"])
        with pytest.raises(Exception):
            send(wallet.functions.executeTransaction(0), NON_OWNER["key"])

    def test_reentrancy_guard_executed_flag(self, wallet):
        """Execute sonrası executed=True — reentrancy koruması."""
        amount = w3.to_wei(0.1, "ether")
        send(wallet.functions.submitTransaction(RECIPIENT["address"], amount, b""), OWNER1["key"])
        send(wallet.functions.confirmTransaction(0), OWNER1["key"])
        send(wallet.functions.confirmTransaction(0), OWNER2["key"])
        send(wallet.functions.executeTransaction(0), OWNER1["key"])
        _, _, _, executed, _ = wallet.functions.getTransaction(0).call()
        assert executed is True

    def test_deposit_increases_balance(self, wallet):
        """ETH gönderilince bakiye artar."""
        before = w3.eth.get_balance(wallet.address)
        fund(wallet, 0.5)
        after = w3.eth.get_balance(wallet.address)
        assert after - before == w3.to_wei(0.5, "ether")


# ════════════════════════════════════════════════════════════════════════════
# BÖLÜM 7: ACİL DURDURMA (EMERGENCY PAUSE)
# ════════════════════════════════════════════════════════════════════════════

class TestEmergencyPause:

    def test_owner_can_pause(self, wallet):
        """Owner cüzdanı durdurabilir."""
        receipt = send(wallet.functions.pause(), OWNER1["key"])
        assert receipt.status == 1
        assert wallet.functions.paused().call() is True

    def test_paused_wallet_rejects_submit(self, wallet):
        """Durdurulmuş cüzdanda submitTransaction çalışmaz."""
        send(wallet.functions.pause(), OWNER1["key"])
        with pytest.raises(Exception):
            send(
                wallet.functions.submitTransaction(RECIPIENT["address"], 100, b""),
                OWNER1["key"]
            )

    def test_owner_can_unpause_and_resume(self, wallet):
        """Owner cüzdanı yeniden açabilir ve işlem tekrar çalışır."""
        send(wallet.functions.pause(), OWNER1["key"])
        assert wallet.functions.paused().call() is True
        send(wallet.functions.unpause(), OWNER1["key"])
        assert wallet.functions.paused().call() is False
        receipt = send(
            wallet.functions.submitTransaction(RECIPIENT["address"], 100, b""),
            OWNER1["key"]
        )
        assert receipt.status == 1

    def test_non_owner_cannot_pause(self, wallet):
        """Non-owner cüzdanı durduramaz."""
        with pytest.raises(Exception):
            send(wallet.functions.pause(), NON_OWNER["key"])
