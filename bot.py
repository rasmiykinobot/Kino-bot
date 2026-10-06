import os
import json
import urllib.parse
import urllib.request

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from telegram.error import TelegramError


# =========================
# SOZLAMALAR
# =========================

TOKEN = os.environ["TOKEN"]
OMDB_API_KEY = os.environ["OMDB_API_KEY"]

ADMIN_ID = 555938273

# Majburiy obuna kanali
FORCE_CHANNEL = "@rasmiykinouz"
FORCE_CHANNEL_URL = "https://t.me/rasmiykinouz"

MOVIES_FILE = "movies.json"


# =========================
# KINOLAR BAZASI
# =========================

if os.path.exists(MOVIES_FILE):
    try:
        with open(MOVIES_FILE, "r", encoding="utf-8") as f:
            movies = json.load(f)
    except Exception:
        movies = {}
else:
    movies = {}


# Admin kino yuklagandan keyin kod kutish
waiting_for_code = False
pending_movie = None


# =========================
# MAJBURIY OBUNA
# =========================

async def is_subscribed(bot, user_id):
    """
    Foydalanuvchi kanalga obuna bo'lganligini tekshiradi.
    """

    try:
        member = await bot.get_chat_member(
            chat_id=FORCE_CHANNEL,
            user_id=user_id
        )

        if member.status in ("member", "administrator", "creator"):
            return True

        # Ba'zi holatlarda restricted bo'lishi mumkin
        if member.status == "restricted":
            return getattr(member, "is_member", False)

        return False

    except TelegramError:
        return False


def subscription_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "📢 Kanalga obuna bo‘lish",
                url=FORCE_CHANNEL_URL
            )
        ],
        [
            InlineKeyboardButton(
                "✅ Obunani tekshirish",
                callback_data="check_subscription"
            )
        ]
    ])


async def require_subscription(update, context):
    """
    Obuna bo'lmagan foydalanuvchini to'xtatadi.
    Admin uchun obuna tekshirilmaydi.
    """

    user = update.effective_user

    # Admin uchun majburiy obuna yo'q
    if user and user.id == ADMIN_ID:
        return True

    if user and await is_subscribed(context.bot, user.id):
        return True

    message = update.effective_message

    if message:
        await message.reply_text(
            "🔒 Botdan foydalanish uchun avval kanalimizga obuna bo‘ling!\n\n"
            "1️⃣ Kanalga obuna bo‘ling\n"
            "2️⃣ «✅ Obunani tekshirish» tugmasini bosing",
            reply_markup=subscription_keyboard()
        )

    return False


# =========================
# /START
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_subscription(update, context):
        return

    await update.message.reply_text(
        "🎬 Kino botga xush kelibsiz!\n\n"
        "Kino kodini yuboring.\n"
        "Masalan: 060\n\n"
        "Yoki kino nomini yozing."
    )


# =========================
# OBUNANI TEKSHIRISH TUGMASI
# =========================

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query

    await query.answer()

    user_id = query.from_user.id

    if await is_subscribed(context.bot, user_id):

        await query.message.edit_text(
            "✅ Obuna tasdiqlandi!\n\n"
            "🎬 Endi kino kodini yoki kino nomini yuboring."
        )

    else:

        await query.answer(
            "❌ Siz hali kanalga obuna bo‘lmagansiz!",
            show_alert=True
        )


# =========================
# ADMIN KINO YUKLASH
# =========================

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global waiting_for_code
    global pending_movie

    # Faqat admin kino yuklay oladi
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Bu funksiya faqat admin uchun."
        )
        return

    file_id = None
    file_type = None

    # Video
    if update.message.video:

        file_id = update.message.video.file_id
        file_type = "video"

    # Document orqali video
    elif update.message.document:

        file_id = update.message.document.file_id
        file_type = "document"

    if not file_id:
        return

    pending_movie = {
        "file_id": file_id,
        "type": file_type
    }

    waiting_for_code = True

    await update.message.reply_text(
        "🎬 Kino qabul qilindi!\n\n"
        "🔢 Endi kino uchun kod yuboring.\n"
        "Masalan: 060"
    )


# =========================
# KOD / KINO NOMI
# =========================

