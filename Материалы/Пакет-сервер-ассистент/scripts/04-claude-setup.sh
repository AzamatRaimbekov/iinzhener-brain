#!/usr/bin/env bash
# Шаг 4. Настройка Claude Code помощника: папка «Мозг», правила, защитный хук, плагины, MCP, скиллы.
# Запускается НА сервере под пользователем помощника:
#   bash 04-claude-setup.sh                 # базовый набор
#   VIDEO=1 bash 04-claude-setup.sh         # + видео-скиллы (HyperFrames, Remotion)
#   WEB=1 bash 04-claude-setup.sh           # + скиллы для сайтов (GSAP, UI/UX Pro Max)
# Повторный запуск безопасен: уже поставленное пропускается, свои правки в CLAUDE.md не затираются.
# Важно: всё здесь — публичное и бесплатное, из официальных репозиториев авторов.
set -uo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
export PATH="$HOME/.local/bin:$HOME/.bun/bin:$PATH"
WORKDIR="${WORKDIR:-$HOME/Мозг}"
CLAUDE_DIR="$HOME/.claude"
REPORT=()
note() { REPORT+=("$1"); echo "  $1"; }

[ "$(id -u)" -ne 0 ] || { echo "Запускай под пользователем помощника, не под root" >&2; exit 1; }
command -v claude >/dev/null || { echo "Нет claude — сначала шаг 1" >&2; exit 1; }

echo "== Папка «Мозг» — рабочее место помощника"
mkdir -p "$WORKDIR"/{Входящие,Заметки,Контент,Документы,Видео,Отчёты,Бренд,_На_удаление}
[ -f "$WORKDIR/ПРАВИЛА.md" ] || cp "$HERE/files/ПРАВИЛА.шаблон.md" "$WORKDIR/ПРАВИЛА.md"
if [ ! -d "$WORKDIR/.git" ]; then
  git -C "$WORKDIR" init -q && git -C "$WORKDIR" add -A && \
    git -C "$WORKDIR" -c user.name=assistant -c user.email=assistant@localhost commit -qm "chore: начало" && \
    note "~/Мозг создан, история изменений (git) включена"
fi

echo "== Правила помощника (~/.claude/CLAUDE.md)"
mkdir -p "$CLAUDE_DIR/hooks"
if [ ! -f "$CLAUDE_DIR/CLAUDE.md" ]; then
  cp "$HERE/files/CLAUDE.template.md" "$CLAUDE_DIR/CLAUDE.md"
  note "CLAUDE.md создан из шаблона — заполни раздел «Кто я» (поля {{…}})"
else
  note "CLAUDE.md уже есть — не трогаю"
fi

echo "== Защитный хук (блокирует опасные команды)"
install -m 755 "$HERE/files/bash-guard.sh" "$CLAUDE_DIR/hooks/bash-guard.sh"
python3 - "$CLAUDE_DIR/settings.json" "$CLAUDE_DIR/hooks/bash-guard.sh" <<'PY'
import json, os, sys
path, hook_cmd = sys.argv[1], sys.argv[2]
settings = json.load(open(path)) if os.path.exists(path) else {}
pre = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
already = any(h.get("command") == hook_cmd for entry in pre for h in entry.get("hooks", []))
if not already:
    pre.append({"matcher": "Bash", "hooks": [{"type": "command", "command": hook_cmd}]})
settings["autoMemoryEnabled"] = True
# Автономный режим во всех сессиях на сервере: без вопросов-подтверждений на обычные действия.
# Страховка — хук выше (блокирует опасное) и пользователь без прав администратора;
# подтверждение человека на опасное задано правилами в CLAUDE.md («делаю сам / спрашиваю»).
settings.setdefault("permissions", {})["defaultMode"] = "bypassPermissions"
settings["skipDangerousModePermissionPrompt"] = True
tmp = path + ".tmp"
json.dump(settings, open(tmp, "w"), ensure_ascii=False, indent=2)
os.chmod(tmp, 0o600)
os.replace(tmp, path)
PY
note "хук bash-guard подключён, автономный режим (без подтверждений на обычные действия) включён"

