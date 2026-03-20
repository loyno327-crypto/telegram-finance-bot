from flask import Flask, request
import requests
import os
import datetime

TOKEN = os.environ.get("TOKEN")

app = Flask(__name__)

users = {}

def send_message(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    if keyboard:
        payload["reply_markup"] = keyboard
    requests.post(url, json=payload, timeout=20)

@app.route("/", methods=["GET"])
def health():
    return "ok", 200

@app.route("/", methods=["POST"])
def webhook():
    data = request.get_json(silent=True) or {}

    if "message" not in data:
        return "ok", 200

    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()

    user = message.get("from", {})
    user_name = user.get("first_name", "User")

    if text == "/start":
        users[chat_id] = {"step": None}
        send_message(chat_id, f"Привет, {user_name}!", {
            "keyboard": [["Доход", "Расход"], ["Баланс"]],
            "resize_keyboard": True
        })
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
