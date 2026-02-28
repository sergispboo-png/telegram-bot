import os
import aiohttp
import base64

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def generate_image_openrouter(prompt: str, model: str, format_value: str):

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://yourapp.com",  # обязательно для OpenRouter
        "X-Title": "LuxRenderBot"
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(OPENROUTER_URL, json=payload, headers=headers) as response:
            data = await response.json()

            if response.status != 200:
                return {"error": data}

            try:
                # Gemini Flash Image возвращает base64 внутри message.content
                content = data["choices"][0]["message"]["content"]

                # Иногда content это строка base64 напрямую
                img_bytes = base64.b64decode(content)

                return {"image_bytes": img_bytes}

            except Exception:
                return {"error": data}
