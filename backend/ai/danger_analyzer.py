"""
ai/danger_analyzer.py — AI Danger Detection Module
====================================================
This is the core AI module that analyzes audio recordings
to determine if a woman is in danger.

CURRENT APPROACH (v1 — Beginner Friendly):
  1. Convert audio → WAV (browser records webm/opus)
  2. WAV → text using SpeechRecognition
  3. Search for danger keywords in the transcript
  4. Compute a danger score from matches
  5. Return a structured risk report

FUTURE APPROACH (v2 — Deep Learning):
  - Use Whisper (OpenAI) for better speech-to-text accuracy
  - Classify audio using CNN on mel spectrograms for scream detection
  - Use voice pitch/energy analysis for stress detection
  - Integrate sentiment analysis for emotional context

WHY KEYWORD-BASED FIRST:
  It's interpretable, fast, requires no GPU, and
  can be deployed on any cheap server. Perfect for a
  hackathon/prototype phase.

FORMAT CONVERSION NOTE:
  Browsers record audio as WebM/Opus via MediaRecorder API.
  SpeechRecognition only accepts WAV, AIFF, or FLAC.
  We convert webm → wav using pydub (ffmpeg backend) or
  subprocess ffmpeg as a fallback. If neither is available,
  transcription is skipped gracefully.
"""

import os
import json
import logging
import re
import subprocess
import tempfile

# ─────────────────────────────────────────────────────────
# SETUP LOGGING
# Logs help us trace AI analysis without print statements.
# ─────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# DANGER KEYWORD DICTIONARY
# Multi-language support makes the system inclusive.
# Each keyword has a weight: higher = more dangerous.
#
# MATCHING RULES:
#  - Keywords are matched with word boundaries (\b) to
#    prevent false positives (e.g. "help" won't match "helpful").
#  - Multi-word phrases are checked FIRST (longest match wins)
#    to prevent double-counting ("help me" scores 25, not 20+25).
# ─────────────────────────────────────────────────────────
DANGER_KEYWORDS = {
    # ── English: High severity (30-40) ───────────────────
    "he's hurting me":   40,
    "she's hurting me":  40,
    "hes hurting me":    40,   # without apostrophe (STT variance)
    "call police":       35,
    "call the police":   35,
    "call 911":          35,
    "call 100":          35,
    "dont touch me":     35,
    "don't touch me":    35,
    "bachao mujhe":      35,   # Hindi: "save me" (emphatic)

    # ── English: Medium-high severity (25-30) ────────────
    "save me":           30,
    "save us":           30,
    "let me go":         30,
    "leave me alone":    30,
    "somebody help":     30,
    "help me please":    28,
    "please help me":    28,
    "help me":           25,
    "please help":       25,
    "leave me":          25,
    "im scared":         25,
    "i'm scared":        25,
    "i am scared":       25,

    # ── Hindi/Urdu (transliterated) ──────────────────────
    "bachao":            30,   # "save me"
    "mujhe chhoddo":     30,   # "let me go"
    "chhor do":          30,   # "leave me"
    "madat karo":        25,   # "help me"
    "madad karo":        25,   # alternate spelling
    "madad":             20,   # "help"

    # ── English: Medium severity (15-20) ─────────────────
    "help":              20,
    "danger":            20,
    "emergency":         20,
    "police":            20,
    "no no no":          20,
    "nooo":              20,
    "noooo":             20,
    "stop it":           18,
    "get away":          18,
    "go away":           18,

    # ── Low severity / ambiguous (10-15) ─────────────────
    "aaah":              15,
    "ahhh":              15,
    "stop":              10,
    "no":                 5,
}

# Pre-sort keywords by length (longest first) so multi-word
# phrases are matched before their sub-phrases.
_SORTED_KEYWORDS = sorted(DANGER_KEYWORDS.keys(), key=len, reverse=True)


