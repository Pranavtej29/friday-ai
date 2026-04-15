from flask import Flask, jsonify, request
from flask_cors import CORS
import speech_recognition as sr
import sounddevice as sd
import io
import wave
import json
import os
import numpy as np
import time
import requests
import pyttsx3
import threading
import subprocess
from groq import Groq
import config

app = Flask(__name__)
CORS(app)

client = Groq(api_key=config.GROQ_API_KEY)
SEARCH_API_KEY = config.SEARCH_API_KEY
ELEVENLABS_KEY = config.ELEVENLABS_KEY
# The previous Voice from the library requires a paid subscription. We use "Bella" instead, a default female voice available to free accounts.
ELEVENLABS_VOICE_ID = "EXAVITQu4vr4xnSDxMaL"  
MEMORY_FILE = "memory.json"

state = {
    "status": "sleeping",
    "transcript": "Say Hey Maxie to wake me up...",
    "last_reply": "",
    "conversation": []
}

def load_memory():
    system_message = {"role": "system", "content": """You are Maxie, a smart AI assistant like from Iron Man.
    Your name is Maxie. NEVER say Friday. You are ONLY Maxie.
    Be helpful, cool and keep answers short. Remember everything the user tells you.
    If the user says anything like goodbye or farewell, respond with a short goodbye."""}
    if os.path.exists(MEMORY_FILE):
        try:
            with open(MEMORY_FILE, "r") as f:
                memory = json.load(f)
            if not memory:
                return [system_message]
            if memory[0]["role"] != "system":
                memory.insert(0, system_message)
            else:
                memory[0] = system_message
            return memory
        except Exception:
            pass
    return [system_message]

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f)

def speak_elevenlabs(text):
    try:
        # Request PCM format directly to play with sounddevice instead of requiring ffplay
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}?output_format=pcm_24000"
        headers = {
            "xi-api-key": ELEVENLABS_KEY,
            "Content-Type": "application/json"
        }
        data = {
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.8
            }
        }
        response = requests.post(url, headers=headers, json=data, timeout=10)
        if response.status_code == 200:
            audio_data = np.frombuffer(response.content, dtype=np.int16)
            sd.play(audio_data, samplerate=24000)
            sd.wait()
            return True
        return False
    except Exception as e:
        print(f"ElevenLabs error: {e}")
        return False

def speak_fallback(text):
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[1].id)
    engine.setProperty('rate', 155)
    engine.say(text)
    engine.runAndWait()
    engine.stop()

def speak(text):
    print(f"Maxie: {text}")
    state["last_reply"] = text
    state["transcript"] = text
    state["conversation"].append({"sender": "Maxie", "text": text})
    if not speak_elevenlabs(text):
        speak_fallback(text)

def listen(silence_limit=1.5, timeout=5.0):
    r = sr.Recognizer()
    sample_rate = 16000
    chunk = 1024
    silent_chunks = 0
    total_chunks = 0
    threshold = 500
    audio_chunks = []
    max_duration = 30
    has_spoken = False

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
        while True:
            data, _ = stream.read(chunk)
            audio_chunks.append(data.copy())
            total_chunks += 1
            volume = np.abs(data).mean()
            if volume < threshold:
                silent_chunks += 1
            else:
                silent_chunks = 0
                has_spoken = True
                
            if not has_spoken and total_chunks > int(timeout * sample_rate / chunk):
                return ""
                
            if has_spoken and silent_chunks > int(silence_limit * sample_rate / chunk):
                break
                
            if len(audio_chunks) > int(max_duration * sample_rate / chunk):
                break

    audio_data = np.concatenate(audio_chunks, axis=0)
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
    wav_buffer.seek(0)

    with sr.AudioFile(wav_buffer) as source:
        audio = r.record(source)
    try:
        return r.recognize_google(audio).lower()
    except:
        return ""

def is_goodbye(text):
    goodbye_words = ["bye", "goodbye", "talk to you later", "reach out",
                     "im busy", "i'm busy", "talk later", "will talk later",
                     "good night", "gotta go", "catch you later",
                     "see you later", "i'll see you", "ill see you"]
    return any(word in text.lower() for word in goodbye_words)

