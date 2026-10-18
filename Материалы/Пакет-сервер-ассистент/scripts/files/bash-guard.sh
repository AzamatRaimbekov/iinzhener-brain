#!/usr/bin/env bash
# PreToolUse-хук bash-guard для сервера-помощника: блокирует опасные команды до их запуска.
# Хозяин сервера — один человек, помощник работает в своей домашней папке без прав администратора.
# Разрешено свободно: свои ключи и настройки в ~/.config, свои скрипты, установка программ в домашнюю
# папку (pip/venv/npm/npx/bun/curl|sh), сеть, bash -c / eval, chmod/ln, systemctl --user, tmux.
# Запрещено: права администратора, удаление корня/дома/массовое вне своей папки, отправка ключей в сеть
# и их печать в чат, правка доступа по SSH, force-push, переписывание истории, отключение этого хука.
# Вход: JSON { tool_name, tool_input: { command } }. Выход 0 — пропустить, 2 — заблокировать.

input="$(cat)"
command -v jq >/dev/null 2>&1 || exit 0
tool="$(printf '%s' "$input" | jq -r '.tool_name // ""' 2>/dev/null)"
[ "$tool" = "Bash" ] || exit 0
cmd="$(printf '%s' "$input" | jq -r '.tool_input.command // ""' 2>/dev/null)"
[ -n "$cmd" ] || exit 0
norm="$(printf '%s' "$cmd" | tr '\n\r\t' '   ' | tr -s ' ')"

block() {
  printf 'Команда заблокирована защитой (bash-guard): %s\n---\n%s\n' "$1" "$cmd" >&2
  exit 2
}
m() { printf '%s' "$norm" | grep -Eq "$1"; }

# Секретные места: SSH-ключи, env-файлы, файлы ключей
SECRET='(\.ssh/|id_(rsa|ed25519|ecdsa)|\.env([^a-zA-Z]|$)|[a-zA-Z0-9_-]+\.env([^a-zA-Z]|$)|credentials|\.pem([^a-zA-Z]|$)|\.key([^a-zA-Z]|$)|\.netrc|\.pgpass|/\.aws/|/\.gnupg/)'

# ===== 1. Права администратора =====
m '(^|[^a-zA-Z_/-])(sudo|su|doas|pkexec)([[:space:]]|$)' && block "права администратора (sudo/su) запрещены"

