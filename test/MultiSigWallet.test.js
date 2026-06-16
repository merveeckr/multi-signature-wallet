import { expect } from "chai";
import hre from "hardhat";

describe("MultiSigWallet", function () {
  let wallet, owner1, owner2, owner3, nonOwner, recipient;

  beforeEach(async function () {
    [owner1, owner2, owner3, nonOwner, recipient] = await hre.ethers.getSigners();

    const MultiSigWallet = await hre.ethers.getContractFactory("MultiSigWallet");
    wallet = await MultiSigWallet.deploy(
      [owner1.address, owner2.address, owner3.address],
      2
    );

    await owner1.sendTransaction({ to: await wallet.getAddress(), value: hre.ethers.parseEther("1.0") });
  });

  // ─── DEPLOY TESTLERİ ───────────────────────────────────────────────────────
  describe("Deploy", function () {
    it("Sahipleri doğru kaydeder", async function () {
      const owners = await wallet.getOwners();
      expect(owners).to.deep.equal([owner1.address, owner2.address, owner3.address]);
    });

    it("Threshold'u doğru ayarlar", async function () {
      expect(await wallet.numConfirmationsRequired()).to.equal(2);
    });

    it("Bakiyeyi alır", async function () {
      const bal = await hre.ethers.provider.getBalance(await wallet.getAddress());
      expect(bal).to.equal(hre.ethers.parseEther("1.0"));
    });

    it("Boş owner listesiyle deploy'u reddeder", async function () {
      const MultiSigWallet = await hre.ethers.getContractFactory("MultiSigWallet");
      await expect(MultiSigWallet.deploy([], 1)).to.be.reverted;
    });

    it("Threshold > N olunca deploy'u reddeder", async function () {
      const MultiSigWallet = await hre.ethers.getContractFactory("MultiSigWallet");
      await expect(MultiSigWallet.deploy([owner1.address, owner2.address], 3)).to.be.reverted;
    });

    it("Threshold = 0 olunca deploy'u reddeder", async function () {
      const MultiSigWallet = await hre.ethers.getContractFactory("MultiSigWallet");
      await expect(MultiSigWallet.deploy([owner1.address, owner2.address], 0)).to.be.reverted;
    });

    it("Duplicate owner ile deploy'u reddeder", async function () {
      const MultiSigWallet = await hre.ethers.getContractFactory("MultiSigWallet");
      await expect(
        MultiSigWallet.deploy([owner1.address, owner1.address, owner2.address], 2)
      ).to.be.reverted;
    });
  });

  // ─── SUBMIT TESTLERİ ───────────────────────────────────────────────────────
  describe("submitTransaction", function () {
    it("Owner işlem teklifleyebilir", async function () {
      await expect(
        wallet.connect(owner1).submitTransaction(recipient.address, hre.ethers.parseEther("0.1"), "0x")
      ).to.emit(wallet, "SubmitTransaction");
    });

    it("Non-owner işlem teklifleyemez", async function () {
      await expect(
        wallet.connect(nonOwner).submitTransaction(recipient.address, 100, "0x")
      ).to.be.reverted;
    });

    it("İşlem sayısı artar", async function () {
      await wallet.connect(owner1).submitTransaction(recipient.address, 100, "0x");
      expect(await wallet.getTransactionCount()).to.equal(1);
    });
  });

  // ─── CONFIRM TESTLERİ ──────────────────────────────────────────────────────
  describe("confirmTransaction", function () {
    beforeEach(async function () {
      await wallet.connect(owner1).submitTransaction(recipient.address, hre.ethers.parseEther("0.1"), "0x");
    });

    it("Owner onay verebilir", async function () {
      await expect(wallet.connect(owner1).confirmTransaction(0)).to.emit(wallet, "ConfirmTransaction");
    });

    it("Non-owner onay veremez", async function () {
      await expect(wallet.connect(nonOwner).confirmTransaction(0)).to.be.reverted;
    });

    it("Aynı owner iki kez onaylayamaz", async function () {
      await wallet.connect(owner1).confirmTransaction(0);
      await expect(wallet.connect(owner1).confirmTransaction(0)).to.be.reverted;
    });

    it("Var olmayan TX onaylanamaz", async function () {
      await expect(wallet.connect(owner1).confirmTransaction(99)).to.be.reverted;
    });

    it("Onay sayısı doğru artar", async function () {
      await wallet.connect(owner1).confirmTransaction(0);
      await wallet.connect(owner2).confirmTransaction(0);
      const [,,,, numConf] = await wallet.getTransaction(0);
      expect(numConf).to.equal(2);
    });
  });

  // ─── EXECUTE TESTLERİ ──────────────────────────────────────────────────────
  describe("executeTransaction", function () {
    beforeEach(async function () {
      await wallet.connect(owner1).submitTransaction(recipient.address, hre.ethers.parseEther("0.1"), "0x");
      await wallet.connect(owner1).confirmTransaction(0);
      await wallet.connect(owner2).confirmTransaction(0);
    });

    it("Yeterli onay sonrası execute çalışır", async function () {
      await expect(wallet.connect(owner1).executeTransaction(0)).to.emit(wallet, "ExecuteTransaction");
    });

    it("Alıcı parayı alır", async function () {
      const before = await hre.ethers.provider.getBalance(recipient.address);
      await wallet.connect(owner1).executeTransaction(0);
      const after = await hre.ethers.provider.getBalance(recipient.address);
      expect(after - before).to.equal(hre.ethers.parseEther("0.1"));
    });

    it("Aynı TX iki kez execute edilemez", async function () {
      await wallet.connect(owner1).executeTransaction(0);
      await expect(wallet.connect(owner1).executeTransaction(0)).to.be.reverted;
    });

    it("Yetersiz onayla execute edilemez", async function () {
      await wallet.connect(owner1).submitTransaction(recipient.address, 100, "0x");
      await wallet.connect(owner1).confirmTransaction(1);
      await expect(wallet.connect(owner1).executeTransaction(1)).to.be.reverted;
    });
  });

  // ─── REVOKE TESTLERİ ───────────────────────────────────────────────────────
  describe("revokeConfirmation", function () {
    beforeEach(async function () {
      await wallet.connect(owner1).submitTransaction(recipient.address, 100, "0x");
      await wallet.connect(owner1).confirmTransaction(0);
    });

    it("Owner onayını geri çekebilir", async function () {
      await expect(wallet.connect(owner1).revokeConfirmation(0)).to.emit(wallet, "RevokeConfirmation");
    });

    it("Onay vermemiş owner revoke edemez", async function () {
      await expect(wallet.connect(owner2).revokeConfirmation(0)).to.be.reverted;
    });

    it("Revoke sonrası execute edilemez", async function () {
      await wallet.connect(owner2).confirmTransaction(0);
      await wallet.connect(owner1).revokeConfirmation(0);
      await expect(wallet.connect(owner1).executeTransaction(0)).to.be.reverted;
    });
  });

  // ─── GÜVENLİK / SALDIRI SİMÜLASYONU ──────────────────────────────────────
  describe("Security — Attack Simulations", function () {

    it("[Replay Attack] TX0 onayı TX1'i onaylamış saymaz", async function () {
      await wallet.connect(owner1).submitTransaction(recipient.address, 100, "0x");
      await wallet.connect(owner1).submitTransaction(recipient.address, 200, "0x");
      await wallet.connect(owner1).confirmTransaction(0);
      const [,,,, conf1] = await wallet.getTransaction(1);
      expect(conf1).to.equal(0);
    });

    it("[Unauthorized Execute] Non-owner execute edemez", async function () {
      await wallet.connect(owner1).submitTransaction(recipient.address, 100, "0x");
      await wallet.connect(owner1).confirmTransaction(0);
      await wallet.connect(owner2).confirmTransaction(0);
      await expect(wallet.connect(nonOwner).executeTransaction(0)).to.be.reverted;
    });

    it("[Reentrancy Guard] Execute sonrası TX executed=true olur", async function () {
      await wallet.connect(owner1).submitTransaction(recipient.address, hre.ethers.parseEther("0.1"), "0x");
      await wallet.connect(owner1).confirmTransaction(0);
      await wallet.connect(owner2).confirmTransaction(0);
      await wallet.connect(owner1).executeTransaction(0);
      const [,,, executed] = await wallet.getTransaction(0);
      expect(executed).to.equal(true);
    });

    it("[Deposit] ETH gönderilince Deposit eventi yayınlanır", async function () {
      await expect(
        owner1.sendTransaction({ to: await wallet.getAddress(), value: hre.ethers.parseEther("0.5") })
      ).to.emit(wallet, "Deposit");
    });
  });
});