def open_app(text):
    apps = {
        "youtube": "https://www.youtube.com",
        "whatsapp": "https://web.whatsapp.com",
        "instagram": "https://www.instagram.com",
        "spotify": "spotify:",
        "google": "https://www.google.com",
        "gmail": "https://mail.google.com",
        "netflix": "https://www.netflix.com",
        "twitter": "https://www.twitter.com",
        "github": "https://www.github.com",
        "calculator": "calc",
        "notepad": "notepad",
        "settings": "ms-settings:",
    }
    for app_name, command in apps.items():
        if app_name in text.lower():
            speak(f"Opening {app_name}!")
            os.system(f"start {command}")
            return True
    return False

def needs_search(text):
    search_words = ["weather", "news", "score", "match", "today", "tomorrow",
                    "current", "latest", "price", "stock", "who won",
                    "what happened", "when is", "how much", "search", "look up"]
    return any(word in text.lower() for word in search_words)

def web_search(query):
    try:
        if "weather" in query.lower():
            query += " exact temperature celsius humidity today"
        response = requests.post("https://api.tavily.com/search", json={
            "api_key": SEARCH_API_KEY,
            "query": query,
            "max_results": 3
        }, timeout=8)
        results = response.json().get("results", [])
        if results:
            return " ".join([r["content"][:300] for r in results[:3]])
        return ""
    except:
        return ""

def ask_maxie(question, memory):
    search_result = ""
    if needs_search(question):
        state["status"] = "searching"
        search_result = web_search(question)
    if search_result:
        full_question = f"{question}\n\nReal time web info: {search_result}\n\nUse this to answer."
    else:
        full_question = question
        
    messages = memory.copy()
    messages.append({"role": "user", "content": full_question})
    
    if len(messages) > 21:
        messages = [messages[0]] + messages[-20:]

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            timeout=10
        )
        reply = response.choices[0].message.content
    except Exception as e:
        print(f"Groq API Error: {e}")
        reply = "Sorry, I had trouble thinking about that or connecting to my brain."

    memory.append({"role": "user", "content": question})
    memory.append({"role": "assistant", "content": reply})
    
    if len(memory) > 31:
        memory = [memory[0]] + memory[-30:]
        
    save_memory(memory)
    return reply

def run_maxie():
    memory = load_memory()
    speak("Hello! I am Maxie. I am online and ready to help you.")

    while True:
        state["status"] = "sleeping"
        state["transcript"] = 'Say "Hey Maxie" to wake me up...'
        
        # Wake word detection
        command = ""
        while True:
            text = listen(silence_limit=1.5, timeout=5.0)
            if text:
                print(f"Heard: {text}")
                
            trigger_words = ["hey maxie", "hey maxi", "maxie", "maxi", "hey max", "hello maxie"]
            triggered = False
            for word in trigger_words:
                if word in text:
                    triggered = True
                    # Extract whatever follows the wake word
                    idx = text.find(word) + len(word)
                    command = text[idx:].strip()
                    break
            
            if triggered:
                break

        state["status"] = "awake"
        first_turn = True
        
        while True:
            if first_turn and command:
                user_input = command
                state["conversation"].append({"sender": "You", "text": "hey maxie " + user_input})
                first_turn = False
            else:
                if first_turn:
                    speak("Yes? I am here!")
                    first_turn = False
                
                state["status"] = "listening"
                state["transcript"] = "Speak now..."
                user_input = listen(silence_limit=1.5, timeout=5.0)

                if not user_input:
                    speak("Going back to sleep.")
                    break

                print(f"You said: {user_input}")
                state["conversation"].append({"sender": "You", "text": user_input})

            # Process the input
            if "power off" in user_input:
                speak("Powering off. Goodbye!")
                os._exit(0)

            if is_goodbye(user_input):
                reply = ask_maxie(user_input, memory)
                speak(reply)
                time.sleep(2)
                break

            if "open" in user_input.lower():
                if open_app(user_input):
                    continue

            state["status"] = "thinking"
            state["transcript"] = "Thinking..."
            reply = ask_maxie(user_input, memory)
            speak(reply)

@app.route('/state')
def get_state():
    return jsonify(state)

@app.route('/conversation')
def get_conversation():
    return jsonify(state["conversation"])

if __name__ == '__main__':
    t = threading.Thread(target=run_maxie, daemon=True)
    t.start()
    app.run(port=5000)
