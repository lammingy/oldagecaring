"""
語音指令式家庭生活便利 Bot (Voice-Controlled Daily Info Panel)
==============================================================
專為患有眼疾或低視能長者設計的高對比度、極簡粵語語音互動生活助手。
升級版：採用微軟極致自然真人級粵語語音 (edge-tts) + 本地 DeepSeek-R1 智慧大腦。

Required Pip Packages:
    pip install streamlit SpeechRecognition ollama edge-tts
"""

import datetime
import io
import json
import asyncio
import urllib.request
import streamlit as st
import ollama

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

try:
    import edge_tts
    EDGE_TTS_AVAILABLE = True
except ImportError:
    EDGE_TTS_AVAILABLE = False


# ==============================================================================
# 1. PAGE CONFIGURATION & SESSION STATE INITIALIZATION
# ==============================================================================
st.set_page_config(
    page_title="長者AI生活伴侶",
    page_icon="🎙️",
    layout="centered",
    initial_sidebar_state="collapsed",
)

if "user_query" not in st.session_state:
    st.session_state.user_query = ""
if "bot_response" not in st.session_state:
    st.session_state.bot_response = (
        "老友記你好！我係你嘅AI生活伴侶，隨時陪你傾偈、講笑話、報天氣同聽你分享心事！"
    )
if "status_message" not in st.session_state:
    st.session_state.status_message = ""
if "tts_trigger_id" not in st.session_state:
    st.session_state.tts_trigger_id = 0
if "last_audio_bytes" not in st.session_state:
    st.session_state.last_audio_bytes = None


