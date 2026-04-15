import customtkinter as ctk
import threading
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

# Your API keys
client = Groq(api_key="your_groq_api_key")
SEARCH_API_KEY = "your_search_api_key"

MEMORY_FILE = "memory.json"

ctk.set_appearance_mode("dark")
app = ctk.CTk()
app.title("Maxie AI")
app.geometry("900x650")
app.configure(fg_color="#08001a")
app.resizable(False, False)

PURPLE = "#7c3aed"
DARK_PURPLE = "#0d0025"
LIGHT_PURPLE = "#c4b0ff"
BG = "#08001a"
CARD = "#160035"
BORDER = "#3a1a6e"

main_frame = ctk.CTkFrame(app, fg_color=BG)
main_frame.pack(fill="both", expand=True)

left = ctk.CTkFrame(main_frame, fg_color=DARK_PURPLE, width=200, corner_radius=0,
                     border_width=1, border_color=BORDER)
left.pack(side="left", fill="y")
left.pack_propagate(False)

ctk.CTkLabel(left, text="SEARCH HISTORY", font=ctk.CTkFont(size=10),
             text_color="#7a5aaa").pack(pady=(16,8), padx=12, anchor="w")

history_items = ["Weather", "Barcelona Match", "Open Spotify",
                 "News Today", "Stock Prices", "Restaurants"]

for item in history_items:
    card = ctk.CTkFrame(left, fg_color=CARD, corner_radius=8,
                        border_width=1, border_color=BORDER)
    card.pack(fill="x", padx=10, pady=4)
    ctk.CTkLabel(card, text=item, font=ctk.CTkFont(size=12),
                 text_color=LIGHT_PURPLE).pack(padx=10, pady=6, anchor="w")

center = ctk.CTkFrame(main_frame, fg_color=BG)
center.pack(side="left", fill="both", expand=True)

header = ctk.CTkFrame(center, fg_color=BG, height=50)
header.pack(fill="x", padx=20, pady=10)

ctk.CTkLabel(header, text="✦ MAXIE AI ✦",
             font=ctk.CTkFont(size=22, weight="bold"),
             text_color=LIGHT_PURPLE).pack(side="left")

status_badge = ctk.CTkLabel(header, text="● SLEEPING",
                              font=ctk.CTkFont(size=12, weight="bold"),
                              text_color="#7a5aaa",
                              fg_color=CARD,
                              corner_radius=20,
                              padx=12, pady=4)
status_badge.pack(side="right")

orb_frame = ctk.CTkFrame(center, fg_color=BG, width=220, height=220)
orb_frame.pack(pady=20)
orb_frame.pack_propagate(False)

orb_canvas = ctk.CTkCanvas(orb_frame, width=220, height=220,
                             bg=BG, highlightthickness=0)
orb_canvas.pack()
orb_canvas.create_oval(10, 10, 210, 210, outline=BORDER, width=1)
orb_canvas.create_oval(25, 25, 195, 195, outline=PURPLE, width=2)
orb_circle = orb_canvas.create_oval(80, 80, 140, 140,
                                     fill="#2a0060", outline=PURPLE, width=2)

transcript_label = ctk.CTkLabel(center,
                                  text='Say "Hey Maxie" to wake me up...',
                                  font=ctk.CTkFont(size=13),
                                  text_color="#9a7acc",
                                  wraplength=350)
transcript_label.pack(pady=8)

status_text = ctk.CTkLabel(center, text="Sleeping",
                             font=ctk.CTkFont(size=20, weight="bold"),
                             text_color=LIGHT_PURPLE)
status_text.pack(pady=4)

mic_btn = ctk.CTkButton(center, text="🎤",
                          width=60, height=60,
                          corner_radius=30,
                          fg_color=PURPLE,
                          hover_color="#5a2aaa",
                          font=ctk.CTkFont(size=22))
mic_btn.pack(pady=16)

right = ctk.CTkFrame(main_frame, fg_color=DARK_PURPLE, width=220, corner_radius=0,
                      border_width=1, border_color=BORDER)
right.pack(side="right", fill="y")
right.pack_propagate(False)

ctk.CTkLabel(right, text="CONVERSATION", font=ctk.CTkFont(size=10),
             text_color="#7a5aaa").pack(pady=(16,8), padx=12, anchor="w")

chat_box = ctk.CTkTextbox(right, fg_color=CARD,
                           text_color=LIGHT_PURPLE,
                           font=ctk.CTkFont(size=12),
                           corner_radius=8,
                           border_color=BORDER,
                           border_width=1,
                           wrap="word")
chat_box.pack(fill="both", expand=True, padx=10, pady=10)
chat_box.insert("end", "Maxie is ready...\n\n")
chat_box.configure(state="disabled")

