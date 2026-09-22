import streamlit as st
import pandas as pd
import os
import json
import base64
import gspread
import traceback
from oauth2client.service_account import ServiceAccountCredentials
from gspread_dataframe import set_with_dataframe

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
        .stApp {{ background-image: url(data:image/jpeg;base64,{encoded_string}); background-size: cover; background-position: center; background-attachment: fixed; }}
        .block-container {{ background-color: rgba(15, 20, 25, 0.35) !important; padding: 1.5rem 1rem !important; border-radius: 16px !important; box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.7) !important; backdrop-filter: blur(8px) !important; -webkit-backdrop-filter: blur(8px) !important; margin-top: 1.5rem !important; margin-bottom: 1.5rem !important; border: 1px solid rgba(255, 255, 255, 0.15) !important; }}
        header {{ background-color: transparent !important; }} footer {{ visibility: hidden; }}
        h1, h2, h3, p, span, div, label {{ color: #F0F2F6 !important; text-shadow: 1px 1px 4px rgba(0,0,0,0.9) !important; }}
        button p, button span, button div {{ color: #1F2937 !important; font-weight: bold !important; text-shadow: none !important; }}
        input, .stDataFrame {{ background-color: rgba(255, 255, 255, 0.1) !important; }}
        </style>
        """
        st.markdown(css, unsafe_allow_html=True)
    else:
        st.warning("找不到背景圖片 bg.jpg。")

set_background(BACKGROUND_IMAGE_PATH)

# --- 3. Google Sheets 連線設定 ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/169HMnMNeiz-IDv-e8FgizB7RV4fEX9TkP-Ax6EyMew8/edit"
SHEET_GID = 0

@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    
    try:
        if creds_json:
            creds_dict = json.loads(creds_json)
            creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
            return gspread.authorize(creds)
        elif os.path.exists("credentials.json"):
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            return gspread.authorize(creds)
        else:
            st.error("⚠️ 找不到 Google 授權憑證！請確認是否有設定環境變數或存在 credentials.json 檔案。")
            return None
    except Exception as e:
        error_details = traceback.format_exc()
        st.error(f"讀取金鑰時發生錯誤：{type(e).__name__} - {str(e)}")
        st.error(f"詳細錯誤：\n```\n{error_details}\n```")
        return None

def load_data_from_gsheets():
    client = get_gspread_client()
    if client:
        try:
            spreadsheet = client.open_by_url(SHEET_URL)
            sheet = spreadsheet.get_worksheet_by_id(SHEET_GID)
            raw_values = sheet.get_all_values()
            
            if not raw_values:
                return sheet, pd.DataFrame(columns=["已購買", "食材", "內容", "價格"])

            header_idx = -1
            for i, row in enumerate(raw_values):
                if '食材' in row and '價格' in row:
                    header_idx = i
                    break
            
            if header_idx != -1:
                headers = raw_values[header_idx]
                idx_buy = headers.index('已購買') if '已購買' in headers else -1
                idx_name = headers.index('食材')
                idx_desc = headers.index('內容') if '內容' in headers else -1
                idx_price = headers.index('價格')
                
                extracted_data = []
                for r in raw_values[header_idx + 1:]:
                    buy_val = r[idx_buy] if idx_buy != -1 and idx_buy < len(r) else ""
                    name_val = r[idx_name] if idx_name < len(r) else ""
                    desc_val = r[idx_desc] if idx_desc != -1 and idx_desc < len(r) else ""
                    price_val = r[idx_price] if idx_price < len(r) else "0"
                    extracted_data.append([buy_val, name_val, desc_val, price_val])
                
                df = pd.DataFrame(extracted_data, columns=["已購買", "食材", "內容", "價格"])
                df = df[df['食材'].astype(str).str.strip() != '']
                
                df['已購買'] = df['已購買'].astype(str).str.upper().map({'TRUE': True, 'FALSE': False, '1': True, '0': False}).fillna(False)
                df['價格'] = df['價格'].astype(str).str.replace(',', '', regex=False)
                df['價格'] = pd.to_numeric(df['價格'], errors='coerce').fillna(0).astype(int)
                
                budget_val, people_val = 6000, 12
                for row in raw_values:
                    if '總預算' in row:
                        idx = row.index('總預算')
                        if idx + 1 < len(row):
                            val = str(row[idx+1]).replace(',', '').strip()
                            if val.isdigit(): budget_val = int(val)
                    if '付錢人數' in row:
                        idx = row.index('付錢人數')
                        if idx + 1 < len(row):
                            val = str(row[idx+1]).replace(',', '').strip()
                            if val.isdigit(): people_val = int(val)
                
                st.session_state.pay_people_default = people_val
                st.session_state.total_budget_default = budget_val
                
                return sheet, df.reset_index(drop=True)
            else:
                return sheet, pd.DataFrame(columns=["已購買", "食材", "內容", "價格"])
        except Exception as e:
            error_details = traceback.format_exc()
            st.error(f"讀取雲端資料失敗：{type(e).__name__} - {str(e)}")
            st.error(f"詳細錯誤訊息：\n```\n{error_details}\n```")
    return None, pd.DataFrame(columns=["已購買", "食材", "內容", "價格"])

def save_data_to_gsheets(sheet, df):
    try:
        sheet.batch_clear(["A:D"])
        set_with_dataframe(sheet, df, row=1, col=1, include_index=False, include_column_header=True)
        return True
    except Exception as e:
        error_details = traceback.format_exc()
        st.error(f"寫入雲端時發生錯誤：{type(e).__name__} - {str(e)}")
        st.error(f"詳細錯誤訊息：\n```\n{error_details}\n```")
        return False

# --- 4. 主要內容與介面區塊 ---
if 'food_list' not in st.session_state or 'sheet_obj' not in st.session_state:
    sheet_obj, df = load_data_from_gsheets()
    st.session_state.sheet_obj = sheet_obj
    st.session_state.food_list = df

with st.sidebar:
    st.markdown("### 雲端同步控制")
    if st.button("🔄 從雲端重新讀取"):
        st.cache_resource.clear()
        sheet_obj, df = load_data_from_gsheets()
        st.session_state.sheet_obj = sheet_obj
        st.session_state.food_list = df
        st.success("✅ 已重新讀取雲端最新狀態！")
        st.rerun()

st.title("🌕 嘉嘉老師的中秋烤肉食材清單")
st.caption("🟢 目前狀態：【雙向同步啟動】已連線至 Google 雲端")
st.write("---")

st.header("💰 預算與人數")
col1, col2 = st.columns(2)
with col1:
    total_budget = st.number_input("總預算 (元)", min_value=0, value=st.session_state.get('total_budget_default', 6000), step=100)
with col2:
    pay_people = st.number_input("付錢人數", min_value=1, value=st.session_state.get('pay_people_default', 12), step=1)

st.write("---")
st.header("📋 採買清單")
st.caption("✨ 提示：修改數量、價格或打勾後，請務必點擊下方按鈕存檔。")

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

if st.button("☁️ 儲存修改並同步至雲端", type="primary"):
    if st.session_state.sheet_obj:
        is_saved = save_data_to_gsheets(st.session_state.sheet_obj, edited_df)
        if is_saved:
            st.session_state.food_list = edited_df
            st.success("✅ 修改已成功寫回 Google 試算表！")
    else:
        st.error("❌ 找不到試算表物件，無法存檔。")

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
        elif not st.session_state.food_list.empty and i_name.strip() in st.session_state.food_list['食材'].values:
            warning_placeholder.error(f"⚠️ 項目重複，『{i_name}』已在購買清單內！")
        else:
            new_row = pd.DataFrame({"已購買": [True if i_price > 0 else False], "食材": [i_name.strip()], "內容": [i_desc], "價格": [i_price]})
            updated_df = pd.concat([st.session_state.food_list, new_row], ignore_index=True)
            st.session_state.food_list = updated_df
            if st.session_state.sheet_obj:
                save_data_to_gsheets(st.session_state.sheet_obj, updated_df)
            st.rerun()

total_cost = edited_df["價格"].sum() if not edited_df.empty else 0
per_person_cost = total_cost / pay_people if pay_people > 0 else 0
remaining_budget = total_budget - total_cost

st.write("---")
st.header("📊 費用彙整")
col_a, col_b, col_c = st.columns(3)
col_a.metric("目前總費用", f"NT$ {total_cost:,}")
col_b.metric("剩餘預算", f"NT$ {remaining_budget:,}")
col_c.metric("單人應付金額", f"NT$ {per_person_cost:,.0f}")
