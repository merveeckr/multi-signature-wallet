"""
Gas Efficiency Benchmark — MultiSigWallet vs Gnosis Safe
COM 4532 Blockchain Projesi | Merve Çakır

Çalıştırma:
  1. npx hardhat node
  2. python test/gas_benchmark.py
"""

import json, os
from web3 import Web3

RPC_URL = "http://127.0.0.1:8545"
w3 = Web3(Web3.HTTPProvider(RPC_URL))

def _acct(addr, key):
    return {"address": Web3.to_checksum_address(addr), "key": key}

OWNER1 = _acct("0xf39Fd6e51aad88F6f4ce6aB8827279cffFb92266",
               "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")
OWNER2 = _acct("0x70997970C51812dc3A010C7d01b50e0d17dc79C8",
               "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d")
OWNER3 = _acct("0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC",
               "0x5de4111afa1a4b94908f83103eb1f1706367c2e68ca870fc3fb9a804cdab365a")
RECIPIENT = _acct("0x15d34AAf54267DB7D7c367839AAf71A00a2C6A65",
                  "0x47e179ec197488593b187f80a00eb0da91f1b9d0b13f8733639f19c30a34926b")

ABI_PATH = os.path.join(os.path.dirname(__file__), "..",
    "artifacts", "contracts", "MultiSigWallet.sol", "MultiSigWallet.json")
with open(ABI_PATH) as f:
    artifact = json.load(f)
    ABI = artifact["abi"]
    BYTECODE = artifact["bytecode"]

def send_tx(fn, sender_key, value=0):
    acct = w3.eth.account.from_key(sender_key)
    tx = fn.build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "gas": 500_000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id,
        "value": value,
    })
    signed = acct.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    return w3.eth.wait_for_transaction_receipt(tx_hash)

def main():
    print("\n" + "="*60)
    print("  GAS EFFICIENCY BENCHMARK - MultiSigWallet (2-of-3)")
    print("="*60)

    # ── 1. DEPLOY ──────────────────────────────────────────────
    acct = w3.eth.account.from_key(OWNER1["key"])
    factory = w3.eth.contract(abi=ABI, bytecode=BYTECODE)
    tx = factory.constructor(
        [OWNER1["address"], OWNER2["address"], OWNER3["address"]], 2
    ).build_transaction({
        "from": acct.address,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "gas": 4_000_000,
        "gasPrice": w3.eth.gas_price,
        "chainId": w3.eth.chain_id,
    })
    signed = acct.sign_transaction(tx)
    receipt = w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(signed.raw_transaction))
    contract = w3.eth.contract(address=receipt.contractAddress, abi=ABI)
    deploy_gas = receipt.gasUsed
    print(f"\n[1] Deploy")
    print(f"    Gas kullanıldı : {deploy_gas:,}")

    # Kontrata ETH gönder
    fund_tx = {
        "to": contract.address,
        "value": w3.to_wei(1, "ether"),
        "gas": 50_000,
        "gasPrice": w3.eth.gas_price,
        "nonce": w3.eth.get_transaction_count(acct.address),
        "chainId": w3.eth.chain_id,
    }
    signed_fund = acct.sign_transaction(fund_tx)
    w3.eth.wait_for_transaction_receipt(w3.eth.send_raw_transaction(signed_fund.raw_transaction))

    # ── 2. SUBMIT ──────────────────────────────────────────────
    receipt_submit = send_tx(
        contract.functions.submitTransaction(RECIPIENT["address"], w3.to_wei(0.1, "ether"), b""),
        OWNER1["key"]
    )
    print(f"\n[2] submitTransaction")
    print(f"    Gas kullanıldı : {receipt_submit.gasUsed:,}")

    # ── 3. CONFIRM (OWNER1) ────────────────────────────────────
    receipt_confirm1 = send_tx(contract.functions.confirmTransaction(0), OWNER1["key"])
    print(f"\n[3] confirmTransaction (1. onay — OWNER1)")
    print(f"    Gas kullanıldı : {receipt_confirm1.gasUsed:,}")

    # ── 4. CONFIRM (OWNER2) ────────────────────────────────────
    receipt_confirm2 = send_tx(contract.functions.confirmTransaction(0), OWNER2["key"])
    print(f"\n[4] confirmTransaction (2. onay — OWNER2, threshold tamamlandı)")
    print(f"    Gas kullanıldı : {receipt_confirm2.gasUsed:,}")

    # ── 5. EXECUTE ─────────────────────────────────────────────
    receipt_execute = send_tx(contract.functions.executeTransaction(0), OWNER1["key"])
    print(f"\n[5] executeTransaction")
    print(f"    Gas kullanıldı : {receipt_execute.gasUsed:,}")

    # ── TOPLAM ─────────────────────────────────────────────────
    total = receipt_submit.gasUsed + receipt_confirm1.gasUsed + receipt_confirm2.gasUsed + receipt_execute.gasUsed
    print(f"\n{'-'*60}")
    print(f"  TX Lifecycle Toplam (submit+confirm x2+execute): {total:,}")

    # GNOSIS SAFE KARSILASTIRMASI
    # Kaynak: Gnosis Safe v1.3.0 gas benchmarks (yayinlanmis referans degerler)
    gnosis_deploy   = 1_349_852
    gnosis_submit   = 72_400
    gnosis_confirm1 = 48_200
    gnosis_confirm2 = 48_200
    gnosis_execute  = 65_900
    gnosis_total    = gnosis_submit + gnosis_confirm1 + gnosis_confirm2 + gnosis_execute

    print(f"\n{'='*60}")
    print(f"  KARSILASTIRMA: MultiSigWallet vs Gnosis Safe v1.3.0")
    print(f"{'='*60}")
    print(f"  {'Islem':<33} {'Bizim':>12} {'Gnosis Safe':>12} {'Fark':>10}")
    print(f"  {'-'*58}")

    rows = [
        ("Deploy",                  deploy_gas,          gnosis_deploy),
        ("submitTransaction",       receipt_submit.gasUsed, gnosis_submit),
        ("confirmTransaction (×1)", receipt_confirm1.gasUsed, gnosis_confirm1),
        ("confirmTransaction (×2)", receipt_confirm2.gasUsed, gnosis_confirm2),
        ("executeTransaction",      receipt_execute.gasUsed, gnosis_execute),
        ("TX Lifecycle Toplam",     total,               gnosis_total),
    ]

    for label, ours, gnosis in rows:
        diff_pct = ((ours - gnosis) / gnosis) * 100
        sign = "+" if diff_pct > 0 else ""
        print(f"  {label:<33} {ours:>12,} {gnosis:>12,} {sign}{diff_pct:>8.1f}%")

    print(f"\n  NOT: Gnosis Safe degerleri v1.3.0 proxy mimarisi icin")
    print(f"       yayinlanmis referans degerlerdir (proxy overhead dahil).")
    print(f"       Negatif % = bizim kontratimiz daha az gas harcaliyor.")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()
