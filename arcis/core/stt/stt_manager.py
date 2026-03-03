import io
from groq import AsyncGroq
from arcis.logger import LOGGER

_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    """Lazy-initialise a reusable async Groq client."""
    global _client
    if _client is None:
        _client = AsyncGroq()          # reads GROQ_API_KEY from env
    return _client


async def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.wav",
    language: str = "en",
    prompt: str | None = None,
) -> str:
    """
    Transcribe raw audio bytes using Groq Whisper (async, non-blocking).

    Args:
        audio_bytes: The raw audio file content.
        filename: Original filename hint (Groq uses the extension to
                  infer format, e.g. .wav, .mp3, .webm, .ogg).
        language: BCP-47 language code.
        prompt: Optional context / spelling hints for the model.

    Returns:
        The transcribed text string.
    """
    client = _get_client()

    # Wrap bytes in a file-like tuple that httpx can stream
    file_tuple = (filename, io.BytesIO(audio_bytes))

    LOGGER.info(f"STT: transcribing {len(audio_bytes)} bytes ({filename})")

    transcription = await client.audio.transcriptions.create(
        file=file_tuple,
        model="whisper-large-v3-turbo",
        language=language,
        temperature=0.0,
        **({"prompt": prompt} if prompt else {}),
    )

    text = transcription.text.strip()
    LOGGER.info(f"STT: result ({len(text)} chars): {text[:120]}...")
    return text
