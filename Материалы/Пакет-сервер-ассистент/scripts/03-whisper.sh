#!/usr/bin/env bash
# Шаг 3. Расшифровка голосовых прямо на сервере: whisper.cpp + модель large-v3-turbo (q5_0).
# Бесплатно, без ключей, понимает русский, казахский, кыргызский, узбекский, английский и др.
# Запускается НА сервере под пользователем помощника (cmake уже поставлен шагом 1):
#   bash 03-whisper.sh
# Результат: ~/.local/bin/whisper-cli, модель в ~/whisper-models/, команда ~/.local/bin/voice-to-text.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
# q5_0 втрое легче и быстрее полной модели на процессоре сервера, качество для голоса почти то же.
MODEL="${MODEL:-ggml-large-v3-turbo-q5_0.bin}"
export PATH="$HOME/.local/bin:$PATH"

command -v cmake >/dev/null || { echo "Нет cmake — сначала шаг 1 (01-bootstrap.sh)" >&2; exit 1; }
command -v heavy >/dev/null || { echo "Нет команды heavy — сначала шаг 2 (02-heavy.sh)" >&2; exit 1; }

cd ~
if [ ! -x ~/.local/bin/whisper-cli ]; then
  echo "Собираю whisper.cpp (несколько минут)…"
  rm -rf ~/src/whisper.cpp
  git clone -q --depth 1 https://github.com/ggml-org/whisper.cpp ~/src/whisper.cpp
  cmake -S ~/src/whisper.cpp -B ~/src/whisper.cpp/build -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF >/dev/null
  heavy cmake --build ~/src/whisper.cpp/build -j"$(nproc)" --target whisper-cli >/dev/null
  install -D -m 755 ~/src/whisper.cpp/build/bin/whisper-cli ~/.local/bin/whisper-cli
fi

install -d ~/whisper-models
if [ ! -s ~/whisper-models/"$MODEL" ]; then
  echo "Скачиваю модель $MODEL (~550 МБ)…"
  curl -fsSL -o ~/whisper-models/"$MODEL".part \
    "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/$MODEL"
  mv ~/whisper-models/"$MODEL".part ~/whisper-models/"$MODEL"
fi

install -m 755 "$HERE/files/voice-to-text" ~/.local/bin/voice-to-text
ls -la ~/.local/bin/whisper-cli ~/whisper-models/
echo "Готово. Проверка: voice-to-text <файл.oga>"
