#!/usr/bin/env python3
"""Находит, кто написал боту, и пускает к боту только этого человека.

Перед запуском владелец пишет боту любое сообщение. Скрипт читает входящие,
не подтверждая их, чтобы сессия Claude потом увидела это сообщение. Берёт
числовой ID единственного отправителя и записывает его в access.json с политикой
allowlist: остальным бот молчит. Если отправителей несколько — ничего не пишет.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

STATE_DIR = os.path.expanduser("~/.claude/channels/telegram")
ENV_FILE = os.path.join(STATE_DIR, ".env")
ACCESS_FILE = os.path.join(STATE_DIR, "access.json")


def read_token():
    with open(ENV_FILE, encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip()
    sys.exit("В .env нет TELEGRAM_BOT_TOKEN")


def get_updates(token, poll_seconds):
    url = (
        f"https://api.telegram.org/bot{token}/getUpdates"
        f"?timeout={poll_seconds}&allowed_updates=%5B%22message%22%5D"
    )
    try:
        with urllib.request.urlopen(url, timeout=poll_seconds + 15) as response:
            payload = json.loads(response.read())
    except urllib.error.URLError as error:
        print(f"Нет связи с Telegram, пробую снова: {error}", file=sys.stderr)
        return []
    if not payload.get("ok"):
        sys.exit(f"Telegram ответил ошибкой: {payload.get('description')}")
    return payload["result"]


def private_senders(updates):
    senders = {}
    for update in updates:
        message = update.get("message") or {}
        if (message.get("chat") or {}).get("type") != "private":
            continue
        sender = message.get("from") or {}
        if sender.get("id") and not sender.get("is_bot"):
            senders[sender["id"]] = sender
    return senders


def main():
    # --wait N: ждать первого сообщения до N секунд (длинный опрос Telegram), иначе проверить один раз.
    wait_seconds = int(sys.argv[2]) if len(sys.argv) == 3 and sys.argv[1] == "--wait" else 0
    token = read_token()
    deadline = time.time() + wait_seconds
    senders = private_senders(get_updates(token, 0))
    while not senders and time.time() < deadline:
        senders = private_senders(get_updates(token, 30))
    if not senders:
        sys.exit("Боту ещё никто не написал. Напиши ему «привет» и запусти снова.")
    if len(senders) > 1:
        listing = ", ".join(f"@{s.get('username', '?')} ({i})" for i, s in senders.items())
        sys.exit(f"Боту писали несколько человек: {listing}. Ничего не записал — нужно уточнить, кто владелец.")
    owner_id, owner = next(iter(senders.items()))
    current = {}
    if os.path.exists(ACCESS_FILE):
        with open(ACCESS_FILE, encoding="utf-8") as handle:
            current = json.load(handle)
    updated = {
        "groups": {},
        "ackReaction": "👀",
        "replyToMode": "first",
        "textChunkLimit": 4096,
        "chunkMode": "newline",
        **current,
        "dmPolicy": "allowlist",
        "allowFrom": [str(owner_id)],
    }
    os.makedirs(STATE_DIR, mode=0o700, exist_ok=True)
    tmp_path = ACCESS_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as handle:
        json.dump(updated, handle, ensure_ascii=False, indent=2)
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, ACCESS_FILE)
    print(f"Владелец: @{owner.get('username', '?')} ({owner.get('first_name', '')}), id {owner_id}. Остальным бот не отвечает.")


if __name__ == "__main__":
    main()
