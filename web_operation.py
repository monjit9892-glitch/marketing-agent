from dotenv import load_dotenv
import os, requests, traceback
from urllib.parse import quote_plus

load_dotenv()
API_KEY = os.getenv("BRIGHTDATA_API_KEY")


def web_search(query: str, engine: str = "google"):
    """Search the web via Bright Data (Google/Bing). Returns simplified results list."""

    engines = {
        "google": "https://www.google.com/search",
        "bing": "https://www.bing.com/search"
    }
    if engine not in engines:
        raise ValueError(f"Unknown engine: {engine}")

    payload = {
        "zone": "serp_api",
        "url": f"{engines[engine]}?q={quote_plus(query)}&brd_json=1",
        "format": "raw"
    }

    try:
        resp = requests.post(
            "https://api.brightdata.com/request",
            headers={"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"❌ Web search failed: {e}")
        traceback.print_exc()
        return []

    # Parse simplified results
    results = []
    for item in data.get("organic", []):
        results.append({
            "title": item.get("title"),
            "url": item.get("url") or item.get("link") or item.get("href"),
            "snippet": item.get("snippet"),
            "source": engine.capitalize()
        })
    print(f"✅ {len(results)} results fetched for: {query}")
    return results
