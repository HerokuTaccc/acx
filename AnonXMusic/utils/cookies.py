import os
import requests
  
from http.cookiejar import MozillaCookieJar as surefir

from AnonXMusic.core.mongo import mongodb


cookie = mongodb.cookie

async def save_cookie(f):
    try:
        with open(f, "rb") as fi:
            fc = fi.read()
        await cookie.update_one(
            {"f_id": 1},
            {"$set": {"f_content": fc}},
            upsert=True
        )
    except Exception:
        pass

async def read_cookie():
    try:
        p = os.path.join(os.getcwd(), "cookies.txt")
        doc = await mongodb.cookie.find_one({"f_id": 1})
        if doc and "f_content" in doc:
            with open(p, "wb") as f:
                f.write(doc["f_content"])
            return p
        return False
    except Exception:
        return None

def loadCookie(cookiePath):
    if not os.path.exists(cookiePath):
        raise FileNotFoundError("The specified file was not found.")
    cookies = surefir(cookiePath)
    cookies.load(ignore_discard=True, ignore_expires=True)
    return cookies

def checkCookie(cookiePath):
    try: cookies = loadCookie(cookiePath)
    except Exception: return False 

    url = "https://www.youtube.com/feed/subscriptions"
    try:
        response = requests.get(url, cookies=cookies)
        if "\"logged_in\":true" in response.text.lower():
            return True
    except Exception:
        return False

    return False
