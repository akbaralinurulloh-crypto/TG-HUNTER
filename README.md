# 🕋 Telegram Umrah Content Agent (v2.0)
## Muhtasham Travel uchun AI kontent yig‘ish va avtomatik nashr qilish tizimi

[![Python](https://img.shields.io/badge/Python-3.12%2B-blue.svg)](https://www.python.org/)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-2CA5E0.svg)](https://docs.aiogram.dev/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red.svg)]()

> **Umrah, Makka, Madina, ziyorat va sayohat mavzularidagi Telegram kanallarini kuzatish, qonuniy foydalanish huquqlarini tekshirish, AI orqali o‘zbek tilida sarlavha va ravon post yaratish, takroriy postlarni bloklash va kuniga 20–50 ta sifatli materialni Muhtasham Travel kanaliga avtomatik taqsimlab nashr qiluvchi aqlli tizim.**

---

## 📋 Mundarija
1. [Loyiha Haqida](#-loyiha-haqida)
2. [Asosiy Xususiyatlar](#-asosiy-xususiyatlar)
3. [Mualliflik Huquqi va Sifat Nazorati](#-mualliflik-huquqi-va-sifat-nazorati)
4. [AI Tahlil va Qayta Yozish Moduli](#-ai-tahlil-va-qayta-yozish-moduli)
5. [Nashr Jadvali (Kuniga 20–50 post)](#-nashr-jadvali-kuniga-2050-post)
6. [Telegram Boshqaruv Boti Buyruqlari](#-telegram-boshqaruv-boti-buyruqlari)
7. [Birinchi Amaliy Bosqich (Kanal Ulanish Sinovi)](#-birinchi-amaliy-bosqich-kanal-ulanish-sinovi)
8. [Tezkor Ishga Tushirish (Docker)](#-tezkor-ishga-tushirish-docker)
9. [Avtomatlashtirilgan Testlar Natijalari](#-avtomatlashtirilgan-testlar-natijalari)

---

## 🔍 Loyiha Haqida

- **Mavzular**: Umrah, Makka, Madina, Masjid al-Haram, Masjid an-Nabaviy, ziyorat, sayohat va ziyoratchilar uchun foydali maslahatlar.
- **Til**: O‘zbek adabiy tili, tabiiy, aniq va ravon uslub.
- **Maqsadli kanal**: [@muhtashamtraveluzz](https://t.me/muhtashamtraveluzz)
- **Avtonashr**: Inson tasdig‘ini kutmasdan, sifat, huquq va faktik xavfsizlik tekshiruvlaridan o‘tgan materiallar avtomatik nashr qilinadi.

---

## 🛡 Mualliflik Huquqi va Sifat Nazorati (TZ Section 6 & 8)

- **Qat'iy qoida**: Foydalanish huquqi tekshirilmagan (`rights_status != 'VERIFIED'`) manbalardan olingan matn, rasm yoki video **hech qachon avtomatik nashr qilinmaydi**.
- **Faktik xavfsizlik**: Asossiz narx, viza kafolatlari, soxta diniy da'volar yoki 100% bepul deb nomlangan manipulyativ postlar qat'iy bloklanadi.
- **Takroriy postlardan himoya**:
  1. `source_id` + `source_message_id` yagona kalit tekshiruvi.
  2. Normallashtirilgan matn va media xeshi (`content_hash`).
  3. Rasm perceptual xeshi (pHash Hamming masofasi $\le 5$).
  4. Semantik va o'zak (stem) o'xshashlik tekshiruvi.

---

## 🧠 AI Tahlil va Qayta Yozish Moduli (TZ Section 7)

AI har bir postni qat'iy Pydantic JSON sxemasi asosida tahlil qiladi:
- `headline` — Qisqa, jozibador sarlavha.
- `body` — Sayqallangan, o'zbekcha ravon post matni (asl faktlarni buzmagan holda).
- `topic` — Umrah, Makka, Madina, Ziyorat, Sayohat.
- `quality_score` — 0 dan 10 gacha umumiy sifat balli.
- `factual_risk` — `NONE`, `SUSPICIOUS`, `HIGH`.
- `media_action` — `USE_ORIGINAL`, `USE_TEXT_ONLY`, `DISCARD`.
- `rights_status` — `VERIFIED` yoki `UNVERIFIED`.
- `publish_decision` — `AUTO_PUBLISH`, `PENDING_APPROVAL`, `REJECT`.
- `rejection_reason` — Rad etish sababi.

---

## ⏰ Nashr Jadvali: Kuniga 20–50 Post (TZ Section 11)

- Postlar kun davomida (`Asia/Tashkent` vaqti bilan **07:00 dan 23:00 gacha**) teng taqsimlanadi.
- Bir vaqtda bir nechta post tashlanib, auditoriya bezor qilinmaydi (interval: 20–35 daqiqa).
- Sifatli material yetarli bo'lmasa, sun'iy ravishda son to'ldirilmaydi (sifat songa qurbon qilinmaydi).
- Har bir nashr bazada atomar tranzaksiya orqali qulflanadi (`SELECT ... FOR UPDATE`), server qayta ishga tushganda birorta post ikki marta chiqib ketmaydi.

---

## 🤖 Telegram Boshqaruv Boti Buyruqlari (TZ Section 12)

Faqat ruxsat berilgan administratorlar (`ADMIN_IDS`) uchun ishlaydi:

| Buyruq | Tavsif |
| :--- | :--- |
| `/start` | Bot menyusi va asosiy tugmalar |
| `/status` | Tizim holati (faol/to'xtatilgan), navbat hajmi, oxirgi nashr vaqti |
| `/sources` | Faol manbalar ro'yxati va ularning mualliflik huquqi holati |
| `/stats` | Oxirgi 24 soatlik to'liq tahliliy hisobot |
| `/pause` | Avtomatik nashrni vaqtincha to'xtatish (ma'lumotlar saqlanadi) |
| `/resume` | Avtomatik nashrni davom ettirish |
| `/queue` | Navbatdagi rejalashtirilgan postlar ro'yxati va vaqtlari |
| `/errors` | Tizim jurnallaridagi oxirgi muhim xatoliklar |
| `/help` | Buyruqlar bo'yicha yo'riqnoma |

---

## 🧪 Birinchi Amaliy Bosqich: Kanal Ulanish Sinovi (TZ Section 17)

Loyiha sozlamalari va Telegram kanal ulanishini tekshirish uchun maxsus diagnostika skripti ishlab chiqilgan:

```bash
python -m app.publisher.channel_tester
```
Bu skript:
1. `BOT_TOKEN` to'g'riligini tekshiradi (`get_me()`).
2. Botning `@muhtashamtraveluzz` kanalida administrator ekanligini va `can_post_messages` huquqi borligini tekshiradi.
3. Kanalga bitta sinov xabarini yuborib, xabar ID raqamini oladi va logga yozadi.

---

## 🐳 Tezkor Ishga Tushirish (Docker Compose)

1. **Sozlamalarni kiriting**:
   ```bash
   cp .env.example .env
   nano .env  # BOT_TOKEN, ADMIN_IDS, GEMINI_API_KEY larni kiriting
   ```

2. **Konteynerlarni ishga tushiring**:
   ```bash
   docker compose up -d --build
   ```

3. **Loglarni kuzatish**:
   ```bash
   docker compose logs -f agent
   ```

---

## 📊 Avtomatlashtirilgan Testlar Natijalari (TZ Section 18)

Barcha 18 ta texnik talab bo'yicha to'liq testlar yozildi va `pytest` orqali 100% muvaffaqiyat bilan bajarildi:

```bash
============================= 22 passed in 2.60s =============================
```
- `test_sources.py` — Manbalar ro'yxati va foydalanish huquqi tekshiruvi: **PASSED**
- `test_ai_processing.py` — AI sxemasi, mavzuga moslik va xavfli postlarni rad etish: **PASSED**
- `test_deduplication.py` — Xesh va semantik dublikatlarni aniqlash: **PASSED**
- `test_scheduler.py` — 20–50 postni kun bo'yicha teng taqsimlash va hisobot: **PASSED**
- `test_publisher.py` — Atomar nashr va takroriy nashr bo'lmasligi (idempotency): **PASSED**
- `test_permissions.py` — Admin filtri, konfiguratsiya tekshiruvi va loglarda tokenlarni niqoblash: **PASSED**
