"""
語音指令式家庭生活便利 Bot (Voice-Controlled Daily Info Panel)
==============================================================
專為患有眼疾或低視能長者設計的高對比度、極簡粵語語音互動生活助手。
Tailored for elderly users with low vision:
- High-contrast dark theme (#000000 background, #FFD700 / #FFFFFF text)
- Massive typography and prominent microphone/quick-action controls
- Cantonese Speech-to-Text (via st.audio_input + SpeechRecognition) + Text Fallback
- AI-First Cantonese Engine (Local DeepSeek-R1 via Ollama + Real-time Context Injection)
- Dual Output: Giant visual response card + automatic browser Web Speech API ('zh-HK') TTS

Required Pip Packages:
    pip install streamlit SpeechRecognition google-genai ollama
"""

import datetime
import io
import json
import os
import urllib.request
import streamlit as st
import streamlit.components.v1 as components
import ollama  # 本地 Ollama 整合套件

# Optional SpeechRecognition import for decoding recorded audio into Cantonese text
try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

# Optional Gemini SDK import for cloud fallback
try:
    from google import genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


# ==============================================================================
# 1. PAGE CONFIGURATION & SESSION STATE INITIALIZATION
# ==============================================================================
st.set_page_config(
    page_title="長者語音生活助手",
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
if "status_type" not in st.session_state:
    st.session_state.status_type = "info"  # "info", "warning", "error"
if "tts_trigger_id" not in st.session_state:
    st.session_state.tts_trigger_id = 0
if "last_audio_bytes" not in st.session_state:
    st.session_state.last_audio_bytes = None


# ==============================================================================
# 2. HIGH-CONTRAST LOW-VISION DARK MODE CSS
# ==============================================================================
def inject_accessible_css() -> None:
    """Injects WCAG AAA high-contrast dark mode styles and oversized UI targets."""
    st.markdown(
        """
        <style>
        /* Force Pure Black Background & High-Contrast Text */
        .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
            background-color: #000000 !important;
            color: #FFFFFF !important;
            font-family: "Noto Sans TC", "PingFang HK", "Microsoft JhengHei", sans-serif !important;
        }

        #MainMenu, footer, [data-testid="stToolbar"] {
            visibility: hidden !important;
        }

        .block-container {
            max-width: 900px !important;
            padding-top: 1.5rem !important;
            padding-bottom: 4rem !important;
        }

        /* Main Header Banner */
        .header-box {
            background-color: #111111;
            border: 4px solid #FFD700;
            border-radius: 20px;
            padding: 20px 24px;
            text-align: center;
            margin-bottom: 24px;
        }
        .header-title {
            font-size: 46px !important;
            font-weight: 900 !important;
            color: #FFD700 !important;
            margin: 0 !important;
            line-height: 1.3 !important;
        }
        .header-subtitle {
            font-size: 28px !important;
            font-weight: 700 !important;
            color: #FFFFFF !important;
            margin-top: 8px !important;
        }

        /* Massive Visual Answer Display Card */
        .response-card {
            background-color: #0A0A0A;
            border: 6px solid #00FF66;
            border-radius: 24px;
            padding: 32px 28px;
            margin-top: 16px;
            margin-bottom: 28px;
            box-shadow: 0 0 25px rgba(0, 255, 102, 0.25);
        }
        .query-echo {
            font-size: 28px !important;
            font-weight: 700 !important;
            color: #00E5FF !important;
            margin-bottom: 16px !important;
            border-bottom: 2px dashed #444444;
            padding-bottom: 12px;
        }
        .response-text {
            font-size: 44px !important;
            font-weight: 900 !important;
            color: #FFD700 !important;
            line-height: 1.45 !important;
            letter-spacing: 1px !important;
            word-break: break-word;
        }

        /* Status & Error Alert Box */
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

        /* Section Dividers / Labels */
        .section-label {
            font-size: 34px !important;
            font-weight: 900 !important;
            color: #00E5FF !important;
            margin-top: 24px !important;
            margin-bottom: 14px !important;
        }

        /* Prominent Microphone / Audio Input Container */
        [data-testid="stAudioInput"] {
            background-color: #141414 !important;
            border: 6px solid #FFD700 !important;
            border-radius: 28px !important;
            padding: 24px !important;
            margin-bottom: 24px !important;
            box-shadow: 0 0 30px rgba(255, 215, 0, 0.3) !important;
        }
        [data-testid="stAudioInput"] label {
            font-size: 36px !important;
            font-weight: 900 !important;
            color: #FFD700 !important;
            line-height: 1.4 !important;
            margin-bottom: 16px !important;
        }
        [data-testid="stAudioInput"] button {
            transform: scale(1.6) !important;
            margin: 14px 24px !important;
            border: 3px solid #FFD700 !important;
        }

        /* Huge Buttons for Quick Commands & Actions */
        div.stButton > button {
            width: 100% !important;
            min-height: 105px !important;
            background-color: #1A1A1A !important;
            color: #FFFFFF !important;
            border: 4px solid #FFD700 !important;
            border-radius: 20px !important;
            padding: 18px 16px !important;
            margin-bottom: 14px !important;
            transition: all 0.15s ease-in-out !important;
        }
        div.stButton > button p {
            font-size: 32px !important;
            font-weight: 900 !important;
            color: #FFD700 !important;
            line-height: 1.3 !important;
        }
        div.stButton > button:hover, div.stButton > button:focus {
            background-color: #FFD700 !important;
            color: #000000 !important;
            border-color: #FFFFFF !important;
            transform: scale(1.02);
        }
        div.stButton > button:hover p, div.stButton > button:focus p {
            color: #000000 !important;
        }

        /* Huge Fallback Text Input */
        div[data-testid="stTextInput"] label {
            font-size: 32px !important;
            font-weight: 800 !important;
            color: #FFFFFF !important;
            margin-bottom: 12px !important;
        }
        div[data-testid="stTextInput"] input {
            font-size: 36px !important;
            font-weight: 800 !important;
            height: 88px !important;
            padding: 16px 22px !important;
            background-color: #121212 !important;
            color: #FFD700 !important;
            border: 4px solid #00E5FF !important;
            border-radius: 18px !important;
        }
        div[data-testid="stTextInput"] input::placeholder {
            color: #888888 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


# ==============================================================================
# 3. CANTONESE TIME & WEATHER UTILITIES
# ==============================================================================
WEEKDAY_CANTONESE = {
    0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四",
    4: "星期五", 5: "星期六", 6: "星期日",
}

NUM_TO_CANTONESE = {
    0: "零", 1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
    6: "六", 7: "七", 8: "八", 9: "九", 10: "十"
}

HK_TZ = datetime.timezone(datetime.timedelta(hours=8))


def number_to_cantonese_str(num: int) -> str:
    if num in NUM_TO_CANTONESE:
        return NUM_TO_CANTONESE[num]
    if num < 20:
        return f"十{NUM_TO_CANTONESE[num % 10]}"
    tens = num // 10
    units = num % 10
    return f"{NUM_TO_CANTONESE[tens]}十{NUM_TO_CANTONESE[units] if units > 0 else ''}"


def get_cantonese_time_string(now: datetime.datetime) -> str:
    hour = now.hour
    minute = now.minute

    if 5 <= hour < 12:
        period = "朝早"
    elif 12 <= hour < 14:
        period = "中午"
    elif 14 <= hour < 18:
        period = "下晝"
    elif 18 <= hour < 23:
        period = "夜晚"
    else:
        period = "深夜"

    display_hour = hour % 12
    if display_hour == 0:
        display_hour = 12

    if minute == 0:
        minute_str = "正"
    elif minute == 30:
        minute_str = "半"
    else:
        minute_str = number_to_cantonese_str(minute)

    return f"而家係香港時間{period}{display_hour}點{minute_str}分"


def get_hk_time_and_weather() -> tuple[datetime.datetime, str]:
    now = datetime.datetime.now(HK_TZ)
    fallback_weather = "今日香港天氣大致天晴，氣溫適中。"

    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=22.3193&longitude=114.1694&current=temperature_2m,weather_code&timezone=Asia/Hong_Kong"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            temp = data.get("current", {}).get("temperature_2m")
            code = data.get("current", {}).get("weather_code", 0)
            
            weather_desc = "天晴"
            if code in [1, 2, 3]:
                weather_desc = "多雲"
            elif code in [45, 48]:
                weather_desc = "有霧"
            elif code in [51, 53, 55, 61, 63, 65, 80, 81, 82]:
                weather_desc = "落雨"
            elif code in [71, 73, 75, 85, 86]:
                weather_desc = "落雪"

            temp_str = f"大約 {int(temp)} 度" if temp is not None else "氣溫適中"
            return now, f"今日香港天氣大致{weather_desc}，氣溫{temp_str}。"
    except Exception:
        return now, fallback_weather


# ==============================================================================
# 4. AI-FIRST CORE RESPONSE ENGINE (LOCAL DEEPSEEK-R1)
# ==============================================================================
def generate_cantonese_response(user_text: str) -> str:
    """
    讓 DeepSeek 成為核心大腦：處理所有日常閒聊、開放式問題、生活伴侶對話，
    同時動態注入即時時間與天氣背景，並保留最高權重的安全緊急覆蓋。
    """
    cleaned = user_text.strip()
    if not cleaned:
        return "我頭先聽唔清楚，你想同我傾啲咩呀？"

    # 1. 唯一保留的絕對安全防線（緊急求助、身體不適）
    if any(k in cleaned for k in ["救命", "唔舒服", "頭暈", "痛", "打電話", "阿仔", "阿女", "屋企人", "幫手"]):
        return (
            "收到！如果你覺得唔舒服，請即刻坐低休息。緊急聯絡人係阿仔 JJ，"
            "電話係 5 2 8 1 0 2 8 5。如果情況緊急，請即刻打 9 9 9 求助！"
        )

    # 2. 獲取即時香港時間與天氣，作為動態背景餵給 DeepSeek
    now, weather_sentence = get_hk_time_and_weather()
    time_sentence = get_cantonese_time_string(now)
    weekday_str = WEEKDAY_CANTONESE[now.weekday()]

    # 3. 將控制權全面交給本地 DeepSeek 模型，給予極大發揮空間
    try:
        response = ollama.chat(
            model='deepseek-r1:8b',
            messages=[
                {
                    'role': 'system',
                    'content': (
                        f"你係一個專為香港長者服務嘅貼心、幽默、有智慧嘅粵語生活伴侶兼助手。"
                        f"當前即時環境：香港時間係 {time_sentence}，{weekday_str}，{weather_sentence}。"
                        f"請用極度親切、生動、溫暖、地道口語化嘅繁體中文（廣東話）回答。"
                        f"你可以隨心所欲同長者傾偈、講笑話、分享養生知識、解答生活疑難。"
                        f"因為會透過語音朗讀，字數請精簡控制喺 60 字以內，語氣要好似老朋友一樣自然。"
                    )
                },
                {
                    'role': 'user',
                    'content': cleaned
                }
            ]
        )
        ai_answer = response.get('message', {}).get('content', '').strip()
        if ai_answer:
            # 清理 DeepSeek-R1 的思考過程標籤
            if "</think>" in ai_answer:
                ai_answer = ai_answer.split("</think>")[-1].strip()
            return ai_answer
    except Exception:
        pass

    # 4. 萬一 Ollama 斷線時的離線備用
    return f"我聽到你講：「{cleaned}」。雖然我依家個腦轉得慢咗少少，但我隨時陪緊你傾偈架！"


# ==============================================================================
# 5. SPEECH-TO-TEXT AUDIO TRANSCRIPTION (CANTONESE 'zh-HK')
# ==============================================================================
def transcribe_cantonese_audio(audio_bytes: bytes) -> tuple[bool, str]:
    if not audio_bytes or len(audio_bytes) < 512:
        return False, "未錄到聲音，請撳實錄音掣講多一次啦。"

    if not SR_AVAILABLE:
        return False, "系統尚未安裝 SpeechRecognition 套件，請使用下方大字輸入框。"

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio_data = recognizer.record(source)
        transcript = recognizer.recognize_google(audio_data, language="zh-HK")
        if not transcript or not transcript.strip():
            return False, "聽唔清楚你講乜，請靠近少少咪高峰再講一次啦。"
        return True, transcript.strip()
    except Exception:
        return False, "聽唔清楚你頭先講乜，請再講一次或者直接打字啦！"


# ==============================================================================
# 6. FLUENT CANTONESE WEB SPEECH SYNTHESIS (TTS) COMPONENT
# ==============================================================================
def render_cantonese_tts_and_voice_helper(text_to_speak: str, trigger_id: int) -> None:
    safe_text_json = json.dumps(text_to_speak, ensure_ascii=False)
    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-HK">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                margin: 0; padding: 0; background-color: #000000;
                font-family: "Noto Sans TC", "PingFang HK", sans-serif; overflow: hidden;
            }}
            .tts-bar {{ display: flex; gap: 16px; width: 100%; box-sizing: border-box; padding: 4px 0; }}
            .tts-btn {{
                flex: 1; min-height: 92px; background-color: #003319; color: #00FF66;
                border: 4px solid #00FF66; border-radius: 20px; font-size: 32px; font-weight: 900;
                cursor: pointer; display: flex; align-items: center; justify-content: center;
            }}
            .tts-btn:hover {{ background-color: #00FF66; color: #000000; }}
            .stop-btn {{
                flex: 0.45; min-height: 92px; background-color: #330000; color: #FF6666;
                border: 4px solid #FF6666; border-radius: 20px; font-size: 30px; font-weight: 900;
                cursor: pointer; display: flex; align-items: center; justify-content: center;
            }}
            .stop-btn:hover {{ background-color: #FF6666; color: #000000; }}
        </style>
    </head>
    <body>
        <div class="tts-bar">
            <button class="tts-btn" onclick="speakCantonese()">🔊 再讀一次答案</button>
            <button class="stop-btn" onclick="stopSpeaking()">⏹️ 停止</button>
        </div>
        <script>
            const responseText = {safe_text_json};
            function speakCantonese() {{
                if (!('speechSynthesis' in window)) return;
                window.speechSynthesis.cancel();
                const utterance = new SpeechSynthesisUtterance(responseText);
                utterance.lang = 'zh-HK';
                utterance.rate = 0.88;
                window.speechSynthesis.speak(utterance);
            }}
            function stopSpeaking() {{
                if ('speechSynthesis' in window) window.speechSynthesis.cancel();
            }}
            setTimeout(speakCantonese, 150);
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=110, scrolling=False)


# ==============================================================================
# 7. HELPER & MAIN UI
# ==============================================================================
def handle_command(command_text: str) -> None:
    cleaned = command_text.strip()
    if not cleaned:
        st.session_state.status_message = "⚠️ 請先講出指令或者輸入文字！"
        st.session_state.status_type = "warning"
        return

    st.session_state.status_message = ""
    st.session_state.user_query = cleaned
    st.session_state.bot_response = generate_cantonese_response(cleaned)
    st.session_state.tts_trigger_id += 1


def main() -> None:
    inject_accessible_css()

    st.markdown(
        """
        <div class="header-box">
            <h1 class="header-title">🎙️ 長者AI生活伴侶</h1>
            <div class="header-subtitle">隨時傾偈、講笑話、報天氣，貼心陪伴無所不談</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-label">1️⃣ 語音對話（撳下面個咪講廣東話）</div>', unsafe_allow_html=True)
    audio_value = st.audio_input("👇 請撳下面個「咪高峰」開始同AI傾偈：")

    if audio_value is not None:
        current_bytes = audio_value.getvalue()
        if current_bytes != st.session_state.last_audio_bytes:
            st.session_state.last_audio_bytes = current_bytes
            with st.spinner("⏳ AI 正在聆聽並思考中..."):
                ok, result_text = transcribe_cantonese_audio(current_bytes)
                if ok:
                    handle_command(result_text)
                else:
                    st.session_state.status_message = f"⚠️ {result_text}"
                    st.session_state.status_type = "error"
                    st.session_state.bot_response = result_text
                    st.session_state.tts_trigger_id += 1

    if st.session_state.status_message:
        st.markdown(f'<div class="alert-box">{st.session_state.status_message}</div>', unsafe_allow_html=True)

    st.markdown('<div class="section-label">2️⃣ AI 伴侶回答（大字顯示 + 自動朗讀）</div>', unsafe_allow_html=True)
    query_html = (
        f'<div class="query-echo">🗣️ 你問：「{st.session_state.user_query}」</div>'
        if st.session_state.user_query
        else '<div class="query-echo">🗣️ 歡迎使用 AI 語音伴侶</div>'
    )

    st.markdown(
        f"""
        <div class="response-card">
            {query_html}
            <div class="response-text">{st.session_state.bot_response}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_cantonese_tts_and_voice_helper(
        st.session_state.bot_response,
        st.session_state.tts_trigger_id,
    )

    st.markdown('<div class="section-label">3️⃣ 快捷話題推薦（直接撳大掣）</div>', unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    with col1:
        if st.button("😂 講個笑話嚟聽下", use_container_width=True):
            handle_command("講個開心嘅笑話嚟聽下啦")
            st.rerun()
        if st.button("🌤️ 今日天氣點呀？", use_container_width=True):
            handle_command("今日香港天氣點呀？")
            st.rerun()
        if st.button("🍵 養生保健貼士", use_container_width=True):
            handle_command("講個簡單實用嘅養生貼士畀我聽")
            st.rerun()

    with col2:
        if st.button("🕒 而家幾點？", use_container_width=True):
            handle_command("而家幾點呀？")
            st.rerun()
        if st.button("📞 搵屋企人電話", use_container_width=True):
            handle_command("我想打電話俾屋企人")
            st.rerun()
        if st.button("🎵 推薦休閒活動", use_container_width=True):
            handle_command("今日下午有咩老友記消閒活動推薦？")
            st.rerun()

    st.markdown('<div class="section-label">4️⃣ 文字輸入聊天（後備輸入框）</div>', unsafe_allow_html=True)
    with st.form(key="text_fallback_form", clear_on_submit=True):
        fallback_input = st.text_input("想講咩心事或者問乜嘢，喺度打字：", placeholder="例如：今日心情好靚，同我傾陣偈...")
        submit_btn = st.form_submit_button("✅ 發送並讓 AI 回答", use_container_width=True)
        if submit_btn:
            handle_command(fallback_input)
            st.rerun()


if __name__ == "__main__":
    main()
