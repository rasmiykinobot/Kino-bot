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

ADMIN_ID = 5559820565

# Majburiy obuna kanali
FORCE_CHANNEL = "@rasmiykinouz"
FORCE_CHANNEL_URL = "https://t.me/rasmiykinouz"

MOVIES_FILE = "movies.json"

CHANNELS_FILE = "channels.json"

DEFAULT_CHANNEL = {
    "chat_id": "@rasmiykinouz",
    "name": "Rasmiy Kino",
    "url": "https://t.me/rasmiykinouz"
}

def load_channels():
    try:
        with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list) and data:
            return data
    except Exception:
        pass
    return [DEFAULT_CHANNEL.copy()]

def save_channels(channels):
    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        json.dump(channels, f, ensure_ascii=False, indent=2)

channels = load_channels()



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
    Foydalanuvchining barcha majburiy kanallarga obuna bo'lganligini tekshiradi.
    """
    for channel in channels:
        try:
            member = await bot.get_chat_member(
                chat_id=channel["chat_id"],
                user_id=user_id
            )

            if member.status in ("member", "administrator", "creator"):
                continue

            if member.status == "restricted":
                if getattr(member, "is_member", False):
                    continue

            return False

        except TelegramError:
            return False

    return True

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

# =========================
# ADMIN PANEL
# =========================

admin_action = None


def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Kanal qo‘shish", callback_data="admin_add")],
        [InlineKeyboardButton("🗑 Kanal o‘chirish", callback_data="admin_remove")],
        [InlineKeyboardButton("📋 Kanallar", callback_data="admin_list")],
    ])


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global admin_action

    if update.effective_user.id != ADMIN_ID:
        return

    admin_action = None

    await update.message.reply_text(
        "🔐 ADMIN PANEL\n\n"
        "Majburiy obuna kanallarini boshqarish:",
        reply_markup=admin_keyboard()
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global admin_action

    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    if query.data == "admin_add":
        admin_action = "add"
        await query.message.reply_text(
            "➕ Kanal qo‘shish\n\n"
            "Kanal username'ini yuboring.\n"
            "Masalan:\n"
            "@kanal_username"
        )

    elif query.data == "admin_remove":
        admin_action = "remove"

        if not channels:
            await query.message.reply_text("❌ Kanallar mavjud emas.")
            return

        text = "🗑 O‘chirish uchun kanal raqamini yuboring:\n\n"

        for i, channel in enumerate(channels, 1):
            text += f"{i}. {channel['name']} — {channel['chat_id']}\n"

        await query.message.reply_text(text)

    elif query.data == "admin_list":
        if not channels:
            await query.message.reply_text("📋 Majburiy kanallar mavjud emas.")
            return

        text = "📋 MAJBURIY OBUNA KANALLARI\n\n"

        for i, channel in enumerate(channels, 1):
            text += (
                f"{i}. {channel['name']}\n"
                f"   🆔 {channel['chat_id']}\n"
                f"   🔗 {channel['url']}\n\n"
            )

        await query.message.reply_text(text)


async def admin_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global admin_action

    if update.effective_user.id != ADMIN_ID:
        return

    if admin_action is None:
        await handle_code(update, context)
        return

    if admin_action == "add":
        chat_id = update.message.text.strip()

        if not chat_id.startswith("@"):
            await update.message.reply_text(
                "❌ Hozircha faqat @username ko‘rinishidagi kanal qo‘shing.\n"
                "Masalan: @mychannel"
            )
            return

        if any(c["chat_id"] == chat_id for c in channels):
            await update.message.reply_text("⚠️ Bu kanal allaqachon qo‘shilgan.")
            admin_action = None
            return

        try:
            chat = await context.bot.get_chat(chat_id)

            channel = {
                "chat_id": chat_id,
                "name": chat.title or chat_id,
                "url": f"https://t.me/{chat_id[1:]}"
            }

            channels.append(channel)
            save_channels(channels)

            admin_action = None

            await update.message.reply_text(
                f"✅ Kanal qo‘shildi!\n\n"
                f"📢 {channel['name']}\n"
                f"🆔 {chat_id}\n"
                f"🔗 {channel['url']}"
            )

        except TelegramError:
            await update.message.reply_text(
                "❌ Kanalni topib bo‘lmadi.\n"
                "Bot kanalga admin ekanini va username to‘g‘ri ekanini tekshiring."
            )

    elif admin_action == "remove":
        try:
            number = int(update.message.text.strip())
            index = number - 1

            if index < 0 or index >= len(channels):
                await update.message.reply_text("❌ Bunday raqamdagi kanal yo‘q.")
                return

            removed = channels.pop(index)
            save_channels(channels)

            admin_action = None

            await update.message.reply_text(
                f"✅ Kanal o‘chirildi:\n"
                f"{removed['name']} — {removed['chat_id']}"
            )

        except ValueError:
            await update.message.reply_text(
                "❌ Kanal raqamini yozing. Masalan: 1"
            )


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

    # /admin
    app.add_handler(
        CommandHandler("admin", admin_panel)
    )

    # Admin panel tugmalari
    app.add_handler(
        CallbackQueryHandler(
            admin_callback,
            pattern="^admin_"
        )
    )

    # Admin paneldagi matnlar
    app.add_handler(
        MessageHandler(
            filters.User(user_id=ADMIN_ID) & filters.TEXT & ~filters.COMMAND,
            admin_text
        )
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
