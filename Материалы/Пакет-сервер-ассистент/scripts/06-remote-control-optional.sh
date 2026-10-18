#!/usr/bin/env bash
# Шаг 6 (по желанию). Remote Control: сервер появляется в приложении Claude (телефон, компьютер,
# claude.ai → Code) как отдельная «машина» — можно открыть там полноценную сессию на сервере.
# Запускается НА сервере под пользователем помощника, после входа в Claude:
#   SERVER_NAME="Мой сервер" bash 06-remote-control-optional.sh
set -euo pipefail
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
SERVER_NAME="${SERVER_NAME:-Мой сервер}"
WORKDIR="${WORKDIR:-$HOME/Мозг}"
mkdir -p "$HOME/.local/bin" "$HOME/.local/state" "$HOME/.config/systemd/user"

cat > "$HOME/.local/bin/claude-rc-start.sh" <<X
#!/bin/bash
# Постоянный вход Remote Control. Чистое окружение — чтобы не унаследовать переменные чужой сессии Claude.
set -euo pipefail
if tmux has-session -t claude-rc 2>/dev/null; then
  # Автообновление Claude удаляет старые версии программы; вход, запущенный из удалённой версии,
  # перестаёт открывать сессии. Тогда перезапускаем его на свежей.
  for pid in \$(pgrep -f "claude remote-control" || true); do
    if readlink "/proc/\$pid/exe" 2>/dev/null | grep -q "(deleted)"; then
      tmux kill-session -t claude-rc; sleep 2; break
    fi
  done
  tmux has-session -t claude-rc 2>/dev/null && exit 0
fi
cd "$WORKDIR"
env -i HOME="\$HOME" USER="\$USER" LANG=C.UTF-8 TERM=xterm-256color \\
  PATH="\$HOME/.local/bin:\$HOME/.bun/bin:/usr/local/bin:/usr/bin:/bin" \\
  tmux new-session -d -s claude-rc -x 200 -y 50 -c "$WORKDIR" \\
  "claude remote-control --name '$SERVER_NAME' --permission-mode bypassPermissions --spawn same-dir --debug-file \$HOME/.local/state/claude-rc-debug.log"
X
chmod +x "$HOME/.local/bin/claude-rc-start.sh"

cat > "$HOME/.config/systemd/user/claude-rc.service" <<'X'
[Unit]
Description=Claude Remote Control (поднять, если не запущен)

[Service]
Type=oneshot
ExecStart=%h/.local/bin/claude-rc-start.sh
KillMode=process
X
cat > "$HOME/.config/systemd/user/claude-rc.timer" <<'X'
[Unit]
Description=Держать Claude Remote Control живым

[Timer]
OnBootSec=1min
OnUnitActiveSec=5min

[Install]
WantedBy=timers.target
X
systemctl --user daemon-reload
systemctl --user enable --now claude-rc.timer
systemctl --user start claude-rc.service
sleep 12
tmux capture-pane -p -t claude-rc | grep -v '^\s*$' | tail -25
echo
echo "Если на экране вопрос (например, включить Remote Control) — подключись: tmux attach -t claude-rc, ответь, выйди Ctrl+B, D."
