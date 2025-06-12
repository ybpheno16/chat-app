import streamlit as st
from streamlit_webrtc import webrtc_streamer, WebRtcMode, ClientSettings
import av
import queue
from langdetect import detect
from googletrans import Translator
from gtts import gTTS
import tempfile
import os
import pygame
import time
import json
import random
import string
from streamlit_autorefresh import st_autorefresh
import speech_recognition as sr

# Setup
pygame.mixer.init()
CONVERSATION_DIR = "conversations"
if not os.path.exists(CONVERSATION_DIR):
    os.makedirs(CONVERSATION_DIR)

SUPPORTED_LANGUAGES = {
    'en': 'English', 'hi': 'Hindi', 'te': 'Telugu', 'ta': 'Tamil',
    'kn': 'Kannada', 'ml': 'Malayalam', 'bn': 'Bengali',
    'gu': 'Gujarati', 'ur': 'Urdu', 'mr': 'Marathi',
}

translator = Translator()
recognizer = sr.Recognizer()
audio_queue = queue.Queue()

def get_room_file(room_id):
    return os.path.join(CONVERSATION_DIR, f"conversation_{room_id}.json")

def load_conversation(room_id):
    room_file = get_room_file(room_id)
    if os.path.exists(room_file):
        with open(room_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"messages": [], "user1_lang": "en", "user2_lang": "hi"}

def save_conversation(room_id, data):
    with open(get_room_file(room_id), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def transcribe_audio(audio_data):
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
            f.write(audio_data)
            f.flush()
            with sr.AudioFile(f.name) as source:
                audio = recognizer.record(source)
                text = recognizer.recognize_google(audio)
        detected_lang = detect(text)
        return text, detected_lang
    except Exception as e:
        st.error(f"Speech recognition failed: {e}")
        return None, None

def translate_text(text, dest_lang):
    try:
        return translator.translate(text, dest=dest_lang).text
    except Exception as e:
        st.error(f"Translation error: {e}")
        return None

def text_to_speech(text, lang_code):
    try:
        tts = gTTS(text=text, lang=lang_code)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tf:
            tts.save(tf.name)
            pygame.mixer.music.load(tf.name)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                time.sleep(0.1)
            pygame.mixer.music.unload()
            os.remove(tf.name)
    except Exception as e:
        st.error(f"TTS playback error: {e}")

# WebRTC Audio Processor
class AudioProcessor:
    def recv(self, frame):
        audio = frame.to_ndarray()
        audio_bytes = frame.to_bytes()
        audio_queue.put(audio_bytes)
        return av.AudioFrame.from_ndarray(audio, layout="mono")

# UI Styling
st.markdown("""
<style>
.status-box {padding: 10px; border-radius: 8px; font-weight: bold; color: white;
background-color: #1E90FF; margin-bottom: 10px; text-align: center;}
.conversation-box {background-color: #f9f9f9; padding: 15px; border-radius: 10px;
margin-top: 10px; border-left: 5px solid;}
.user1-msg { border-color: #4CAF50; }
.user2-msg { border-color: #FFC107; }
</style>
""", unsafe_allow_html=True)

# Session state
st.set_page_config(layout="wide")
for key in ["status", "last_played_timestamp", "user_id", "room_id"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "last_played_timestamp" else 0
st.session_state.room_id = st.query_params.get("room_id", None)

# Chat UI
def chat_room_ui(room_id, user_id):
    st_autorefresh(interval=3000, key="data_refresher")
    conversation_data = load_conversation(room_id)
    messages = conversation_data["messages"]
    user1_lang = conversation_data["user1_lang"]
    user2_lang = conversation_data["user2_lang"]

    my_lang = user1_lang if user_id == "User 1" else user2_lang
    target_lang = user2_lang if user_id == "User 1" else user1_lang

    st.title(f"🌐 Room: `{room_id}`")
    st.info(f"You are **{user_id}**. Translates to **{SUPPORTED_LANGUAGES[target_lang]}**.")

    st.markdown(f"<div class='status-box'>{st.session_state.status or '🎙️ Ready to speak'}</div>", unsafe_allow_html=True)

    webrtc_streamer(
        key="speech",
        mode=WebRtcMode.SENDONLY,
        in_audio=True,
        client_settings=ClientSettings(media_stream_constraints={"audio": True, "video": False}),
        audio_processor_factory=AudioProcessor
    )

    if st.button("Process Last Speech"):
        if not audio_queue.empty():
            audio_data = audio_queue.get()
            text, detected_lang = transcribe_audio(audio_data)
            if text:
                translated_text = text if detected_lang == target_lang else translate_text(text, target_lang)
                timestamp = time.time()
                msg = {
                    "user": user_id,
                    "text": text,
                    "lang_detected": SUPPORTED_LANGUAGES.get(detected_lang, detected_lang),
                    "translated_text": translated_text,
                    "timestamp": timestamp
                }
                messages.append(msg)
                save_conversation(room_id, conversation_data)
                st.session_state.status = "✅ Message processed!"
                st.rerun()

    # Display Messages
    st.markdown("---")
    st.markdown("### 💬 Conversation")
    for msg in reversed(messages):
        css = "user1-msg" if msg["user"] == "User 1" else "user2-msg"
        st.markdown(f"""
            <div class="conversation-box {css}">
                <b>{msg['user']}</b> <span style='font-size: smaller; color: grey;'>({msg['lang_detected']})</span>:
                <p>{msg['text']}</p>
                <hr><b>Translation:</b><em>{msg['translated_text']}</em>
            </div>
        """, unsafe_allow_html=True)

    # TTS Playback
    if messages:
        last_msg = messages[-1]
        if last_msg["user"] != user_id and last_msg["timestamp"] > st.session_state.last_played_timestamp:
            with st.spinner("🔊 Playing translation..."):
                text_to_speech(last_msg["translated_text"], target_lang)
            st.session_state.last_played_timestamp = last_msg["timestamp"]

# Lobby UI
def lobby_ui():
    st.title("🎤 Real-Time Voice Translator")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Create Room")
        l1 = st.selectbox("User 1 Language", SUPPORTED_LANGUAGES.keys(), format_func=lambda x: SUPPORTED_LANGUAGES[x])
        l2 = st.selectbox("User 2 Language", SUPPORTED_LANGUAGES.keys(), format_func=lambda x: SUPPORTED_LANGUAGES[x])
        if st.button("Create"):
            room_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            st.session_state.update({"room_id": room_id, "user_id": "User 1"})
            save_conversation(room_id, {"messages": [], "user1_lang": l1, "user2_lang": l2})
            st.query_params["room_id"] = room_id
            st.rerun()
    with col2:
        st.subheader("Join Room")
        room = st.text_input("Enter Room ID").strip().upper()
        if st.button("Join"):
            if os.path.exists(get_room_file(room)):
                st.session_state.update({"room_id": room, "user_id": "User 2"})
                st.query_params["room_id"] = room
                st.rerun()
            else:
                st.error("❌ Room not found")

# Routing
if st.session_state.room_id and st.session_state.user_id:
    chat_room_ui(st.session_state.room_id, st.session_state.user_id)
else:
    lobby_ui()
