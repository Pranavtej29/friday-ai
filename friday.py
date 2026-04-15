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
from groq import Groq
import config

# Your API keys
client = Groq(api_key=config.GROQ_API_KEY)
SEARCH_API_KEY = config.SEARCH_API_KEY

MEMORY_FILE = "memory.json"

def load_memory():
    system_message = {"role": "system", "content": """You are Maxie, a smart AI assistant like from Iron Man.
    Your name is Maxie. NEVER say Friday. NEVER say any other name. You are ONLY Maxie.
    Be helpful, cool and keep answers short. Remember everything the user tells you.
    IMPORTANT: If the user says anything like they are leaving, busy, will talk later, goodbye, or any farewell,
    always respond with a short goodbye like 'Okay, talk to you later!' or 'Got it, I ll be here!' and nothing else."""}
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

def speak(text):
    print(f"Maxie: {text}")
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[1].id)
    engine.setProperty('rate', 155)
    engine.setProperty('volume', 1.0)
    engine.say(text)
    engine.runAndWait()
    engine.stop()

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

            chunks_for_silence = int(silence_limit * sample_rate / chunk)
            if has_spoken and silent_chunks > chunks_for_silence:
                break

            max_chunks = int(max_duration * sample_rate / chunk)
            if len(audio_chunks) > max_chunks:
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
        text = r.recognize_google(audio)
        return text.lower()
    except:
        return ""

def wait_for_wake_word():
    print("💤 Sleeping... say 'Hey Maxie' to wake me up!")
    while True:
        text = listen(silence_limit=1)
        if text:
            print(f"Heard: {text}")
        if "hey" in text or "maxie" in text or "maxi" in text or "max" in text:
            print("✅ Wake word detected!")
            speak("Yes? I am here!")
            return

def is_goodbye(text):
    goodbye_words = [
        "bye", "goodbye", "talk to you later", "reach out",
        "im busy", "i'm busy", "talk later", "will talk later",
        "ill talk later", "i'll talk later", "good night", "gotta go",
        "catch you later", "see you later", "i'll see you", "ill see you"
    ]
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

    for app, command in apps.items():
        if app in text.lower():
            speak(f"Opening {app}!")
            if command.startswith("http"):
                os.system(f"start {command}")
            else:
                os.system(f"start {command}")
            return True
    return False

def needs_search(text):
    search_words = [
        "weather", "news", "score", "match", "today", "tomorrow",
        "current", "latest", "price", "stock", "who won", "what happened",
        "when is", "how much", "tell me about", "search", "look up"
    ]
    return any(word in text.lower() for word in search_words)

def web_search(query):
    try:
        if "weather" in query.lower():
            query = query + " exact temperature celsius humidity today"
        url = "https://api.tavily.com/search"
        response = requests.post(url, json={
            "api_key": SEARCH_API_KEY,
            "query": query,
            "max_results": 3
        })
        data = response.json()
        results = data.get("results", [])
        if results:
            summary = " ".join([r["content"][:300] for r in results[:3]])
            return summary
        return ""
    except:
        return ""

def ask_maxie(question, memory):
    search_result = ""
    if needs_search(question):
        print("🔍 Searching the web...")
        search_result = web_search(question)

    if search_result:
        full_question = f"{question}\n\nHere is real time info from the web: {search_result}\n\nUse this info to answer."
    else:
        full_question = question

    messages = memory.copy()
    messages.append({"role": "user", "content": full_question})
    
    if len(messages) > 21:
        messages = [messages[0]] + messages[-20:]

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            timeout=15
        )
        reply = response.choices[0].message.content
    except Exception as e:
        print(f"Groq API Error: {e}")
        reply = "Sorry, I had trouble searching for that."

    memory.append({"role": "user", "content": question})
    memory.append({"role": "assistant", "content": reply})
    
    if len(memory) > 31:
        memory = [memory[0]] + memory[-30:]

    save_memory(memory)

    return reply

# Start
memory = load_memory()
speak("Hello! I am Maxie. I am online and ready to help you.")

while True:
    wait_for_wake_word()

    no_input_count = 0
    while True:
        print("Listening... 🎤")
        user_input = listen(silence_limit=1.5, timeout=5.0)

        if not user_input:
            speak("Going to sleep. Say Hey Maxie to wake me!")
            break

        print(f"You said: {user_input}")

        if "power off" in user_input:
            speak("Powering off. Goodbye!")
            exit()

        if is_goodbye(user_input):
            reply = ask_maxie(user_input, memory)
            speak(reply)
            time.sleep(2)
            break

        if "open" in user_input.lower():
            if open_app(user_input):
                continue

        reply = ask_maxie(user_input, memory)
        speak(reply)