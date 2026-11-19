import feedparser
import os
import requests
import google.generativeai as genai

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHAT_ID = os.environ.get('TELEGRAM_CHAT_ID')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')

# Initialize Gemini
genai.configure(api_key=GOOGLE_API_KEY)

# News Sources
RSS_URLS = [
    "https://indianexpress.com/section/technology/feed/",
    "https://indianexpress.com/section/sports/feed/",
    "https://indianexpress.com/section/india/feed/",
    # Fallback feeds agar IE fail ho jaye
    "https://www.thehindu.com/news/national/feeder/default.rss",
    "https://feeds.feedburner.com/ndtvnews-top-stories"
]

def get_news():
    """Multiple RSS feeds se mixed news nikalta hai"""
    all_news = []
    success_count = 0
    
    for url in RSS_URLS:
        try:
            feed = feedparser.parse(url)
            if feed.entries:
                for entry in feed.entries[:3]:
                    title = entry.title
                    link = entry.link
                    all_news.append(f"• {title}\n  {link}")
                success_count += 1
                print(f"Success: {url}")
            else:
                print(f"Empty feed: {url}")
        except Exception as e:
            print(f"Failed to parse {url}: {str(e)}")
            
    print(f"Total feeds successful: {success_count}")
    
    if not all_news:
        return None  # None return karo taaki main function handle kar sake
            
    return "\n\n".join(all_news)
def summarize_with_ai(raw_news):
    """Gemini se Hinglish summary banata hai"""
    
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
        model = genai.GenerativeModel('gemini-2.0-flash')
        response = model.generate_content(prompt)
        
        if not response.text:
            return "AI Error: Empty response from Gemini"
            
        return response.text
        
    except Exception as e:
        error_msg = str(e)[:150]  # First 150 chars of error
        print(f"Gemini Error: {error_msg}")
        return f"AI Error: {error_msg}"

def send_to_telegram(message):
    """Telegram par message bhejta hai"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code != 200:
            print(f"Telegram Error: {resp.text}")
    except Exception as e:
        print(f"Telegram Request Failed: {str(e)}")

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("News fetch kar raha hu...")
    raw_news = get_news()
    
    if not raw_news:
        print("Koi news nahi mili!")
        exit(1)
    
    print("Gemini se summary bana raha hu...")
    summary = summarize_with_ai(raw_news)
    
    final_message = f"📰 *Aaj Ki Taaza Khabrein*\n\n{summary}"
    
    print("Telegram par bhej raha hu...")
    send_to_telegram(final_message)
    print("Ho gaya!")
