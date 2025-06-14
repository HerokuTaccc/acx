import asyncio
from io import BytesIO
from PIL import Image
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import MessageEntityType
from datetime import datetime
from moviepy import VideoFileClip
from tempfile import NamedTemporaryFile as ntf
from AnonXMusic.core.mongo import mongodb
from AnonXMusic import app
from config import LOGGER_ID 


# --- In-memory AFK cache ---
afk_users = {}
afkdb = mongodb.afk

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
            return f"{user_first_name} is AFK (since {duration_fmt})."
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
                        {'file_id': sent.photo.file_id,     'type': 'photo'     } if sent.photo     else \
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


async def set_afk(user, reason=None, media = None):
    afk_data = {
        "user": {
            "id": user.id,
            "first_name": user.first_name,
        },
        "reason": reason,
        "since": datetime.now()
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
