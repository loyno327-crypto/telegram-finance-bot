import datetime
import logging
import os
from urllib.parse import urlparse

import requests
from flask import Flask, jsonify, request

TOKEN = os.environ.get("TOKEN") or os.environ.get("TELEGRAM_BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL") or os.environ.get("RENDER_EXTERNAL_URL")
WEBHOOK_PATH = os.environ.get("WEBHOOK_PATH", "/webhook")
TELEGRAM_API_BASE = "https://api.telegram.org"

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

users = {}
_webhook_initialized = False


def telegram_api_url(method: str) -> str:
    if not TOKEN:
        raise RuntimeError("Telegram bot token is not configured")
    return f"{TELEGRAM_API_BASE}/bot{TOKEN}/{method}"


def normalize_webhook_url() -> str | None:
    if not WEBHOOK_URL:
        return None

    url = WEBHOOK_URL.rstrip("/")
    parsed = urlparse(url)
    if not parsed.scheme:
        url = f"https://{url}"
        parsed = urlparse(url)

    path = parsed.path.rstrip("/")
    if path.endswith(WEBHOOK_PATH):
        return url

    return f"{url}{WEBHOOK_PATH}"


def call_telegram(method: str, payload: dict | None = None) -> dict:
    response = requests.post(telegram_api_url(method), json=payload or {}, timeout=20)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API error for {method}: {data}")
    return data


def send_message(chat_id, text, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    if keyboard:
        payload["reply_markup"] = keyboard

    try:
        call_telegram("sendMessage", payload)
    except Exception:
        app.logger.exception("Failed to send message to chat_id=%s", chat_id)



def ensure_webhook():
    global _webhook_initialized

    if _webhook_initialized:
        return
    _webhook_initialized = True

    if not TOKEN:
        app.logger.warning(
            "Telegram token is missing. Set TOKEN or TELEGRAM_BOT_TOKEN to enable bot replies."
        )
        return

    webhook_url = normalize_webhook_url()
    if not webhook_url:
        app.logger.warning(
            "Webhook URL is missing. Set WEBHOOK_URL or RENDER_EXTERNAL_URL so Telegram knows where to send updates."
        )
        return

    try:
        current = call_telegram("getWebhookInfo").get("result", {})
        if current.get("url") == webhook_url:
            app.logger.info("Telegram webhook already configured: %s", webhook_url)
            return

        call_telegram("setWebhook", {"url": webhook_url, "drop_pending_updates": False})
        app.logger.info("Telegram webhook configured: %s", webhook_url)
    except Exception:
        app.logger.exception("Failed to configure Telegram webhook")


@app.before_request
def initialize_once():
    ensure_webhook()


@app.route("/", methods=["GET"])
def health():
    return jsonify(
        {
            "ok": True,
            "service": "telegram-finance-bot",
            "webhook_path": WEBHOOK_PATH,
            "token_configured": bool(TOKEN),
            "webhook_url_configured": bool(normalize_webhook_url()),
        }
    ), 200


@app.route(WEBHOOK_PATH, methods=["POST"])
@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}
    app.logger.info("Incoming update keys: %s", list(data.keys()))

    if "message" not in data:
        return "ok", 200

    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    user = message.get("from", {})
    user_name = user.get("first_name", "User")

    if text == "/start":
        users[chat_id] = {"step": None}
        send_message(
            chat_id,
            f"Привет, {user_name}!",
            {
                "keyboard": [["Доход", "Расход"], ["Баланс"]],
                "resize_keyboard": True,
            },
        )
        return "ok", 200

    if text == "Доход":
        users[chat_id] = {"step": "amount", "type": "income"}
        send_message(chat_id, "Введи сумму дохода:")
        return "ok", 200

    if text == "Расход":
        users[chat_id] = {"step": "amount", "type": "expense"}
        send_message(chat_id, "Введи сумму расхода:")
        return "ok", 200

    if text == "Баланс":
        send_message(chat_id, "Баланс пока тестовый. Следующим шагом подключим таблицу.")
        return "ok", 200

    if chat_id in users and users[chat_id].get("step") == "amount":
        try:
            amount = float(text.replace(",", "."))
        except Exception:
            send_message(chat_id, "Введи число, например: 1500")
            return "ok", 200

        users[chat_id]["amount"] = amount
        users[chat_id]["step"] = "comment"
        send_message(chat_id, "Напиши комментарий:")
        return "ok", 200

    if chat_id in users and users[chat_id].get("step") == "comment":
        comment = text or "-"
        data_user = users[chat_id]

        entry = f"{datetime.datetime.now()} | {user_name} | {data_user['type']} | {data_user['amount']} | {comment}"
        print(entry, flush=True)

        send_message(chat_id, f"Записано:\n{data_user['amount']} ₽\n{comment}")
        users[chat_id] = {"step": None}
        return "ok", 200

    send_message(chat_id, "Нажми /start")
    return "ok", 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
