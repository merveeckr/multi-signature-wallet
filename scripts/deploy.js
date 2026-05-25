/**
 * MultiSigWallet — Sepolia Deploy Script
 * Kullanım: node scripts/deploy.js
 *
 * Önce .env dosyasını doldur:
 *   SEPOLIA_RPC_URL  → Infura/Alchemy URL
 *   PRIVATE_KEY      → Owner 1 (senin) private key
 *   OWNER_1          → Senin adresin
 *   OWNER_2          → Emine'nin adresi
 *   OWNER_3          → İrem'in adresi
 */

import { ethers } from "ethers";
import dotenv from "dotenv";
import { readFileSync, writeFileSync } from "fs";

dotenv.config();

// ─── Config ──────────────────────────────────────────────────────────────────

const SEPOLIA_CHAIN_ID = 11155111;

const OWNERS = [
  process.env.OWNER_1,
  process.env.OWNER_2,
  process.env.OWNER_3,
];

const M = 2; // 2-of-3

// ─── Validate env ────────────────────────────────────────────────────────────

function validateEnv() {
  const required = ["SEPOLIA_RPC_URL", "PRIVATE_KEY", "OWNER_1", "OWNER_2", "OWNER_3"];
  const missing = required.filter((k) => !process.env[k] || process.env[k] === "0x");
  if (missing.length > 0) {
    console.error("Eksik .env değerleri:", missing.join(", "));
    process.exit(1);
  }

  for (const addr of OWNERS) {
    if (!ethers.isAddress(addr)) {
      console.error("Geçersiz Ethereum adresi:", addr);
      process.exit(1);
    }
  }

  const uniqueOwners = new Set(OWNERS.map((a) => a.toLowerCase()));
  if (uniqueOwners.size !== OWNERS.length) {
    console.error("Aynı owner adresi birden fazla kez girilmiş.");
    process.exit(1);
  }
}

// ─── Deploy ──────────────────────────────────────────────────────────────────

async function main() {
  validateEnv();

  const artifact = JSON.parse(
    readFileSync(
      "./artifacts/contracts/MultiSigWallet.sol/MultiSigWallet.json",
      "utf8"
    )
  );

  const provider = new ethers.JsonRpcProvider(process.env.SEPOLIA_RPC_URL);
  const network = await provider.getNetwork();

  if (Number(network.chainId) !== SEPOLIA_CHAIN_ID) {
    console.error(
      `Yanlış ağ! Beklenen: Sepolia (${SEPOLIA_CHAIN_ID}), Bağlı: ${network.chainId}`
    );
    process.exit(1);
  }

  const deployer = new ethers.Wallet(process.env.PRIVATE_KEY, provider);
  const balance = await provider.getBalance(deployer.address);

  console.log("\n=== MultiSigWallet Deploy ===");
  console.log("Deployer :", deployer.address);
  console.log("Bakiye   :", ethers.formatEther(balance), "ETH");
  console.log("Ağ       : Sepolia");
  console.log("Owners   :", OWNERS);
  console.log("M        :", M, "/ 3");
  console.log("");

  if (balance === 0n) {
    console.error("Yetersiz bakiye! https://sepoliafaucet.com adresinden Sepolia ETH al.");
    process.exit(1);
  }

  console.log("Deploy başlıyor...");
  const factory = new ethers.ContractFactory(
    artifact.abi,
    artifact.bytecode,
    deployer
  );

  const contract = await factory.deploy(OWNERS, M);
  console.log("İşlem hash :", contract.deploymentTransaction().hash);
  console.log("Onay bekleniyor...");

  await contract.waitForDeployment();
  const contractAddress = await contract.getAddress();

  console.log("\n✓ Deploy tamamlandı!");
  console.log("Contract adresi:", contractAddress);
  console.log(
    "Etherscan     : https://sepolia.etherscan.io/address/" + contractAddress
  );

  // Deploy bilgisini kaydet
  const deployInfo = {
    contractAddress,
    deployer: deployer.address,
    owners: OWNERS,
    numConfirmationsRequired: M,
    network: "sepolia",
    chainId: SEPOLIA_CHAIN_ID,
    deployTxHash: contract.deploymentTransaction().hash,
    deployedAt: new Date().toISOString(),
  };

  writeFileSync("./scripts/deploy_info.json", JSON.stringify(deployInfo, null, 2));
  console.log("\nDeploy bilgisi scripts/deploy_info.json dosyasına kaydedildi.");
  console.log("\n.env dosyasında şunu güncelle:");
  console.log(`CONTRACT_ADDRESS=${contractAddress}`);
  console.log("\nSonraki adım: node scripts/verify.js");
}

main().catch((err) => {
  console.error("\nDeploy hatası:", err.message);
  process.exit(1);
});
