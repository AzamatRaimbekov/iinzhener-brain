#!/usr/bin/env bash
# Шаг 7 (по желанию). Tailscale — личная закрытая сеть между сервером и твоими устройствами.
# Нужен, чтобы открывать с телефона то, что помощник поднимает на сервере (сайт в разработке,
# браузер сервера, страницу загрузки файлов), НЕ открывая сервер в интернет.
# Запускается НА сервере с правами администратора:
#   sudo AGENT_USER=assistant bash 07-tailscale-optional.sh
# В конце печатает ссылку входа — её открывает человек и входит своим аккаунтом Tailscale.
set -euo pipefail
AGENT_USER="${AGENT_USER:-assistant}"
[[ ${EUID} -eq 0 ]] || { echo "Запускать через sudo" >&2; exit 1; }

if ! command -v tailscale >/dev/null; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
systemctl enable --now tailscaled
# Помощник сможет сам включать «tailscale serve» для своих страниц без прав администратора.
tailscale set --operator="${AGENT_USER}" 2>/dev/null || true

if tailscale status >/dev/null 2>&1; then
  echo "Tailscale уже подключён:"
  tailscale status | head -n 5
else
  # tailscale up ждёт входа человека — запускаем в фоне, иначе ссылка не покажется, пока ждём.
  LOG=/var/log/tailscale-up.log
  nohup tailscale up --operator="${AGENT_USER}" --hostname="$(hostname)-assistant" --timeout=30m > "$LOG" 2>&1 &
  sleep 8
  echo "Ссылка входа (пришли человеку: открыть → войти своим аккаунтом Tailscale → «Connect»):"
  grep -Eo 'https://login\.tailscale\.com/[^[:space:]]+' "$LOG" | head -n 1
  echo "После входа проверь: sudo tailscale status   (лог ожидания: $LOG)"
fi
tailscale ip -4 2>/dev/null || true
echo "Адрес сервера в личной сети — 100.x.x.x. Порты для своих страниц снаружи открывать НЕ нужно."
