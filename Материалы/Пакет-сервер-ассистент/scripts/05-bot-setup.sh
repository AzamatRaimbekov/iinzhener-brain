#!/usr/bin/env bash
# Шаг 5. Подготовка Telegram-бота: папка ~/assistant, службы systemd (пока выключены), настройки Claude.
# Запускается НА сервере под пользователем помощника ПОСЛЕ входа в Claude (шаг «вход»):
#   bash 05-bot-setup.sh
# Бот включается позже, когда человек сохранит ключ бота (save-token.sh) и напишет боту «привет»:
#   ~/assistant/capture_owner.py --wait 600
#   systemctl --user enable --now assistant.timer && systemctl --user start assistant.service
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
WORKDIR="${WORKDIR:-$HOME/Мозг}"
[ "$(id -u)" -ne 0 ] || { echo "Запускай под пользователем помощника, не под root" >&2; exit 1; }

echo "== ~/assistant"
mkdir -p "$HOME/assistant" "$HOME/.local/bin" "$HOME/.config/systemd/user"
for f in start-bot.sh save-token.sh capture_owner.py; do
  install -m 755 "$HERE/assistant/$f" "$HOME/assistant/$f"
done
# style.md не перезаписываем, если владелец его уже правил
[ -f "$HOME/assistant/style.md" ] || install -m 644 "$HERE/assistant/style.md" "$HOME/assistant/style.md"
install -m 755 "$HERE/files/restart-bot" "$HOME/.local/bin/restart-bot"
install -d -m 700 "$HOME/.claude/channels/telegram"
[ -f "$HOME/.config/assistant-model" ] || echo "sonnet" > "$HOME/.config/assistant-model"

echo "== Настройки Claude: без первого онбординга, папки доверенные, режим без вопросов принят"
python3 - "$WORKDIR" <<'PY'
import json, os, sys
workdir = sys.argv[1]
path = os.path.expanduser("~/.claude.json")
config = json.load(open(path)) if os.path.exists(path) else {}
config["hasCompletedOnboarding"] = True
config["bypassPermissionsModeAccepted"] = True
for folder in (workdir, os.path.expanduser("~/assistant"), os.path.expanduser("~")):
    config.setdefault("projects", {}).setdefault(folder, {})["hasTrustDialogAccepted"] = True
tmp = path + ".tmp"
json.dump(config, open(tmp, "w"), indent=2, ensure_ascii=False)
os.chmod(tmp, 0o600)
os.replace(tmp, path)
print("~/.claude.json обновлён")
PY

echo "== Службы systemd (автоподъём бота каждые 5 минут, если он упал)"
cat > "$HOME/.config/systemd/user/assistant.service" <<'X'
[Unit]
Description=Помощник: Claude в Telegram (поднимает tmux-сессию, если её нет)

[Service]
Type=oneshot
# tmux-сервер должен пережить завершение этого запуска.
KillMode=process
Environment=PATH=%h/.local/bin:%h/.bun/bin:/usr/local/bin:/usr/bin:/bin
Environment=LANG=C.UTF-8
EnvironmentFile=-%h/.config/assistant.env
ExecStart=/bin/bash %h/assistant/start-bot.sh
X
cat > "$HOME/.config/systemd/user/assistant.timer" <<'X'
[Unit]
Description=Помощник: проверка каждые 5 минут

[Timer]
OnBootSec=45s
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
X
systemctl --user daemon-reload
echo "assistant.timer: $(systemctl --user is-enabled assistant.timer 2>&1 || true) (до ключа бота должен быть disabled)"
ls -la "$HOME/assistant"
echo
echo "Дальше: человек сохраняет ключ бота (save-token.sh в своём терминале) и пишет боту «привет»."
