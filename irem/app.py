import streamlit as st
import pandas as pd
import plotly.express as px
from fpdf import FPDF
from datetime import datetime
import time

# ── 1. SESSION STATE BAŞLANGICI ──
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "active_key" not in st.session_state:
    st.session_state.active_key = None
if "logs" not in st.session_state:
    st.session_state.logs = []
if "last_tx_link" not in st.session_state:
    st.session_state.last_tx_link = None

# ── 2. GİRİŞ EKRANI ──
if not st.session_state.logged_in:
    st.title("🔐 Web3 MultiSig Wallet Access Portal")
    st.subheader("Please connect your credentials to access the enterprise dashboard")

    with st.form("login_form"):
        user_private_key = st.text_input("Enter Your Private Key:", type="password")
        user_contract_address = st.text_input(
            "Enter MultiSig Contract Address:",
            placeholder="0x...",
        )
        submit_login = st.form_submit_button("Connect Wallet & Contract")

        if submit_login:
            if user_private_key and user_contract_address:
                try:
                    from web3 import Web3
                    from backend import wallet_service as _ws

                    # Girilen key ve kontrat adresiyle servisi güncelle
                    _ws.account = _ws.w3.eth.account.from_key(user_private_key)
                    _ws.contract = _ws.w3.eth.contract(
                        address=Web3.to_checksum_address(user_contract_address),
                        abi=_ws.abi,
                    )

                    # Bağlantıyı test et
                    _ws.get_wallet_stats()

                    st.session_state.logged_in = True
                    st.session_state.active_key = user_private_key
                    st.session_state.logs.append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] Sepolia testnet bağlantısı kuruldu."
                    )
                    st.success("Bağlantı başarılı!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Bağlantı hatası: {e}")
            else:
                st.warning("Lütfen tüm alanları doldurun.")
    st.stop()

# ── 3. LOGIN SONRASI: GERÇEK MODÜLLER ──
from backend import wallet_service as ws

active_key = st.session_state.active_key

# ── 4. PDF Oluşturucu ──
def generate_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt="MultiSig Wallet - Transaction Report", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    for _, row in data.iterrows():
        txt = f"ID: {row['id']} | Recipient: {row['recipient']} | Amount: {row['amount_eth']} ETH"
        pdf.cell(0, 10, txt=txt, ln=True)
    return bytes(pdf.output())

# ── 5. KONTRAT VERİSİ ──
try:
    stats = ws.get_wallet_stats()
except Exception as e:
    st.error(f"Kontrat verisi alınamadı: {e}")
    st.stop()

try:
    pending_txs_list = ws.get_pending_transactions()
except Exception:
    pending_txs_list = []

pending_txs_df = pd.DataFrame(pending_txs_list)

# ── 6. SIDEBAR ──
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/7032/7032314.png", width=100)
    st.title("Wallet Identity")
    st.info(f"**Owners:**\n" + "\n".join(stats["owner_addresses"]))
    st.warning(f"**Threshold:** {stats['threshold']} of {stats['total_owners']}")
    st.divider()

    active_address = ws.get_active_address(active_key)
    st.subheader("Aktif Hesap")
    st.success(f"`{active_address[:10]}...{active_address[-6:]}`")
    if st.button("Çıkış Yap"):
        st.session_state.logged_in = False
        st.session_state.active_key = None
        st.rerun()

    st.divider()
    st.subheader("Reports")
    try:
        if not pending_txs_df.empty:
            pdf_file = generate_pdf(pending_txs_df)
            st.download_button(
                label="📥 Download Pending (PDF)",
                data=pdf_file,
                file_name="wallet_report.pdf",
                mime="application/pdf",
            )
        else:
            st.caption("No pending data available for PDF generation.")
    except Exception as e:
        st.error(f"PDF Error: {e}")

# ── 7. DASHBOARD METRİKLERİ ──
st.title("🛡️ MultiSig Enterprise Dashboard")

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Total Balance", f"{stats['balance_eth']} ETH")
with c2:
    st.metric("Pending Actions", str(len(pending_txs_df)))
with c3:
    st.metric("Total Owners", str(stats["total_owners"]))

st.divider()

# ── 8. SEKMELER ──
tab1, tab2, tab3 = st.tabs(["⏳ Pending Approvals", "📜 Transaction History", "🧪 QA Test Suite"])

