# Деплой на AWS EC2 (t3.micro)

Пошаговая инструкция для production-запуска Pribilka Backend.

## Что нужно заранее

- EC2 `t3.micro`, Ubuntu 24.04 LTS
- Elastic IP привязан к инстансу
- Security Group с правилами:

| Type  | Port | Source    | Назначение        |
|-------|------|-----------|-------------------|
| SSH   | 22   | My IP     | Подключение       |
| HTTP  | 80   | 0.0.0.0/0 | HTTPS (Caddy)     |
| HTTPS | 443  | 0.0.0.0/0 | API               |

> Порты 5432, 6379, 8000 **не открывайте** наружу. API доступен через Caddy на 443.

---

## Шаг 1. Подключиться к серверу

```bash
ssh -i ~/.ssh/your-key.pem ubuntu@<ELASTIC_IP>
```

---

## Шаг 2. Обновить систему и установить Docker

```bash
sudo apt update && sudo apt upgrade -y

sudo apt install -y ca-certificates curl git

# Docker
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu

# Перелогиниться, чтобы группа docker применилась
exit
```

Подключиться снова:

```bash
ssh -i ~/.ssh/your-key.pem ubuntu@<ELASTIC_IP>
docker --version
docker compose version
```

---

## Шаг 3. Swap (рекомендуется для t3.micro, 1 GB RAM)

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
free -h
```

---

## Шаг 4. Клонировать репозиторий

```bash
cd ~
git clone git@github.com:igor-chernetsky/PribilkeBE.git
cd PribilkeBE
```

---

## Шаг 5. Настроить переменные окружения

```bash
cp .env.production.example .env
nano .env
```

Обязательно смените `POSTGRES_PASSWORD` и обновите пароль в `DATABASE_URL`.

---

## Шаг 6. Запустить приложение

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

Все 4 сервиса (`db`, `redis`, `api`, `worker`) должны быть `running`.

---

## Шаг 7. Заполнить БД начальными данными

```bash
docker compose -f docker-compose.prod.yml exec worker \
  python -c "
import sys; sys.path.insert(0, '/app/src')
from pribilka.workers.tasks import run_collector, COLLECTOR_MAP
for key in COLLECTOR_MAP:
    print(run_collector(key))
"
```

---

## Шаг 8. Проверить API

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/api/v1/markets/pl/summary
```

Ожидаемый ответ `/health`:

```json
{"status": "ok", "country": "PL"}
```

---

## Шаг 9. Домен Dynu (pribilka.webredirect.org)

