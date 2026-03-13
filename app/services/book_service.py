import requests


OPEN_LIBRARY_SEARCH_URL = "https://openlibrary.org/search.json"
OPEN_LIBRARY_COVER_URL = "https://covers.openlibrary.org/b/id/{cover_id}-M.jpg"


def _extract_description(doc: dict) -> str:
    desc = None
    first_sentence = doc.get("first_sentence")
    if isinstance(first_sentence, list) and first_sentence:
        desc = first_sentence[0]
    elif isinstance(first_sentence, str):
        desc = first_sentence
    if not desc:
        subtitle = doc.get("subtitle")
        if isinstance(subtitle, str):
            desc = subtitle
    if not desc:
        subjects = doc.get("subject", [])
        if subjects:
            desc = "Subjects: " + ", ".join(subjects[:5])
    return desc or "No description available."


def search_books_by_topic(topic: str, limit: int = 6):
    """
    Simple Open Library search for a topic. Returns a list of dicts with:
    book_key, title, author, cover_url, description.
    """
    if not topic:
        return []

    try:
        params = {"q": topic, "limit": limit}
        resp = requests.get(OPEN_LIBRARY_SEARCH_URL, params=params, timeout=5)
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = []
        for doc in data.get("docs", [])[:limit]:
            title = doc.get("title") or "Untitled"
            author = (doc.get("author_name") or ["Unknown author"])[0]
            cover_id = doc.get("cover_i")
            cover_url = OPEN_LIBRARY_COVER_URL.format(cover_id=cover_id) if cover_id else ""
            description = _extract_description(doc)
            key = doc.get("key") or ""
            results.append({
                "book_key": key,
                "title": title,
                "author": author,
                "cover_url": cover_url,
                "description": description,
                "topic": topic,
            })
        return results
    except Exception:
        return []


def recommend_for_weak_topics(weak_topics, per_topic_limit: int = 3, overall_limit: int = 12):
    """
    Given an array of weak topic entries [{topic, ...}], fetch books per topic.
    """
    recommendations = []
    for wt in weak_topics or []:
        topic_label = wt.get("topic")
        if not topic_label:
            continue
        books = search_books_by_topic(topic_label, limit=per_topic_limit)
        for b in books:
            recommendations.append(b)
            if len(recommendations) >= overall_limit:
                return recommendations
    return recommendations

