import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import time
from fpdf import FPDF 

# 1. Sayfa Ayarları
st.set_page_config(page_title="MultiSig Wallet Pro", layout="wide", page_icon="🛡️")

# 2. Log Sistemi Başlatma
if "logs" not in st.session_state:
    st.session_state.logs = [f"[{datetime.now().strftime('%H:%M:%S')}] Connection to Hardhat established."]

# 3. PDF Oluşturma Fonksiyonu (Hatalardan Arındırılmış)
def generate_pdf(data):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="MultiSig Wallet - Transaction Report", ln=True, align='C')
    pdf.ln(10)
    pdf.set_font("Arial", size=12)
    for index, row in data.iterrows():
        # Emojileri PDF'den temizledik (Latin-1 hatasını engellemek için)
        clean_result = str(row['Result']).replace("✅ ", "")
        txt = f"ID: {row['ID']} | Recipient: {row['Recipient']} | Amount: {row['Amount']} | Result: {clean_result}"
        pdf.cell(0, 10, txt=txt, ln=True)
    return pdf.output(dest='S').encode('latin-1')

# 4. Sahte Veri Fonksiyonları
def get_wallet_stats():
    return {"balance": "1.25 ETH", "threshold": "2 / 3", "owners": "Irem, Merve, Emine"}

def get_pending_txs():
    return pd.DataFrame({
        "ID": [101, 102],
        "Recipient": ["0x71C...3a", "0xAA1...9b"],
        "Amount": ["0.5 ETH", "1.0 ETH"],
        "Status": ["1/2 Signs", "0/2 Signs"]
    })

def get_history_txs():
    return pd.DataFrame({
        "ID": [98, 99, 100],
        "Recipient": ["0x321...ff", "0x555...aa", "0x999...cc"],
        "Amount": ["2.1 ETH", "0.2 ETH", "1.5 ETH"],
        "Result": ["✅ Success", "✅ Success", "✅ Success"]
    })

# 5. Yan Menü (Sidebar)
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/7032/7032314.png", width=100)
    st.title("Wallet Identity")
    stats = get_wallet_stats()
    st.info(f"**Owners:** \n{stats['owners']}")
    st.warning(f"**Threshold:** {stats['threshold']}")
    st.divider()
    
    st.subheader("Reports")
    history_data = get_history_txs()
    
    # PDF Butonu Denemesi
    try:
        pdf_file = generate_pdf(history_data)
        st.download_button(
            label="📥 Download History (PDF)", 
            data=pdf_file, 
            file_name="wallet_report.pdf", 
            mime="application/pdf"
        )
    except Exception as e:
        st.error(f"PDF Error: {e}")

# 6. Ana Dashboard
st.title("🛡️ MultiSig Enterprise Dashboard")

c1, c2, c3 = st.columns(3)
with c1: st.metric("Total Balance", stats['balance'])
with c2: st.metric("Pending Actions", "2")
with c3: st.metric("Total Executed", "15")

st.divider()

# 7. Sekmeler (Tabs)
tab1, tab2, tab3 = st.tabs(["⏳ Pending Approvals", "📜 Transaction History", "🧪 QA Test Suite"])

with tab1:
    col_left, col_right = st.columns([2, 1])
    with col_left:
        st.table(get_pending_txs())
    with col_right:
        st.subheader("Expense Split")
        df_chart = pd.DataFrame({"Cat": ["Dev", "Ops", "Marketing"], "Val": [70, 20, 10]})
        fig = px.pie(df_chart, values='Val', names='Cat', hole=.4)
        fig.update_layout(showlegend=False, height=220, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig, width='stretch')

with tab2:
    st.subheader("Past Executions")
    st.dataframe(get_history_txs(), width='stretch')

with tab3:
    st.subheader("Manual Error Simulation")
    st.write("Use these buttons to test how the UI handles contract errors.")
    col_test1, col_test2 = st.columns(2)
    with col_test1:
        if st.button("Simulate 'Unauthorized User' Error", width='stretch'):
            st.error("Error: Caller is not an owner of this wallet.")
            st.session_state.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] Failed Security Test: Unauthorized access attempt.")
        if st.button("Simulate 'Insufficient Funds' Error", width='stretch'):
            st.warning("Warning: Contract balance is lower than the requested amount.")
    with col_test2:
        if st.button("Simulate 'Already Executed' Error", width='stretch'):
            st.error("Error: This transaction has already been processed.")
        if st.button("Simulate 'Gas Limit' Warning", width='stretch'):
            st.info("Info: Transaction might fail due to low gas limit settings.")

# 8. İşlem Merkezi (Action Center)
st.divider()
st.subheader("✍️ Action Center")
action_col1, action_col2 = st.columns(2)

with action_col1:
    selected_id = st.selectbox("Select ID to approve:", [101, 102])
    if st.button("Confirm Approval", width='stretch'):
        new_log = f"[{datetime.now().strftime('%H:%M:%S')}] Transaction {selected_id} approved by Irem."
        st.session_state.logs.append(new_log)
        for _ in range(3):
            st.balloons()
            time.sleep(0.1)
        st.success(f"Approval registered for ID {selected_id}")

with action_col2:
    with st.expander("➕ Propose New Transfer"):
        rec = st.text_input("Recipient Address")
        amt = st.number_input("Amount", min_value=0.0)
        if st.button("Submit to Owners"):
            new_log = f"[{datetime.now().strftime('%H:%M:%S')}] New proposal created for {amt} ETH."
            st.session_state.logs.append(new_log)
            for _ in range(3):
                st.balloons()
                time.sleep(0.1)
            st.info("Proposal submitted!")

# 9. Canlı Loglar
st.divider()
st.caption("📜 Live System Logs")
log_content = "\n".join(st.session_state.logs[-5:])
st.code(log_content, language="bash")