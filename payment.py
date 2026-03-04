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
            "return_url": "https://t.me/YOUR_BOT_USERNAME"
        },
        "capture": True,
        "description": f"Пополнение баланса LuxRender {user_id}",
        "metadata": {
            "user_id": user_id
        }
    }, uuid.uuid4())

    return payment.confirmation.confirmation_url
