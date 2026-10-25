import sys
import json
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import google.generativeai as genai
from app.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-3.5-flash')

with open('./temp_media/muhtashamtravel_8448.mp4', 'rb') as f:
    video_bytes = f.read()

prompt = """
Sen Muhtasham Travel agentligi uchun professional kontent tahlilchisisan.
Ushbu videoni (tasvir va audioni) to'liq tekshir:
1. Videoning ichida (ekrandagi yozuvlarda, orqa fondagi peshlavhalarda, kiyimlarda yoki suv belgilarida) 'Nurli Safar' yoki boshqa begona kompaniya yozuvi bormi?
2. Videoning ovozida (audioda) 'Nurli Safar' yoki begona kompaniya nomi aytilganmi?
3. Videoda '+998 88 832 77 00' dan boshqa birorta begona telefon raqami ko'rsatilganmi?
4. QAT'IY QOIDA: Agar 1, 2 yoki 3-bandlardan birortasi 'Ha' bo'lsa, 'has_competitor_mark' qiymatini true qil va 'publish_decision' ni 'REJECT' qil!
5. QAT'IY QOIDA: Hech qachon hadis to'qima va hadis qo'shma! Hadis yozish taqiqlangan!

Quyidagi qat'iy JSON formatida javob ber:
{
  "has_competitor_mark": true,
  "competitor_details": "aniqlangan begona yozuv yoki raqam tafsiloti",
  "topic": "Umrah",
  "quality_score": 9,
  "publish_decision": "REJECT",
  "rejection_reason": "Videoda Nurli Safar yozuvi aniqlandi",
  "headline": "Qisqa mos sarlavha",
  "body": "Izoh matni...\\n\\n📞 Murojaat uchun: +998 88 832 77 00"
}
"""

res = model.generate_content(
    [prompt, {"mime_type": "video/mp4", "data": video_bytes}],
    generation_config={"response_mime_type": "application/json"}
)
print("JSON OUTPUT:\n", res.text)
