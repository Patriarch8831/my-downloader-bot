import os
import re
import requests
import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ─── پیام خوش‌آمد ───────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 سلام! به بات دانلودر خوش اومدی!\n\n"
        "🔗 کافیه لینکت رو بفرستی:\n"
        "• 📸 اینستاگرام (پست، ریلز، استوری)\n"
        "• ▶️ یوتیوب (ویدیو)\n"
        "• 🎵 تیک‌تاک\n"
        "• 📁 لینک مستقیم (فایل، زیپ، ...)\n\n"
        "⬇️ فقط لینک بفرست، بقیه‌اش با منه!"
    )

# ─── تشخیص نوع لینک ─────────────────────────────────────────────
def detect_link_type(url: str) -> str:
    url = url.lower()
    if "instagram.com" in url:
        return "instagram"
    elif "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    elif "tiktok.com" in url:
        return "tiktok"
    elif url.startswith("http"):
        return "direct"
    return "unknown"

# ─── دانلود با yt-dlp (اینستاگرام، یوتیوب، تیک‌تاک) ────────────
async def download_with_ytdlp(url: str, update: Update) -> bool:
    msg = await update.message.reply_text("⏳ در حال دانلود... لطفاً صبر کن.")
    
    output_path = f"/tmp/dl_{update.message.message_id}"
    
    ydl_opts = {
        "outtmpl": output_path + ".%(ext)s",
        "format": "bestvideo[ext=mp4][filesize<45M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<45M]/best[filesize<45M]",
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get("title", "ویدیو")

        # پیدا کردن فایل دانلود شده
        downloaded_file = None
        for ext in ["mp4", "mkv", "webm", "mp3", "m4a"]:
            candidate = f"{output_path}.{ext}"
            if os.path.exists(candidate):
                downloaded_file = candidate
                break

        if not downloaded_file:
            await msg.edit_text("❌ فایل پیدا نشد.")
            return False

        file_size = os.path.getsize(downloaded_file)
        
        if file_size > 50 * 1024 * 1024:  # بیشتر از 50MB
            await msg.edit_text("⚠️ فایل بزرگتر از 50MB هست و تلگرام اجازه ارسال نمیده.\nلطفاً لینک با کیفیت پایین‌تر امتحان کن.")
            os.remove(downloaded_file)
            return False

        await msg.edit_text(f"📤 در حال آپلود: {title[:50]}...")
        
        with open(downloaded_file, "rb") as f:
            if downloaded_file.endswith((".mp4", ".mkv", ".webm")):
                await update.message.reply_video(video=f, caption=f"✅ {title[:100]}")
            else:
                await update.message.reply_audio(audio=f, caption=f"✅ {title[:100]}")

        os.remove(downloaded_file)
        await msg.delete()
        return True

    except Exception as e:
        error_msg = str(e)
        if "Private" in error_msg or "login" in error_msg.lower():
            await msg.edit_text("🔒 این محتوا خصوصی هست و قابل دانلود نیست.")
        elif "not available" in error_msg.lower():
            await msg.edit_text("❌ این محتوا در دسترس نیست یا حذف شده.")
        else:
            await msg.edit_text(f"❌ خطا در دانلود:\n{error_msg[:200]}")
        return False

# ─── دانلود لینک مستقیم ─────────────────────────────────────────
async def download_direct(url: str, update: Update) -> bool:
    msg = await update.message.reply_text("⏳ در حال دانلود لینک مستقیم...")
    
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, stream=True, timeout=30, headers=headers)
        response.raise_for_status()

        # نام فایل از URL
        filename = url.split("/")[-1].split("?")[0] or "file"
        if "." not in filename:
            content_type = response.headers.get("content-type", "")
            ext_map = {"video/mp4": ".mp4", "audio/mpeg": ".mp3", "application/zip": ".zip", "application/pdf": ".pdf"}
            filename += ext_map.get(content_type.split(";")[0], ".bin")

        filepath = f"/tmp/{filename}"
        total = 0
        with open(filepath, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
                total += len(chunk)
                if total > 50 * 1024 * 1024:
                    f.close()
                    os.remove(filepath)
                    await msg.edit_text("⚠️ فایل بزرگتر از 50MB هست. تلگرام اجازه ارسال نمیده.")
                    return False

        await msg.edit_text(f"📤 در حال آپلود: {filename}...")
        with open(filepath, "rb") as f:
            await update.message.reply_document(document=f, filename=filename, caption=f"✅ {filename}")

        os.remove(filepath)
        await msg.delete()
        return True

    except requests.exceptions.ConnectionError:
        await msg.edit_text("❌ نمیتونم به این آدرس وصل بشم.")
        return False
    except Exception as e:
        await msg.edit_text(f"❌ خطا: {str(e)[:200]}")
        return False

# ─── هندلر اصلی پیام ────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    
    # استخراج لینک از متن
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, text)
    
    if not urls:
        await update.message.reply_text("❓ لینکی پیدا نکردم!\nلطفاً یه لینک معتبر بفرست.")
        return
    
    url = urls[0]
    link_type = detect_link_type(url)
    
    if link_type in ("instagram", "youtube", "tiktok"):
        await download_with_ytdlp(url, update)
    elif link_type == "direct":
        await download_direct(url, update)
    else:
        await update.message.reply_text("❓ این نوع لینک رو نمیشناسم. لینک اینستاگرام، یوتیوب، تیک‌تاک یا لینک مستقیم بفرست.")

# ─── اجرای بات ──────────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("✅ بات روشن شد!")
    app.run_polling()
