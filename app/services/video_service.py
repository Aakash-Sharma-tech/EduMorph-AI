import os
import requests


YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def search_videos_by_topic(topic: str, limit: int = 3):
    """
    Search YouTube for educational videos on a topic.
    Returns a list of dicts with: video_id, title, channel, thumbnail_url, description, topic.
    """
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key or not topic:
        # Fallback: no API key or empty topic -> no results.
        return []

    try:
        params = {
            "part": "snippet",
            "q": topic,
            "type": "video",
            "maxResults": limit,
            "key": api_key,
            "safeSearch": "strict",
            "relevanceLanguage": "en",
        }
        resp = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=5)
        if resp.status_code != 200:
            return []
        data = resp.json()
        results = []
        for item in data.get("items", [])[:limit]:
            snippet = item.get("snippet", {}) or {}
            video_id = (item.get("id") or {}).get("videoId", "")
            if not video_id:
                continue
            title = snippet.get("title") or "Untitled video"
            channel = snippet.get("channelTitle") or "Unknown channel"
            thumbs = snippet.get("thumbnails") or {}
            thumb = thumbs.get("medium") or thumbs.get("default") or {}
            thumb_url = thumb.get("url", "")
            description = snippet.get("description") or ""
            results.append({
                "video_id": video_id,
                "title": title,
                "channel": channel,
                "thumbnail_url": thumb_url,
                "description": description,
                "topic": topic,
                "url": f"https://www.youtube.com/watch?v={video_id}",
            })
        return results
    except Exception:
        return []


def recommend_videos_for_weak_topics(weak_topics, per_topic_limit: int = 3, overall_limit: int = 20):
    """
    Given weak topics, fetch YouTube videos per topic.
    Returns a dict: {topic: [video, ...], ...}
    """
    by_topic = {}
    total_count = 0
    for wt in weak_topics or []:
        topic_label = wt.get("topic")
        if not topic_label:
            continue
        videos = search_videos_by_topic(topic_label, limit=per_topic_limit)
        if videos:
            by_topic[topic_label] = videos
            total_count += len(videos)
            if total_count >= overall_limit:
                break
    return by_topic

