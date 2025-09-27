import asyncio, os

from pyrogram import filters
from pyrogram.types import Message


from AnonXMusic import app, cookiePath
from AnonXMusic.utils.cookies import checkCookie, save_cookie

from config import LOGGER_ID

setc_task = None


@app.on_message(filters.chat(LOGGER_ID) & filters.command(["set_cookie", "setc"]))
async def setc(c, m: Message):
    """Handles cookie setup. Cancels previous instances before starting a new one."""
    
    
    if checkCookie(cookiePath):
        await m.reply("✅ Cookies are already valid!")
        return

    # Cancel previous task if running
    if setc_task and not setc_task.done():
        setc_task.cancel()
        try:
            await setc_task
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(0.5)

    async def cookie_setup():
        isDoc = False
        
        try:
            if m.reply_to_message and m.reply_to_message.document:
                isDoc = True
                msg = m.reply_to_message
                doc = msg.document
            else:
                await m.reply("📂 Waiting for cookies... Send a `.txt` file (Max: 5MB).\n\nTo skip, send `/ignorec`.")

            for i in [1]:
                try:
                    if not isDoc:
                        msg = await app.listen(filters.chat(LOGGER_ID) & filters.document, timeout=300)  # 5 minute timeout
                        doc = msg.document
                    
                    if not doc.file_name.endswith(".txt") or doc.mime_type != "text/plain":
                        await msg.reply("❌ Invalid file format! Send a valid `.txt` file.")
                        isDoc = False
                        return

                    # Validate file size
                    if doc.file_size == 0 or doc.file_size > 5 * 1024 * 1024:
                        await msg.reply("❌ Invalid file size! Ensure the file is between 1 byte and 5MB.")
                        isDoc = False
                        return 

                    newCookiePath = await msg.download('cookies.txt')
                    await msg.reply("🔍 Checking cookies...")

                    if checkCookie(newCookiePath):
                        with open(cookiePath, 'wb') as w, open(newCookiePath, 'rb') as  r:
                            w.write(r.read())

                        await save_cookie(newCookiePath)
                        await app.send_message(LOGGER_ID, "✅ Cookies are valid and set successfully! Exiting Cookie Setup Mode.")
                        return
                    else:
                        await msg.reply("❌ Invalid cookies! Exited...")
                        
                        try:
                            os.remove(newCookiePath)
                        except Exception as e:
                            pass
                        isDoc = False
                        return

                except asyncio.TimeoutError:
                    await m.reply("⏰ Cookie setup timed out after 5 minutes. Use `/setc` again to restart.")
                    return
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    await msg.reply(f"⚠️ Error processing file: {e}. Please try again.")
                    isDoc = False
                    return

        except asyncio.CancelledError:
            pass
        except Exception as e:
            await app.send_message(LOGGER_ID, f"❌ Cookie setup failed: {e}. Send `/setc` to restart.")

    # Start the cookie setup task
    setc_task = asyncio.create_task(cookie_setup())
