/**
 * MultiSigWallet — Etherscan Verify Script
 * Kullanım: node scripts/verify.js
 *
 * Gerekli .env değerleri:
 *   ETHERSCAN_API_KEY → etherscan.io → My Account → API Keys
 *   CONTRACT_ADDRESS  → deploy.js çıktısındaki adres
 *   OWNER_1, OWNER_2, OWNER_3
 */

import { ethers } from "ethers";
import dotenv from "dotenv";
import { readFileSync } from "fs";

dotenv.config();

const ETHERSCAN_API = "https://api-sepolia.etherscan.io/api";

async function main() {
  // Önce deploy_info.json'dan bilgileri al
  let deployInfo;
  try {
    deployInfo = JSON.parse(readFileSync("./scripts/deploy_info.json", "utf8"));
  } catch {
    console.error("deploy_info.json bulunamadı. Önce deploy.js çalıştır.");
    process.exit(1);
  }

  const apiKey = process.env.ETHERSCAN_API_KEY;
  if (!apiKey) {
    console.error("ETHERSCAN_API_KEY .env dosyasında eksik.");
    process.exit(1);
  }

  // Flattened source code oluştur
  console.log("Source code hazırlanıyor...");

  // Constructor arguments ABI encode
  const ownerAddresses = deployInfo.owners;
  const M = deployInfo.numConfirmationsRequired;
  const abiCoder = ethers.AbiCoder.defaultAbiCoder();
  const constructorArgs = abiCoder
    .encode(["address[]", "uint256"], [ownerAddresses, M])
    .slice(2); // 0x kaldır

  console.log("\n=== Etherscan Verification ===");
  console.log("Contract :", deployInfo.contractAddress);
  console.log("API Key  :", apiKey.slice(0, 6) + "...");
  console.log("");
  console.log("Etherscan verification için iki yöntem:");
  console.log("");
  console.log("─── Yöntem 1: Manuel (Daha kolay) ────────────────────────────");
  console.log("1. https://sepolia.etherscan.io/address/" + deployInfo.contractAddress + "#code");
  console.log('2. "Verify and Publish" butonuna tıkla');
  console.log("3. Compiler type: Solidity (Single file) SEÇ");
  console.log("4. Compiler version: v0.8.20 SEÇ");
  console.log("5. License: MIT SEÇ");
  console.log("6. Aşağıdaki komutu çalıştır, çıktıyı Source Code kutusuna yapıştır:");
  console.log("   npx hardhat flatten contracts/MultiSigWallet.sol");
  console.log("7. Constructor Arguments (ABI-encoded):");
  console.log("  ", constructorArgs);
  console.log("");
  console.log("─── Yöntem 2: Otomatik (npx hardhat verify) ──────────────────");
  console.log("Önce hardhat.config.js güncelle, sonra:");
  console.log(
    `npx hardhat verify --network sepolia ${deployInfo.contractAddress} "${ownerAddresses.join('" "')}" ${M}`
  );
}

main().catch((err) => {
  console.error("Hata:", err.message);
  process.exit(1);
});
