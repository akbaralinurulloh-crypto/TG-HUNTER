# 💾 Zaxira Nusxa Olish va Tiklash Yo'riqnomasi (BACKUP.md)

Ushbu hujjat **Muhtasham Telegram AI Agent** tizimining PostgreSQL ma'lumotlar bazasidan zaxira nusxa (backup) olish va uni qayta tiklash (restore — AT-12) tartibini belgilaydi.

---

## 1. Zaxira Nusxa Olish Mexanizmi

Tizimda zaxira nusxa olish `scripts/backup.sh` skripti orqali amalga oshiriladi:
- Barcha jadvallar (`sources`, `source_messages`, `analyses`, `publications`, `approvals`, `audit_logs`) to'liq eksport qilinadi.
- Chiqarilgan SQL ma'lumotlari `gzip` yordamida siqiladi (fayl hajmi 85-90% gacha kamayadi).
- Nusxalar `./backups/` papkasida `muhtasham_db_YYYYMMDD_HHMMSS.sql.gz` ko'rinishida saqlanadi.
- 7 kundan eski nusxalar disk joyini tejash maqsadida avtomatik o'chiriladi.

---

## 2. Qo'lda Zaxira Nusxa Olish

Serverda qo'lda tezkor nusxa olish:

```bash
# Docker konteyner ichidan nusxa olish:
docker compose exec agent /app/scripts/backup.sh

# Yoki to'g'ridan-to'g'ri xost orqali:
./scripts/backup.sh
```

Natija quyidagicha ko'rinadi:
```
[Fri Oct 16 03:00:01 UTC 2026] Zaxira nusxa olish boshlandi: muhtasham_db...
[Fri Oct 16 03:00:03 UTC 2026] Zaxira nusxa muvaffaqiyatli saqlandi: /backups/muhtasham_db_20261016_030001.sql.gz (Hajmi: 4.2M)
[Fri Oct 16 03:00:03 UTC 2026] 7 kundan eski nusxalar tozalandi.
```

---

## 3. Zaxira Nusxadan Qayta Tiklash (AT-12 Qabul Testi)

Kutilmagan nosozlik, server almashuvi yoki test o'tkazish uchun zaxira nusxadan tiklash:

### 3.1. Test Bazasiga Tiklash Sinovi:
```bash
# 1. Test uchun bo'sh baza yaratish:
docker compose exec db psql -U postgres -c "CREATE DATABASE test_restore_db;"

# 2. scripts/restore.sh orqali ma'lumotlarni test bazasiga tiklash:
./scripts/restore.sh backups/muhtasham_db_20261016_030001.sql.gz test_restore_db

# 3. Tiklangan jadvallarni tekshirish:
docker compose exec db psql -U postgres -d test_restore_db -c "\dt"
docker compose exec db psql -U postgres -d test_restore_db -c "SELECT count(*) FROM source_messages;"
```

### 3.2. Asosiy Bazani To'liq Qayta Tiklash:
Agar asosiy bazani tiklash zarur bo'lsa:
```bash
# 1. Agentni vaqtincha to'xtatish
docker compose stop agent

# 2. Tiklashni amalga oshirish
./scripts/restore.sh backups/muhtasham_db_20261016_030001.sql.gz muhtasham_db

# 3. Agentni qayta ishga tushirish
docker compose start agent
```

---

## 4. Zaxira Nusxalarni Xavfsiz Masofaviy Saqlash

Zaxira fayllarini har doim boshqa mustaqil serverga (yoki S3 / Google Drive / Telegram maxfiy arxiv kanaliga) ko'chirish tavsiya etiladi:
```bash
# rsync orqali ikkinchi serverga uzatish namunasi:
rsync -avz -e ssh /opt/tg_ovchi/backups/ backupuser@backup.server.com:/secure_storage/
```
