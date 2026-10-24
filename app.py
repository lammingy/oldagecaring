"""
語音指令式家庭生活便利 Bot (Voice-Controlled Daily Info Panel)
==============================================================
專為患有眼疾或低視能長者設計的高對比度、極簡粵語語音互動生活助手。
Tailored for elderly users with low vision:
- High-contrast dark theme (#000000 background, #FFD700 / #FFFFFF text)
- Massive typography and prominent microphone/quick-action controls
- Cantonese Speech-to-Text (via st.audio_input + SpeechRecognition) + Text Fallback
- Cantonese Intent Engine (Time, Date, Weather, Reminders, Emergency, AI Chat)
- Dual Output: Giant visual response card + automatic browser Web Speech API ('zh-HK') TTS

Required Pip Packages:
    pip install streamlit SpeechRecognition google-genai
"""

import datetime
import io
import json
import os
import urllib.request
import streamlit as st
import streamlit.components.v1 as components

# Optional SpeechRecognition import for decoding recorded audio into Cantonese text
try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    SR_AVAILABLE = False

# Optional Gemini SDK import for open-ended Cantonese questions
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
        "老友記你好！請撳下面嘅大掣或者對住咪高峰講嘢，我可以報時、報天氣同埋提你食藥。"
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

        /* Hide Streamlit default chrome to reduce cognitive load */
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
# 3. CANTONESE INTENT & LIVE HONG KONG TIME / WEATHER ENGINE
# ==============================================================================
WEEKDAY_CANTONESE = {
    0: "星期一",
    1: "星期二",
    2: "星期三",
    3: "星期四",
    4: "星期五",
    5: "星期六",
    6: "星期日",
}

NUM_TO_CANTONESE = {
    0: "零", 1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
    6: "六", 7: "七", 8: "八", 9: "九", 10: "十"
}

HK_TZ = datetime.timezone(datetime.timedelta(hours=8))


def number_to_cantonese_str(num: int) -> str:
    """Converts a number (0-59) into Chinese Cantonese text (e.g., 49 -> 四十九)."""
    if num in NUM_TO_CANTONESE:
        return NUM_TO_CANTONESE[num]
    if num < 20:
        return f"十{NUM_TO_CANTONESE[num % 10]}"
    
    tens = num // 10
    units = num % 10
    tens_str = f"{NUM_TO_CANTONESE[tens]}十"
    units_str = NUM_TO_CANTONESE[units] if units > 0 else ""
    return f"{tens_str}{units_str}"


def get_cantonese_time_string(now: datetime.datetime) -> str:
    """
    Formats current time into exact specified format:
    e.g., 而家係香港時間深夜12點四十九
    """
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

    return f"而家係香港時間{period}{display_hour}點{minute_str}"


def get_hk_time_and_weather() -> tuple[datetime.datetime, str]:
    """
     獲取精確嘅即時香港時間（直接使用系統即時時鐘確保準確），
     並同時從 Open-Meteo API 獲取即時天氣。
    """
    # 直接使用當刻即時嘅香港時間，確保分秒 100% 準確
    now = datetime.datetime.now(HK_TZ)
    fallback_weather = "今日香港天氣大致天晴，氣溫適中。出門散步記得帶把遮傍身啦！"

    try:
        # Hong Kong coordinates: Lat 22.3193, Lon 114.1694
        url = "https://api.open-meteo.com/v1/forecast?latitude=22.3193&longitude=114.1694&current=temperature_2m,weather_code&timezone=Asia/Hong_Kong"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            
            # 提取天氣資訊
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
            weather_sentence = f"今日香港天氣大致{weather_desc}，氣溫{temp_str}。出門散步記得着返件薄外套，最好帶埋把遮傍身啦！"
            
            return now, weather_sentence
    except Exception:
        return now, fallback_weather


