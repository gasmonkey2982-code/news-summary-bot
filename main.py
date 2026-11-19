import requests
import feedparser
import os

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY')

# News Source (RSS Link)
RSS_URL = "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"

# --- FUNCTIONS ---

def get_news():
    """Multiple RSS feeds se mixed news nikalta hai"""
    rss_urls = [
        "https://indianexpress.com/section/technology/feed/",
        "https://indianexpress.com/section/sports/feed/",
        "https://indianexpress.com/section/india/feed/"
    ]
    
    all_news = []
    
    for url in rss_urls:
        feed = feedparser.parse(url)
        # Har category se top 3 articles le rahe hain (Total 9 max)
        for entry in feed.entries[:3]:
            title = entry.title
            link = entry.link
            all_news.append(f"• {title}\n  {link}")
            
    return "\n\n".join(all_news)

def summarize_with_ai(raw_news):
    """OpenRouter se free model use karke summary banata hai"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com",
    }
    
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

    data = {
        "model": "inclusionai/ling-3.2-flash:free",
        "messages": [{"role": "user", "content": prompt}]
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions", 
            json=data, 
            headers=headers,
            timeout=30
        )
        
        print(f"OpenRouter Status Code: {response.status_code}")
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            print(f"Error Response: {response.text[:300]}")
            return f"AI Error: Status {response.status_code}"
            
    except Exception as e:
        print(f"Request Failed: {str(e)}")
        return "AI Error: Connection failed"

def send_to_telegram(message):
    """Telegram par message bhejta hai"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("News fetch kar raha hu...")
    raw_news = get_news()
    
    print("AI se summary bana raha hu...")
    summary = summarize_with_ai(raw_news)
    
    final_message = f"📰 *Aaj Ki Taaza Khabrein*\n\n{summary}"
    
    print("Telegram par bhej raha hu...")
    send_to_telegram(final_message)
    print("Ho gaya!")
