import os
import logging
import asyncio
from flask import Flask, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# إعداد السجلات
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "9278942278:AAF8sn53bX6HgKKgf8bALJ9D9umeRD3uAg4"
ADMIN_ID = 893206139

# رابط مشروعك على Render
RENDER_EXTERNAL_URL = os.environ.get("RENDER_EXTERNAL_URL", "https://mohamd-it3.onrender.com")
PORT = int(os.environ.get("PORT", 8080))

app_web = Flask(__name__)

UNIVERSITY_DATA = {
    "doc1": {"name": "د. محمد حمود", "lectures": {}},
    "doc2": {"name": "د. علي حيدر", "lectures": {}},
    "doc3": {"name": "د. محمد حبيب (نظري)", "lectures": {}},
    "doc4": {"name": "د. محمد حبيب (عملي)", "lectures": {}},
    "doc5": {"name": "د. شعيب", "lectures": {}},
    "doc6": {"name": "د. احلام العريقي (نظري)", "lectures": {}},
    "doc10": {"name": "د. احلام العريقي (عملي)", "lectures": {}},
    "doc7": {"name": "م. جواد (عملي)", "lectures": {}},
    "doc8": {"name": "م. جوهر (عملي)", "lectures": {}},
    "doc9": {"name": "م. يسرى (عملي)", "lectures": {}},
}

user_states = {}
temp_lec_titles = {}

telegram_app = None
loop = None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = []

    for doc_id, doc_info in UNIVERSITY_DATA.items():
        keyboard.append(
            [InlineKeyboardButton(doc_info["name"], callback_data=f"user_doc_{doc_id}")]
        )

    if user_id == ADMIN_ID:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "⚙️ لوحة تحكم المالك لإضافة المحاضرات", callback_data="admin_panel"
                )
            ]
        )

    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "مرحباً بك في بوت المحاضرات والملخصات الجامعية 🎓\nإشراف الزميل: محمد الهياجم\n\nاختر الدكتور لعرض المحاضرات:"

    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    else:
        query = update.callback_query
        await query.edit_message_text(text, reply_markup=reply_markup)


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = []
    for doc_id, doc_info in UNIVERSITY_DATA.items():
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"➕ إضافة محاضرة لـ {doc_info['name']}",
                    callback_data=f"add_lec_{doc_id}",
                )
            ]
        )
    keyboard.append(
        [InlineKeyboardButton("🔙 رجوع للقائمة الرئيسية", callback_data="main_menu")]
    )

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "لوحة التحكم: اختر الدكتور لإضافة محاضرة جديدة:", reply_markup=reply_markup
    )


