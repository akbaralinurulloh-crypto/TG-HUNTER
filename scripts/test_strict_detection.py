import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from PIL import Image
import google.generativeai as genai
from app.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.5-flash')
img = Image.open('./temp_media/nurlisafar_19991.jpg')

prompt = """
Sen Muhtasham Travel agentligi uchun professional kontent tahlilchisisan.
Ushbu media (rasm yoki video) va undagi matn/audioni o'ta sinchkovlik bilan tekshir:
1. Ekrandagi yozuvlarda, ziyoratchilarning sumkalari, kiyimlari, lentalarida yoki fonda 'Nurli Safar' yoki boshqa birorta begona turagentlik/brend nomi yoki logotipi bormi?
2. '+998 88 832 77 00' yoki '888327700' dan boshqa har qanday telefon raqam bormi (hatto sumka va kiyimlarda kichik yozilgan bo'lsa ham)?
3. Videoning audio ovozida 'Nurli Safar' yoki begona kompaniya haqida gapirilganmi?
4. QAT'IY TAQIQLANADI: Hadis to'qima va hadis qo'shma! Hadis yozish taqiqlangan!

MUHIM QOIDA:
- Agar yuqoridagilardan birortasida begona firma, 'Nurli Safar' yoki begona telefon raqam ko'rinsa:
  publish_decision: REJECT, has_competitor: true, rejection_reason: aniqlangan sabab.
- Faqat va faqat begona firma va begona raqamsiz toza media bo'lsa:
  publish_decision: AUTO_PUBLISH, has_competitor: false, va rasm/videoga mos go'zal, samimiy izoh yoz (oxiriga 📞 Murojaat uchun: +998 88 832 77 00 qo'sh).

Quyidagi JSON formatida javob ber:
{
  "detected_text_and_logos": "tasvirda ko'ringan yozuvlar va logotiplar",
  "detected_phone_numbers": "tasvirda ko'ringan telefon raqamlar yoki yo'q",
  "has_competitor": true,
  "publish_decision": "REJECT",
  "rejection_reason": "rad etish sababi",
  "headline": null,
  "body": null
}
"""

res = model.generate_content([prompt, img], generation_config={"response_mime_type": "application/json"})
print(res.text)
