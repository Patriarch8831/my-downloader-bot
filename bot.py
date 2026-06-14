import os
import re
import requests
import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN", "")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! به بات دانلودر خوش اومدی!\n\n"
        "🔗 کافیه لینکت رو بفرستی:\n"
        "• 📸 اینستاگرام\n"
        "• ▶️ یوتیوب\n"
        "• 🎵 تیک‌تاک\n"
        "• 📁 لینک مستقیم\n\n"
        "⬇️ فقط لینک بفرست!"
    )

def detect_link_type(url):
    url_lower = url.lower()
    if "instagram.com" in url_lower:
        return "ytdlp"
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "ytdlp"
    elif "tiktok.com" in url_lower:
        return "ytdlp"
    elif url_lower.startswith("http"):
        return "direct"
    return "unknown"

async def download_ytdlp(url, update):
    msg = await update.message.reply_text("⏳ در حال دانلود...")
    output_path = f"/tmp/dl_{update.message.message_id}"

    ydl_opts = {
        "outtmpl": output_path + ".%(ext)s",
        "format": "best[filesize<45M]/best",
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "ویدیو")

        downloaded_file = None
        for ext in ["mp4", "mkv", "webm", "mp3", "m4a"]:
            candidate = f"{output_path}.{ext}"
            if os.path.exists(candidate):
                downloaded_file = candidate
                break

        if not downloaded_file:
            await msg.edit_text("❌ فایل پیدا نشد.")
            return

        if os.path.getsize(downloaded_file) > 50 * 1024 * 1024:
            await msg.edit_text("⚠️ فایل بیشتر از 50MB هست، تلگرام اجازه ارسال نمیده.")
            os.remove(downloaded_file)
            return

        await msg.edit_text(f"📤 در حال آپلود...")
        with open(downloaded_file, "rb") as f:
            if downloaded_file.endswith((".mp4", ".mkv", ".webm")):
                await update.message.reply_video(video=f, caption=f"✅ {title[:100]}")
            else:
                await update.message.reply_audio(audio=f, caption=f"✅ {title[:100]}")

        os.remove(downloaded_file)
        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ خطا در دانلود:\n{str(e)[:200]}")

async def download_direct(url, update):
    msg = await update.message.reply_text("⏳ در حال دانلود لینک مستقیم...")
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        response.raise_for_status()

        filename = url.split("/")[-1].split("?")[0] or "file"
        if "." not in filename:
            filename += ".bin"

        filepath = f"/tmp/{filename}"
        total = 0
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                total += len(chunk)
                if total > 50 * 1024 * 1024:
                    os.remove(filepath)
                    await msg.edit_text("⚠️ فایل بیشتر از 50MB هست.")
                    return

        await msg.edit_text("📤 در حال آپلود...")
        with open(filepath, "rb") as f:
            await update.message.reply_document(document=f, filename=filename)

        os.remove(filepath)
        await msg.delete()

    except Exception as e:
        await msg.edit_text(f"❌ خطا: {str(e)[:200]}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    urls = re.findall(r'https?://[^\s]+', text)

    if not urls:
        await update.message.reply_text("❓ لینکی پیدا نکردم!")
        return

    url = urls[0]
    link_type = detect_link_type(url)

    if link_type == "ytdlp":
        await download_ytdlp(url, update)
    elif link_type == "direct":
        await download_direct(url, update)
    else:
        await update.message.reply_text("❓ این نوع لینک رو نمیشناسم.")

if __name__ == "__main__":
    if not TOKEN:
        print("❌ BOT_TOKEN تنظیم نشده!")
        exit(1)
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ بات روشن شد!")
    app.run_polling()
