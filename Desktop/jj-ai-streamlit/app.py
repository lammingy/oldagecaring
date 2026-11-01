import base64
import datetime
import os
import requests
import streamlit as st
import pytz
from openai import OpenAI
from pypdf import PdfReader

# -----------------------------------------------------------------------------
# 0. 讀取背景照片並轉為 Base64
# -----------------------------------------------------------------------------
def get_base64_image(image_path):
    if os.path.exists(image_path):
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode("utf-8")
    return ""

bg_img_base64 = get_base64_image("student_photo.jpg")

# -----------------------------------------------------------------------------
# 1. 頁面設定與亮色玻璃擬態樣式 (Light Glassmorphic UI)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="JJ AI",
    page_icon="✨",
    layout="wide",
    initial_sidebar_state="expanded"
)

LIGHT_GLASS_CSS_TEMPLATE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', "Microsoft JhengHei", sans-serif;
}

/* 亮色漸層背景與動態浮動光暈 */
.stApp {
    background: linear-gradient(135deg, #63cfff, #8a7cff, #c896ff);
    background-attachment: fixed;
    color: #1e293b;
}

/* 動態發光背景光暈特效 */
.stApp::before {
    content: "";
    position: fixed;
    width: 500px;
    height: 500px;
    background: radial-gradient(circle, rgba(255,255,255,0.4), transparent 70%);
    top: -150px;
    left: -100px;
    animation: floatGlow 12s ease-in-out infinite;
    z-index: 0;
    pointer-events: none;
}

@keyframes floatGlow {
    0% { transform: translate(0, 0) scale(1); }
    50% { transform: translate(120px, 80px) scale(1.1); }
    100% { transform: translate(0, 0) scale(1); }
}

/* 側邊欄樣式 - 半透明毛玻璃 */
[data-testid="stSidebar"] {
    background: rgba(255, 255, 255, 0.75) !important;
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-right: 1px solid rgba(255, 255, 255, 0.4);
}

/* 側邊欄標題與文字強制改為黑色 */
[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] [data-testid="stFileUploader"] label p {
    color: #000000 !important;
    font-weight: 600;
}

[data-testid="stSidebar"] .stButton > button {
    background: linear-gradient(135deg, #8d63ff, #4c9fff);
    color: white;
    border: none;
    border-radius: 15px;
    font-weight: 600;
    padding: 10px 18px;
    transition: all 0.2s ease-in-out;
}

[data-testid="stSidebar"] .stButton > button:hover {
    opacity: 0.9;
    transform: scale(1.03);
}

/* 主標題卡片 (使用 Base64 編碼的 student_photo.jpg 作為背景) */
.glass-header {
    background-image: linear-gradient(rgba(15, 23, 42, 0.65), rgba(15, 23, 42, 0.65)), url('data:image/jpeg;base64,BG_IMG_PLACEHOLDER');
    background-size: cover;
    background-position: center;
    backdrop-filter: blur(25px);
    -webkit-backdrop-filter: blur(25px);
    border: 1px solid rgba(255, 255, 255, 0.6);
    border-radius: 25px;
    padding: 35px;
    margin-bottom: 25px;
    text-align: center;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.18);
    position: relative;
    z-index: 1;
}

.glass-header h1 {
    color: #ffffff;
    font-size: 42px;
    font-weight: 900;
    letter-spacing: 6px;
    margin: 0;
    text-shadow: 0 0 15px rgba(255, 255, 255, 0.8), 0 0 30px #7ed7ff;
}

.glass-header p {
    color: #e2e8f0;
    margin-top: 8px;
    font-size: 13px;
    letter-spacing: 2px;
    font-weight: 600;
}

/* 對話訊息容器 */
[data-testid="stChatMessage"] {
    background: transparent !important;
    padding: 8px 0 !important;
    position: relative;
    z-index: 1;
}

/* 用戶訊息泡泡 */
div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]) {
    flex-direction: row-reverse;
}