def generate_cantonese_response(user_text: str) -> str:
    """
    Processes the user's Cantonese command and returns a friendly, concise
    Cantonese answer tailored for elderly daily life.
    """
    cleaned = user_text.strip()
    if not cleaned:
        return "我頭先聽唔清楚，請你再講多次，或者撳下面嘅大掣啦。"

    # Fetch live synchronized Hong Kong time and weather
    now, weather_sentence = get_hk_time_and_weather()
    weekday_str = WEEKDAY_CANTONESE[now.weekday()]

    # 1. Time Intent (報時)
    if any(k in cleaned for k in ["幾點", "時間", "報時", "鐘數", "而家幾點"]):
        time_sentence = get_cantonese_time_string(now)
        return f"{time_sentence}。記得多飲溫水，坐低休息下呀！"

    # 2. Date / Day of Week Intent (日期 / 星期)
    if any(k in cleaned for k in ["幾號", "日期", "星期幾", "今日係", "邊日", "日曆"]):
        return (
            f"今日係香港時間 {now.year}年 {now.month}月 {now.day}號，{weekday_str}。"
            "祝你今日心境開朗，身體健康！"
        )

    # 3. Weather Intent (天氣 / 出街)
    if any(k in cleaned for k in ["天氣", "落雨", "幾度", "氣溫", "凍唔凍", "熱唔熱", "出街", "帶遮"]):
        return weather_sentence

    # 4. Medication & Daily Reminders Intent (食藥 / 覆診 / 提醒)
    if any(k in cleaned for k in ["食藥", "血壓", "覆診", "提醒", "備忘", "食咗藥未", "藥"]):
        return (
            "溫馨提醒你：朝早八點半要食血壓藥（一粒白色圓形藥丸），食完早餐先好食呀！"
            "另外，下星期三朝早十點半要返眼科診所覆診。"
        )

    # 5. Emergency / Family Contact Intent (求助 / 屋企人 / 打電話)
    if any(k in cleaned for k in ["救命", "唔舒服", "頭暈", "痛", "打電話", "阿仔", "阿女", "屋企人", "幫手"]):
        return (
            "收到！如果你覺得唔舒服，請即刻坐低休息。緊急聯絡人係阿仔（陳大文），"
            "電話係 9 1 2 3 4 5 6 7。如果情況緊急，請即刻打 9 9 9 求助！"
        )

    # 6. Greeting / Health Tip / Chat Intent (問候 / 傾偈 / 養生)
    if any(k in cleaned for k in ["你好", "早晨", "早唞", "健康", "飲湯", "養生", "悶", "傾偈"]):
        return (
            "老友記你好呀！今日精神好嗎？護眼小貼士提提你：平時唔好喺太暗嘅地方睇嘢，"
            "每隔半個鐘就合埋對眼休息五分鐘，得閒聽下粵曲或者收音機就最舒服喇！"
        )

    # 7. Optional Gemini AI Fallback (if GEMINI_API_KEY is configured in environment)
    api_key = os.environ.get("GEMINI_API_KEY")
    if GENAI_AVAILABLE and api_key:
        try:
            client = genai.Client(api_key=api_key)
            prompt = (
                "你係一個專為患有眼疾嘅香港長者服務嘅語音生活助手。"
                "請用非常親切、簡單、口語化嘅廣東話（繁體中文）回答以下問題，"
                "字數控制喺 50 字以內，唔好用複雜標點符號，方便語音朗讀：\n"
                f"長者問：{cleaned}"
            )
            ai_resp = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            if ai_resp and ai_resp.text:
                return ai_resp.text.strip()
        except Exception:
            pass

    # 8. Graceful Offline Fallback for Unrecognized Queries
    return (
        f"我聽到你講：「{cleaned}」。"
        "我而家可以幫你報時、查今日日期、報天氣、提醒食藥同埋搵屋企人電話。"
        "你可以試下講：「而家幾點」或者「今日天氣點呀」！"
    )


# ==============================================================================
# 4. SPEECH-TO-TEXT AUDIO TRANSCRIPTION (CANTONESE 'zh-HK')
# ==============================================================================
def transcribe_cantonese_audio(audio_bytes: bytes) -> tuple[bool, str]:
    """
    Transcribes recorded WAV audio bytes into Cantonese text using SpeechRecognition.
    Returns (success: bool, result_or_error_message: str).
    """
    if not audio_bytes or len(audio_bytes) < 512:
        return False, "未錄到聲音，請撳實錄音掣講多一次啦。"

    if not SR_AVAILABLE:
        return (
            False,
            "系統尚未安裝 SpeechRecognition 語音識別套件，請使用下方大字輸入框或快捷大掣。",
        )

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(io.BytesIO(audio_bytes)) as source:
            audio_data = recognizer.record(source)

        # Recognize Cantonese (Hong Kong)
        transcript = recognizer.recognize_google(audio_data, language="zh-HK")
        if not transcript or not transcript.strip():
            return False, "聽唔清楚你講乜，請靠近少少咪高峰再講一次啦。"
        return True, transcript.strip()

    except sr.UnknownValueError:
        return False, "我聽唔清楚你頭先講乜，請慢少少、大聲少少再講一次啦！"
    except sr.RequestError:
        return False, "語音識別網絡暫時連唔到，你可以直接撳下面嘅快捷大掣或者打字！"
    except Exception:
        return False, "處理錄音時出現小問題，請再試一次或者撳下面嘅大掣啦！"


