#!/usr/bin/env bash
# Сохраняет ключ (токен) бота от @BotFather в ~/.claude/channels/telegram/.env с правами 600.
# Ввод скрыт, ключ на экран не выводится и в чат с ИИ не попадает.
# Запускает САМ ЧЕЛОВЕК в своём терминале:
#   ssh -t -i <ключ> <пользователь-помощника>@<IP> '~/assistant/save-token.sh'
set -euo pipefail
umask 077
STATE_DIR="$HOME/.claude/channels/telegram"
mkdir -p "$STATE_DIR"
read -r -s -p "Вставь ключ бота от BotFather (символы не видны) и нажми Enter: " RAW
echo
BOT_KEY="$(printf '%s' "$RAW" | tr -d ' \r\n' | grep -oE '[0-9]{6,12}:[A-Za-z0-9_-]{35}' | head -n 1 || true)"
unset RAW
if [[ -z "$BOT_KEY" ]]; then
  echo "Это не похоже на ключ бота (формат 123456789:AA…). Скопируй строку от BotFather ещё раз и запусти снова."
  exit 1
fi
printf 'TELEGRAM_BOT_TOKEN=%s\n' "$BOT_KEY" > "$STATE_DIR/.env"
chmod 600 "$STATE_DIR/.env"
unset BOT_KEY
echo "Ключ сохранён. Теперь напиши своему боту в Telegram «привет» и скажи своему Claude «готово»."