div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-user"]) [data-testid="stChatMessageContent"] {
    background: #4c9fff !important;
    color: #ffffff !important;
    border-radius: 22px !important;
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08);
    max-width: 75%;
    margin-left: auto;
}

/* AI 訊息泡泡 */
div[data-testid="stChatMessage"]:has(div[data-testid="chatAvatarIcon-assistant"]) [data-testid="stChatMessageContent"] {
    background: #ffffff !important;
    border-radius: 22px !important;
    color: #1e293b !important;
    box-shadow: 0 5px 15px rgba(0, 0, 0, 0.08);
    max-width: 75%;
}

/* 浮動輸入列 (深色半透明毛玻璃背景 + 白色輸入字體) */
[data-testid="stChatInput"] {
    border-radius: 18px !important;
    background: rgba(15, 23, 42, 0.75) !important;
    backdrop-filter: blur(20px) !important;
    border: 1px solid rgba(255, 255, 255, 0.2) !important;
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.2) !important;
    position: relative;
    z-index: 1;
}

[data-testid="stChatInput"] textarea {
    color: #ffffff !important;
}

[data-testid="stChatInput"] textarea::placeholder {
    color: rgba(255, 255, 255, 0.6) !important;
}

/* 捲軸美化 */
::-webkit-scrollbar {
    width: 6px;
    height: 6px;
}
::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.05);
}
::-webkit-scrollbar-thumb {
    background: rgba(141, 99, 255, 0.3);
    border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
    background: rgba(141, 99, 255, 0.6);
}
</style>
"""

LIGHT_GLASS_CSS = LIGHT_GLASS_CSS_TEMPLATE.replace("BG_IMG_PLACEHOLDER", bg_img_base64)
st.markdown(LIGHT_GLASS_CSS, unsafe_allow_html=True)


# -----------------------------------------------------------------------------
# 2. API 與香港即時數據輔助函數
# -----------------------------------------------------------------------------
OPENROUTER_API_KEY = st.secrets.get("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY", "")
MODEL_NAME = "nvidia/nemotron-3.5-lightning:free"

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

def get_hong_kong_time_info() -> str:
    hk_tz = pytz.timezone("Asia/Hong_Kong")
    now = datetime.datetime.now(hk_tz)
    weekday_cn = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"][now.weekday()]
    return f"目前香港當地時間：{now.strftime('%Y年%m月%d日 %H:%M:%S')} ({weekday_cn})"

def get_hong_kong_weather() -> str:
    try:
        url = "https://data.weather.gov.hk/weatherAPI/opendata/weather.php?dataType=rhrread&lang=tc"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            temp = data.get("temperature", {}).get("data", [{}])[0].get("value", "未知")
            humidity = data.get("humidity", {}).get("data", [{}])[0].get("value", "未知")
            warning_msg = ""
            warnings = data.get("warningMessage", [])
            if warnings:
                warning_msg = f"（警告信號：{' '.join(warnings)}）"
            return f"香港即時氣溫：{temp}°C，相對濕度：{humidity}%。{warning_msg}"
    except Exception as e:
        return "暫時無法獲取香港即時天氣資訊。"
    return "暫時無法獲取香港即時天氣資訊。"

def check_and_append_hk_context(prompt: str) -> str:
    context_additions = []
    time_keywords = ["幾點", "時間", "日期", "今天幾號", "今日幾號", "星期幾", "禮拜幾", "date", "time"]
    if any(kw in prompt.lower() for kw in time_keywords):
        context_additions.append(get_hong_kong_time_info())

    weather_keywords = ["天氣", "氣溫", "幾度", "落雨", "下雨", "颱風", "風球", "weather", "temperature"]
    if any(kw in prompt.lower() for kw in weather_keywords):
        context_additions.append(get_hong_kong_weather())

    if context_additions:
        context_str = "\n".join(context_additions)
        return f"\n\n[系統即時數據提示 (Hong Kong Local Context)]:\n{context_str}\n請依據以上真實資訊精準回答用戶。"
    return ""

SYSTEM_PROMPT = """
你叫 JJ AI。
請永遠使用繁體中文回覆。
使用香港常用用語。
保持專業、友善和有禮貌。
若系統提示中包含香港當地即時時間或天氣數據，請直接據此準確回答用戶。
"""

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "👋 你好！我是 JJ AI。請問有什麼可以幫到你？"}
    ]

# -----------------------------------------------------------------------------
# 3. 介面佈局 (Sidebar & Header)
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### 💬 控制台")
    st.markdown("---")
    
    if st.button("➕ 開啟新對話", use_container_width=True):
        st.session_state.messages = [
            {"role": "assistant", "content": "👋 你好！我是 JJ AI。請問有什麼可以幫到你？"}
        ]
        st.rerun()

    st.markdown("---")
    st.markdown("### 📎 檔案上傳")
    uploaded_file = st.file_uploader("上傳 PDF 或圖片", type=["pdf", "png", "jpg", "jpeg"])
    if uploaded_file:
        st.success(f"已載入: {uploaded_file.name}")

# 頂部標題（帶有背景照片）
st.markdown("""
<div class="glass-header">
    <h1>JJ AI</h1>
    <p>Next Generation AI Assistant</p>
