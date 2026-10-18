# 🚀 Muhtasham Telegram AI Agent — VPS Joylashtirish Qo'llanmasi (DEPLOYMENT.md)

Ushbu qo'llanma **Ubuntu Server 24.04 LTS** (yoki Ubuntu 22.04 LTS) serverida tizimni 24/7 uzluksiz, xavfsiz va barqaror ishga tushirish uchun mo'ljallangan.

---

## 1. Server Minimal Talablari

- **OS**: Ubuntu Server 24.04 LTS (x86_64)
- **CPU**: 2 vCPU
- **RAM**: 4 GB RAM
- **Disk**: 40 GB NVMe / SSD
- **Tarmoq**: Barqaror internet ulanishi va statik IP

---

## 2. Serverni Dastlabki Tayyorlash va Xavfsizlik

### 2.1. Tizimni yangilash:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget ufw fail2ban htop ffmpeg
```

### 2.2. Xavfsizlik devorini (UFW) sozlash:
Faqat SSH portini ochiq qoldiring (masalan 22), PostgreSQL yoki boshqa ichki portlarni tashqi internetdan yoping:
```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw enable
```

---

## 3. Docker va Docker Compose O'rnatish

Docker rasmiy repozitoriyasidan o'rnatish:
```bash
# Docker o'rnatish
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Joriy foydalanuvchini docker guruhiga qo'shish
sudo usermod -aG docker $USER
newgrp docker

# O'rnatilganini tekshirish
docker --version
docker compose version
```

---

## 4. Loyiha Kodini Serverga Joylash

```bash
# Loyiha papkasini yaratish va o'tish
cd /opt
sudo git clone <REPO_URL> tg_ovchi
sudo chown -R $USER:$USER tg_ovchi
cd tg_ovchi
```

---

## 5. Telethon Sessiyasini Yaratish (Sessiya Kaliti)

Telethon kuzatuv akkauntini bir marta serverda autentifikatsiya qilish uchun quyidagi qadamlarni bajaring:

```bash
# Python venv yaratish
python3 -m venv setup_env
source setup_env/bin/activate
pip install telethon

# Sessiya generatorini ishga tushirish
python scripts/generate_session.py
```
1. Telefon raqamingizni kiriting.
2. Telegramingizga kelgan tasdiqlash kodini kiriting.
3. Skript ekranga chiqarib bergan `TELETHON_SESSION_STRING=...` qiymatini nusxalab oling.
4. Muhitdan chiqing: `deactivate && rm -rf setup_env`

---

## 6. Maxfiy Sozlamalar Faylini (`.env`) Yaratish

```bash
cp .env.example .env
nano .env
```

Quyidagi parametrlarni o'z ma'lumotlaringiz bilan to'ldiring:
```env
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abcdef0123456789abcdef0123456789
TELETHON_SESSION_STRING=1ApWapzMB...nusxalangan_sessiya...
BOT_TOKEN=1234567890:ABCDefGhIJKlmNoPQRsTUVwxyZ_1234567
ADMIN_IDS=123456789,987654321
GEMINI_API_KEY=AIzaSyYourActualApiKeyHere
POSTGRES_PASSWORD=JudaXavfsizParol2026!
TARGET_CHANNEL=@muhtashamtraveluzz
```

Fayl ruxsatini cheklang (faqat server egasi o'qiy olsin):
```bash
chmod 600 .env
```

---

## 7. Loyihani Docker Compose Orqali Ishga Tushirish

```bash
# Konteynerlarni yig'ish va fonda ishga tushirish
docker compose up -d --build

# Ishlayotgan konteynerlarni tekshirish
docker compose ps
```

Konteynerlar holati:
- `muhtasham_postgres`: `healthy`
- `muhtasham_agent`: `running`

---

## 8. Loglarni Kuzatish va Diagnostika

```bash
# Agent faoliyatini jonli kuzatish
docker compose logs -f agent

# Baza loglarini ko'rish
docker compose logs -f db
```

---

## 9. Avtomatik Zaxira Nusxa (Cron Backup) Sozlash

Server har kuni 03:00 da bazaning zaxira nusxasini olishi uchun cron vazifasini qo'shamiz:

```bash
crontab -e
```
Quyidagi qatorni qo'shing:
```cron
0 3 * * * cd /opt/tg_ovchi && docker compose exec -T db /backups/../scripts/backup.sh >> /opt/tg_ovchi/logs/backup.log 2>&1
```

---

## 10. Tizimni Yangilash (Update)

Kodga yangi o'zgartirish kiritilganda serverda yangilash:
```bash
cd /opt/tg_ovchi
git pull
docker compose up -d --build
```
PostgreSQL ma'lumotlari `postgres_data` jildida saqlanadi va yangilanishlar vaqtida o'chib ketmaydi.
