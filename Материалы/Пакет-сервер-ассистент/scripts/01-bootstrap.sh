#!/usr/bin/env bash
# Шаг 1. Первичная настройка и защита нового сервера (Ubuntu 24.04).
# Запускается НА сервере с правами администратора (под root или через sudo):
#   sudo AGENT_USER=assistant TIMEZONE=Europe/Moscow bash 01-bootstrap.sh
#
# Что делает:
#   - админ-пользователь со входом по ключу (если провайдер дал только root — создаёт его);
#   - SSH только по ключу, root закрыт, файрвол (снаружи открыт только SSH), fail2ban;
#   - автообновления безопасности, подкачка (swap), часовой пояс;
#   - Node.js, GitHub CLI, ffmpeg, cmake и прочие инструменты;
#   - пользователь помощника БЕЗ прав администратора, в нём Claude Code, Bun и Chromium.
# Скрипт можно запускать повторно: каждый шаг сначала проверяет, сделан ли он.
set -euo pipefail

AGENT_USER="${AGENT_USER:-assistant}"     # пользователь, под которым живёт помощник
ADMIN_USER="${ADMIN_USER:-}"              # пусто = определить самому (ubuntu / тот, кто вызвал sudo / admin)
TIMEZONE="${TIMEZONE:-UTC}"               # например Asia/Almaty, Europe/Moscow, Asia/Bishkek
SWAP_SIZE_GB="${SWAP_SIZE_GB:-4}"
NODE_MAJOR="${NODE_MAJOR:-24}"

log() { printf '\n==> %s\n' "$*"; }
fail() { printf '\nОШИБКА: %s\n' "$*" >&2; exit 1; }

[[ ${EUID} -eq 0 ]] || fail "запускать через sudo или под root"
grep -qi 'ubuntu' /etc/os-release || echo "ВНИМАНИЕ: скрипт проверен на Ubuntu 24.04, на другой системе возможны ошибки"

# ---------- Админ-пользователь ----------
if [[ -z "${ADMIN_USER}" ]]; then
  if [[ -n "${SUDO_USER:-}" && "${SUDO_USER}" != "root" ]]; then
    ADMIN_USER="${SUDO_USER}"
  elif id ubuntu >/dev/null 2>&1; then
    ADMIN_USER="ubuntu"
  else
    ADMIN_USER="admin"
  fi
fi
[[ "${ADMIN_USER}" != "${AGENT_USER}" ]] || fail "ADMIN_USER и AGENT_USER должны отличаться"

log "Админ-пользователь: ${ADMIN_USER}"
if ! id "${ADMIN_USER}" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash --groups sudo "${ADMIN_USER}"
fi
usermod -aG sudo "${ADMIN_USER}"
ADMIN_HOME="$(getent passwd "${ADMIN_USER}" | cut -d: -f6)"
if [[ ! -s "${ADMIN_HOME}/.ssh/authorized_keys" ]]; then
  if [[ -s /root/.ssh/authorized_keys ]]; then
    install -d -m 700 -o "${ADMIN_USER}" -g "${ADMIN_USER}" "${ADMIN_HOME}/.ssh"
    install -m 600 -o "${ADMIN_USER}" -g "${ADMIN_USER}" /root/.ssh/authorized_keys "${ADMIN_HOME}/.ssh/authorized_keys"
  else
    fail "нет SSH-ключа ни у ${ADMIN_USER}, ни у root. Без ключа закрытие входа по паролю отрежет доступ. Сначала положи ключ."
  fi
fi
# Вход только по ключу, пароля у админа нет — поэтому повышение прав без пароля.
echo "${ADMIN_USER} ALL=(ALL) NOPASSWD:ALL" > "/etc/sudoers.d/90-${ADMIN_USER}"
chmod 440 "/etc/sudoers.d/90-${ADMIN_USER}"
visudo -cf "/etc/sudoers.d/90-${ADMIN_USER}" >/dev/null

export DEBIAN_FRONTEND=noninteractive

log "Обновляю систему"
apt-get update -y
apt-get -y -o Dpkg::Options::=--force-confold full-upgrade

log "Базовые пакеты"
apt-get install -y --no-install-recommends \
  ca-certificates curl gnupg git jq unzip zip tmux htop ripgrep fd-find \
  build-essential cmake python3 python3-pip python3-venv sqlite3 rsync \
  ufw fail2ban unattended-upgrades ffmpeg

log "Часовой пояс ${TIMEZONE}"
timedatectl set-timezone "${TIMEZONE}"

log "Автоматические обновления безопасности"
cat > /etc/apt/apt.conf.d/20auto-upgrades <<'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
EOF

