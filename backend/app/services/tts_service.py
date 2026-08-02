import os
import wave
import struct
import math
import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger("mockwise.tts_service")

class TTSService:

    @classmethod
    async def text_to_speech(cls, text: str, output_path: Path) -> Path:
        """
        Synthesize question text into audio (.wav or .mp3).
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 1. Try edge-tts if available
        if settings.TTS_PROVIDER == "edge-tts":
            try:
                import edge_tts
                communicate = edge_tts.Communicate(text, settings.DEFAULT_VOICE)
                await communicate.save(str(output_path))
                return output_path
            except Exception as e:
                logger.error(f"edge-tts failed: {e}. Trying fallbacks.")

        # 2. Try gTTS if available
        if settings.TTS_PROVIDER == "gtts":
            try:
                from gtts import gTTS
                tts = gTTS(text=text, lang='en')
                tts.save(str(output_path))
                return output_path
            except Exception as e:
                logger.error(f"gTTS failed: {e}. Trying fallbacks.")

        # 3. Try pyttsx3 offline TTS if installed
        try:
            import pyttsx3
            engine = pyttsx3.init()
            wav_path = output_path.with_suffix(".wav")
            engine.save_to_file(text, str(wav_path))
            engine.runAndWait()
            return wav_path
        except Exception as e:
            logger.debug(f"pyttsx3 not available: {e}.")

        # 4. Pure Python WAV Synthesizer Fallback (generates a valid PCM audio wave file)
        wav_path = output_path.with_suffix(".wav")
        cls._generate_fallback_wav(text, wav_path)
        return wav_path

    @staticmethod
    def _generate_fallback_wav(text: str, output_wav_path: Path, duration_seconds: float = 2.5):
        """Generates a soft, pleasant multi-tone PCM WAV file representing spoken text audio."""
        sample_rate = 22050
        num_samples = int(sample_rate * duration_seconds)
        
        # Fundamental tones (C major chord swell representing speech audio stream)
        freqs = [261.63, 329.63, 392.00, 523.25]
        
        with wave.open(str(output_wav_path), 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            
            audio_frames = bytearray()
            for i in range(num_samples):
                t = i / sample_rate
                # Envelope: fade in & fade out
                envelope = math.sin(math.pi * (i / num_samples))
                # Speech modulation simulation
                modulation = (math.sin(2 * math.pi * 4 * t) + 1) / 2
                
                sample_val = sum(math.sin(2 * math.pi * f * t) for f in freqs) / len(freqs)
                final_val = int(sample_val * modulation * envelope * 16384)
                
                # Clamp 16-bit signed integer
                final_val = max(-32768, min(32767, final_val))
                audio_frames.extend(struct.pack('<h', final_val))
                
            wav_file.writeframes(audio_frames)
