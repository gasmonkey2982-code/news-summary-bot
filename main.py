import feedparser
import os
from google import genai

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

client = genai.Client(api_key=GOOGLE_API_KEY)

# News Sources
RSS_URLS = [
    "https://indianexpress.com/section/technology/feed/",
    "https://indianexpress.com/section/sports/feed/",
    "https://indianexpress.com/section/india/feed/"
]

def get_news():
    """Multiple RSS feeds se mixed news nikalta hai"""
    all_news = []
    for url in RSS_URLS:
        feed = feedparser.parse(url)
        for entry in feed.entries[:3]:
            title = entry.title
            link = entry.link
            all_news.append(f"• {title}\n  {link}")
            
    return "\n\n".join(all_news)

def summarize_with_ai(raw_news):
    """Gemini se free model use karke summary banata hai"""
    
    prompt = f"""
    Yeh taaza khabrein hain:
    {raw_news}

    IMPORTANT INSTRUCTIONS:
    1. Summary SIRF ROMAN SCRIPT (English letters) mein likho. Devanagari/Hindi font bilkul mat use karo.
    2. Language HINGLISH honi chahiye (Hindi words English letters mein). 
       Example: "PUC certificate check kar lo" ✅ | "Check your PUC certificate" ❌
    3. 5 chhote bullet points banao. Tone casual rakho.

    Summary shuru karo:
    """

    try:
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt
        )
        return response.text
        
    except Exception as e:
        print(f"Gemini Error: {str(e)}")
        return "AI Error: Summary generate nahi ho payi."

def send_to_telegram(message):
    """Telegram par message bhejta hai"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    import requests
    requests.post(url, json=payload)

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("News fetch kar raha hu...")
    raw_news = get_news()
    
    print("Gemini se summary bana raha hu...")
    summary = summarize_with_ai(raw_news)
    
    final_message = f"📰 *Aaj Ki Taaza Khabrein*\n\n{summary}"
    
    print("Telegram par bhej raha hu...")
    send_to_telegram(final_message)
    print("Ho gaya!")
