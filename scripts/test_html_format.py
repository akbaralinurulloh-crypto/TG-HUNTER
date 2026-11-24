import html
import re

def format_html(cleaned_text, caption, instagram_url='https://www.instagram.com/muhtasham_travel/'):
    text = html.escape(cleaned_text.strip(), quote=False)
    cap = html.escape(caption.strip(), quote=False)
    insta_link = f'<a href="{instagram_url}">Instagram</a>'

    if instagram_url:
        if re.search(r'\binstagram\b', text, re.IGNORECASE):
            text = re.sub(r'instagram(?:\s*[:\-–]\s*https?://\S+)?', insta_link, text, count=1, flags=re.IGNORECASE)
        elif text:
            text = f"{text}\n\n📷 {insta_link}"
        elif cap:
            if re.search(r'\binstagram\b', cap, re.IGNORECASE):
                cap = re.sub(r'instagram(?:\s*[:\-–]\s*https?://\S+)?', insta_link, cap, count=1, flags=re.IGNORECASE)
            else:
                cap = f"{cap}\n\n📷 {insta_link}"

    combined = f"{text}\n\n{cap}".strip() if cap else text
    return combined

sample = """Бугун дастурхонда ҳақиқий байрам! 😍🍽️
“Muhtasham Travel — xotirjam 
ibodatni xohlovchilar uchun!”

📱 Telegram  😎 Instagram
😎YouTube     📱 Facebook"""

result = format_html(sample, "Go'zal ziyorat onlari.")
print(result)
