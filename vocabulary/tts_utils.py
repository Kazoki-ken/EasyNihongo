import asyncio
import edge_tts
import io

# Valid voices:
# ja-JP-NanamiNeural (Female)
# ja-JP-KeitaNeural (Male)

async def generate_edge_audio(text, voice="ja-JP-NanamiNeural"):
    """
    Generates MP3 audio bytes for the given text using Edge TTS.
    """
    communicate = edge_tts.Communicate(text, voice)
    audio_stream = io.BytesIO()

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_stream.write(chunk["data"])

    audio_stream.seek(0)
    return audio_stream.read()

def get_edge_audio_sync(text, voice="ja-JP-NanamiNeural"):
    """
    Synchronous wrapper for generating Edge TTS audio.
    """
    return asyncio.run(generate_edge_audio(text, voice))
