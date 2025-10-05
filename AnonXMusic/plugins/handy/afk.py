import asyncio, zoneinfo
from io import BytesIO
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import MessageEntityType
from datetime import datetime, timedelta
from moviepy import VideoFileClip
from tempfile import NamedTemporaryFile as ntf
from AnonXMusic.core.mongo import mongodb
from AnonXMusic import app
from config import LOGGER_ID 


# --- In-memory AFK cache ---
afk_users = {}
afkdb = mongodb.afk
aafkdb = mongodb.aafk
aafk_users = {}

# --- Important Vars ---
class UserLike:
    def __init__(self, id=None, first_name=None):
        self.id = id
        self.first_name = first_name
    def __getattr__(self, name):
        return self.__dict__.get(name, None)

DEFAULT_TZ = "Asia/Kolkata"
DEFAULT_MAIN_HOURS = 2
DEFAULT_NIGHT_HOURS = 1
    
# --- Helper Functions ---
def get_afk_user_duration(since):
  try:
    delta = datetime.now() - since
    seconds = int(delta.total_seconds())
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    duration = []
    if days: duration.append(f"{days}d")
    if hours: duration.append(f"{hours}h")
    if minutes: duration.append(f"{minutes}m")
    duration.append(f"{seconds}s")
    return " ".join(duration)
  except Exception:
    return None
def format_afk_message(user_first_name, reason, duration):
    duration_fmt = f"<code>{duration}</code>"
    if reason:
        if duration:
            return f"{user_first_name} is AFK: {reason} (since {duration_fmt})."
        else:
            return f"{user_first_name} is AFK: {reason}"
    else:
        if duration:
            return f"{user_first_name} is AFK since {duration_fmt}."
        return f"{user_first_name} is AFK"

async def convert_(io: BytesIO, mtype: str) -> BytesIO:
    loop = asyncio.get_running_loop()
    out = BytesIO()
    def convert_ps():
        
        io.seek(0)
        img = Image.open(io)
        if img.mode == "RGBA":
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])  # Apply alpha mask
            background.save(out, format="JPEG")
        else:
            img.convert("RGB").save(out, format="JPEG")

        out.name = "converted.jpeg"
        out.seek(0)
        return out

    def convert_as():
        io.seek(0)
        with ntf(suffix='.webm') as tmp_in, ntf(suffix='.gif') as tmp_out:
            tmp_in.write(io.read())
            tmp_in.flush()
            clip = VideoFileClip(tmp_in.name)
            clip.write_gif(filename=tmp_out.name, fps=clip.fps or 10)
            tmp_out.seek(0)
            out.write(tmp_out.read())
            out.name = 'converted.gif'
            out.seek(0)
            return out
    
    convert = convert_ps if mtype == 'photo' else convert_as

    return await loop.run_in_executor(None, convert)



async def extract_media(c:Client,m:Message):
    media = None
    r = m.reply_to_message
    if not r:
        return media
    s = r.sticker
    p = r.photo
    v = r.video
    a = r.animation
    if p:
        f_id = p.file_id
        media = {'file_id': f_id, 'type': 'photo'}
    elif v:
        f_id = v.file_id
        media = {'file_id': f_id, 'type': 'video'}
    elif a:
        f_id = a.file_id
        media = {'file_id': f_id, 'type': 'animation'}
    elif s:
        f_id = s.file_id
        if s.is_video:
            media = {'file_id': f_id, 'type': 'animation'}
        elif not s.is_animated:
            media = {'file_id': f_id, 'type': 'photo'}
        if media:
            mtype = media['type']
            try: med = await c.download_media(f_id,in_memory=True);med = await convert_(med,mtype)
            except Exception as e: med = None; print(e)
            try:
                sent:Message = (await (getattr(c,f"send_{mtype}",None))(LOGGER_ID,med))
                media = {'file_id': sent.photo.file_id,     'type': 'photo'     } if sent.photo     else \
                        {'file_id': sent.video.file_id,     'type': 'video'     } if sent.video     else \
                        {'file_id': sent.animation.file_id, 'type': 'animation' } if sent.animation else \
                        {'file_id': sent.document.file_id,  'type': 'document'  } if sent.document  else \
                        None
            except Exception:
                media = None
            try:await sent.delete()
            except Exception: pass
    return media

async def notify(c: Client, m: Message, media, caption):
    try:
        reply_func = getattr(m, f"reply_{media['type']}", None)
        await reply_func(media['file_id'], caption=caption)
    except Exception as e:
        try:
            await m.reply(caption)
        except Exception:
            pass


