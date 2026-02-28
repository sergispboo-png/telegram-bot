import os
import aiohttp
import base64

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def generate_image_openrouter(prompt: str, model: str, format_value: str):

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://luxrender.app",
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
            print("OPENROUTER RESPONSE:", data)

            if response.status != 200:
                return {"error": data}

            try:
                message = data["choices"][0]["message"]

                # 🔥 Вот правильное извлечение изображения
                image_data_url = message["images"][0]["image_url"]["url"]

                # Убираем префикс data:image/png;base64,
                base64_data = image_data_url.split(",")[1]

                image_bytes = base64.b64decode(base64_data)

                return {"image_bytes": image_bytes}

            except Exception as e:
                print("PARSE ERROR:", e)
                return {"error": "Failed to parse image response"}