В [Dynu Control Panel](https://www.dynu.com/ControlPanel) → **DDNS Services** → ваш hostname.

**Важно:** используйте **A-запись на Elastic IP**, а не «Web Redirect / Port Forwarding» — иначе HTTPS и API работать не будут.

1. Откройте hostname `pribilka.webredirect.org`
2. В разделе **IPv4 Address** укажите **Elastic IP** вашего EC2
3. Сохраните

Проверка с вашего компьютера (подождите 1–5 мин):

```bash
dig +short pribilka.webredirect.org
# должен вернуть ваш Elastic IP
```

### Security Group

Добавьте правила (если ещё нет):

| Type  | Port | Source    |
|-------|------|-----------|
| HTTP  | 80   | 0.0.0.0/0 |
| HTTPS | 443  | 0.0.0.0/0 |

Порт **8000 наружу не открывайте** — доступ только через Caddy на 443.

---

## Шаг 10. HTTPS через Caddy

На EC2 (API должен уже работать на `127.0.0.1:8000`):

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy

cd ~/PribilkeBE
sudo cp Caddyfile.example /etc/caddy/Caddyfile
sudo systemctl enable caddy
sudo systemctl reload caddy
```

Caddy автоматически получит сертификат Let's Encrypt для `pribilka.webredirect.org`.

Проверка:

```bash
curl https://pribilka.webredirect.org/health
curl https://pribilka.webredirect.org/api/v1/markets/pl/summary
```

Документация API: `https://pribilka.webredirect.org/docs`

Если Caddy не стартует — смотрите логи:

```bash
sudo journalctl -u caddy -f
```

Частые причины: DNS ещё не обновился, порты 80/443 закрыты в Security Group.

---

## Шаг 11. Base URL для приложения

Польское приложение:

```
https://pribilka.webredirect.org/api/v1/markets/pl
```

Примеры:
- Health: `https://pribilka.webredirect.org/health`
- Депозиты: `https://pribilka.webredirect.org/api/v1/markets/pl/deposits`
- Сводка: `https://pribilka.webredirect.org/api/v1/markets/pl/summary`
- Swagger: `https://pribilka.webredirect.org/docs`

---

## Шаг 12. Автозапуск после перезагрузки

Docker с `restart: unless-stopped` в `docker-compose.prod.yml` поднимет контейнеры автоматически.

Проверка:

```bash
sudo reboot
# после переподключения:
docker compose -f docker-compose.prod.yml ps
```

---

## Автодеплой через GitHub Actions

После каждого push в `master`: тесты → SSH на EC2 → `git pull` → `docker compose up --build`.

### 1. Deploy key на EC2 (для private repo)

На EC2:

```bash
ssh-keygen -t ed25519 -C "pribilka-deploy" -f ~/.ssh/github_deploy -N ""
cat ~/.ssh/github_deploy.pub
```

GitHub → репозиторий **PribilkeBE** → Settings → Deploy keys → Add deploy key:
- Title: `ec2-production`
- Key: содержимое `.pub`
- Allow write access: **выключено**

На EC2 настроить git на SSH:

```bash
cd ~/PribilkeBE
git remote set-url origin git@github.com:igor-chernetsky/PribilkeBE.git

cat >> ~/.ssh/config << 'EOF'
Host github.com
  HostName github.com
  User git
  IdentityFile ~/.ssh/github_deploy
  IdentitiesOnly yes
EOF
chmod 600 ~/.ssh/config

ssh -T git@github.com   # должно: Hi igor-chernetsky/PribilkeBE! ...
git pull
```

### 2. Security Group — SSH для GitHub Actions

GitHub Actions подключается с **динамических IP**. Варианты:

**Простой (для MVP):** открыть SSH для всех, доступ только по ключу:

| Type | Port | Source    |
|------|------|-----------|
| SSH  | 22   | 0.0.0.0/0 |

**Безопаснее:** self-hosted GitHub runner на EC2 (настройка сложнее).

### 3. Secrets в GitHub

Репозиторий → Settings → Secrets and variables → Actions → New repository secret:

| Secret       | Значение                          |
|--------------|-----------------------------------|
| `EC2_HOST`   | Elastic IP, напр. `52.x.x.x`      |
| `EC2_USER`   | `ubuntu`                          |
| `EC2_SSH_KEY`| полное содержимое `.pem` файла    |

### 4. Первый push с workflow

Локально:

```bash
git add .
git commit -m "Add GitHub Actions deploy"
git push origin master
```

GitHub → вкладка **Actions** → workflow **Deploy** → статус run.

### 5. Ручной деплой (если нужно)

```bash
cd ~/PribilkeBE
bash scripts/deploy.sh
```

---

## Обновление после изменений в коде (вручную)

```bash
cd ~/PribilkeBE
bash scripts/deploy.sh
```

---

## Полезные команды

```bash
# Логи API
docker compose -f docker-compose.prod.yml logs -f api

# Логи worker (коллекторы)
docker compose -f docker-compose.prod.yml logs -f worker

# Статус
docker compose -f docker-compose.prod.yml ps

# Остановить
docker compose -f docker-compose.prod.yml down
```

---

## Алерты админу при сбое парсеров

Когда парсер банка падает или возвращает 0 оферт, worker отправляет уведомление (не чаще 1 раза в 12 ч).

### Telegram (рекомендуется)

1. Напишите [@BotFather](https://t.me/BotFather) → `/newbot` → получите токен
2. Напишите боту любое сообщение
3. Откройте `https://api.telegram.org/bot<TOKEN>/getUpdates` → найдите `"chat":{"id":123456789}`
4. Добавьте в `.env` на EC2:

```bash
ADMIN_TELEGRAM_BOT_TOKEN=123456:ABC...
ADMIN_TELEGRAM_CHAT_ID=123456789
COLLECTOR_ALERT_COOLDOWN_HOURS=12
```

5. Перезапустите worker:

```bash
docker compose -f docker-compose.prod.yml up -d worker
```

Пример сообщения:

```
⚠️ Pribilka — problem z kolektorem depozytów
• ING Bank Śląski (IngDepositParser): 0 ofert (możliwa zmiana layoutu strony)
```

Альтернатива: `ADMIN_WEBHOOK_URL` — POST JSON `{"text": "...", "source": "pribilka-collector"}`.

---

## Если не хватает RAM

При OOM или медленной работе — вынести БД и Redis наружу:

- PostgreSQL → [Neon](https://neon.tech) (бесплатно)
- Redis → [Upstash](https://upstash.com) (бесплатно)

Обновите `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL` в `.env` и уберите сервисы `db`/`redis` из compose.