async def handle_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id

    if data == "main_menu":
        await start(update, context)
    elif data == "admin_panel" and user_id == ADMIN_ID:
        await admin_panel(update, context)
    elif data.startswith("user_doc_"):
        doc_id = data.replace("user_doc_", "")
        doc_info = UNIVERSITY_DATA.get(doc_id)

        keyboard = []
        if doc_info["lectures"]:
            for lec_id, lec_info in doc_info["lectures"].items():
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            lec_info["title"],
                            callback_data=f"get_file_{doc_id}_{lec_id}",
                        )
                    ]
                )
        else:
            keyboard.append(
                [InlineKeyboardButton("📌 لم تُرفع محاضرات بعد", callback_data="none")]
            )

        keyboard.append([InlineKeyboardButton("🔙 رجوع", callback_data="main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            f"محاضرات {doc_info['name']}:", reply_markup=reply_markup
        )

    elif data.startswith("get_file_"):
        _, _, doc_id, lec_id = data.split("_", 3)
        lec_info = UNIVERSITY_DATA[doc_id]["lectures"][lec_id]
        file_id = lec_info["file_id"]
        file_type = lec_info["type"]

        if file_type == "document":
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=file_id,
                caption=lec_info["title"],
            )
        elif file_type == "video":
            await context.bot.send_video(
                chat_id=update.effective_chat.id,
                video=file_id,
                caption=lec_info["title"],
            )
        elif file_type == "photo":
            await context.bot.send_photo(
                chat_id=update.effective_chat.id,
                photo=file_id,
                caption=lec_info["title"],
            )

    elif data.startswith("add_lec_") and user_id == ADMIN_ID:
        doc_id = data.replace("add_lec_", "")
        user_states[user_id] = f"waiting_for_title_{doc_id}"
        doc_name = UNIVERSITY_DATA[doc_id]["name"]
        await query.edit_message_text(
            f"أنت تضيف محاضرة لـ ({doc_name}).\nالخطوة 1: أرسل **عنوان المحاضرة** الآن:",
            parse_mode="Markdown",
        )


async def handle_admin_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID or user_id not in user_states:
        return

    state = user_states[user_id]

    if state.startswith("waiting_for_title_"):
        doc_id = state.replace("waiting_for_title_", "")
        title = update.message.text
        temp_lec_titles[user_id] = {"doc_id": doc_id, "title": title}
        user_states[user_id] = f"waiting_for_file_{doc_id}"
        await update.message.reply_text(
            f"عنوان المحاضرة: ({title}).\nالخطوة 2: **أرسل الملف أو الفيديو أو الصورة الآن**:"
        )

    elif state.startswith("waiting_for_file_"):
        doc_id = state.replace("waiting_for_file_", "")
        lec_data = temp_lec_titles.get(user_id)

        if not lec_data:
            await update.message.reply_text("حدث خطأ، ابدأ العملية من جديد.")
            return

        title = lec_data["title"]
        file_id = None
        file_type = None

        if update.message.document:
            file_id = update.message.document.file_id
            file_type = "document"
        elif update.message.video:
            file_id = update.message.video.file_id
            file_type = "video"
        elif update.message.photo:
            file_id = update.message.photo[-1].file_id
            file_type = "photo"
        else:
            await update.message.reply_text("❌ يرجى إرسال ملف، فيديو، أو صورة حصراً.")
            return

        lec_id = f"lec_{len(UNIVERSITY_DATA[doc_id]['lectures']) + 1}"
        UNIVERSITY_DATA[doc_id]["lectures"][lec_id] = {
            "title": title,
            "file_id": file_id,
            "type": file_type,
        }

        del user_states[user_id]
        del temp_lec_titles[user_id]
        await update.message.reply_text(
            f"✅ تم حفظ المحاضرة ({title}) بنجاح يا محمد!\nاضغط /start للعودة."
        )


@app_web.route("/")
def home():
    return "Bot is active and running via Webhook!"


@app_web.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    if request.method == "POST":
        json_data = request.get_json(force=True)
        update = Update.de_json(json_data, telegram_app.bot)
        # استخدام حلقة الأحداث الأساسية المفتوحة دون إغلاقها
        asyncio.run_coroutine_threadsafe(telegram_app.process_update(update), loop)
    return "ok", 200


async def main_async():
    global telegram_app, loop
    loop = asyncio.get_running_loop()

    telegram_app = Application.builder().token(TOKEN).build()

    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(handle_buttons))
    telegram_app.add_handler(
        MessageHandler(
            (filters.Document.ALL | filters.VIDEO | filters.PHOTO | filters.TEXT)
            & ~filters.COMMAND,
            handle_admin_messages,
        )
    )

    await telegram_app.initialize()
    await telegram_app.start()

    webhook_url = f"{RENDER_EXTERNAL_URL}/{TOKEN}"
    await telegram_app.bot.set_webhook(url=webhook_url)
    logger.info(f"Webhook set to: {webhook_url}")

    # تشغيل خادم Flask في خلفية غير متزامنة ليبقى الـ Event Loop نشطاً
    import hypercorn.asyncio
    from hypercorn.config import Config

    config = Config()
    config.bind = [f"0.0.0.0:{PORT}"]
    await hypercorn.asyncio.serve(app_web, config)


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
