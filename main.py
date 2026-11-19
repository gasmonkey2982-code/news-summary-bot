import os
import feedparser
import requests
from google import genai

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

RSS_URLS = [
    ("Tech", "https://indianexpress.com/section/technology/feed/"),
    ("Sports", "https://indianexpress.com/section/sports/feed/"),
    ("India", "https://indianexpress.com/section/india/feed/"),
    ("National", "https://www.thehindu.com/news/national/feeder/default.rss"),
    ("Top", "https://feeds.feedburner.com/ndtvnews-top-stories"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NewsSummaryBot/1.0)"
}


def validate_config():
    missing = [
        name for name, val in [
            ("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN),
            ("TELEGRAM_CHAT_ID", TELEGRAM_CHAT_ID),
            ("GOOGLE_API_KEY", GOOGLE_API_KEY),
        ]
        if not val
    ]
    if missing:
        raise ValueError(f"Missing environment variables: {', '.join(missing)}")


def get_news():
    """Multiple RSS feeds se mixed headlines nikalta hai."""
    headlines = []
    success_count = 0

    for category, url in RSS_URLS:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)

            if feed.entries:
                for entry in feed.entries[:3]:
                    title = (entry.get("title") or "").strip()
                    if title:
                        headlines.append(f"[{category}] {title}")
                success_count += 1
                print(f"Success ({category}): {url}")
            else:
                print(f"Empty feed ({category}): {url}")
        except Exception as e:
            print(f"Failed to parse {url}: {str(e)}")

    print(f"Total feeds successful: {success_count}")
    return "\n".join(headlines) if headlines else None


def summarize_with_ai(raw_news: str) -> str:
    """Gemini se Hinglish summary banata hai."""
    prompt = f"""
Yeh aaj ki taaza headlines hain:
{raw_news}

INSTRUCTIONS:
1. Summary SIRF Roman script (English letters) mein likho. Devanagari/Hindi script bilkul use mat karo.
2. Language HINGLISH honi chahiye (Hindi words English letters mein, natural aur casual tone).
   Example: "PUC certificate check kar lo" ✅ | "Check your PUC certificate" ❌
3. Exact 5 short bullet points mein summary do (har bullet ke aage "• " lagao).
4. Extra intro ya outro text mat likho.

Summary:
"""
    try:
        client = genai.Client(api_key=GOOGLE_API_KEY)
        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=prompt,
        )
        text = (response.text or "").strip()
        if not text:
            return "AI Error: Empty response from Gemini"
        return text
    except Exception as e:
        error_msg = str(e)[:200]
        print(f"Gemini Error: {error_msg}")
        return f"AI Error: {error_msg}"


def send_to_telegram(message: str):
    """Telegram par safely message bhejta hai (4096 char limit handle karte hue)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = [message[i:i + 4000] for i in range(0, len(message), 4000)]

    for chunk in chunks:
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
        }
        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code != 200:
                print(f"Telegram Error: {resp.text}")
        except Exception as e:
            print(f"Telegram Request Failed: {str(e)}")


if __name__ == "__main__":
    validate_config()

    print("News fetch kar raha hu...")
    raw_news = get_news()
    if not raw_news:
        print("Koi news nahi mili!")
        exit(1)

    print("Gemini se summary bana raha hu...")
    summary = summarize_with_ai(raw_news)

    final_message = f"📰 Aaj Ki Taaza Khabrein\n\n{summary}"

    print("Telegram par bhej raha hu...")
    send_to_telegram(final_message)
    print("Ho gaya!")
