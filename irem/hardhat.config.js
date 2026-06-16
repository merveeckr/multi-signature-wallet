import dotenv from "dotenv";
dotenv.config();

/** @type import('hardhat/config').HardhatUserConfig */
export default {
  solidity: {
    version: "0.8.20",
    settings: {
      optimizer: {
        enabled: true,
        runs: 200,
      },
    },
  },
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
  // Sepolia ağı — sadece .env doldurulunca aktif olur
  ...(process.env.SEPOLIA_RPC_URL
    ? {
        networks: {
          sepolia: {
            type: "http",
            url: process.env.SEPOLIA_RPC_URL,
            accounts: process.env.PRIVATE_KEY ? [process.env.PRIVATE_KEY] : [],
            chainId: 11155111,
          },
        },
        etherscan: {
          apiKey: {
            sepolia: process.env.ETHERSCAN_API_KEY || "",
          },
        },
      }
    : {}),
};
