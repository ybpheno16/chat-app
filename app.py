import streamlit as st
from streamlit_webrtc import webrtc_streamer
import av
import numpy as np
from langdetect import detect
from googletrans import Translator
from gtts import gTTS
import os
import tempfile
import time
import base64
import json
import random
import string
from streamlit_autorefresh import st_autorefresh
import io
import soundfile as sf

# --- Initial Setup ---

# Path to store conversation files
CONVERSATION_DIR = "conversations"
if not os.path.exists(CONVERSATION_DIR):
    os.makedirs(CONVERSATION_DIR)

SUPPORTED_LANGUAGES = {
    'en': 'English',
    'hi': 'Hindi',
    'te': 'Telugu',
    'ta': 'Tamil',
    'kn': 'Kannada',
    'ml': 'Malayalam',
    'bn': 'Bengali',
    'gu': 'Gujarati',
    'ur': 'Urdu',
    'mr': 'Marathi',
}

translator = Translator()

# --- Helper Functions ---

def get_room_file(room_id):
    return os.path.join(CONVERSATION_DIR, f"conversation_{room_id}.json")

def load_conversation(room_id):
    room_file = get_room_file(room_id)
    if os.path.exists(room_file):
        with open(room_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"messages": [], "user1_lang": "en", "user2_lang": "hi"}

def save_conversation(room_id, data):
    room_file = get_room_file(room_id)
    with open(room_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def transcribe_audio(audio_bytes):
    import speech_recognition as sr
    recognizer = sr.Recognizer()
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as f:
        f.write(audio_bytes)
        file_path = f.name
    with sr.AudioFile(file_path) as source:
        audio_data = recognizer.record(source)
    os.remove(file_path)
    try:
        text = recognizer.recognize_google(audio_data)
        detected_lang = detect(text)
        return text, detected_lang
    except Exception as e:
        st.error(f"Speech recognition failed: {e}")
        return None, None

def translate_text(text, dest_lang):
    try:
        translated = translator.translate(text, dest=dest_lang)
        return translated.text
    except Exception as e:
        st.error(f"Translation error: {e}")
        return None

def text_to_speech(text, lang_code):
    try:
        tts = gTTS(text=text, lang=lang_code)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tf:
            tts.save(tf.name)
            return tf.name
    except Exception as e:
        st.error(f"TTS error: {e}")
        return None

def lobby_ui():
    st.title("🎙️ Real-Time Voice Translator")
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Create a New Room")
        user1_lang = st.selectbox("Your Language (will be User 1)", list(SUPPORTED_LANGUAGES.keys()), format_func=lambda x: SUPPORTED_LANGUAGES[x], key="create_lang1")
        user2_lang = st.selectbox("Other User's Language", list(SUPPORTED_LANGUAGES.keys()), format_func=lambda x: SUPPORTED_LANGUAGES[x], key="create_lang2")
        if st.button("Create Room"):
            room_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            st.session_state.room_id = room_id
            st.session_state.user_id = "User 1"
            save_conversation(room_id, {
                "messages": [],
                "user1_lang": user1_lang,
                "user2_lang": user2_lang
            })
            st.query_params["room_id"] = room_id
            st.rerun()
    with col2:
        st.subheader("Join Room")
        room_to_join = st.text_input("Enter Room ID").strip().upper()
        if st.button("Join Room"):
            if os.path.exists(get_room_file(room_to_join)):
                st.session_state.room_id = room_to_join
                st.session_state.user_id = "User 2"
                st.query_params["room_id"] = room_to_join
                st.rerun()
            else:
                st.error("Room not found.")

def chat_room_ui(room_id, user_id):
    st_autorefresh(interval=3000, key="refresh")
    st.title(f"🗣️ Room ID: `{room_id}`")
    conversation = load_conversation(room_id)
    user_lang = conversation["user1_lang"] if user_id == "User 1" else conversation["user2_lang"]
    target_lang = conversation["user2_lang"] if user_id == "User 1" else conversation["user1_lang"]
    st.info(f"You are **{user_id}** speaking in any language. It will be translated to **{SUPPORTED_LANGUAGES[target_lang]}**.")

    audio_bytes = st.file_uploader("Upload your voice (.wav)", type=["wav"])
    if st.button("Translate") and audio_bytes:
        text, detected_lang = transcribe_audio(audio_bytes.read())
        if text:
            translated = translate_text(text, target_lang)
            msg = {
                "user": user_id,
                "text": text,
                "lang_detected": SUPPORTED_LANGUAGES.get(detected_lang, detected_lang),
                "translated_text": translated,
                "timestamp": time.time()
            }
            conversation["messages"].append(msg)
            save_conversation(room_id, conversation)
            st.success("Message translated and saved!")

    st.markdown("### 🧾 Conversation History")
    for msg in reversed(conversation["messages"]):
        st.markdown(f"""
        **{msg['user']}** (_{msg['lang_detected']}_) said:  
        > {msg['text']}  
        **Translated:** _{msg['translated_text']}_
        """)

        if st.button(f"🔊 Play {msg['user']}", key=msg['timestamp']):
            audio_file_path = text_to_speech(msg["translated_text"], target_lang)
            if audio_file_path:
                with open(audio_file_path, "rb") as audio_file:
                    st.audio(audio_file.read(), format="audio/mp3")
                os.remove(audio_file_path)

# --- Streamlit State Setup ---
st.set_page_config(layout="wide")
if "room_id" not in st.session_state:
    st.session_state.room_id = st.query_params.get("room_id")
if "user_id" not in st.session_state:
    st.session_state.user_id = None

# --- Router ---
if st.session_state.room_id and st.session_state.user_id:
    chat_room_ui(st.session_state.room_id, st.session_state.user_id)
else:
    lobby_ui()
