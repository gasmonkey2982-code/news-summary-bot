import html
import os
import re
import time
import feedparser
import requests
from google import genai
from google.genai import types

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

RSS_URLS = [
    ("National", "https://www.thehindu.com/news/national/feeder/default.rss"),
    ("National", "https://indianexpress.com/section/india/feed/"),
    ("International", "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ("Tech", "https://inc42.com/feed/"),
    ("Business", "https://www.livemint.com/rss/news"),
    ("Sports", "https://www.espncricinfo.com/rss/content/story/feeds/0.xml"),
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; NewsSummaryBot/1.0)"
}


def validate_config():
    """Verify karta hai ki zaroori environment variables set hain ya nahi."""
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


def clean_html(raw_html: str) -> str:
    """HTML tags aur entities (&amp;, &#39;, etc.) saaf karta hai."""
    text = re.sub(r"<.*?>", " ", raw_html or "")
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_article_context(url: str, fallback_summary: str) -> str:
    """Fast context extraction (max 120 chars) taaki request light rahe."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=4)
        resp.raise_for_status()
        paragraphs = re.findall(
            r"<p[^>]*>(.*?)</p>",
            resp.text,
            flags=re.DOTALL | re.IGNORECASE,
        )
        clean_paras = []
        for p in paragraphs:
            txt = clean_html(p)
            if (
                len(txt) > 50
                and "cookie" not in txt.lower()
                and "subscribe" not in txt.lower()
            ):
                clean_paras.append(txt)
            if len(" ".join(clean_paras)) > 120:
                break

        if clean_paras:
            return " ".join(clean_paras)[:120]
    except Exception:
        pass

    return (fallback_summary or "")[:120]

def _generate_part(client, news_slice: str, section_template: str, count: int) -> str:
    """503/504 demand spikes handle karne ke liye 3 attempts aur backoff ke saath chalata hai."""
    prompt = f"""
Khabrein:
{news_slice}

Rules:
1. Sirf Roman script (English letters) mein Hinglish likho. Hindi script nahi.
2. Exact {count} short points niche diye format mein banao (har section ke neeche 2 bullets):

{section_template}

3. Har point 1-2 line ka ho aur andar ki main baat bataye. Category dubara mat likho. No extra text.
"""
    wait_times = [3, 7]
    last_error = ""

    for attempt in range(len(wait_times) + 1):
        try:
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=550,
                    temperature=0.3,
                ),
            )
            text = (response.text or "").strip()
            if text:
                return text
            last_error = "Empty response"
        except Exception as e:
            err_str = str(e)
            last_error = err_str[:150]
            print(f"Attempt {attempt + 1} error: {last_error}")
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                break
            if attempt < len(wait_times):
                sleep_sec = wait_times[attempt]
                print(f"{sleep_sec}s baad retry...")
                time.sleep(sleep_sec)

    raise RuntimeError(last_error)
    
def get_news():
    """RSS feeds aur article context se crisp news pool banata hai."""
    items = []
    seen_titles = set()
    success_count = 0

    for category, url in RSS_URLS:
        try:
            resp = requests.get(url, headers=HEADERS, timeout=10)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)

            if feed.entries:
                for entry in feed.entries[:2]:
                    title = clean_html(entry.get("title", ""))
                    if not title or title.lower() in seen_titles:
                        continue
                    seen_titles.add(title.lower())

                    rss_content = ""
                    if entry.get("content"):
                        rss_content = clean_html(entry.content[0].get("value", ""))
                    if not rss_content:
                        rss_content = clean_html(entry.get("summary", ""))

                    link = entry.get("link", "")
                    details = (
                        fetch_article_context(link, rss_content)
                        if link
                        else rss_content[:300]
                    )

                    if details:
                        items.append(
                            f"[{category}] HEADLINE: {title}\nDETAILS: {details}"
                        )
                    else:
                        items.append(f"[{category}] HEADLINE: {title}")

                success_count += 1
                print(f"Success ({category}): {url}")
            else:
                print(f"Empty feed ({category}): {url}")
        except Exception as e:
            print(f"Failed ({category}) {url}: {str(e)}")

    print(f"Total feeds successful: {success_count}")
    return "\n\n".join(items) if items else None


def summarize_with_ai(raw_news: str) -> str:
    """10 points ko 2 fast batches mein banata hai taaki 504 deadline exceed na ho."""
    client = genai.Client(
        api_key=GOOGLE_API_KEY,
        http_options=types.HttpOptions(timeout=25000),
    )

    blocks = raw_news.split("\n\n")
    part1_news = "\n\n".join(
        b for b in blocks if b.startswith(("[National]", "[International]", "[Tech]"))
    )
    part2_news = "\n\n".join(
        b for b in blocks if b.startswith(("[Business]", "[Sports]"))
    )

    part1_template = """🇮🇳 National
• ...
• ...

🌍 International
• ...
• ...

💻 Tech
• ...
• ..."""

    part2_template = """📈 Business
• ...
• ...

🏏 Sports
• ...
• ..."""

    try:
        res1 = _generate_part(client, part1_news, part1_template, 6)
        res2 = _generate_part(client, part2_news, part2_template, 4)
        return f"{res1}\n\n{res2}"
    except Exception as e:
        return f"AI Error: {str(e)}"


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

    final_message = f"📰 Aaj Ki 10 Taaza Khabrein\n\n{summary}"

    print("Telegram par bhej raha hu...")
    send_to_telegram(final_message)
    print("Ho gaya!")
