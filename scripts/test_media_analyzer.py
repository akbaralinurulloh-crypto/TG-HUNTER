import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import cv2
from PIL import Image
import google.generativeai as genai
from app.config import settings

genai.configure(api_key=settings.GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-3.5-flash")


def test_media(path, mtype):
    parts = []
    if mtype == "PHOTO" and os.path.exists(path):
        parts.append(Image.open(path))
    elif mtype == "VIDEO" and os.path.exists(path):
        size_mb = os.path.getsize(path) / (1024 * 1024)
        if size_mb <= 15:
            with open(path, "rb") as f:
                parts.append({"mime_type": "video/mp4", "data": f.read()})
        else:
            cap = cv2.VideoCapture(path)
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            for idx in [total // 4, total // 2, (3 * total) // 4]:
                cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                ret, frame = cap.read()
                if ret:
                    parts.append(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
            cap.release()

    prompt = """
    Sen Muhtasham Travel uchun professional kontent tahlilchisisan.
    Ushbu mediani tekshir:
    1. 'Nurli Safar' yoki begona kompaniya logotipi, yozuvi yoki audioda tili bormi?
    2. +998 88 832 77 00 dan boshqa begona telefon raqam bormi?
    3. Hadis yozish qat'iyan taqiqlangan! Hadis to'qima!
    
    Agar begona belgi yoki raqam bo'lsa:
    {"has_competitor": true, "decision": "REJECT", "rejection_reason": "Begona belgi"}
    Agar toza bo'lsa:
    {"has_competitor": false, "decision": "AUTO_PUBLISH", "headline": "Sarlavha", "body": "Go'zal izoh...\\n\\n📞 Murojaat uchun: +998 88 832 77 00"}
    """
    res = model.generate_content([prompt] + parts, generation_config={"response_mime_type": "application/json"})
    print(f"=== {os.path.basename(path)} ===")
    print(res.text)


if __name__ == "__main__":
    test_media("./temp_media/muhtashamtravel_8406.jpg", "PHOTO")
    test_media("./temp_media/nurlisafar_19991.jpg", "PHOTO")
