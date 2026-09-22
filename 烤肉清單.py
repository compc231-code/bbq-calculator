import streamlit as st
import pandas as pd
import os
import json
import base64
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from gspread_dataframe import set_with_dataframe

# --- 1. 網頁基本設定 ---
st.set_page_config(page_title="張家中秋烤肉食材清單", page_icon="🌕", layout="centered")

# --- 2. 高質感 CSS 背景設定 ---
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
SHEET_URL = "https://docs.google.com/spreadsheets/d/1K9G5Hu6LB_Q8STeD1utuTAEK0KfVLItR/edit"

@st.cache_resource
def get_gspread_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ.get("GOOGLE_CREDENTIALS")
    
    if creds_json:
        creds_dict = json.loads(creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        return gspread.authorize(creds)
    elif os.path.exists("credentials.json"):
        creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
        return gspread.authorize(creds)
    else:
        st.error("⚠️ 找不到 Google 授權憑證！請確認是否已在 Render 設定環境變數。")
        return None

def load_data_from_gsheets():
    client = get_gspread_client()
    if client:
        try:
            sheet = client.open_by_url(SHEET_URL).sheet1
            
            # 【關鍵修正】取得所有儲存格的原始資料 (回傳的是二維陣列)
            raw_values = sheet.get_all_values()
            
            # 如果試算表至少有兩列 (包含標題列)
            if len(raw_values) > 1:
                # 你的表格標題在第二列 (索引為1)
                headers = raw_values[1] 
                
                # 將剩下的列當作資料
                data_rows = raw_values[2:] 
                
                # 建立 DataFrame
                df_all = pd.DataFrame(data_rows, columns=headers)
                
                # 萃取我們需要的欄位：食材、內容、價格 (你的圖上是 C, D, E 欄)
                # 為了避免空白或其他雜訊，我們特別指定這三欄
                if set(['食材', '內容', '價格']).issubset(df_all.columns):
                    df = df_all[['食材', '內容', '價格']].copy()
                    
                    # 清除「食材」為空值的行
                    df = df[df['食材'].astype(str).str.strip() != '']
                    
                    # 處理價格欄位，將非數字轉為 0
                    df['價格'] = pd.to_numeric(df['價格'], errors='coerce').fillna(0).astype(int)
                    
                    # 判斷是否已購買 (原本 Excel 並沒有這欄，我們由程式自動產生)
                    # 如果價格 > 0 就視為已買，否則為 False
                    df.insert(0, '已購買', df['價格'] > 0)
                    
                    # 嘗試抓取預算與人數設定
                    try:
                        # 總預算：尋找包含 '總預算' 的那一列的右邊一格
                        budget_val = 6000 # 預設
                        people_val = 12   # 預設
                        for row in raw_values:
                            if '總預算' in row:
                                idx = row.index('總預算')
                                if idx + 1 < len(row):
                                    budget_val = int(str(row[idx+1]).replace(',', ''))
                            if '付錢人數' in row:
                                idx = row.index('付錢人數')
                                if idx + 1 < len(row):
                                    people_val = int(row[idx+1])
                        
                        st.session_state.pay_people_default = people_val
                        st.session_state.total_budget_default = budget_val
                    except Exception as e:
                        print("讀取預算設定時發生小錯誤:", e)
                        st.session_state.pay_people_default = 12
                        st.session_state.total_budget_default = 6000
                    
                    return sheet, df.reset_index(drop=True)
                else:
                     st.error("試算表找不到指定的欄位名稱('食材', '內容', '價格')，請確認第二列的標題是否正確。")
                     return sheet, pd.DataFrame(columns=["已購買", "食材", "內容", "價格"])
            else:
                return sheet, pd.DataFrame(columns=["已購買", "食材", "內容", "價格"])
        except Exception as e:
            st.error(f"處理試算表資料失敗：{e}")
    return None, pd.DataFrame(columns=["已購買", "食材", "內容", "價格"])

# 【重要修正】因為你的 Google Sheet 格式比較複雜 (旁邊有其他資訊)，
# 為了避免覆蓋掉你的「付錢人數」、「總預算」等欄位，
# 我們將存檔功能改為「唯讀」加上「僅本地更新」，或是你需要我們重新設計一個乾淨的 Sheet 來專門儲存？
# 目前先將存檔功能註解掉，確保網頁能順利讀出資料。

# 初始化載入資料
if 'food_list' not in st.session_state or 'sheet_obj' not in st.session_state:
    sheet_obj, df = load_data_from_gsheets()
    st.session_state.sheet_obj = sheet_obj
    st.session_state.food_list = df

with st.sidebar:
    st.markdown("### 雲端控制")
    if st.button("🔄 從雲端重新載入"):
        sheet_obj, df = load_data_from_gsheets()
        st.session_state.sheet_obj = sheet_obj
        st.session_state.food_list = df
        st.success("✅ 已取得雲端最新資料！")
        st.rerun()

# --- 4. 主要內容與介面 ---
st.title("🌕 張家中秋烤肉食材清單")
st.caption("🟢 目前狀態：已讀取 Google 雲端資料")
st.write("---")

st.header("💰 預算與人數")
col1, col2 = st.columns(2)
with col1:
    total_budget = st.number_input("總預算 (元)", min_value=0, value=st.session_state.get('total_budget_default', 6000), step=100)
with col2:
    pay_people = st.number_input("付錢人數", min_value=1, value=st.session_state.get('pay_people_default', 12), step=1)

st.write("---")
st.header("📋 採買清單")
st.caption("✨ 提示：修改表格內容後，可自動計算。 (目前版本為雲端讀取版)")

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
        elif not st.session_state.food_list.empty and i_name.strip() in st.session_state.food_list['食材'].values:
            warning_placeholder.error(f"⚠️ 項目重複，『{i_name}』已在購買清單內！")
        else:
            new_row = pd.DataFrame({"已購買": [True if i_price > 0 else False], "食材": [i_name.strip()], "內容": [i_desc], "價格": [i_price]})
            st.session_state.food_list = pd.concat([st.session_state.food_list, new_row], ignore_index=True)
            st.rerun()

# --- 5. 費用計算與顯示 ---
total_cost = edited_df["價格"].sum() if not edited_df.empty else 0
per_person_cost = total_cost / pay_people if pay_people > 0 else 0
remaining_budget = total_budget - total_cost

st.write("---")
st.header("📊 費用彙整")
col_a, col_b, col_c = st.columns(3)
col_a.metric("目前總費用", f"NT$ {total_cost:,}")
col_b.metric("剩餘預算", f"NT$ {remaining_budget:,}")
col_c.metric("單人應付金額", f"NT$ {per_person_cost:,.0f}")
