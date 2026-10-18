#!/usr/bin/env bash
# Собирает скилл в архив для передачи другому человеку.
#
# Личный профиль (config/profile.json) в архив НЕ попадает: там id аватара
# и голоса конкретного владельца, чужому человеку они бесполезны, а получателю
# всё равно нужно завести свои. Вместо него уезжает profile.example.json,
# и скилл при первом запуске проводит нового владельца через настройку.

set -e

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${1:-$HOME/Desktop/reels-clone.zip}"
TMP="$(mktemp -d)"
STAGE="$TMP/reels-clone"

mkdir -p "$STAGE"
rsync -a --exclude 'config/profile.json' \
         --exclude '__pycache__' \
         --exclude '.DS_Store' \
         "$SKILL_DIR/" "$STAGE/"

if [ -f "$STAGE/config/profile.json" ]; then
  echo "ОШИБКА: личный профиль попал в архив, прерываю" >&2
  exit 1
fi

rm -f "$OUT"
(cd "$TMP" && zip -qr "$OUT" reels-clone)
rm -rf "$TMP"

echo "Готово: $OUT"
echo
echo "Что внутри:"
unzip -l "$OUT" | sed -n '4,40p'
echo
echo "Получателю: распаковать в ~/.claude/skills/ и запустить любую задачу"
echo "про клонирование рилса — скилл сам проведёт настройку."
