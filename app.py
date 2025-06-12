import streamlit as st
import speech_recognition as sr
from langdetect import detect
from googletrans import Translator
from gtts import gTTS
import tempfile
import os
import pygame
import time
import base64
import json
import random
import string
from streamlit_autorefresh import st_autorefresh

# --- Initial Setup ---

# Init pygame for TTS playback
pygame.mixer.init()

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

recognizer = sr.Recognizer()
translator = Translator()

# --- Helper Functions ---

### CHANGE ###
# Helper functions to manage the conversation state in a JSON file
def get_room_file(room_id):
    """Gets the file path for a given room ID."""
    return os.path.join(CONVERSATION_DIR, f"conversation_{room_id}.json")

def load_conversation(room_id):
    """Loads the conversation history from a room's JSON file."""
    room_file = get_room_file(room_id)
    if os.path.exists(room_file):
        with open(room_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"messages": [], "user1_lang": "en", "user2_lang": "hi"} # Default structure

def save_conversation(room_id, data):
    """Saves the conversation data to a room's JSON file."""
    room_file = get_room_file(room_id)
    with open(room_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def record_speech(timeout=30, max_phrase_time=120):
    with sr.Microphone() as source:
        recognizer.energy_threshold = 400
        recognizer.pause_threshold = 2.0
        st.session_state.status = "🎙️ Listening..."
        st.rerun() # Refresh the UI to show the status
        try:
            audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=max_phrase_time)
            st.session_state.status = "Processing..."
            st.rerun()
            return audio
        except sr.WaitTimeoutError:
            st.session_state.status = "Listening timed out. Please try again."
            st.rerun()
            return None

def transcribe_audio(audio):
    try:
        text = recognizer.recognize_google(audio)
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
            file_path = tf.name
        
        # Playback using pygame
        pygame.mixer.music.load(file_path)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            time.sleep(0.1)
        pygame.mixer.music.unload()
        os.remove(file_path)
    except Exception as e:
        st.error(f"TTS playback error: {e}")

# --- Streamlit UI ---

st.set_page_config(layout="wide")

# Custom CSS
st.markdown("""
<style>
    .status-box {
        padding: 10px; border-radius: 8px; font-weight: bold; color: white;
        background-color: #1E90FF; margin-bottom: 10px; text-align: center;
    }
    .conversation-box {
        background-color: #f9f9f9; padding: 15px; border-radius: 10px;
        margin-top: 10px; border-left: 5px solid;
    }
    .user1-msg { border-color: #4CAF50; }
    .user2-msg { border-color: #FFC107; }
</style>
""", unsafe_allow_html=True)

# Initialize session state variables
if 'status' not in st.session_state:
    st.session_state.status = "Welcome! Create or join a room."
if 'last_played_timestamp' not in st.session_state:
    st.session_state.last_played_timestamp = 0
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'room_id' not in st.session_state:
    st.session_state.room_id = st.query_params.get("room_id", None)


### CHANGE ###
# Main application logic: Either show the lobby or the chat room
def chat_room_ui(room_id, user_id):
    """The main UI for the conversation room."""
    
    # Auto-refresh the page every 3 seconds to check for new messages
    st_autorefresh(interval=3000, key="data_refresher")

    conversation_data = load_conversation(room_id)
    messages = conversation_data.get("messages", [])
    user1_lang = conversation_data.get("user1_lang")
    user2_lang = conversation_data.get("user2_lang")
    
    my_lang = user1_lang if user_id == "User 1" else user2_lang
    target_lang = user2_lang if user_id == "User 1" else user1_lang

    st.title(f"🌐 Voice Translator Room: `{room_id}`")
    st.info(f"You are **{user_id}**. You speak in any language, and it will be translated to **{SUPPORTED_LANGUAGES[target_lang]}**.")
    st.markdown("---")
    
    # Status box
    if st.session_state.status:
        st.markdown(f"<div class='status-box'>{st.session_state.status}</div>", unsafe_allow_html=True)

    # Speak button
    if st.button(f"🎙️ Speak ({user_id})"):
        audio = record_speech()
        if audio:
            text, detected_lang = transcribe_audio(audio)
            if text:
                timestamp = time.time()
                message_entry = {
                    "user": user_id,
                    "text": text,
                    "lang_detected": SUPPORTED_LANGUAGES.get(detected_lang, detected_lang),
                    "timestamp": timestamp
                }

                # Translate if necessary
                translated_text = text
                if detected_lang != target_lang:
                    translated_text = translate_text(text, target_lang)
                
                message_entry["translated_text"] = translated_text
                
                # Append and save the new message
                messages.append(message_entry)
                save_conversation(room_id, conversation_data)
                st.session_state.status = "" # Clear status after processing
                st.rerun() # Rerun immediately to show the new message
    
    st.markdown("---")
    
    # Conversation History
    st.markdown("### 💬 Conversation History")
    if not messages:
        st.info("The conversation is empty. Click 'Speak' to begin!")

    for msg in reversed(messages):
        css_class = "user1-msg" if msg["user"] == "User 1" else "user2-msg"
        st.markdown(f"""
            <div class="conversation-box {css_class}">
                <b>{msg['user']}</b> <span style='font-size: smaller; color: grey;'>({msg['lang_detected']})</span>:
                <p style='margin-top: 5px;'>{msg['text']}</p>
                <hr style='margin: 5px 0;'>
                <b>Translation:</b>
                <p style='margin: 0;'><em>{msg['translated_text']}</em></p>
            </div>
        """, unsafe_allow_html=True)
    
    # TTS Playback Logic
    if messages:
        last_message = messages[-1]
        # Play only if the last message is from the *other* user and hasn't been played in this session
        if last_message["user"] != user_id and last_message["timestamp"] > st.session_state.last_played_timestamp:
            with st.spinner(f"Playing translation for {user_id}..."):
                 text_to_speech(last_message["translated_text"], target_lang)
            st.session_state.last_played_timestamp = last_message["timestamp"]


def lobby_ui():
    """The UI for creating or joining a room."""
    st.title("Welcome to the Real-Time Translator")
    st.markdown("Create a room to start a new conversation or join an existing one using a room ID.")

    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Create a New Room")
        user1_lang = st.selectbox("Your Language (will be User 1)", list(SUPPORTED_LANGUAGES.keys()), format_func=lambda x: SUPPORTED_LANGUAGES[x], key="create_lang1")
        user2_lang = st.selectbox("The Other User's Language", list(SUPPORTED_LANGUAGES.keys()), format_func=lambda x: SUPPORTED_LANGUAGES[x], key="create_lang2")
        if st.button("Create Room"):
            room_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            st.session_state.room_id = room_id
            st.session_state.user_id = "User 1"
            
            # Create the initial conversation file
            initial_data = {
                "messages": [],
                "user1_lang": user1_lang,
                "user2_lang": user2_lang
            }
            save_conversation(room_id, initial_data)
            st.query_params["room_id"] = room_id
            st.rerun()

    with col2:
        st.subheader("Join an Existing Room")
        join_room_id = st.text_input("Enter Room ID").strip().upper()
        if st.button("Join Room"):
            if os.path.exists(get_room_file(join_room_id)):
                st.session_state.room_id = join_room_id
                st.session_state.user_id = "User 2"
                st.query_params["room_id"] = join_room_id
                st.rerun()
            else:
                st.error("Room not found. Please check the ID.")

# --- Main App Router ---
if st.session_state.room_id and st.session_state.user_id:
    chat_room_ui(st.session_state.room_id, st.session_state.user_id)
else:
    lobby_ui()