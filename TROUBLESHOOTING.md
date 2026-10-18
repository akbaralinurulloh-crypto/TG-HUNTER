# 🔧 Nosozliklarni Aniqlash va Bartaraf Etish (TROUBLESHOOTING.md)

Ushbu qo'llanmada **Muhtasham Telegram AI Agent** faoliyatida yuzaga kelishi mumkin bo'lgan texnik holatlar, xatoliklar va ularni bartaraf etish bosqichlari keltirilgan (TZ 9-bandi).

---

## 1. Telegram FloodWait Xatoligi
- **Alomat**: Loglarda `FloodWaitError: A wait of X seconds is required` ko'rinadi.
- **Sabab**: Telegram serverlari so'rovlar chastotasini cheklagan (rate limit).
- **Tizim harakati**: Telethon va aiogram klientlarida avtomatik `FloodWait` ushlagichi mavjud. Agent so'ralgan $X$ soniyani kutadi (`sleep(X + 1)`) va jarayonni xavfsiz davom ettiradi. Hech qanday ma'lumot yo'qolmaydi.
- **Tavsiya**: Agar kutish vaqti 300 soniyadan oshsa, `SOURCE_CHANNELS` yangiliklarini tekshirish intervali va tarixni skan qilish hajmini kamaytiring.

---

## 2. Telegram Noaniq Javobi (Telegram Timeout / Network Error)
- **Alomat**: Post nashr qilinayotganda tarmoq uzilib, `TelegramNetworkError` yuzaga keldi.
- **Tizim harakati**: Tizim postni **hech qachon darhol qayta yubormaydi** (aks holda maqsadli kanalda ikkita bir xil post chiqib qolishi mumkin!). Post holati `UNCERTAIN` qilib belgilanadi va `audit_logs`ga yoziladi.
- **Bartaraf etish**:
  1. `/status` buyrug'i orqali agent holatini ko'ring.
  2. `@muhtashamtraveluzz` kanaliga kirib, post chiqqan-chiqmaganini tekshiring.
  3. Agar chiqqan bo'lsa, holat bazada `PUBLISHED`ga o'tkaziladi. Agar chiqmagan bo'lsa, botdan qayta tasdiqlash mumkin.

---

## 3. Server Qayta Ishga Tushganda (Restart Recovery)
- **Alomat**: VPS server o'chib yondi yoki Docker konteyner qayta ishga tushdi.
- **Tizim harakati**: `src/services/recovery.py` skripti ishga tushish paytida avtomatik ravishda barcha holatlarni tekshiradi:
  * `PUBLISHING` holatida qolib ketgan postlar tekshiriladi: agar `publications` jadvalida yozuv bo'lsa, `PUBLISHED`ga to'g'irlanadi; yozuv bo'lmasa, qayta dublikat bo'lmasligi uchun `UNCERTAIN` holatiga o'tkaziladi.
  * Tahlili to'xtab qolgan postlar xavfsiz qayta ko'rib chiqish uchun `NEW` holatiga qaytariladi.
- Hech qanday ma'lumot o'chib ketmaydi va allaqachon chiqqan postlar takrorlanmaydi.

---

## 4. Google Gemini AI API Ishlamay Qolishi
- **Alomat**: Loglarda `Gemini API call failed` yoki `ResourceExhausted` xabari chiqadi.
- **Tizim harakati**: Tizim tekshiruvni chetlab o'tib, postni xavfsizliksiz kanalga joylab yubormaydi!
  * Deterministik xavfsiz qoidalar asosidagi baholash ishga tushadi.
  * Muhim yoki shubhali bo'lishi mumkin bo'lgan barcha postlar zaxira tarzida administrator tasdig'iga (`PENDING_APPROVAL`) yo'naltiriladi.
- **Bartaraf etish**: `https://aistudio.google.com` orqali AI API kaliti kvotasi va faolligini tekshiring.

---

## 5. Begona Shaxs Botni Boshqarishga Urinishi
- **Alomat**: Loglarda `UNAUTHORIZED_ACCESS_ATTEMPT` va foydalanuvchi IDsi chiqadi.
- **Tizim harakati**: `IsAdminFilter` notanish foydalanuvchilarning barcha buyruq va tugma bosishlarini rad etadi va ularga "Sizda huquq yo'q" xabari beriladi. Begona shaxs postni tasdiqlay yoki o'chira olmaydi.
- **Admin qo'shish**: Agar yangi adminga ruxsat berish kerak bo'lsa, `.env` faylidagi `ADMIN_IDS` qatoriga uning Telegram ID raqamini vergul bilan qo'shing va agentni qayta ishga tushiring:
  ```env
  ADMIN_IDS=123456789,987654321,YANGI_ID
  ```

---

## 6. Telethon Sessiyasi Bekor Qilinishi (Session Revoked)
- **Alomat**: `telethon.errors.rpcerrorlist.AuthKeyUnregisteredError` yoki `SessionPasswordNeededError`.
- **Sabab**: Telegram akkauntidan sessiya o'chirilgan yoki 2FA parol o'zgargan.
- **Bartaraf etish**:
  1. `python scripts/generate_session.py` skriptini ishga tushiring.
  2. Yangi sessiya kalitini oling.
  3. `.env` dagi `TELETHON_SESSION_STRING` parametriga yangi kalitni yozing.
  4. Konteynerni qayta ishga tushiring: `docker compose restart agent`.