# ─────────────────────────────────────────────────────────
# RISK LEVEL THRESHOLDS
# Based on the accumulated danger score from keyword matches.
# ─────────────────────────────────────────────────────────
def compute_risk_level(score: float) -> str:
    """
    Convert numeric danger score into a human-readable risk label.

    Score >= 70 → CRITICAL (immediate intervention)
    Score 50–69 → HIGH     (urgent, likely real danger)
    Score 30–49 → MEDIUM   (attention needed)
    Score 1–29  → LOW      (might be false alarm)
    Score 0     → NONE     (no danger indicators)
    """
    if score >= 70:
        return "CRITICAL"
    elif score >= 50:
        return "HIGH"
    elif score >= 30:
        return "MEDIUM"
    elif score > 0:
        return "LOW"
    else:
        return "NONE"


def analyze_text_for_danger(transcript: str) -> dict:
    """
    Core analysis function: given a text transcript,
    find danger keywords and compute a danger score.

    MATCHING STRATEGY:
      1. Normalize text (lowercase, strip punctuation).
      2. Check longest keywords first to prevent double-counting.
      3. Use word-boundary-aware matching to avoid false positives.
      4. Each keyword can only score once per analysis.

    Args:
        transcript (str): The speech-to-text output from audio.

    Returns:
        dict: {
            "danger_score": float,
            "detected_words": list,
            "risk_level": str,
            "transcript": str
        }
    """
    if not transcript:
        return {
            "danger_score": 0.0,
            "detected_words": [],
            "risk_level": "NONE",
            "transcript": ""
        }

    # Normalize: lowercase, collapse whitespace, remove punctuation
    normalized = transcript.lower()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    found_keywords = []
    total_score = 0.0
    # Track which parts of the text have been "consumed" by a match
    # so multi-word phrases don't also trigger their sub-words.
    consumed_text = normalized

    # Check keywords longest-first to prevent double-counting
    for keyword in _SORTED_KEYWORDS:
        # Use word boundary regex for precise matching
        # \b ensures "help" doesn't match inside "helpful"
        pattern = r"\b" + re.escape(keyword) + r"\b"

        if re.search(pattern, consumed_text):
            weight = DANGER_KEYWORDS[keyword]
            found_keywords.append(keyword)
            total_score += weight
            logger.info(f"[AI] Detected keyword: '{keyword}' (+{weight})")

            # Remove matched phrase so sub-words don't double-score
            # e.g. after matching "help me", "help" alone won't match again
            consumed_text = re.sub(pattern, " ", consumed_text, count=1)

    # Cap score at 100 — it's a percentage-like metric
    total_score = min(total_score, 100.0)
    risk_level = compute_risk_level(total_score)

    logger.info(f"[AI] Analysis complete: Score={total_score}, Level={risk_level}, "
                f"Keywords={found_keywords}")

    return {
        "danger_score": round(total_score, 2),
        "detected_words": found_keywords,
        "risk_level": risk_level,
        "transcript": transcript[:500]  # Truncate for storage
    }


# ─────────────────────────────────────────────────────────
# AUDIO FORMAT CONVERSION
# Browser records WebM/Opus → must convert to WAV for STT.
# ─────────────────────────────────────────────────────────

def _convert_to_wav_pydub(audio_path: str) -> str:
    """
    Convert audio file to WAV using pydub (requires ffmpeg on PATH).
    Returns path to the temporary WAV file, or empty string on failure.
    """
    try:
        from pydub import AudioSegment

        # pydub auto-detects format from extension/header
        audio = AudioSegment.from_file(audio_path)

        # Create temp WAV file
        wav_path = audio_path.rsplit(".", 1)[0] + "_converted.wav"
        audio.export(wav_path, format="wav")
        logger.info(f"[CONVERT] pydub: {audio_path} → {wav_path}")
        return wav_path

    except ImportError:
        logger.info("[CONVERT] pydub not installed, skipping.")
        return ""
    except Exception as e:
        logger.warning(f"[CONVERT] pydub conversion failed: {e}")
        return ""


