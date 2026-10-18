#!/usr/bin/env bash
# Проверка готовности сервера. Запускается НА сервере под пользователем помощника:
#   bash check.sh
# Печатает ✅ / ❌ по каждому пункту. Сдавать сервер человеку можно, когда нет ❌ (⚪ — необязательное).
set -uo pipefail
export PATH="$HOME/.local/bin:$HOME/.bun/bin:$PATH"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
FAILS=0
ok()   { echo "✅ $1"; }
bad()  { echo "❌ $1"; FAILS=$((FAILS+1)); }
opt()  { echo "⚪ $1"; }
t()    { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
o()    { if eval "$2" >/dev/null 2>&1; then ok "$1"; else opt "$1 — не настроено (необязательно)"; fi; }

echo "== Защита"
t "работаю НЕ под root"                        '[ "$(id -u)" -ne 0 ]'
t "нет прав администратора у помощника"         '! sudo -n true'
t "файрвол включён"                             'systemctl is-active ufw'
t "fail2ban работает"                           'systemctl is-active fail2ban'
t "подкачка (swap) включена"                    'swapon --show | grep -q .'
t "автообновления безопасности"                 'grep -q "Unattended-Upgrade \"1\"" /etc/apt/apt.conf.d/20auto-upgrades'

echo "== Инструменты"
t "Claude Code установлен"                      'claude --version'
t "Node.js"                                     'node --version'
t "Bun (нужен боту)"                            'bun --version'
t "ffmpeg"                                      'ffmpeg -version'
t "службы живут без входа (linger)"             'loginctl show-user "$USER" -p Linger | grep -q yes'

echo "== Память: отсек heavy"
t "правило «падает только виновник»"            '[ "$(systemctl --user show -p DefaultOOMPolicy --value)" = continue ]'
t "отсек heavy.slice"                           'systemctl --user cat heavy.slice'
t "команда heavy"                               'heavy true'

echo "== Голосовые"
t "whisper-cli"                                 '[ -x "$HOME/.local/bin/whisper-cli" ]'
t "модель whisper скачана"                      'ls "$HOME"/whisper-models/*.bin'
t "команда voice-to-text"                       '[ -x "$HOME/.local/bin/voice-to-text" ]'

echo "== Claude"
t "вход в Claude выполнен"                      'timeout 90 claude -p "ответь одним словом: ок" --model haiku'
t "CLAUDE.md на месте"                          '[ -s "$HOME/.claude/CLAUDE.md" ]'
t "раздел «Кто я» заполнен (нет {{…}})"         '! grep -q "{{" "$HOME/.claude/CLAUDE.md"'
t "защитный хук подключён"                      'grep -q bash-guard "$HOME/.claude/settings.json"'
t "хук блокирует sudo"                          'printf "%s" "{\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"sudo ls\"}}" | "$HOME/.claude/hooks/bash-guard.sh"; [ $? -eq 2 ]'
t "автономный режим включён"                    'grep -q "\"bypassPermissions\"" "$HOME/.claude/settings.json"'
t "правила «делаю сам / спрашиваю» в CLAUDE.md" 'grep -q "Спрашиваю и жду" "$HOME/.claude/CLAUDE.md"'
t "плагин telegram установлен"                 'claude plugin list | grep -q "telegram@"'
t "плагин claude-mem установлен"                'claude plugin list | grep -q "claude-mem@"'
t "скилл impeccable"                            'ls -d "$HOME"/.claude/skills/impeccable'
t "папка ~/Мозг"                                '[ -d "$HOME/Мозг/Входящие" ]'

echo "== Telegram-бот"
t "ключ бота сохранён (600)"                    '[ "$(stat -c %a "$HOME/.claude/channels/telegram/.env")" = 600 ]'
t "доступ только владельцу (allowlist)"         'grep -q "\"allowlist\"" "$HOME/.claude/channels/telegram/access.json"'
t "автоподъём бота включён"                     'systemctl --user is-enabled assistant.timer'
t "сессия бота запущена"                        'tmux has-session -t "${BOT_SESSION:-assistant-telegram}"'

echo "== Необязательное"
o "Remote Control (сервер в приложении Claude)" 'systemctl --user is-enabled claude-rc.timer'
o "Tailscale"                                   'command -v tailscale && tailscale status'

echo
if [ "$FAILS" -eq 0 ]; then echo "ВСЁ ГОТОВО ✅"; else echo "Проблем: $FAILS — разобраться до сдачи"; fi
