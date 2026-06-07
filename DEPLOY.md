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
git clone https://github.com/YOUR_USER/PribilkaBE.git
cd PribilkaBE
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
curl http://127.0.0.1:8000/api/v1/market-summary
```

Ожидаемый ответ `/health`:

```json
{"status": "ok", "country": "PL"}
```

---

## Шаг 9. HTTPS через Caddy (если есть домен)

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update && sudo apt install -y caddy

cp Caddyfile.example Caddyfile
nano Caddyfile   # заменить api.yourdomain.com

sudo cp Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

В DNS добавьте A-запись: `api.yourdomain.com` → Elastic IP.

Проверка:

```bash
curl https://api.yourdomain.com/health
```

---

## Шаг 10. Автозапуск после перезагрузки

Docker с `restart: unless-stopped` в `docker-compose.prod.yml` поднимет контейнеры автоматически.

Проверка:

```bash
sudo reboot
# после переподключения:
docker compose -f docker-compose.prod.yml ps
```

---

## Обновление после изменений в коде

```bash
cd ~/PribilkaBE
git pull
docker compose -f docker-compose.prod.yml up -d --build
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

## Если не хватает RAM

При OOM или медленной работе — вынести БД и Redis наружу:

- PostgreSQL → [Neon](https://neon.tech) (бесплатно)
- Redis → [Upstash](https://upstash.com) (бесплатно)

Обновите `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL` в `.env` и уберите сервисы `db`/`redis` из compose.