def _convert_to_wav_ffmpeg(audio_path: str) -> str:
    """
    Convert audio file to WAV using ffmpeg subprocess.
    Fallback when pydub is not installed.
    Returns path to the temporary WAV file, or empty string on failure.
    """
    wav_path = audio_path.rsplit(".", 1)[0] + "_converted.wav"
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",        # overwrite output
                "-i", audio_path,      # input file
                "-ar", "16000",        # 16kHz sample rate (good for STT)
                "-ac", "1",            # mono channel
                "-f", "wav",           # output format
                wav_path
            ],
            capture_output=True,
            timeout=30
        )

        if result.returncode == 0 and os.path.exists(wav_path):
            logger.info(f"[CONVERT] ffmpeg: {audio_path} → {wav_path}")
            return wav_path
        else:
            stderr = result.stderr.decode("utf-8", errors="replace")[:200]
            logger.warning(f"[CONVERT] ffmpeg failed (rc={result.returncode}): {stderr}")
            return ""

    except FileNotFoundError:
        logger.info("[CONVERT] ffmpeg not found on PATH, skipping.")
        return ""
    except subprocess.TimeoutExpired:
        logger.warning("[CONVERT] ffmpeg conversion timed out.")
        return ""
    except Exception as e:
        logger.warning(f"[CONVERT] ffmpeg error: {e}")
        return ""


def convert_to_wav(audio_path: str) -> str:
    """
    Convert audio to WAV format. Tries pydub first, then ffmpeg subprocess.

    Args:
        audio_path: Path to the source audio file.

    Returns:
        str: Path to WAV file (may be the original if already WAV),
             or empty string if conversion failed.
    """
    # If already WAV, no conversion needed
    if audio_path.lower().endswith(".wav"):
        return audio_path

    # Try pydub first (most reliable when installed)
    wav_path = _convert_to_wav_pydub(audio_path)
    if wav_path:
        return wav_path

    # Fallback to raw ffmpeg subprocess
    wav_path = _convert_to_wav_ffmpeg(audio_path)
    if wav_path:
        return wav_path

    logger.warning(
        "[CONVERT] No conversion method available. "
        "Install pydub (`pip install pydub`) or ffmpeg for WebM support."
    )
    return ""


# ─────────────────────────────────────────────────────────
# SPEECH-TO-TEXT
# ─────────────────────────────────────────────────────────

def transcribe_audio(audio_path: str) -> str:
    """
    Convert audio file to text using Google Speech Recognition.

    PIPELINE:
      1. Convert to WAV (if webm/ogg/mp3/etc.)
      2. Load WAV via SpeechRecognition
      3. Send to Google Web Speech API
      4. Clean up temp WAV file

    WHY GOOGLE API (for prototype):
    - Free tier available (unlimited for short audio)
    - No API key required for basic usage
    - Works with any internet connection

    PRODUCTION UPGRADE:
    - Replace with OpenAI Whisper (local model, no API key needed)
    - pip install openai-whisper

    Args:
        audio_path: Absolute path to the audio file.

    Returns:
        str: Transcribed text or empty string on failure.
    """
    wav_path = None
    try:
        import speech_recognition as sr

        # STEP 1: Convert to WAV if needed
        wav_path = convert_to_wav(audio_path)
        if not wav_path:
            logger.warning(
                f"[STT] Cannot convert {audio_path} to WAV. "
                "Transcription skipped — keyword analysis unavailable."
            )
            return ""

        # STEP 2: Load WAV and transcribe
        recognizer = sr.Recognizer()

        # Tune noise reduction for better accuracy
        recognizer.energy_threshold = 300
        recognizer.dynamic_energy_threshold = True
        recognizer.pause_threshold = 0.8

        with sr.AudioFile(wav_path) as source:
            # Adjust for ambient noise in the first 0.5s
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            audio_data = recognizer.record(source)

        # Try Google Web Speech API with en-IN (Indian English) and fallback
        transcript = ""
        try:
            transcript = recognizer.recognize_google(audio_data, language="en-IN")
        except sr.UnknownValueError:
            # Speech was unintelligible — try Hindi
            try:
                transcript = recognizer.recognize_google(audio_data, language="hi-IN")
                logger.info("[STT] Fallback to Hindi recognition succeeded.")
            except (sr.UnknownValueError, sr.RequestError):
                logger.info("[STT] Audio contains no recognizable speech.")
                return ""
        except sr.RequestError as e:
            logger.warning(f"[STT] Google API request failed: {e}")
            return ""

        logger.info(f"[STT] Transcribed: '{transcript}'")
        return transcript

    except ImportError:
        logger.warning("[STT] SpeechRecognition not installed. Run: pip install SpeechRecognition")
        return ""
    except Exception as e:
        logger.warning(f"[STT] Transcription failed: {e}")
        return ""
    finally:
        # Clean up temporary WAV file (only if we created one)
        if wav_path and wav_path != audio_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
                logger.info(f"[STT] Cleaned up temp WAV: {wav_path}")
            except OSError:
                pass


