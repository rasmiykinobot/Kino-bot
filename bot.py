import os
import json
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from urllib.parse import quote
from urllib.request import urlopen
import json

# =========================
# SOZLAMALAR
# =========================

TOKEN = os.environ["TOKEN"]

OMDB_API_KEY = os.environ["OMDB_API_KEY"]

# Bu yerga o'zingizning Telegram ID'ingizni yozing
ADMIN_ID = 5559820565

# Kino ma'lumotlari shu lug'atda saqlanadi
MOVIES_FILE = "movies.json"

if os.path.exists(MOVIES_FILE):
    with open(MOVIES_FILE, "r", encoding="utf-8") as f:
        movies = json.load(f)
else:
    movies = {}

# =========================
# /start
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 Assalomu alaykum!\n\n"
        "Kino topish uchun kino nomini yoki kino kodini yuboring.\n\n"
        "Masalan:\n"
        "🎥 Avatar\n"
        "yoki\n"
        "🔢 060"
    )

# =========================
# ADMIN KINO QO'SHISH
# =========================

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Sizda kino qo'shish huquqi yo'q."
        )
        return

    if not update.message.video:
        return

    context.user_data["waiting_for_code"] = True
    context.user_data["video_file_id"] = update.message.video.file_id

    await update.message.reply_text(
        "✅ Kino qabul qilindi!\n\n"
        "🔢 Endi kino uchun kod yuboring.\n"
        "Masalan: 060"
    )

# =========================
# KOD QABUL QILISH
# =========================

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user_id = update.effective_user.id
    text = update.message.text.strip()

    # Admin kino uchun kod berayotgan bo'lsa
    if (
        user_id == ADMIN_ID
        and context.user_data.get("waiting_for_code")
    ):

        file_id = context.user_data.get("video_file_id")

        if not file_id:
            return

        movies[text] = file_id

        with open(MOVIES_FILE, "w", encoding="utf-8") as f:
            json.dump(movies, f, ensure_ascii=False, indent=2)

        context.user_data["waiting_for_code"] = False
        context.user_data["video_file_id"] = None
        await update.message.reply_text(
            f"✅ Kino muvaffaqiyatli saqlandi!\n\n"
            f"🔢 Kod: {text}\n\n"
            f"Endi foydalanuvchi {text} kodini yuborsa,\n"
            f"shu kino yuboriladi. 🎬"
        )

        return

    # =========================
    # KINO KODI ORQALI QIDIRISH
    # =========================

    if text in movies:

        await update.message.reply_video(
            video=movies[text],
            caption=f"🎬 Kino kodi: {text}"
        )

        return

    # =========================
    # OMDB ORQALI KINO QIDIRISH
    # =========================

    await update.message.reply_text(
        "🔎 Kino qidirilmoqda..."
    )

    url = (
        "https://www.omdbapi.com/"
        "?apikey=" + OMDB_API_KEY +
        "&s=" + quote(text)
    )

    try:

        with urlopen(url, timeout=10) as response:
            data = json.loads(
                response.read().decode()
            )

        if data.get("Response") == "True":

            movies_list = data.get("Search", [])[:5]

            result = "🎬 Topilgan kinolar:\n\n"

            for movie in movies_list:

                title = movie.get(
                    "Title",
                    "Noma'lum"
                )

                year = movie.get(
                    "Year",
                    "Noma'lum"
                )

                movie_type = movie.get(
                    "Type",
                    "Noma'lum"
                )

                result += (
                    f"🎥 {title}\n"
                    f"📅 Yil: {year}\n"
                    f"🎞 Turi: {movie_type}\n\n"
                )

            await update.message.reply_text(
                result
            )

        else:

            await update.message.reply_text(
                "❌ Kino topilmadi."
            )

    except Exception as error:

        print("Xatolik:", error)

        await update.message.reply_text(
            "⚠️ Kino qidirishda xatolik yuz berdi."
        )

# =========================
# ADMIN KINO O'CHIRISH
# =========================

async def delete_movie(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Siz admin emassiz."
        )
        return

    if not context.args:

        await update.message.reply_text(
            "Foydalanish:\n"
            "/delete 060"
        )

        return

    code = context.args[0]

    if code in movies:

        del movies[code]

        await update.message.reply_text(
            f"🗑 Kino o'chirildi.\n"
            f"🔢 Kod: {code}"
        )

    else:

        await update.message.reply_text(
            "❌ Bunday koddagi kino topilmadi."
        )

# =========================
# ADMIN KINOLAR RO'YXATI
# =========================

async def movie_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Siz admin emassiz."
        )
        return

    if not movies:

        await update.message.reply_text(
            "📂 Hozircha kino qo'shilmagan."
        )

        return

    text = "🎬 Saqlangan kinolar:\n\n"

    for code in movies:
        text += f"🔢 {code}\n"

    await update.message.reply_text(text)

# =========================
# BOTNI ISHGA TUSHIRISH
# =========================

def main():

    app = Application.builder().token(TOKEN).build()

    app.add_handler(
        CommandHandler("start", start)
    )

    app.add_handler(
        CommandHandler("delete", delete_movie)
    )

    app.add_handler(
        CommandHandler("list", movie_list)
    )

    app.add_handler(
        MessageHandler(
            filters.VIDEO,
            handle_video
        )
    )

    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_code
        )
    )

    print("🤖 Bot ishga tushdi...")

    app.run_polling()


if __name__ == "__main__":
    main()
