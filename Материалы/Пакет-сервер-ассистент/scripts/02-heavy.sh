#!/usr/bin/env bash
# Шаг 2. Защита памяти: отсек heavy.slice + команда heavy.
# Запускается НА сервере под пользователем помощника (не root):
#   bash 02-heavy.sh            # один помощник на сервере
#   bash 02-heavy.sh --share 2  # два помощника на одной машине — потолки делятся пополам
#
# Зачем. Рендер видео вместе с расшифровкой голосового съедает всю память сервера.
# Тогда система убивает не одну задачу, а всю сессию бота целиком: бот замолкает,
# фоновые задачи пропадают, последнее сообщение теряется. Поэтому:
#   1) правило «падает только виновник» (DefaultOOMPolicy=continue);
#   2) отсек heavy.slice с потолком памяти (40% памяти машины) и пониженным приоритетом процессора;
#   3) команда `heavy <команда>` — запускает тяжёлую задачу внутри отсека.
# Повторный запуск безопасен.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
SHARE=1
while [ "$#" -gt 0 ]; do
  case "$1" in
    --share) SHARE="${2:?после --share нужно число}"; shift 2 ;;
    *) echo "неизвестный ключ: $1" >&2; exit 2 ;;
  esac
done

[ "$(id -u)" -ne 0 ] || { echo "Запускай под пользователем помощника, не под root" >&2; exit 1; }
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
UNIT_DIR="$HOME/.config/systemd/user"
mkdir -p "$UNIT_DIR" "$HOME/.config/systemd/user.conf.d" "$HOME/.local/bin"

TOTAL_MB=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
HEAVY_MAX=$(( TOTAL_MB * 40 / 100 / SHARE ))
HEAVY_HIGH=$(( TOTAL_MB * 35 / 100 / SHARE ))
echo "Память машины: ${TOTAL_MB} МБ, помощников на машине: ${SHARE}"

# 1. Нехватка памяти убивает одну задачу, а не всю сессию бота
cat > "$HOME/.config/systemd/user.conf.d/oom-policy.conf" <<'EOF'
# При нехватке памяти ядро убивает один прожорливый процесс, а systemd НЕ гасит всю
# область tmux (правило по умолчанию «stop» убивало бота вместе со всеми его задачами).
[Manager]
DefaultOOMPolicy=continue
EOF
systemctl --user daemon-reexec
echo "1/3 правило «падает только виновник»: $(systemctl --user show -p DefaultOOMPolicy --value)"

# 2. Отсек для тяжёлых задач
cat > "$UNIT_DIR/heavy.slice" <<EOF
[Unit]
Description=Отсек для тяжёлых задач помощника: рендер видео, ffmpeg, whisper

[Slice]
MemoryHigh=${HEAVY_HIGH}M
MemoryMax=${HEAVY_MAX}M
MemorySwapMax=1G
CPUWeight=40
EOF
systemctl --user daemon-reload
echo "2/3 отсек heavy.slice: потолок ${HEAVY_MAX} МБ"

# 3. Команда heavy
install -m 755 "$HERE/files/heavy" "$HOME/.local/bin/heavy"
echo "3/3 команда ~/.local/bin/heavy установлена"

# Проверка: переполнение внутри отсека убивает только задачу (код 137), остальное живо
set +e
systemd-run --user --scope --quiet --collect --slice=heavy.slice \
  -p MemoryMax=300M -p MemorySwapMax=0 -p OOMPolicy=continue -- \
  python3 -c 'a = bytearray(1024 ** 3)' 2>/dev/null
CHECK=$?
set -e
if [ "$CHECK" -eq 137 ]; then
  echo "ПРОВЕРКА ОК: задача сверх потолка убита (137), остальное живо"
else
  echo "ПРОВЕРКА НЕ ПРОШЛА: код $CHECK (ожидался 137). Не идти дальше, пока не разобрались." >&2
  exit 1
fi
"$HOME/.local/bin/heavy" true && echo "heavy работает"