# ─────────────────────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────────────────────

def analyze_audio_file(audio_path: str) -> dict:
    """
    Full pipeline: audio file → conversion → transcription → danger analysis.

    This is the main function called by the Flask route.

    Pipeline:
      1. Verify file exists
      2. Convert to WAV (webm/ogg → wav)
      3. Transcribe WAV → text
      4. Analyze text for danger keywords
      5. (Optional) Analyze audio energy with librosa
      6. Return structured result

    Args:
        audio_path: Path to uploaded audio file.

    Returns:
        dict: Complete danger analysis result.
    """
    logger.info(f"[AI] Starting analysis for: {audio_path}")

    # STEP 1: Check if file exists before processing
    if not os.path.exists(audio_path):
        logger.error(f"[AI] Audio file not found: {audio_path}")
        return {
            "danger_score": 0.0,
            "detected_words": [],
            "risk_level": "UNKNOWN",
            "transcript": "",
            "error": "Audio file not found"
        }

    # STEP 2: Try to transcribe audio to text
    transcript = transcribe_audio(audio_path)

    # STEP 3: Analyze the transcript for danger keywords
    if transcript:
        analysis = analyze_text_for_danger(transcript)
    else:
        # No transcript available — return UNKNOWN instead of NONE.
        # NONE means "analyzed and found safe". UNKNOWN means
        # "couldn't determine" (STT failed, no speech, format issue).
        analysis = {
            "danger_score": 0.0,
            "detected_words": [],
            "risk_level": "UNKNOWN",
            "transcript": "",
            "note": "Transcription unavailable — audio could not be analyzed for keywords."
        }

    # STEP 4: Add audio metadata using librosa (optional, graceful fallback)
    try:
        import librosa
        audio_array, sample_rate = librosa.load(audio_path, sr=None, duration=30)

        # Compute RMS energy — loud audio might indicate screaming
        rms_energy = float(librosa.feature.rms(y=audio_array).mean())

        # High RMS energy boosts danger score slightly
        if rms_energy > 0.1:
            energy_boost = min(rms_energy * 100, 20)  # max +20 points
            analysis["danger_score"] = min(analysis["danger_score"] + energy_boost, 100.0)
            analysis["risk_level"] = compute_risk_level(analysis["danger_score"])
            logger.info(f"[AI] Audio energy boost: +{energy_boost:.1f} (RMS={rms_energy:.4f})")

        analysis["audio_duration"] = round(float(librosa.get_duration(y=audio_array, sr=sample_rate)), 2)
        analysis["sample_rate"] = int(sample_rate)

    except ImportError:
        logger.info("[AI] librosa not installed. Skipping audio energy analysis.")
    except Exception as e:
        logger.warning(f"[AI] librosa analysis failed: {e}")

    logger.info(f"[AI] Final result: {json.dumps(analysis, indent=2)}")
    return analysis
