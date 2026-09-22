import streamlit as st
import pandas as pd
import os
import base64

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="張家中秋烤肉食材清單", page_icon="🌕", layout="centered")

# --- 2. 注入高質感 CSS ---
BACKGROUND_IMAGE_PATH = "bg.jpg"

def set_background(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as f:
            encoded_string = base64.b64encode(f.read()).decode()
        
        css = f"""
        <style>
        .stApp {{
            background-image: url(data:image/jpeg;base64,{encoded_string});
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
        
        .block-container {{
            background-color: rgba(15, 20, 25, 0.35) !important;
            padding: 1.5rem 1rem !important;
            border-radius: 16px !important;
            box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.7) !important;
            backdrop-filter: blur(8px) !important;
            -webkit-backdrop-filter: blur(8px) !important;
            margin-top: 1.5rem !important;
            margin-bottom: 1.5rem !important;
            border: 1px solid rgba(255, 255, 255, 0.15) !important;
        }}
        
        header {{ background-color: transparent !important; }}
        footer {{ visibility: hidden; }}
        
        h1, h2, h3, p, span, div, label {{
            color: #F0F2F6 !important;
            text-shadow: 1px 1px 4px rgba(0,0,0,0.9) !important;
        }}
        
        button p, button span, button div {{
            color: #1F2937 !important; 
            font-weight: bold !important;
            text-shadow: none !important; 
        }}
        
        input, .stDataFrame {{
            background-color: rgba(255, 255, 255, 0.1) !important;
        }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
    else:
        st.warning("找不到背景圖片 bg.jpg，請確認已將圖片放置於同一個資料夾內。")

set_background(BACKGROUND_IMAGE_PATH)

# --- 3. 讀取 Excel 的功能 ---
FILE_PATH = "烤肉清單.xlsx"

def load_excel_data():
    if os.path.exists(FILE_PATH):
        try:
            df_excel = pd.read_excel(FILE_PATH, sheet_name='工作表1')
            df_items = df_excel[['Unnamed: 2', 'Unnamed: 3', 'Unnamed: 4']].iloc[1:].copy()
            df_items.columns = ['食材', '內容', '價格']
            df_items = df_items.dropna(subset=['食材'])
            df_items['價格'] = pd.to_numeric(df_items['價格'], errors='coerce').fillna(0).astype(int)
            df_items.insert(0, '已購買', df_items['價格'] > 0)
            st.session_state.food_list = df_items.reset_index(drop=True)
            
            try:
                st.session_state.pay_people_default = int(df_excel['Unnamed: 7'].iloc[1])
                st.session_state.total_budget_default = int(df_excel['Unnamed: 7'].iloc[3])
            except:
                st.session_state.pay_people_default = 12
                st.session_state.total_budget_default = 6000
        except Exception as e:
            st.error(f"讀取 Excel 發生錯誤：{e}")
            st.session_state.food_list = pd.DataFrame(columns=["已購買", "食材", "內容", "價格"])
    else:
        st.error(f"找不到檔案：{FILE_PATH}")
        st.session_state.food_list = pd.DataFrame(columns=["已購買", "食材", "內容", "價格"])

if 'food_list' not in st.session_state:
    load_excel_data()

with st.sidebar:
    st.markdown("### 資料控制")
    if st.button("🔄 強制從 Excel 重新載入"):
        load_excel_data()
        st.success("✅ 資料已重新載入！")
        st.rerun()

# --- 4. 主要內容與介面 ---
st.title("🌕 張家中秋烤肉食材清單")
st.write("---")

st.header("💰 預算與人數")
col1, col2 = st.columns(2)
with col1:
    total_budget = st.number_input("總預算 (元)", min_value=0, value=st.session_state.get('total_budget_default', 6000), step=100)
with col2:
    pay_people = st.number_input("付錢人數", min_value=1, value=st.session_state.get('pay_people_default', 12), step=1)

st.write("---")
st.header("📋 採買清單")
st.caption("✨ 提示：可直接在表格內雙擊修改名稱、內容與價格，系統會自動儲存並計算！")

# 確保表格所有欄位都可編輯，並允許動態增減列
edited_df = st.data_editor(
    st.session_state.food_list,
    column_config={
        "已購買": st.column_config.CheckboxColumn("已買?", default=False),
        "食材": st.column_config.TextColumn("食材", required=True),
        "內容": st.column_config.TextColumn("內容"),
        "價格": st.column_config.NumberColumn("價格 (元)", min_value=0, step=10),
    },
    num_rows="dynamic",
    hide_index=True,
    width='stretch',
    key="food_editor"
)
st.session_state.food_list = edited_df

st.write("---")
st.header("🛒 新增額外食材")

warning_placeholder = st.empty()

with st.form("add_item_form", clear_on_submit=True):
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        i_name = st.text_input("食材名稱 (例如: 金針菇)")
    with col_f2:
        i_desc = st.text_input("內容 (例如: 2包)")
    i_price = st.number_input("價格 (元)", min_value=0, value=0, step=10)
    submitted = st.form_submit_button("＋ 加入清單")
    
    if submitted:
        if not i_name.strip():
            warning_placeholder.warning("請輸入食材名稱！")
        elif i_name.strip() in st.session_state.food_list['食材'].values:
            warning_placeholder.error(f"⚠️ 項目重複，『{i_name}』已在購買清單內！")
        else:
            new_row = pd.DataFrame({"已購買": [True if i_price > 0 else False], "食材": [i_name.strip()], "內容": [i_desc], "價格": [i_price]})
            st.session_state.food_list = pd.concat([st.session_state.food_list, new_row], ignore_index=True)
            st.rerun()

# --- 5. 費用計算與顯示 ---
total_cost = st.session_state.food_list["價格"].sum() if not st.session_state.food_list.empty else 0
per_person_cost = total_cost / pay_people if pay_people > 0 else 0
remaining_budget = total_budget - total_cost

st.write("---")
st.header("📊 費用彙整")
col_a, col_b, col_c = st.columns(3)
col_a.metric("目前總費用", f"NT$ {total_cost:,}")
col_b.metric("剩餘預算", f"NT$ {remaining_budget:,}")
col_c.metric("單人應付金額", f"NT$ {per_person_cost:,.0f}")