# ==============================================================================
# 2. HIGH-CONTRAST LOW-VISION DARK MODE CSS
# ==============================================================================
def inject_accessible_css() -> None:
    st.markdown(
        """
        <style>
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background-color: #000000 !important;
            color: #FFFFFF !important;
            font-family: "Noto Sans TC", "PingFang HK", "Microsoft JhengHei", sans-serif !important;
        }
        #MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden !important; }
        .block-container { max-width: 900px !important; padding-top: 1.5rem !important; padding-bottom: 4rem !important; }

        .header-box {
            background-color: #111111;
            border: 4px solid #FFD700;
            border-radius: 20px;
            padding: 20px 24px;
            text-align: center;
            margin-bottom: 24px;
        }
        .header-title { font-size: 46px !important; font-weight: 900 !important; color: #FFD700 !important; margin: 0 !important; }
        .header-subtitle { font-size: 28px !important; font-weight: 700 !important; color: #FFFFFF !important; margin-top: 8px !important; }

        .response-card {
            background-color: #0A0A0A;
            border: 6px solid #00FF66;
            border-radius: 24px;
            padding: 32px 28px;
            margin-top: 16px;
            margin-bottom: 28px;
            box-shadow: 0 0 25px rgba(0, 255, 102, 0.25);
        }
        .query-echo { font-size: 28px !important; font-weight: 700 !important; color: #00E5FF !important; margin-bottom: 16px !important; border-bottom: 2px dashed #444; padding-bottom: 12px; }
        .response-text { font-size: 44px !important; font-weight: 900 !important; color: #FFD700 !important; line-height: 1.45 !important; word-break: break-word; }

        .alert-box {
            background-color: #2B0000;
            border: 4px solid #FF4444;
            border-radius: 18px;
            padding: 20px 24px;
            margin-bottom: 20px;
            font-size: 32px !important;
            font-weight: 800 !important;
            color: #FFDDDD !important;
            text-align: center;
        }
        .section-label { font-size: 34px !important; font-weight: 900 !important; color: #00E5FF !important; margin-top: 24px !important; margin-bottom: 14px !important; }

        [data-testid="stAudioInput"] {
            background-color: #141414 !important;
            border: 6px solid #FFD700 !important;
            border-radius: 28px !important;
            padding: 24px !important;
            margin-bottom: 24px !important;
        }
        [data-testid="stAudioInput"] label { font-size: 36px !important; font-weight: 900 !important; color: #FFD700 !important; }
        [data-testid="stAudioInput"] button { transform: scale(1.6) !important; margin: 14px 24px !important; border: 3px solid #FFD700 !important; }

        div.stButton > button {
            width: 100% !important; min-height: 105px !important;
            background-color: #1A1A1A !important; color: #FFFFFF !important;
            border: 4px solid #FFD700 !important; border-radius: 20px !important;
            padding: 18px 16px !important; margin-bottom: 14px !important;
        }
        div.stButton > button p { font-size: 32px !important; font-weight: 900 !important; color: #FFD700 !important; }
        div.stButton > button:hover { background-color: #FFD700 !important; color: #000000 !important; }
        div.stButton > button:hover p { color: #000000 !important; }

        div[data-testid="stTextInput"] label { font-size: 32px !important; font-weight: 800 !important; color: #FFFFFF !important; }
        div[data-testid="stTextInput"] input {
            font-size: 36px !important; font-weight: 800 !important; height: 88px !important;
            background-color: #121212 !important; color: #FFD700 !important; border: 4px solid #00E5FF !important; border-radius: 18px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# 3. TIME & WEATHER UTILITIES
# ==============================================================================
WEEKDAY_CANTONESE = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"}
HK_TZ = datetime.timezone(datetime.timedelta(hours=8))

def get_hk_time_and_weather():
    now = datetime.datetime.now(HK_TZ)
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=22.3193&longitude=114.1694&current=temperature_2m,weather_code&timezone=Asia/Hong_Kong"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            temp = data.get("current", {}).get("temperature_2m")
            code = data.get("current", {}).get("weather_code", 0)
            weather_desc = "落雨" if code in [51,53,55,61,63,65,80,81,82] else ("多雲" if code in [1,2,3] else "天晴")
            temp_str = f"大約 {int(temp)} 度" if temp else "氣溫適中"
            return now, f"今日香港天氣大致{weather_desc}，氣溫{temp_str}。"
    except Exception:
        return now, "今日香港天氣大致天晴，氣溫適中。"


# ==============================================================================
# 4. AI-FIRST DEEPSEEK CORE
# ==============================================================================
def generate_cantonese_response(user_text: str) -> str:
    cleaned = user_text.strip()
    if not cleaned:
        return "我頭先聽唔清楚，你想同我傾啲咩呀？"

    if any(k in cleaned for k in ["救命", "唔舒服", "頭暈", "痛", "打電話", "阿仔", "阿女", "屋企人", "幫手"]):
        return "收到！如果你覺得唔舒服，請即刻坐低休息。緊急聯絡人係阿仔 JJ，電話係 5 2 8 1 0 2 8 5，情況緊急請打 9 9 9！"

    now, weather_sentence = get_hk_time_and_weather()
    time_str = f"朝早{now.hour}點" if 5<=now.hour<12 else ("下晝" if now.hour<18 else "夜晚")

    try:
        response = ollama.chat(
            model='deepseek-r1:8b',
            messages=[
                {
                    'role': 'system',
                    'content': (
                        f"你係一個專為香港長者服務、幽默風趣、識講好多笑話同傳統廣東俗語嘅老友記生活伴侶。"
                        f"當前環境：{time_str}，{WEEKDAY_CANTONESE[now.weekday()]}，{weather_sentence}。"
                        f"請用極度地道、生動、溫暖嘅廣東話回答。多多運用香港俗語（如『濕濕碎』、『行得快好世界』）或笑話。"
                        f"字數必須控制喺 50 字以內，語氣要好似茶樓吹水一樣親切。"
                    )
                },
                {'role': 'user', 'content': cleaned}
            ]
        )
        ai_answer = response.get('message', {}).get('content', '').strip()
        if "</think>" in ai_answer:
            ai_answer = ai_answer.split("</think>")[-1].strip()
        return ai_answer if ai_answer else "呢樣嘢真係得意喎，同我講多啲啦！"
    except Exception:
        return "我個腦暫時連唔到本地AI，不過我隨時陪緊你傾偈架！"


# ==============================================================================
# 5. SPEECH-TO-TEXT & EDGE-TTS (NATURAL HUMAN VOICE)
# ==============================================================================
def transcribe_cantonese_audio(audio_bytes: bytes) -> tuple[bool, str]:
    if not audio_bytes or len(audio_bytes) < 512:
        return False, "未錄到聲音，請再講一次啦。"
    if not SR_AVAILABLE:
        return False, "未安裝 SpeechRecognition 套件。"
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio_data = recognizer.record(source)
        transcript = recognizer.recognize_google(audio_data, language="zh-HK")
        return (True, transcript.strip()) if transcript else (False, "聽唔清楚你講乜。")
    except Exception:
        return False, "聽唔清楚你頭先講乜，請再講一次！"

async def generate_edge_tts_audio(text: str, filename: str = "response.mp3"):
    if not EDGE_TTS_AVAILABLE:
        return
    # 使用微軟極致自然的香港女聲 zh-HK-HiuMaanNeural (聽起來像真人廣東話主播)
    communicate = edge_tts.Communicate(text, "zh-HK-HiuMaanNeural", rate="+0%", pitch="+0Hz")
    await communicate.save(filename)


# ==============================================================================
# 6. MAIN UI & LOGIC
# ==============================================================================
def handle_command(command_text: str):
    cleaned = command_text.strip()
    if not cleaned:
        st.session_state.status_message = "⚠️ 請先講出指令或者輸入文字！"
        return
    st.session_state.status_message = ""
    st.session_state.user_query = cleaned
    st.session_state.bot_response = generate_cantonese_response(cleaned)
    st.session_state.tts_trigger_id += 1


def main():
    inject_accessible_css()

    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">🎙️ 長者AI生活伴侶</h1>
            <div class="header-subtitle">微軟真人級粵語語音 + DeepSeek 智能陪傾偈</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 產生並播放極度自然的 Edge-TTS 語音
    audio_filename = "response.mp3"
    if EDGE_TTS_AVAILABLE:
        try:
            asyncio.run(generate_edge_tts_audio(st.session_state.bot_response, audio_filename))
        except Exception:
            pass

    st.markdown('<div class="section-label">1️⃣ 語音對話（撳下面個咪講廣東話）</div>', unsafe_allow_html=True)
    audio_value = st.audio_input("👇 請撳下面個「咪高峰」開始傾偈：")

    if audio_value is not None:
        current_bytes = audio_value.getvalue()
        if current_bytes != st.session_state.last_audio_bytes:
            st.session_state.last_audio_bytes = current_bytes
            with st.spinner("⏳ AI 正在聆聽並思考中..."):
                ok, result_text = transcribe_cantonese_audio(current_bytes)
                if ok:
                    handle_command(result_text)
                    st.rerun()
                else:
                    st.session_state.status_message = f"⚠️ {result_text}"

    if st.session_state.status_message:
        st.markdown(f'<div class="alert-box">{st.session_state.status_message}</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label">2️⃣ AI 伴侶回答（大字顯示 + 真人語音朗讀）</div>', unsafe_allow_html=True)
    query_html = f'<div class="query-echo">🗣️ 你問：「{st.session_state.user_query}」</div>' if st.session_state.user_query else '<div class="query-echo">🗣️ 歡迎使用 AI 語音伴侶</div>'

    st.markdown(
        f"""
        <div class="response-card">
            {query_html}
            <div class="response-text">{st.session_state.bot_response}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 自動播放微軟真人級粵語語音
    if EDGE_TTS_AVAILABLE:
        st.audio(audio_filename, format="audio/mp3", autoplay=True)

    st.markdown('<div class="section-label">3️⃣ 快捷話題推薦</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("😂 講個笑話嚟聽下", use_container_width=True):
            handle_command("講個開心嘅笑話嚟聽下啦")
            st.rerun()
        if st.button("🌤️ 今日天氣點呀？", use_container_width=True):
            handle_command("今日香港天氣點呀？")
            st.rerun()
    with col2:
        if st.button("🍵 養生保健貼士", use_container_width=True):
            handle_command("講個簡單實用嘅養生貼士畀我聽")
            st.rerun()
        if st.button("🎵 推薦休閒活動", use_container_width=True):
            handle_command("今日下午有咩老友記消閒活動推薦？")
            st.rerun()

    st.markdown('<div class="section-label">4️⃣ 文字輸入聊天</div>', unsafe_allow_html=True)
    with st.form(key="text_fallback_form", clear_on_submit=True):
        fallback_input = st.text_input("想講咩心事或者問乜嘢，喺度打字：", placeholder="例如：今日心情好靚，同我傾陣偈...")
        if st.form_submit_button("✅ 發送並讓 AI 回答", use_container_width=True):
            handle_command(fallback_input)
            st.rerun()


if __name__ == "__main__":
    main()