# ==============================================================================
# 5. FLUENT CANTONESE WEB SPEECH SYNTHESIS (TTS) + BROWSER STT COMPONENT
# ==============================================================================
def render_cantonese_tts_and_voice_helper(text_to_speak: str, trigger_id: int) -> None:
    """
    Injects an accessible HTML/JS component that:
    1. Automatically speaks `text_to_speak` aloud in fluent Cantonese ('zh-HK')
       whenever `trigger_id` increments.
    2. Provides a huge one-tap "🔊 再讀一次 (Replay Audio)" button in the browser.
    """
    safe_text_json = json.dumps(text_to_speak, ensure_ascii=False)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-HK">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{
                margin: 0;
                padding: 0;
                background-color: #000000;
                font-family: "Noto Sans TC", "PingFang HK", "Microsoft JhengHei", sans-serif;
                overflow: hidden;
            }}
            .tts-bar {{
                display: flex;
                gap: 16px;
                width: 100%;
                box-sizing: border-box;
                padding: 4px 0;
            }}
            .tts-btn {{
                flex: 1;
                min-height: 92px;
                background-color: #003319;
                color: #00FF66;
                border: 4px solid #00FF66;
                border-radius: 20px;
                font-size: 32px;
                font-weight: 900;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.15s ease;
            }}
            .tts-btn:hover, .tts-btn:focus {{
                background-color: #00FF66;
                color: #000000;
            }}
            .stop-btn {{
                flex: 0.45;
                min-height: 92px;
                background-color: #330000;
                color: #FF6666;
                border: 4px solid #FF6666;
                border-radius: 20px;
                font-size: 30px;
                font-weight: 900;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            .stop-btn:hover, .stop-btn:focus {{
                background-color: #FF6666;
                color: #000000;
            }}
        </style>
    </head>
    <body>
        <div class="tts-bar" role="region" aria-label="語音朗讀控制">
            <button class="tts-btn" onclick="speakCantonese()" aria-label="大聲朗讀答案">
                🔊 再讀一次答案 (粵語朗讀)
            </button>
            <button class="stop-btn" onclick="stopSpeaking()" aria-label="停止朗讀">
                ⏹️ 停止
            </button>
        </div>

        <script>
            const responseText = {safe_text_json};
            const currentTriggerId = {trigger_id};

            function pickCantoneseVoice() {{
                if (!('speechSynthesis' in window)) return null;
                const voices = window.speechSynthesis.getVoices();
                if (!voices || voices.length === 0) return null;

                let hkVoice = voices.find(v =>
                    v.lang.toLowerCase() === 'zh-hk' ||
                    v.lang.toLowerCase() === 'yue-hk' ||
                    v.lang.toLowerCase().includes('hk') ||
                    v.name.toLowerCase().includes('cantonese') ||
                    v.name.includes('粵語') ||
                    v.name.includes('廣東話') ||
                    v.name.includes('Hong Kong')
                );
                if (hkVoice) return hkVoice;

                let twVoice = voices.find(v => v.lang.toLowerCase().includes('zh-tw'));
                if (twVoice) return twVoice;

                return voices.find(v => v.lang.toLowerCase().startsWith('zh')) || null;
            }}

            function speakCantonese() {{
                if (!('speechSynthesis' in window)) {{
                    alert("你部機嘅瀏覽器暫時唔支援語音朗讀功能。");
                    return;
                }}
                window.speechSynthesis.cancel();

                const utterance = new SpeechSynthesisUtterance(responseText);
                utterance.lang = 'zh-HK';
                utterance.rate = 0.88;
                utterance.pitch = 1.0;
                utterance.volume = 1.0;

                const selectedVoice = pickCantoneseVoice();
                if (selectedVoice) {{
                    utterance.voice = selectedVoice;
                }}

                window.speechSynthesis.speak(utterance);
            }}

            function stopSpeaking() {{
                if ('speechSynthesis' in window) {{
                    window.speechSynthesis.cancel();
                }}
            }}

            if ('speechSynthesis' in window) {{
                if (window.speechSynthesis.getVoices().length === 0) {{
                    window.speechSynthesis.onvoiceschanged = function() {{
                        speakCantonese();
                        window.speechSynthesis.onvoiceschanged = null;
                    }};
                }} else {{
                    setTimeout(speakCantonese, 150);
                }}
            }}
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=110, scrolling=False)


# ==============================================================================
# 6. HELPER TO TRIGGER COMMANDS UNIFORMLY
# ==============================================================================
def handle_command(command_text: str) -> None:
    """Updates session state with the user query, generates the Cantonese response, and triggers TTS."""
    cleaned = command_text.strip()
    if not cleaned:
        st.session_state.status_message = "⚠️ 請先講出指令或者輸入文字，唔好留空呀！"
        st.session_state.status_type = "warning"
        return

    st.session_state.status_message = ""
    st.session_state.user_query = cleaned
    st.session_state.bot_response = generate_cantonese_response(cleaned)
    st.session_state.tts_trigger_id += 1


# ==============================================================================
# 7. MAIN APPLICATION UI LAYOUT
# ==============================================================================
def main() -> None:
    inject_accessible_css()

    st.markdown(
        """
        <div class="header-box" role="banner">
            <h1 class="header-title">🎙️ 長者語音生活助手</h1>
            <div class="header-subtitle">撳一下咪高峰講廣東話，大字顯示兼自動讀出答案</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="section-label">1️⃣ 語音指令（撳下面個咪講嘢）</div>', unsafe_allow_html=True)

    audio_value = st.audio_input(
        "👇 請撳下面個「咪高峰」開始講廣東話（講完再撳一下停止）："
    )

    if audio_value is not None:
        current_bytes = audio_value.getvalue()
        if current_bytes != st.session_state.last_audio_bytes:
            st.session_state.last_audio_bytes = current_bytes
            with st.spinner("⏳ 正在聽取你嘅廣東話指令..."):
                ok, result_text = transcribe_cantonese_audio(current_bytes)
                if ok:
                    handle_command(result_text)
                else:
                    st.session_state.status_message = f"⚠️ {result_text}"
                    st.session_state.status_type = "error"
                    st.session_state.bot_response = result_text
                    st.session_state.tts_trigger_id += 1

    if st.session_state.status_message:
        st.markdown(
            f'<div class="alert-box" role="alert">{st.session_state.status_message}</div>',
            unsafe_allow_html=True,
        )

    st.markdown('<div class="section-label">2️⃣ 助手回答（大字顯示 + 自動朗讀）</div>', unsafe_allow_html=True)

    query_html = (
        f'<div class="query-echo">🗣️ 你問：「{st.session_state.user_query}」</div>'
        if st.session_state.user_query
        else '<div class="query-echo">🗣️ 歡迎使用語音助手</div>'
    )

    st.markdown(
        f"""
        <div class="response-card" role="status" aria-live="polite">
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

    st.markdown('<div class="section-label">3️⃣ 常用一鍵指令（直接撳大掣）</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🕒 而家幾點？", use_container_width=True):
            handle_command("而家幾點？")
            st.rerun()
        if st.button("🌤️ 今日天氣點呀？", use_container_width=True):
            handle_command("今日天氣點呀？")
            st.rerun()
        if st.button("💊 提醒我食藥", use_container_width=True):
            handle_command("今日有咩藥要食？")
            st.rerun()

    with col2:
        if st.button("📅 今日幾月幾號？", use_container_width=True):
            handle_command("今日係幾月幾號星期幾？")
            st.rerun()
        if st.button("📞 搵屋企人電話", use_container_width=True):
            handle_command("我想打電話俾屋企人")
            st.rerun()
        if st.button("👁️ 護眼健康貼士", use_container_width=True):
            handle_command("你好，講個護眼貼士嚟聽下")
            st.rerun()

    st.markdown('<div class="section-label">4️⃣ 大字打字輸入（後備輸入框）</div>', unsafe_allow_html=True)

    with st.form(key="text_fallback_form", clear_on_submit=True):
        fallback_input = st.text_input(
            "如果唔想講嘢，可以喺呢度打字（例如：而家幾點、今日天氣）：",
            placeholder="請喺度輸入廣東話問題...",
        )
        submit_btn = st.form_submit_button("✅ 發送問題並朗讀答案", use_container_width=True)
        if submit_btn:
            handle_command(fallback_input)
            st.rerun()


if __name__ == "__main__":
    main()