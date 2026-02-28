import os
import aiohttp
import logging
import base64

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


async def generate_image_openrouter(prompt: str, model: str, format_value: str):
    try:
        headers = {
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
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
                    return {"error": f"Invalid response: {data}"}

                message = data["choices"][0]["message"]

                if "images" not in message or not message["images"]:
                    return {"error": f"No images in response: {data}"}

                image_obj = message["images"][0]

                # --- Вариант 1: image_url ---
                if "image_url" in image_obj:
                    url = image_obj["image_url"]["url"]

                    # 🔥 DATA URI (base64 внутри)
                    if url.startswith("data:image"):
                        base64_data = url.split("base64,")[1]
                        image_bytes = base64.b64decode(base64_data)
                        return {"image_bytes": image_bytes}

                    # 🔥 Обычный URL
                    async with session.get(url) as img_resp:
                        if img_resp.status != 200:
                            return {"error": f"Image download failed: {img_resp.status}"}
                        image_bytes = await img_resp.read()
                        return {"image_bytes": image_bytes}

                return {"error": "Unknown image format in response"}

    except Exception as e:
        logging.exception("OpenRouter generation error")
        return {"error": str(e)}