async def set_afk(user, reason=None, media = None, last_seen=None):
    if not last_seen:
        last_seen = datetime.now()
    afk_data = {
        "user": {
            "id": user.id,
            "first_name": user.first_name,
        },
        "reason": reason,
        "since": last_seen
    }
    # In-memory
    afk_data['media'] = media
    afk_users[user.id] = afk_data
    # Persistent (upsert)
    try:
        await afkdb.update_one(
        {"user.id": user.id},
        {"$set": afk_data},
        upsert=True
        )
    except Exception:
        pass

async def get_afk(user_id):
    # In-memory check first
    data = afk_users.get(user_id)
    if data:
        return data

    # Check MongoDB if not in-memory
    data = await afkdb.find_one({"user.id": user_id})
    if data:
        # MongoDB stores "since" as a datetime object — ensure correct type
        if isinstance(data["since"], str):
            data["since"] = datetime.fromisoformat(data["since"])
        afk_users[user_id] = data
    return data


async def remove_afk(user_id):
    # Remove from both
    afk_users.pop(user_id, None)
    await afkdb.delete_one({"user.id": user_id})

# --- AFK Command Handler ---
@app.on_message(filters.command("afk") & filters.group,2)
async def afk_command(_, message: Message):
    user = message.from_user
    reason = " ".join(message.command[1:]).strip()[:200] or None
    await set_afk(user, reason)
    response = f"{user.mention} is now AFK."
    if reason:
        response += f"\nReason: {reason}"
    await message.reply(response)
    media = await extract_media(_,message)
    if media:
        await set_afk(user, reason, media) if await get_afk(user.id) else None

# --- Main AFK Checker ---
@app.on_message(filters.all & ~filters.service & filters.group,2)
async def afk_user_handler(_, message: Message):
    if message.from_user and message.from_user.id == _.me.id:
        return
    
    user = getattr(message, "from_user", None)
    afk_check_done_users = []
    # Check if sender was AFK
    if user:
        afk_data = await get_afk(user.id)
        afk_check_done_users.append(user.id)
        if afk_data:
            await remove_afk(user.id)
            duration = get_afk_user_duration(afk_data["since"])
            duration_fmt = f"<code>{duration}</code>"
            text = f"Welcome back, {user.mention}!"
            if duration:
                text += f" You were AFK for {duration_fmt}."
            await message.reply(
                text
            )
    
            # return

    # Check if replied user is AFK
    if message.reply_to_message:
        replied_user = message.reply_to_message.from_user
        if replied_user and replied_user.id in afk_check_done_users:
            replied_user = None
        if replied_user:
            afk_data = await get_afk(replied_user.id)
            afk_check_done_users.append(replied_user.id)
            if afk_data:
                duration = get_afk_user_duration(afk_data["since"])
                text = format_afk_message(
                    replied_user.mention, afk_data["reason"], duration
                )
                await notify(_,message,afk_data['media'],text)
                #await message.reply(text)
                # return

    # Check mentioned users
    mentioned_users = []
    if message.entities:
        for entity in message.entities:
            if entity.type == MessageEntityType.TEXT_MENTION:
                mentioned_users.append(entity.user)
            elif entity.type == MessageEntityType.MENTION:
                username = message.text[entity.offset : entity.offset + entity.length]
                try:
                    mentioned_user = await app.get_users(username)
                    if mentioned_user:
                        mentioned_users.append(mentioned_user)
                except Exception:
                    pass

    for u in mentioned_users:
        if u.id in afk_check_done_users:
            continue 
        afk_data = await get_afk(u.id)
        afk_check_done_users.append(u.id)
        if afk_data:
            duration = get_afk_user_duration(afk_data["since"])
            text = format_afk_message(
                u.mention, afk_data["reason"], duration
            )
            await notify(_,message,afk_data['media'],text)
            #await message.reply(text)
            # break  # stop after first AFK mention


 



# --- Helper: Get user aAFK data (sync) --- #
def get_aafk(user_id) -> dict:
    """Return aAFK data from in-memory cache only."""
    return aafk_users.get(user_id, {})


# --- Helper: Update last_seen (sync memory + async DB write) --- #
async def update_last_seen(user_id):
    data = aafk_users.get(user_id)
    if not data or not data.get("enabled"):
        return

    now = datetime.now()
    data["last_seen"] = now
    aafk_users[user_id] = data

    try:
        await aafkdb.update_one(
            {"_id": user_id},
            {"$set": {"last_seen": now}}
        )
    except Exception:
        pass


