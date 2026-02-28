import aiohttp
import logging
from config import OPENROUTER_API_KEY, OPENROUTER_MODEL

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

async def generate_image(prompt: str) -> bytes:
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt}
                ]
            }
        ]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(OPENROUTER_URL, headers=headers, json=payload) as resp:
            data = await resp.json()

            logging.info(f"OpenRouter response: {data}")

            if "choices" not in data:
                raise Exception(f"Invalid response: {data}")

            message = data["choices"][0]["message"]

            if "images" not in message or not message["images"]:
                raise Exception(f"No images in response: {data}")

            image_url = message["images"][0]["image_url"]["url"]

            async with session.get(image_url) as img_resp:
                if img_resp.status != 200:
                    raise Exception(f"Image download failed: {img_resp.status}")

                return await img_resp.read()
