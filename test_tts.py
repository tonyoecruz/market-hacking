
import asyncio
import nest_asyncio
import edge_tts
import tempfile
import os

nest_asyncio.apply()

async def test_tts():
    print("Starting TTS generation...")
    voice = "pt-BR-FranciscaNeural"
    text = "Teste de áudio."
    comm = edge_tts.Communicate(text, voice)
    fname = os.path.join(tempfile.gettempdir(), "test_tts.mp3")
    await comm.save(fname)
    print(f"File created at: {fname}")
    return fname

def main():
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            print("Loop is running, using nest_asyncio patch...")
            loop.run_until_complete(test_tts())
        else:
            print("Loop is not running, starting it...")
            loop.run_until_complete(test_tts())
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
