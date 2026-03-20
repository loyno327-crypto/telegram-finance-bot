from flask import Flask, request
import requests
import os
import datetime

TOKEN = os.environ.get("TOKEN")

app = Flask(__name__)

users = {}  # временно в памяти


def send_message(chat_id, text, keyboard=None):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "text": text
    }

    if keyboard:
        payload["reply_markup"] = keyboard

    requests.post(url, json=payload)


@app.route("/", methods=["POST"])
def webhook():
    data = request.json

    if "message" not in data:
        return "ok"

    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")

    user = message["from"]
    user_name = user.get("first_name", "User")

    # --- START ---
    if text == "/start":
        users[chat_id] = {"step": None}

        send_message(chat_id, f"Привет, {user_name}!", {
            "keyboard": [["Доход", "Расход"], ["Баланс"]],
            "resize_keyboard": True
        })
        return "ok"

    # --- ДОХОД ---
    if text == "Доход":
        users[chat_id] = {"step": "amount", "type": "income"}
        send_message(chat_id, "Введи сумму дохода:")
        return "ok"

    # --- РАСХОД ---
    if text == "Расход":
        users[chat_id] = {"step": "amount", "type": "expense"}
        send_message(chat_id, "Введи сумму расхода:")
        return "ok"

    # --- ВВОД СУММЫ ---
    if chat_id in users and users[chat_id].get("step") == "amount":
        try:
            amount = float(text.replace(",", "."))
        except:
            send_message(chat_id, "Введи число")
            return "ok"

        users[chat_id]["amount"] = amount
        users[chat_id]["step"] = "comment"

        send_message(chat_id, "Напиши комментарий:")
        return "ok"

    # --- КОММЕНТАРИЙ ---
    if chat_id in users and users[chat_id].get("step") == "comment":
        comment = text
        data_user = users[chat_id]

        entry = f"{datetime.datetime.now()} | {user_name} | {data_user['type']} | {data_user['amount']} | {comment}"
        print(entry)

        send_message(chat_id, f"Записано:\n{data_user['amount']} ₽\n{comment}")

        users[chat_id] = {"step": None}
        return "ok"

    return "ok"