echo "== Плагины"
plugins="$(claude plugin list 2>/dev/null || true)"
claude plugin marketplace add anthropics/claude-plugins-official >/dev/null 2>&1 || true
grep -q "superpowers@" <<<"$plugins" || { claude plugin install superpowers@claude-plugins-official >/dev/null 2>&1 \
  && note "плагин superpowers (методика работы над задачами) поставлен" || note "НЕ удалось поставить superpowers"; }
if ! grep -q "telegram@" <<<"$plugins"; then
  claude plugin install telegram@claude-plugins-official >/dev/null 2>&1 \
    && note "плагин telegram поставлен" || note "НЕ удалось поставить telegram"
fi
# Включённый везде, плагин Telegram запускался бы в КАЖДОЙ сессии и отбирал бота у основной.
# Поэтому глобально выключен, а включается флагом только в сессии бота (assistant/start-bot.sh).
claude plugin disable telegram@claude-plugins-official >/dev/null 2>&1 || true
if ! grep -q "claude-mem@" <<<"$plugins"; then
  { claude plugin marketplace add thedotmack/claude-mem >/dev/null 2>&1 || true
    claude plugin install claude-mem@thedotmack >/dev/null 2>&1; } \
    && note "плагин claude-mem (долгая память между разговорами) поставлен" || note "НЕ удалось поставить claude-mem"
fi

echo "== MCP-серверы"
claude mcp get context7 >/dev/null 2>&1 || { claude mcp add -s user context7 -- npx -y @upstash/context7-mcp >/dev/null 2>&1 \
  && note "MCP context7 (свежая документация библиотек)" || note "НЕ удалось добавить context7"; }
claude mcp get playwright >/dev/null 2>&1 || { claude mcp add -s user playwright -- npx -y @playwright/mcp@latest --headless >/dev/null 2>&1 \
  && note "MCP playwright (браузер без экрана)" || note "НЕ удалось добавить playwright"; }

echo "== Скиллы (публичные и бесплатные, ставятся инструментом npx skills)"
add_skills() {
  local repo="$1"; shift
  if npx -y skills add "$repo" -g -a claude-code -y "$@" >/dev/null 2>&1; then
    note "скиллы из $repo"
  else
    note "НЕ удалось поставить скиллы из $repo (проверь: npx skills add $repo --list)"
  fi
}
add_skills pbakaus/impeccable                                    # вкус и качество интерфейсов
add_skills Leonxlnx/taste-skill --skill taste-skill              # «вкус»: без шаблонного ИИ-дизайна
add_skills emilkowalski/skill --skill emil-design-eng --skill apple-design   # полировка UI и анимаций
add_skills blader/humanizer                                      # убирает «ИИ-шные» обороты из текстов
add_skills vercel-labs/skills --skill find-skills                # поиск новых скиллов по просьбе
add_skills anthropics/skills --skill docx --skill pdf --skill pptx --skill xlsx --skill skill-creator  # документы
if [ "${VIDEO:-0}" = "1" ]; then
  add_skills heygen-com/hyperframes --skill '*'                  # видео из HTML (HyperFrames)
  add_skills remotion-dev/skills --skill '*'                     # видео на React (Remotion)
fi
if [ "${WEB:-0}" = "1" ]; then
  add_skills greensock/gsap-skills --skill '*'                   # анимации для сайтов (GSAP)
  add_skills nextlevelbuilder/ui-ux-pro-max-skill --skill ui-ux-pro-max   # правила UI/UX
fi

echo "== graphify (карта связей заметок)"
if command -v uv >/dev/null; then
  { uv tool install -q graphifyy >/dev/null 2>&1 && graphify install >/dev/null 2>&1; } \
    && note "graphify поставлен" || note "НЕ удалось поставить graphify (необязательно)"
fi

echo
echo "===== ИТОГ ====="
printf '%s\n' "${REPORT[@]}"
echo "Скиллы видны в новой сессии Claude: claude -p 'перечисли свои скиллы одной строкой'"