def update_status(badge_text, badge_color, orb_color, status, transcript):
    status_badge.configure(text=f"● {badge_text}", text_color=badge_color)
    orb_canvas.itemconfig(orb_circle, fill=orb_color)
    status_text.configure(text=status)
    transcript_label.configure(text=transcript)

def add_message(sender, message):
    chat_box.configure(state="normal")
    if sender == "You":
        chat_box.insert("end", f"You: {message}\n\n")
    else:
        chat_box.insert("end", f"Maxie: {message}\n\n")
    chat_box.see("end")
    chat_box.configure(state="disabled")

def load_memory():
    system_message = {"role": "system", "content": """You are Maxie, a smart AI assistant like from Iron Man.
    Your name is Maxie. NEVER say Friday. You are ONLY Maxie.
    Be helpful, cool and keep answers short. Remember everything the user tells you.
    If the user says anything like goodbye or farewell, respond with a short goodbye."""}
    if os.path.exists(MEMORY_FILE):
        with open(MEMORY_FILE, "r") as f:
            memory = json.load(f)
        if memory[0]["role"] != "system":
            memory.insert(0, system_message)
        else:
            memory[0] = system_message
        return memory
    return [system_message]

def save_memory(memory):
    with open(MEMORY_FILE, "w") as f:
        json.dump(memory, f)

def speak(text):
    print(f"Maxie: {text}")
    app.after(0, lambda: add_message("Maxie", text))
    app.after(0, lambda: update_status("SPEAKING", PURPLE, PURPLE,
                                        "Speaking...", text[:60] + "..." if len(text) > 60 else text))
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[1].id)
    engine.setProperty('rate', 155)
    engine.setProperty('volume', 1.0)
    engine.say(text)
    engine.runAndWait()
    engine.stop()

def listen(silence_limit=1):
    r = sr.Recognizer()
    sample_rate = 16000
    chunk = 1024
    silent_chunks = 0
    threshold = 500
    audio_chunks = []
    max_duration = 30

    with sd.InputStream(samplerate=sample_rate, channels=1, dtype='int16') as stream:
        while True:
            data, _ = stream.read(chunk)
            audio_chunks.append(data.copy())
            volume = np.abs(data).mean()
            if volume < threshold:
                silent_chunks += 1
            else:
                silent_chunks = 0
            if silent_chunks > int(silence_limit * sample_rate / chunk):
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
        })
        results = response.json().get("results", [])
        if results:
            return " ".join([r["content"][:300] for r in results[:3]])
        return ""
    except:
        return ""

def ask_maxie(question, memory):
    search_result = ""
    if needs_search(question):
        app.after(0, lambda: update_status("SEARCHING", "#f39c12", "#f39c12",
                                            "Searching web...", "Looking up real time info..."))
        search_result = web_search(question)
    if search_result:
        full_question = f"{question}\n\nReal time web info: {search_result}\n\nUse this to answer."
    else:
        full_question = question
    memory.append({"role": "user", "content": full_question})
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=memory
    )
    reply = response.choices[0].message.content
    memory.append({"role": "assistant", "content": reply})
    save_memory(memory)
    return reply

def run_maxie():
    memory = load_memory()
    speak("Hello! I am Maxie. I am online and ready to help you.")

    while True:
        app.after(0, lambda: update_status("SLEEPING", "#7a5aaa", "#2a0060",
                                            "Sleeping", 'Say "Hey Maxie" to wake me up...'))
        while True:
            text = listen(silence_limit=2)
            if text:
                print(f"Heard: {text}")
            if "hey" in text or "maxie" in text or "maxi" in text or "max" in text:
                break

        app.after(0, lambda: update_status("AWAKE", PURPLE, PURPLE,
                                            "Awake!", "Yes? I am here!"))
        speak("Yes? I am here!")

        no_input_count = 0
        while True:
            app.after(0, lambda: update_status("LISTENING", "#2ecc71", "#1a0060",
                                                "Listening...", "Speak now..."))
            user_input = listen(silence_limit=1)

            if not user_input:
                no_input_count += 1
                if no_input_count >= 4:
                    speak("Going to sleep. Say Hey Maxie to wake me!")
                    break
                continue

            no_input_count = 0
            print(f"You said: {user_input}")
            app.after(0, lambda u=user_input: add_message("You", u))

            if "power off" in user_input:
                speak("Powering off. Goodbye!")
                app.after(0, app.quit)
                return

            if is_goodbye(user_input):
                reply = ask_maxie(user_input, memory)
                speak(reply)
                time.sleep(2)
                break

            if "open" in user_input.lower():
                if open_app(user_input):
                    continue

            app.after(0, lambda: update_status("THINKING", PURPLE, "#4a0090",
                                                "Thinking...", "Processing your request..."))
            reply = ask_maxie(user_input, memory)
            speak(reply)

thread = threading.Thread(target=run_maxie, daemon=True)
thread.start()

app.mainloop()