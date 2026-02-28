import os
import aiohttp
import base64

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def generate_image_openrouter(prompt: str, model: str, format_value: str):
    """
    Генерация изображения через OpenRouter API
    Поддерживает модели с output_modalities=image
    """

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    # payload для генерации изображения
    payload = {
        "model": model,
        "input": [
            {
                "role": "user",
                "content": prompt
            }
        ],
        "modalities": ["image"],
        # дополнительные параметры по желанию
        # "image_config": {"aspect": format_value}
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(OPENROUTER_URL, json=payload, headers=headers) as response:
            data = await response.json()

            # Если ошибка
            if response.status != 200:
                return {"error": data}

            # иногда API возвращает base64 в
            # candidates[0].content.parts[].inline_data.data
            try:
                parts = data["output"][0]["content"]
            except Exception:
                return {"error": data}

            # ищем base64
            for part in parts:
                inline = part.get("inline_data")
                if inline and inline.get("type") == "image":
                    b64 = inline.get("data")
                    img_bytes = base64.b64decode(b64)
                    return {"image_bytes": img_bytes}

            return {"error": "no_image_found"}
