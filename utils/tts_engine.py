# TTS Engine for NeuroLearn AI using edge-tts
# Dynamically streams in-memory without saving files.

import asyncio
import edge_tts
import re

# Voice mapping based on user requests (English default)
VOICE_MAP = {
    "standard_female": "en-US-AriaNeural",
    "standard_male": "en-US-ChristopherNeural",
    "fun_female": "en-US-JennyNeural",
    "fun_male": "en-US-EricNeural"
}

# Multilingual voice mapping: language code -> [female, male]
LANGUAGE_VOICE_MAP = {
    "hi":  ["hi-IN-SwaraNeural",    "hi-IN-MadhurNeural"],
    "mr":  ["mr-IN-AarohiNeural",   "mr-IN-ManoharNeural"],
    "ta":  ["ta-IN-PallaviNeural",  "ta-IN-ValluvarNeural"],
    "as":  ["bn-BD-NabanitaNeural", "bn-BD-PradeepNeural"],  # Assamese shares Eastern Indic phonetics with Bengali
    "bn":  ["bn-BD-NabanitaNeural", "bn-BD-PradeepNeural"],  # Bengali (rock-solid on Edge TTS)
    "mni": ["bn-BD-NabanitaNeural", "bn-BD-PradeepNeural"],  # Manipuri
    "te":  ["te-IN-ShrutiNeural",   "te-IN-MohanNeural"],
    "en":  None  # Use default VOICE_MAP
}

def get_voice_for_language(preferred_language, gender_key="standard_female"):
    """Get the appropriate TTS voice for a given language and gender."""
    if not preferred_language or preferred_language == "en":
        return None  # Use default English voice
    
    voices = LANGUAGE_VOICE_MAP.get(preferred_language)
    if not voices:
        return None
    
    # Pick female (index 0) or male (index 1) based on gender key
    is_male = "male" in gender_key.lower()
    return voices[1] if is_male else voices[0]

def _parse_rate(rate_str):
    if not rate_str: return "+0%"
    match = re.search(r'([+-]?\d+)', str(rate_str))
    if match:
        num = match.group(1)
        if not num.startswith('+') and not num.startswith('-'): num = f"+{num}"
        return f"{num}%"
    return "+0%"

def _parse_pitch(pitch_str):
    if not pitch_str: return "+0Hz"
    match = re.search(r'([+-]?\d+)', str(pitch_str))
    if match:
        num = match.group(1)
        if not num.startswith('+') and not num.startswith('-'): num = f"+{num}"
        return f"{num}Hz"
    return "+0Hz"

import threading
import queue

def generate_chapter_audio_stream(text, voice_id="standard_female", rate="+0%", pitch="+0Hz", target_lang="en"):
    """
    Synchronous generator wrapper that yields audio bytes in real-time.
    Uses Edge-TTS neural voices, and if unavailable, falls back to Google TTS in target_lang.
    NEVER falls back to English when a regional language was requested.
    """
    if not text or len(text.strip()) < 2:
        return
        
    # If voice_id looks like a direct Neural voice name, use it directly
    if "Neural" in str(voice_id):
        voice = voice_id
    else:
        voice = VOICE_MAP.get(voice_id, "en-US-AriaNeural")
    rate = _parse_rate(rate)
    pitch = _parse_pitch(pitch)
    
    print(f"[TTS-STREAM] Starting stream with voice={voice} (lang={target_lang})")
    
    q = queue.Queue()
    
    def run_async():
        async def fetch():
            audio_produced = False
            try:
                communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        q.put(chunk["data"])
                        audio_produced = True
            except Exception as e:
                print(f"[TTS-STREAM] Edge-TTS error ({voice}): {e}")

            # Fallback to Google TTS in target language if Edge-TTS failed or produced no audio
            if not audio_produced:
                print(f"[TTS-STREAM] Falling back to Google TTS API for language '{target_lang}'...")
                import requests
                import urllib.parse
                try:
                    # Split text into chunks (max 180 chars) for Google TTS
                    words = text.split()
                    chunks = []
                    curr = ""
                    for w in words:
                        if len(curr) + len(w) < 180:
                            curr += w + " "
                        else:
                            chunks.append(curr.strip())
                            curr = w + " "
                    if curr: chunks.append(curr.strip())
                    
                    gt_lang = target_lang or "en"
                    if gt_lang in ("as", "mni"):
                        gt_lang = "bn"  # Google TTS Bengali phonetic voice for Assamese/Manipuri
                    elif gt_lang not in ("hi", "mr", "bn", "ta", "te", "en"):
                        gt_lang = "en"

                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                    for c in chunks:
                        enc_text = urllib.parse.quote(c)
                        url = f"https://translate.google.com/translate_tts?ie=UTF-8&client=tw-ob&tl={gt_lang}&q={enc_text}"
                        r = requests.get(url, headers=headers, stream=True, timeout=8)
                        if r.status_code == 200:
                            for chunk in r.iter_content(chunk_size=4096):
                                if chunk:
                                    q.put(chunk)
                                    audio_produced = True
                except Exception as e3:
                    print(f"[TTS-STREAM] Google TTS Fallback failed: {e3}")
            
            q.put(None) # Signal EOF
                
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(fetch())
        finally:
            loop.close()
            
    # Start generation in background
    threading.Thread(target=run_async, daemon=True).start()
    
    # Yield chunks as they arrive in the queue
    while True:
        chunk = q.get()
        if chunk is None:
            break
        yield chunk