async def handle_code(update: Update, context: ContextTypes.DEFAULT_TYPE):

    global waiting_for_code
    global pending_movie

    text = update.message.text.strip()

    # =====================
    # ADMIN KOD BERAYOTGAN BO'LSA
    # =====================

    if update.effective_user.id == ADMIN_ID and waiting_for_code:

        code = text

        if not code:
            return

        movies[code] = pending_movie

        with open(MOVIES_FILE, "w", encoding="utf-8") as f:
            json.dump(
                movies,
                f,
                ensure_ascii=False,
                indent=2
            )

        waiting_for_code = False
        pending_movie = None

        await update.message.reply_text(
            f"✅ Kino saqlandi!\n\n"
            f"🔢 Kodi: `{code}`",
            parse_mode="Markdown"
        )

        return

    # =====================
    # MAJBURIY OBUNA
    # =====================

    if not await require_subscription(update, context):
        return

    # =====================
    # KOD ORQALI KINO
    # =====================

    if text in movies:

        movie = movies[text]

        # Eski formatdagi movies.json bilan moslik
        if isinstance(movie, str):

            await update.message.reply_video(
                video=movie,
                caption=f"🎬 Kino kodi: {text}"
            )

            return

        file_id = movie.get("file_id")
        file_type = movie.get("type", "video")

        if file_type == "document":

            await update.message.reply_document(
                document=file_id,
                caption=f"🎬 Kino kodi: {text}"
            )

        else:

            await update.message.reply_video(
                video=file_id,
                caption=f"🎬 Kino kodi: {text}"
            )

        return

    # =====================
    # OMDBDAN QIDIRISH
    # =====================

    try:

        params = urllib.parse.urlencode({
            "apikey": OMDB_API_KEY,
            "s": text,
            "type": "movie"
        })

        url = f"https://www.omdbapi.com/?{params}"

        with urllib.request.urlopen(url, timeout=10) as response:
            data = json.loads(response.read().decode("utf-8"))

        if data.get("Response") != "True":

            await update.message.reply_text(
                "❌ Kino topilmadi."
            )
            return

        results = data.get("Search", [])

        if not results:

            await update.message.reply_text(
                "❌ Kino topilmadi."
            )
            return

        message = "🔎 Topilgan kinolar:\n\n"

        for movie in results[:10]:

            title = movie.get("Title", "Noma'lum")
            year = movie.get("Year", "Noma'lum")
            imdb_id = movie.get("imdbID", "")

            message += (
                f"🎬 {title}\n"
                f"📅 {year}\n"
                f"🆔 {imdb_id}\n\n"
            )

        await update.message.reply_text(message)

    except Exception as e:

        print("OMDb xatosi:", e)

        await update.message.reply_text(
            "⚠️ Kino qidirishda xatolik yuz berdi."
        )


# =========================
# /DELETE
# =========================

async def delete_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Bu buyruq faqat admin uchun."
        )
        return

    if not context.args:

        await update.message.reply_text(
            "❗ Misol:\n/delete 060"
        )
        return

    code = context.args[0]

    if code not in movies:

        await update.message.reply_text(
            "❌ Bunday kod mavjud emas."
        )
        return

    del movies[code]

    # O'chirilgan kino bazadan ham o'chiriladi
    with open(MOVIES_FILE, "w", encoding="utf-8") as f:
        json.dump(
            movies,
            f,
            ensure_ascii=False,
            indent=2
        )

    await update.message.reply_text(
        f"✅ `{code}` kodi o‘chirildi.",
        parse_mode="Markdown"
    )


# =========================
# /LIST
# =========================

async def list_movies(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "❌ Bu buyruq faqat admin uchun."
        )
        return

    if not movies:

        await update.message.reply_text(
            "📂 Kino bazasi hozircha bo‘sh."
        )
        return

    text = "📂 Kino kodlari:\n\n"

    for code in movies:
        text += f"🎬 `{code}`\n"

    await update.message.reply_text(
        text,
        parse_mode="Markdown"
    )


# =========================
# BOTNI ISHGA TUSHIRISH
# =========================

def main():

    app = Application.builder().token(TOKEN).build()

    # /start
    app.add_handler(
        CommandHandler("start", start)
    )

    # /delete
    app.add_handler(
        CommandHandler("delete", delete_movie)
    )

    # /list
    app.add_handler(
        CommandHandler("list", list_movies)
    )

    # Obunani tekshirish tugmasi
    app.add_handler(
        CallbackQueryHandler(
            check_subscription,
            pattern="^check_subscription$"
        )
    )

    # Video/document qabul qilish
    app.add_handler(
        MessageHandler(
            filters.VIDEO | filters.Document.ALL,
            handle_video
        )
    )

    # Oddiy matnlar
    app.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_code
        )
    )

    print("🤖 Kino bot ishga tushdi...")

    app.run_polling()


if __name__ == "__main__":
    main()