# ===== 2. Удаление корня, дома целиком и массовое вне своей папки =====
rm_targets_ok() (
  set -f
  joined="${norm//&&/;}"; joined="${joined//\|\|/;}"; joined="${joined//|/;}"
  IFS=';'; set -- $joined; IFS=' '
  for seg in "$@"; do
    case " $seg " in *" rm "*|"rm "*) ;; *) continue ;; esac
    seen=0
    for tok in $seg; do
      tok="${tok//\"/}"; tok="${tok//\'/}"
      if [ "$seen" -eq 0 ]; then [ "$tok" = "rm" ] && seen=1; continue; fi
      case "$tok" in
        -*) continue ;;
        /|/\*|'~'|'~/'|'~/*'|'$HOME'|'$HOME/'|'$HOME/*'|'${HOME}'|'${HOME}/'|'${HOME}/*'|.|./|..|../*|*/..|*/../*) return 1 ;;
        '~/.ssh'|'~/.ssh/'*|'$HOME/.ssh'*|*/.ssh|*/.ssh/*) return 1 ;;
        '~/.claude'|'~/.claude/'|'$HOME/.claude'|'$HOME/.claude/'|'~/.config'|'~/.config/'|'$HOME/.config'|'$HOME/.config/') return 1 ;;
        /tmp/?*|/var/tmp/?*) continue ;;
        /home/*/?*) continue ;;
        /*) return 1 ;;
        *) continue ;;
      esac
    done
  done
  return 0
)
if m '(^|[^a-zA-Z0-9_])rm[[:space:]]+([^|;&]*[[:space:]])?(-[a-zA-Z]*[rR][a-zA-Z]*|--recursive)([[:space:]]|$)'; then
  rm_targets_ok || block "рекурсивное удаление корня, домашней папки, ~/.ssh или системных путей"
fi
m 'find[[:space:]]+(/|~|\$HOME)([[:space:]]|$)[^|;&]*(-delete|-exec[[:space:]]+rm)' && block "find -delete по корню или всей домашней папке"
m '(^|[^a-zA-Z])(mkfs|dd[[:space:]]+[^|;&]*of=/dev/)' && block "форматирование или запись на диск"

# ===== 3. Ключи — не в сеть и не в чат =====
# 3а. Отправка содержимого секретов в сеть
m '(curl|wget|http|https|nc|ncat|socat|scp|rsync|sftp)[[:space:]][^|;&]*'"$SECRET" && block "отправка ключей/env/SSH-ключа в сеть"
m "$SECRET"'[^;&]*\|[[:space:]]*(curl|wget|nc|ncat|socat|http)([[:space:]]|$)' && block "ключи из файла по трубе в сеть"
m '(curl|wget)[[:space:]][^|;&]*(-d|--data[a-z-]*|-F|--form|-T|--upload-file)[[:space:]]*[^|;&]*@[^[:space:]]*'"$SECRET" && block "загрузка файла с ключами в сеть"
m '(cat|base64|xxd)[[:space:]][^|;&]*'"$SECRET"'[^;&]*\|[[:space:]]*(curl|wget|nc)' && block "ключи по трубе в сеть"
# 3б. Печать ключей в чат (читать скриптом можно: source, python, grep -c)
m '(^|[;&|][[:space:]]*|[[:space:]])(cat|less|more|head|tail|bat|xxd|od|strings|nl|tac)[[:space:]][^|;&]*(\.ssh/id_|id_(rsa|ed25519|ecdsa)([^.]|$)|\.env([^a-zA-Z.]|$)|[a-zA-Z0-9_-]+\.env([^a-zA-Z.]|$))' && block "вывод ключа или env-файла на экран (читай скриптом, не печатай)"
m '(^|[;&|][[:space:]]*)(echo|printf)[[:space:]][^|;&]*\$\{?[A-Za-z_]*(KEY|TOKEN|SECRET|PASSWORD|PASS)[A-Za-z_]*\}?' && block "печать ключа в чат"
m '(^|[;&|][[:space:]]*)printenv([[:space:]]*$|[[:space:]]*[|>;&])' && block "полный вывод переменных окружения"
m '(^|[;&|][[:space:]]*)env([[:space:]]*$|[[:space:]]*[|>;&])' && block "полный вывод переменных окружения"
m '(^|[;&|][[:space:]]*)set[[:space:]]*($|\|)' && block "полный вывод переменных окружения"

# ===== 4. Доступ по SSH и сервер =====
m 'authorized_keys' && m '(>|tee|sed[[:space:]]+-i|cp[[:space:]]|mv[[:space:]]|rm[[:space:]]|ln[[:space:]]|chmod|python|perl|awk)' && block "изменение доступа по SSH (authorized_keys)"
m '(sshd_config|/etc/ssh/|ssh-copy-id)' && block "изменение настроек SSH-сервера"

# ===== 5. Git: необратимое =====
m 'git[[:space:]]+push[[:space:]][^|;&]*(--force|-f([[:space:]]|$)|--force-with-lease)' && block "git push --force — перезапись истории"
m 'git[[:space:]]+filter-(branch|repo)' && block "переписывание истории репозитория"
m '(^|[^a-zA-Z_/])dropdb([[:space:]]|$)' && block "удаление базы данных"
m 'supabase[[:space:]]+db[[:space:]]+reset([[:space:]]|$)' && block "сброс базы Supabase"

# ===== 6. Отключение защиты =====
m 'bash-guard' && m '(rm[[:space:]]|mv[[:space:]]|>|tee|sed[[:space:]]+-i|chmod|truncate|cp[[:space:]]|ln[[:space:]]|python|perl)' && block "изменение или отключение защитного хука"
m 'disableAllHooks' && block "отключение хуков"
m '\.claude/settings(\.local)?\.json' && m '(PreToolUse|"hooks"|hooks)' && m '(sed[[:space:]]+-i|>|tee|jq[^|]*>|python|perl)' && block "правка подключения хуков в settings.json"

exit 0
