import os
import pyttsx3
import speech_recognition as sr
import sounddevice as sd
import io
import wave
from groq import Groq

# Load the Groq API key from an environment variable.
client = Groq(api_key=os.getenv("YOUR_KEY_HERE"))

def speak(text):
    print(f"Friday: {text}")
    engine = pyttsx3.init()
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[0].id)
    engine.setProperty('rate', 170)
    engine.say(text)
    engine.runAndWait()
    engine.stop()

def listen():
    r = sr.Recognizer()
    print("Listening... 🎤")

    duration = 5
    sample_rate = 16000
    audio_data = sd.rec(int(duration * sample_rate),
                        samplerate=sample_rate,
                        channels=1,
                        dtype='int16')
    sd.wait()

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
        print(f"You said: {text}")
        return text
    except:
        speak("Sorry I didn't catch that!")
        return ""

def ask_friday(question):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are Friday, a smart AI assistant like from Iron Man. Be helpful, cool and keep answers short."},
            {"role": "user", "content": question}
        ]
    )
    return response.choices[0].message.content

# Start
speak("Hello! I am Friday. I am online and ready to help you.")

while True:
    user_input = listen()

    if not user_input:
        continue

    if "stop" in user_input.lower() or "exit" in user_input.lower():
        speak("Goodbye!")
        break

    reply = ask_friday(user_input)
    speak(reply)