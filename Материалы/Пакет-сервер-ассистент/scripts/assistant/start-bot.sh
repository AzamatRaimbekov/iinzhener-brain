#!/usr/bin/env bash
# Запускает постоянную сессию Claude, которая отвечает владельцу в Telegram.
# Живёт в tmux: посмотреть — tmux attach -t assistant-telegram (выйти, не останавливая: Ctrl+B, потом D).
# Обычно запускается не руками, а службой: systemctl --user start assistant.service
#
# Плагин Telegram включается только в этой сессии: включённый везде, он отбирал бы бота у неё.
# claude-mem здесь по умолчанию выключен: его хук на старте каждого сообщения может тормозить
# или ронять канал Telegram. Хочешь попробовать с ним — CLAUDE_MEM_IN_BOT=true в ~/.config/assistant.env.
set -euo pipefail
SESSION="${BOT_SESSION:-assistant-telegram}"
WORKDIR="${WORKDIR:-$HOME/Мозг}"
STYLE_FILE="$HOME/assistant/style.md"
# Модель меняется одной строкой в ~/.config/assistant-model (sonnet или opus), без правки скрипта.
# По умолчанию sonnet: на подписке Pro лимиты Opus кончаются быстро. На Max можно opus.
MODEL="$(cat "$HOME/.config/assistant-model" 2>/dev/null || true)"
MODEL="${MODEL:-sonnet}"
MEM="${CLAUDE_MEM_IN_BOT:-false}"

if [[ ! -s "$HOME/.claude/channels/telegram/.env" ]]; then
  echo "Нет ключа бота (~/.claude/channels/telegram/.env) — сначала ~/assistant/save-token.sh"
  exit 1
fi
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "Бот уже запущен (tmux: $SESSION)"
  exit 0
fi
# RESUME_SESSION=<id> продолжает прежний разговор; WAKE_PROMPT — первое сообщение сессии.
# Автономный режим (--dangerously-skip-permissions): обычные действия бот делает сам, без вопросов —
# в Telegram некому нажимать «разрешить». Страховка: хук bash-guard блокирует опасные команды (он работает
# и в этом режиме), у пользователя нет прав администратора, а на опасное (оплата, удаление, отправка от имени
# владельца, публикация, доступ) бот по правилам CLAUDE.md и style.md спрашивает «да, делай» в чате.
[ -x "$HOME/.claude/hooks/bash-guard.sh" ] || { echo "Нет защитного хука bash-guard — без него автономный режим не запускаю (шаг 04)"; exit 1; }
tmux new-session -d -s "$SESSION" -x 200 -y 50 -c "$WORKDIR" \
  claude \
    --model "$MODEL" \
    --settings "{\"enabledPlugins\":{\"telegram@claude-plugins-official\":true,\"claude-mem@thedotmack\":${MEM}}}" \
    --channels plugin:telegram@claude-plugins-official \
    --dangerously-skip-permissions \
    --append-system-prompt "$(cat "$STYLE_FILE")" \
    ${RESUME_SESSION:+--resume "$RESUME_SESSION"} \
    ${WAKE_PROMPT:+"$WAKE_PROMPT"}
echo "Бот запущен (tmux: $SESSION${RESUME_SESSION:+, разговор $RESUME_SESSION})"
