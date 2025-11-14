import os
import asyncio 
from pathlib import Path

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from pyrogram.enums import ChatAction, ChatType

import yt_dlp
from AnonXMusic import app
from AnonXMusic.utils import AsyncVideosSearch

# Command: /download <song name>
@app.on_message(filters.command(["download"]))
async def search_song(client: Client, message: Message):
    if len(message.command) < 2:
        return await message.reply_text("❌ Please provide a song name to search.")

    query = message.text.partition(' ')[2] if message.text else ''
    results = await AsyncVideosSearch(query, limit=5)

    if not results:
        return await message.reply_text("❌ No results found.")

    if message.chat.type != ChatType.PRIVATE:
       try:
           await client.send_chat_action(message.from_user.id, ChatAction.TYPING)
       except Exception:
            bot_username = client.me.username
            keyboard = InlineKeyboardMarkup(
                [
                    [InlineKeyboardButton("🚀 Start Bot in DM", url=f"https://t.me/{bot_username}?start=download")]
                ]
                )
            await message.reply_text(
                f"⚠️ To use the **/download** command, please start me in **DM** first.",
                reply_markup=keyboard
                )
            return 


    keyboard = []
    for idx, result in enumerate(results, start=1):
        title = result["title"]
        video_id = result["id"]
        keyboard.append([
            InlineKeyboardButton(
                f"{idx}. {title[:40]}",
                callback_data=f"download:{message.from_user.id}:{video_id}"
            )
        ])

    await message.reply_text(
        f"🔎 Results for **{query}**:",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def run_yt_dlp(url: str):
    loop = asyncio.get_event_loop()
    
    
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": "%(title)s",
        "noplaylist": True,
        "quite": True,
        "cookiefile": "cookies.txt",
        # Postprocessors
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
            },
            {
                "key": "FFmpegMetadata", 
            },
        ],
    }


    def _download():
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_name = ydl.prepare_filename(info)
            return info, f"{file_name}.mp3"

    return await loop.run_in_executor(None, _download)


@app.on_callback_query(filters.regex(r"^download:"))
async def callback_download(client, callback_query: CallbackQuery):
    data = callback_query.data.split(":")
    user_id, video_id = int(data[1]), data[2]

    if callback_query.from_user.id != user_id:
        return await callback_query.answer("❌ This button isn’t for you!", show_alert=True)

    url = f"https://www.youtube.com/watch?v={video_id}"
    m = await callback_query.message.reply_text("⬇️ Downloading... please wait.")

    try:
        info, file_name = await run_yt_dlp(url)

        file_path = Path(file_name).resolve()

        # Check filesize (20 MB max)
        if file_path.stat().st_size > 20 * 1024 * 1024:
            await m.edit_text("❌ File too large! Max 20 MB allowed.")
            if file_path.exists():
                os.remove(file_path)
            return

        await m.edit_text("✅ Uploading song ...")
        await client.send_audio(
            chat_id=callback_query.message.chat.id,
            audio=str(file_path),
            title=info.get("title"),
            performer=info.get("uploader"),
            duration=int(info.get("duration") or 0),
        )

        file_path.unlink(missing_ok=True)
        await m.delete()
    except Exception as e:
        await m.edit_text(f"❌ Error: {str(e)}")

