import asyncio
import yt_dlp
import datetime

# ───────────────────────────────────────────────
# AsyncVideosSearch — yt_dlp-based drop-in version
# ───────────────────────────────────────────────

def _format_duration(seconds):
    if not seconds:
        return None
    seconds = int(seconds)
    h, m, s = seconds // 3600, (seconds % 3600) // 60, seconds % 60
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def _shorten_views(views):
    if views is None:
        return {"text": "0 views", "short": "0 views"}
    if views >= 1_000_000:
        return {"text": f"{views:,} views", "short": f"{int(views/1_000_000)}M views"}
    if views >= 1_000:
        return {"text": f"{views:,} views", "short": f"{int(views/1_000)}K views"}
    return {"text": f"{views} views", "short": f"{views} views"}


def _format_published(upload_date):
    if not upload_date:
        return None
    try:
        upload_dt = datetime.datetime.strptime(upload_date, "%Y%m%d")
        delta = datetime.datetime.now(datetime.timezone.utc) - upload_dt
        if delta.days < 1:
            return "today"
        if delta.days < 30:
            return f"{delta.days} days ago"
        if delta.days < 365:
            return f"{delta.days // 30} months ago"
        return f"{delta.days // 365} years ago"
    except Exception:
        return None



async def AsyncVideosSearch(query, limit=1):
    """
    Async YouTube search using yt_dlp that mimics youtube-search-python's VideosSearch.
    Returns identical structure and value types.
    """
    try:
        def _extract():
            ydl_opts = {
                "quiet": True,
                "extract_flat": True,
                "skip_download": True,
                "default_search": "ytsearch",
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(f"ytsearch{limit}:{query}", download=False)

        loop = asyncio.get_running_loop()
        info = await loop.run_in_executor(None, _extract)
        entries = info.get("entries", [info])
        results = []

        for e in entries[:limit]:
            # Normalize thumbnail list (make sure order + key names match)
            thumbnails = []
            for thumb in e.get("thumbnails") or []:
                thumbnails.append({
                    "url": thumb.get("url"),
                    "width": thumb.get("width"),
                    "height": thumb.get("height"),
                })

            # Construct the result dictionary to match youtube-search-python format exactly
            result = {
                "type": "video",
                "id": e.get("id"),
                "title": e.get("title"),
                "publishedTime": _format_published(e.get("upload_date")),
                "duration": _format_duration(e.get("duration")),
                "viewCount": _shorten_views(e.get("view_count")),
                "thumbnails": thumbnails,
                "richThumbnail": thumbnails[-1] if thumbnails else None,
                "descriptionSnippet": [],
                "channel": {
                    "name": e.get("uploader") or e.get("channel"),
                    "id": e.get("channel_id"),
                    "thumbnails": [
                        {
                            "url": e.get("channel_url") + "/profile_photo" if e.get("channel_url") else "",
                            "width": 68,
                            "height": 68
                        }
                    ] if e.get("channel_url") else [],
                    "link": e.get("uploader_url") or e.get("channel_url"),
                },
                "accessibility": {
                    "title": e.get("title"),
                    "duration": _format_duration(e.get("duration")),
                },
                "link": f"https://www.youtube.com/watch?v={e.get('id')}" if e.get("id") else e.get("url"),
                "shelfTitle": None,
            }

            # Only add descriptionSnippet if description exists
            if e.get("description"):
                result["descriptionSnippet"] = [{"text": e.get("description")}]

            results.append(result)

        return results

    except Exception:
        return []