import os
import io
import re
import json
import asyncio
import base64
import tempfile
import scipy.io.wavfile

from pocket_tts import TTSModel


class TTSManager:
    def __init__(self):
        self.tts_model = None
        self.voice_states = {}
        self.default_voice_state = None


    def initialize(self, default_voice: str = "alba"):
        try:
            print("[INFO] Loading TTS model...")
            self.tts_model = TTSModel.load_model()
            print(f"[INFO] TTS model loaded successfully (sample rate: {self.tts_model.sample_rate}Hz)")

            if default_voice:
                print(f"[INFO] Pre-loading default voice state: {default_voice}")
                self.default_voice_state = self.tts_model.get_state_for_audio_prompt(default_voice)
                self.voice_states["default"] = self.default_voice_state
                print("[INFO] Default voice state loaded successfully.")
            else:
                print(f"[WARNING] No default voice provided. First synthesis might lag.")
        except Exception as e:
            error_msg = str(e)
            print(f"[ERROR] Failed to initialize TTS: {error_msg}")


    def update_voice_state_from_bytes(self, voice_id: str, wav_bytes: bytes):
        """Update or add a voice state from uploaded WAV bytes."""
        if not self.tts_model:
            raise RuntimeError("TTS model not initialized")
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                temp_wav.write(wav_bytes)
                temp_path = temp_wav.name
                
            print(f"[INFO] Parsing new voice state for {voice_id}")
            state = self.tts_model.get_state_for_audio_prompt(temp_path)
            self.voice_states[voice_id] = state
            return True
        except Exception as e:
            print(f"[ERROR] Failed to extract voice state: {e}")
            raise e
        finally:
            if 'temp_path' in locals() and os.path.exists(temp_path):
                os.remove(temp_path)


    def _split_into_sentences(self, text: str):
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        return [s.strip() for s in sentences if s.strip()]


    def _generate_sentence_audio_sync(self, voice_state, sentence: str):
        try:
            audio = self.tts_model.generate_audio(voice_state, sentence)
            audio_np = audio.numpy()
            wav_buffer = io.BytesIO()
            scipy.io.wavfile.write(wav_buffer, self.tts_model.sample_rate, audio_np)
            wav_buffer.seek(0)
            audio_bytes = wav_buffer.read()
            return base64.b64encode(audio_bytes).decode()
        except Exception as e:
            print(f"[WARNING] Failed to generate audio for sentence '{sentence[:20]}...': {e}")
            return None


    async def stream_text_and_audio(self, text: str, voice_id: str = "default"):
        """
        Async generator for streaming TTS sentence by sentence via SSE.
        Yields text content and Base64 audio chunks.
        """
        if not self.tts_model:
            yield f"data: {{\"type\": \"error\", \"message\": \"TTS not available\"}}\n\n"
            return
            
        voice_state = self.voice_states.get(voice_id, self.default_voice_state)
        if not voice_state:
            yield f"data: {{\"type\": \"error\", \"message\": \"Voice state '{voice_id}' not found\"}}\n\n"
            return

        sentences = self._split_into_sentences(text)
        loop = asyncio.get_event_loop()
        
        # Stream out the full text first (or we can stream it sentence by sentence)
        yield f"data: {json.dumps({'type': 'text', 'content': text})}\n\n"

        for idx, sentence in enumerate(sentences):
            if len(sentence) > 1:
                try:
                    audio_data = await loop.run_in_executor(
                        None,
                        self._generate_sentence_audio_sync,
                        voice_state,
                        sentence
                    )

                    if audio_data:
                        yield f"data: {json.dumps({'type': 'audio', 'data': audio_data, 'format': 'wav', 'chunk': idx})}\n\n"
                except Exception as e:
                    print(f"[ERROR] TTS stream failed on chunk {idx}: {e}")

        yield f"data: {json.dumps({'type': 'done'})}\n\n"


tts_manager = TTSManager()