# --- Message listener: track user activity --- #
@app.on_message(filters.all & ~filters.service & filters.group, 3)
async def aafk_checker(client: Client, message: Message):
    user = message.from_user
    if not user or user.is_bot or user.id == client.me.id:
        return
    await update_last_seen(user.id)


# --- Background loop: Auto AFK --- #
async def auto_afk_loop():
    while True:
        try:
            for user_id, data in list(aafk_users.items()):
                if not data.get("enabled"):
                    continue

                # Skip if already AFK
                if await get_afk(user_id):
                    continue

                last_seen = data.get("last_seen")
                if not last_seen:
                    continue

                # Determine user timezone
                tz_name = data.get("timezone", DEFAULT_TZ)
                tz = zoneinfo.ZoneInfo(tz_name)
                tz_now = datetime.now(tz)
                now = datetime.now()
                # Night mode: 0AM–6:59AM
                is_night = 0 <= tz_now.hour <= 6

                # Choose threshold
                hours_limit = data.get("night_pref") if is_night else data.get("main_pref")
                hours_limit = hours_limit or DEFAULT_MAIN_HOURS

                total_inactivity = (now - last_seen).total_seconds() / 3600  # hours
                if total_inactivity > hours_limit:
                    if await get_afk(user_id):
                        continue

                    fake_user = UserLike(user_id, data.get("first_name", "User"))

                    # Pass original last_seen to set_afk
                    await set_afk(fake_user, reason="Auto AFK (inactive)", last_seen=last_seen)

        except Exception as e:
            print(f"[AutoAFK Loop Error]: {e}")

        await asyncio.sleep(300)  # Run every 5 minutes


async def start_aafk_loop():
    try:
        cursor = aafkdb.find({})
        users = await cursor.to_list(length=None)
        for user in users:
            try:
                uid = user.pop("_id")
                last_seen = user.pop("last_seen", None)
                if isinstance(last_seen, str):
                    last_seen = datetime.fromisoformat(last_seen)
                user["last_seen"] = last_seen
                aafk_users[uid] = user
            except Exception:
                continue
    except Exception as e:
        print(f"[Startup Load Error]: {e}")

    asyncio.create_task(auto_afk_loop())

asyncio.create_task(start_aafk_loop())

# --- /aafk Command: Show toggle buttons ---
@app.on_message(filters.command("aafk") & filters.group)
async def aafk(client: Client, message: Message):
    user = message.from_user
    if not user or user.is_bot:
        return

    # Get user data from memory
    user_data = get_aafk(user.id)
    enabled = user_data.get("enabled", False)

    # Buttons
    buttons = [
        [
            InlineKeyboardButton("Enable ✅", callback_data=f"aafk_toggle:{user.id}:enable"),
            InlineKeyboardButton("Disable ❌", callback_data=f"aafk_toggle:{user.id}:disable")
        ]
    ]
    markup = InlineKeyboardMarkup(buttons)

    status_text = "enabled ✅" if enabled else "disabled ❌"
    await message.reply_text(
        f"Your Auto-AFK is currently {status_text}. Use the buttons below to toggle.",
        reply_markup=markup
    )


# --- Single callback handler for enable/disable ---
@app.on_callback_query(filters.regex(r"^aafk_toggle:(\d+):(enable|disable)"))
async def aafk_toggle_handler(client: Client, callback: CallbackQuery):
    user_id, action = callback.data.split(":")[1:]
    user_id = int(user_id)
    enable = action == "enable"
    user = callback.from_user

    # Get or create user profile
    user_data = aafk_users.get(user_id, {})
    if not user_data:
        user_data = {
            "enabled": enable,
            "main_pref": DEFAULT_MAIN_HOURS,
            "night_pref": DEFAULT_NIGHT_HOURS,
            "timezone": DEFAULT_TZ,
            "first_name": user.first_name,
            "last_seen": datetime.now()
        }
    else:
        user_data["enabled"] = enable
        # Ensure defaults exist
        user_data.setdefault("main_pref", 2)
        user_data.setdefault("night_pref", 1)
        user_data.setdefault("timezone", "Asia/Kolkata")
        user_data.setdefault("first_name", user.first_name)
        user_data.setdefault("last_seen", datetime.now())

    # Update in-memory and DB
    aafk_users[user_id] = user_data
    try:
        await aafkdb.update_one(
            {"_id": user_id},
            {"$set": user_data},
            upsert=True
        )
    except Exception:
        pass

    status_text = "enabled ✅" if enable else "disabled ❌"
    await callback.answer(f"Auto-AFK {status_text}", show_alert=True)
    try:
        await asyncio.sleep(5)
        await callback.message.delete()
    except Exception:pass