</div>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 4. 對話記錄與多模態訊息處理
# -----------------------------------------------------------------------------
for message in st.session_state.messages:
    avatar = "🤖" if message["role"] == "assistant" else "👤"
    with st.chat_message(message["role"], avatar=avatar):
        st.write(message["content"])
        if "image_data" in message and message["image_data"]:
            st.image(base64.b64decode(message["image_data"]), caption="上傳的圖片", width=300)

if prompt := st.chat_input("輸入訊息..."):
    file_context_text = ""
    image_payload = None

    if uploaded_file:
        if uploaded_file.type == "application/pdf":
            try:
                reader = PdfReader(uploaded_file)
                pdf_text = "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])
                file_context_text = f"\n\n[用戶上傳的 PDF 檔案內容 ({uploaded_file.name})]:\n{pdf_text}"
            except Exception as e:
                file_context_text = f"\n\n[系統通知]: 無法解析上傳的 PDF 檔案: {str(e)}"
        elif uploaded_file.type.startswith("image/"):
            bytes_data = uploaded_file.getvalue()
            encoded_img = base64.b64encode(bytes_data).decode("utf-8")
            image_payload = encoded_img
            file_context_text = f"\n\n[用戶上傳了一張圖片: {uploaded_file.name}]"

    full_user_display_text = prompt + (f"\n*(已附加檔案: {uploaded_file.name})*" if uploaded_file else "")

    with st.chat_message("user", avatar="👤"):
        st.write(full_user_display_text)
        if image_payload:
            st.image(base64.b64decode(image_payload), caption=uploaded_file.name, width=300)

    msg_record = {"role": "user", "content": full_user_display_text}
    if image_payload:
        msg_record["image_data"] = image_payload
    st.session_state.messages.append(msg_record)

    context_addon = check_and_append_hk_context(prompt)

    api_messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    for idx, msg in enumerate(st.session_state.messages):
        if idx == len(st.session_state.messages) - 1 and msg["role"] == "user":
            content_content = prompt + file_context_text + context_addon
            if "image_data" in msg and msg["image_data"]:
                api_messages.append({
                    "role": "user",
                    "content": [
                        {"type": "text", "text": content_content},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{msg['image_data']}"}}
                    ]
                })
            else:
                api_messages.append({"role": "user", "content": content_content})
        else:
            api_messages.append({"role": msg["role"], "content": msg["content"]})

    with st.chat_message("assistant", avatar="🤖"):
        message_placeholder = st.empty()
        full_response = ""

        try:
            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=api_messages,
                stream=True
            )
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
                    message_placeholder.markdown(full_response + "▌")
            
            message_placeholder.markdown(full_response)
            st.session_state.messages.append({"role": "assistant", "content": full_response})
            
        except Exception as e:
            error_msg = f"⚠️ 連線失敗或模型繁忙: {str(e)}"
            message_placeholder.markdown(error_msg)
            st.session_state.messages.append({"role": "assistant", "content": error_msg})