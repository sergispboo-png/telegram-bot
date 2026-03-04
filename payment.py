import uuid
import os
from yookassa import Configuration, Payment

Configuration.account_id = os.getenv("YOOKASSA_SHOP_ID")
Configuration.secret_key = os.getenv("YOOKASSA_SECRET_KEY")


def create_payment(user_id: int, amount: int):

    payment = Payment.create({
        "amount": {
            "value": str(amount),
            "currency": "RUB"
        },
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me/LuxRenderBot"
        },
        "capture": True,
        "description": f"LuxRender balance topup",
        "metadata": {
            "user_id": str(user_id)
        }
    }, uuid.uuid4())

    return {
        "payment_id": payment.id,
        "payment_url": payment.confirmation.confirmation_url
    }
