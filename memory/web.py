"""The web, for the memory: pages for a query, with their text, from Tavily."""
import json
import os
import urllib.request

TAVILY = "https://api.tavily.com/search"


def tavily(query: str, pages: int) -> list[dict]:
    """Pages for a query straight from Tavily, with their text: url, title, published, text."""
    body = json.dumps({"query": query, "max_results": max(pages, 5), "include_raw_content": True}).encode()
    request = urllib.request.Request(TAVILY, data=body, headers={
        "Content-Type": "application/json", "Authorization": f"Bearer {os.environ['TAVILY_API_KEY']}"})
    with urllib.request.urlopen(request, timeout=120) as answer:
        found = json.loads(answer.read()).get("results", [])
    return [{"url": r["url"], "title": r.get("title"), "published": r.get("published_date"),
             "text": r.get("raw_content") or r.get("content") or ""} for r in found if r.get("url")][:pages]