log "SSH: вход только по ключу, root закрыт"
# Префикс 10- важен: sshd берёт ПЕРВОЕ встреченное значение, а образы провайдеров
# кладут свой 50-cloud-init.conf, который разрешает пароли.
cat > /etc/ssh/sshd_config.d/10-hardening.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
PubkeyAuthentication yes
X11Forwarding no
MaxAuthTries 3
EOF
# Ubuntu 24.04 запускает sshd по сокету: пока никто не подключался, /run/sshd нет и проверка падает.
install -d -m 755 /run/sshd
sshd -t
systemctl restart ssh

log "Файрвол: снаружи открыт только SSH"
ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw --force enable

log "fail2ban: бан за подбор пароля к SSH"
cat > /etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
maxretry = 5
findtime = 10m
bantime = 1h
EOF
systemctl enable fail2ban
systemctl restart fail2ban

log "Подкачка ${SWAP_SIZE_GB} ГБ"
if ! swapon --show | grep -q '^/swapfile'; then
  fallocate -l "${SWAP_SIZE_GB}G" /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
fi
grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' >> /etc/fstab
echo 'vm.swappiness=10' > /etc/sysctl.d/99-swappiness.conf
sysctl -q --system

log "Node.js ${NODE_MAJOR}"
if ! command -v node >/dev/null || [[ "$(node -v)" != "v${NODE_MAJOR}."* ]]; then
  curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash -
  apt-get install -y nodejs
fi

log "GitHub CLI"
if ! command -v gh >/dev/null; then
  install -d -m 755 /etc/apt/keyrings
  curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg \
    -o /etc/apt/keyrings/githubcli-archive-keyring.gpg
  chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
    > /etc/apt/sources.list.d/github-cli.list
  apt-get update -y
  apt-get install -y gh
fi

log "Пользователь помощника ${AGENT_USER} (без прав администратора)"
if ! id "${AGENT_USER}" >/dev/null 2>&1; then
  useradd --create-home --shell /bin/bash "${AGENT_USER}"
fi
AGENT_HOME="$(getent passwd "${AGENT_USER}" | cut -d: -f6)"
install -d -m 700 -o "${AGENT_USER}" -g "${AGENT_USER}" "${AGENT_HOME}/.ssh"
install -m 600 -o "${AGENT_USER}" -g "${AGENT_USER}" \
  "${ADMIN_HOME}/.ssh/authorized_keys" "${AGENT_HOME}/.ssh/authorized_keys"
# Службы пользователя (бот, проверки) живут, даже когда никто не вошёл по SSH.
loginctl enable-linger "${AGENT_USER}"

# cd в свой дом: sudo оставляет текущую папку админа, куда у помощника нет доступа, и npx падает.
as_agent() { sudo -u "${AGENT_USER}" -H bash -lc "cd \"\$HOME\" && $1"; }

log "Системные библиотеки для браузера без экрана (нужен для скриншотов и проверки сайтов)"
npx -y playwright@latest install-deps chromium

log "Claude Code, Bun (нужен плагину Telegram) и Chromium для ${AGENT_USER}"
as_agent 'command -v claude >/dev/null || [ -x "$HOME/.local/bin/claude" ] || curl -fsSL https://claude.ai/install.sh | bash'
as_agent 'command -v bun >/dev/null || [ -x "$HOME/.bun/bin/bun" ] || curl -fsSL https://bun.sh/install | bash'
as_agent '[ -x "$HOME/.local/bin/uv" ] || curl -LsSf https://astral.sh/uv/install.sh | sh'
as_agent 'npx -y playwright@latest install chromium'
as_agent 'grep -q "local/bin" ~/.bashrc || echo "export PATH=\"\$HOME/.local/bin:\$HOME/.bun/bin:\$PATH\"" >> ~/.bashrc'

log "Проверка"
sshd -T | grep -Ei '^(passwordauthentication|permitrootlogin|kbdinteractiveauthentication) '
ufw status | head -n 6
swapon --show
as_agent 'export PATH="$HOME/.local/bin:$HOME/.bun/bin:$PATH"; echo "claude $(claude --version)"; echo "bun $(bun --version)"; echo "node $(node --version)"; echo "gh $(gh --version | head -n 1)"'

log "Готово"
echo "Дальше подключаться так:"
echo "  админ:     ssh ${ADMIN_USER}@<IP>   (для системных дел, есть sudo)"
echo "  помощник:  ssh ${AGENT_USER}@<IP>   (для всего остального)"
echo "Вход под root и по паролю теперь закрыт."