with tab1:
    col_left, col_right = st.columns([2, 1])
    with col_left:
        if pending_txs_df.empty:
            st.info("🎉 Excellent! There are no pending transaction proposals.")
        else:
            st.dataframe(pending_txs_df, use_container_width=True)
    with col_right:
        st.subheader("Approval Status")
        if pending_txs_list:
            confirmed_count = sum(
                1 for tx in pending_txs_list
                if tx["current_confirmations"] >= stats["threshold"]
            )
            waiting_count = len(pending_txs_list) - confirmed_count
            df_chart = pd.DataFrame({
                "Status": ["Ready to Execute", "Awaiting Confirmations"],
                "Value": [confirmed_count, waiting_count],
            })
            fig = px.pie(df_chart, values="Value", names="Status", hole=0.4)
            fig.update_layout(showlegend=False, height=220, margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.caption("No pending transactions.")

with tab2:
    st.subheader("Past Executions")
    st.info("Executed transactions can be tracked in real-time on Etherscan.")
    st.markdown(
        f"[🔗 Kontrat işlemlerini Etherscan'da gör](https://sepolia.etherscan.io/address/{stats['contract_address']})"
    )

with tab3:
    st.subheader("Manual Error Simulation")
    col_test1, col_test2 = st.columns(2)
    with col_test1:
        if st.button("Simulate 'Unauthorized User' Error", use_container_width=True):
            st.error("Contract Error: Caller is not an owner of this multisig wallet.")
        if st.button("Simulate 'Insufficient Funds' Error", use_container_width=True):
            st.warning("Contract Warning: Wallet balance is lower than the requested transfer amount.")
    with col_test2:
        if st.button("Simulate 'Already Executed' Error", use_container_width=True):
            st.error("Contract Error: This transaction ID has already been fully processed.")

# ── 9. ACTION CENTER ──
st.divider()
st.subheader("✍️ Action Center")
action_col1, action_col2 = st.columns(2)

with action_col1:
    st.write("### Handle Pending Transaction")
    if pending_txs_df.empty:
        st.caption("No pending transactions to manage.")
    else:
        selected_id = st.selectbox("Select ID to Action:", pending_txs_df["id"].tolist())
        tx_row = pending_txs_df[pending_txs_df["id"] == selected_id].iloc[0]
        already_confirmed = ws.get_confirmation_status(selected_id, active_address)

        btn_confirm, btn_execute = st.columns(2)

        with btn_confirm:
            if st.button("Confirm Approval", width="stretch", disabled=already_confirmed):
                res = ws.approve_transaction(selected_id, private_key=active_key)
                if res["status"] == "success":
                    st.session_state.last_tx_link = f"https://sepolia.etherscan.io/tx/{res['tx_hash']}"
                    st.session_state.logs.append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] Approved ID {selected_id}. Hash: {res['tx_hash'][:10]}..."
                    )
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Error: {res['message']}")

        with btn_execute:
            current_conf = int(tx_row["current_confirmations"])
            required_conf = int(stats["threshold"])

            if stats["balance_eth"] == 0:
                st.error("Balance is 0 ETH! Execution is locked.")
                st.button("Execute", width="stretch", disabled=True, key="bal_lock")
            elif current_conf < required_conf:
                st.warning(f"Insufficient Confirmations! ({current_conf}/{required_conf} approved)")
                st.button("Execute Transaction", width="stretch", disabled=True, key="conf_lock")
            else:
                if st.button("Execute Transaction", width="stretch"):
                    res = ws.execute_transaction(selected_id, private_key=active_key)
                    if res["status"] == "success":
                        st.session_state.last_tx_link = f"https://sepolia.etherscan.io/tx/{res['tx_hash']}"
                        st.session_state.logs.append(
                            f"[{datetime.now().strftime('%H:%M:%S')}] Executed ID {selected_id}. Hash: {res['tx_hash'][:10]}..."
                        )
                        st.balloons()
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"Error: {res['message']}")

with action_col2:
    with st.expander("➕ Propose New Transfer"):
        rec = st.text_input("Recipient Address")
        amt = st.number_input("Amount (ETH)", min_value=0.0, step=0.001, format="%.3f")
        if st.button("Submit to Owners", width="stretch"):
            if rec:
                res = ws.submit_transaction(rec, amt, private_key=active_key)
                if res["status"] == "success":
                    st.session_state.last_tx_link = f"https://sepolia.etherscan.io/tx/{res['tx_hash']}"
                    st.session_state.logs.append(
                        f"[{datetime.now().strftime('%H:%M:%S')}] New proposal created. ID: {res['tx_index']}"
                    )
                    st.balloons()
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error(f"Error: {res['message']}")
            else:
                st.warning("Please enter a valid recipient address.")

# ── 10. SON İŞLEM LİNKİ ──
if st.session_state.last_tx_link:
    st.divider()
    st.success("🎉 Transaction successfully broadcasted to the blockchain network!")
    st.markdown(f"🔗 **[View Last Operation on Etherscan]({st.session_state.last_tx_link})**")
    st.caption("Not: İşlem Sepolia testnet üzerinde yayınlandı. Onaylanması ~15 saniye sürebilir.")

# ── 11. CANLI LOG ──
st.divider()
st.caption("📜 Live System Logs")
log_content = "\n".join(st.session_state.logs[-5:])
st.code(log_content, language="bash")
