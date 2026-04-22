import logging
import os
from collections import defaultdict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMIN_GROUP_ID = int(os.environ["ADMIN_GROUP_ID"])

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

CHOOSING_LANG = 1
CHOOSING_CATEGORY = 2
WAITING_FEEDBACK = 3
WAITING_REPLY = 4

stats = defaultdict(lambda: defaultdict(int))

TEXTS = {
    "ru": {
        "welcome": "👋 Привет! Это бот обратной связи.\n\nВыберите язык:",
        "choose_category": "📋 Выберите категорию:",
        "cat_question": "❓ Вопрос",
        "cat_complaint": "😞 Жалоба",
        "cat_suggestion": "💡 Предложение",
        "write_message": "✍️ Напишите ваше сообщение.\n\nМожно отправить текст, фото, видео или файл.\n\nДля отмены — /cancel",
        "thanks": "✅ Спасибо! Ваше обращение отправлено.\nМы ответим вам как можно скорее.",
        "error": "❌ Произошла ошибка. Попробуйте позже.",
        "cancelled": "❌ Отменено. Напишите /start чтобы начать снова.",
        "reply_button": "↩️ Ответить",
        "reply_prompt": "✏️ Введите ответ для пользователя",
        "reply_sent": "✅ Ответ отправлен пользователю",
        "reply_failed": "❌ Не удалось отправить. Возможно пользователь заблокировал бота.",
        "reply_received": "📬 <b>Ответ от администратора:</b>\n\n",
    },
    "en": {
        "welcome": "👋 Hi! This is a feedback bot.\n\nChoose language:",
        "choose_category": "📋 Choose a category:",
        "cat_question": "❓ Question",
        "cat_complaint": "😞 Complaint",
        "cat_suggestion": "💡 Suggestion",
        "write_message": "✍️ Write your message.\n\nYou can send text, photo, video or file.\n\nTo cancel — /cancel",
        "thanks": "✅ Thank you! Your message has been sent.\nWe will reply as soon as possible.",
        "error": "❌ An error occurred. Please try again later.",
        "cancelled": "❌ Cancelled. Type /start to begin again.",
        "reply_button": "↩️ Reply",
        "reply_prompt": "✏️ Enter your reply for user",
        "reply_sent": "✅ Reply sent to user",
        "reply_failed": "❌ Could not send. The user may have blocked the bot.",
        "reply_received": "📬 <b>Reply from administrator:</b>\n\n",
    }
}

CATEGORY_NAMES = {
    "question": {"ru": "❓ Вопрос", "en": "❓ Question"},
    "complaint": {"ru": "😞 Жалоба", "en": "😞 Complaint"},
    "suggestion": {"ru": "💡 Предложение", "en": "💡 Suggestion"},
}


def t(lang, key):
    return TEXTS.get(lang, TEXTS["ru"]).get(key, "")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("🇷🇺 Русский", callback_data="lang_ru"),
        InlineKeyboardButton("🇬🇧 English", callback_data="lang_en"),
    ]]
    await update.message.reply_text(
        "👋 Привет! / Hi!\n\nВыберите язык / Choose language:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING_LANG


async def choose_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    lang = query.data.split("_")[1]
    context.user_data["lang"] = lang
    keyboard = [
        [InlineKeyboardButton(t(lang, "cat_question"), callback_data="cat_question")],
        [InlineKeyboardButton(t(lang, "cat_complaint"), callback_data="cat_complaint")],
        [InlineKeyboardButton(t(lang, "cat_suggestion"), callback_data="cat_suggestion")],
    ]
    await query.edit_message_text(
        t(lang, "choose_category"),
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return CHOOSING_CATEGORY


async def choose_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    category = query.data.split("_")[1]
    context.user_data["category"] = category
    lang = context.user_data.get("lang", "ru")
    await query.edit_message_text(t(lang, "write_message"))
    return WAITING_FEEDBACK


async def receive_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message
    lang = context.user_data.get("lang", "ru")
    category = context.user_data.get("category", "question")

    stats[category][lang] += 1

    category_label = CATEGORY_NAMES.get(category, {}).get(lang, category)
    lang_label = "Русский 🇷🇺" if lang == "ru" else "English 🇬🇧"

    user_info = (
        f"📨 <b>Новое обращение</b>\n\n"
        f"📋 Категория: <b>{category_label}</b>\n"
        f"🌐 Язык: {lang_label}\n"
        f"👤 От: {user.full_name}"
    )
    if user.username:
        user_info += f" (@{user.username})"
    user_info += f"\n🆔 ID: <code>{user.id}</code>"

    keyboard = [[InlineKeyboardButton(
        t(lang, "reply_button"), callback_data=f"reply_{user.id}_{lang}"
    )]]

    try:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=user_info,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        await message.forward(chat_id=ADMIN_GROUP_ID)
        await message.reply_text(t(lang, "thanks"))
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        await message.reply_text(t(lang, "error"))

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = context.user_data.get("lang", "ru")
    await update.message.reply_text(t(lang, "cancelled"))
    return ConversationHandler.END


async def admin_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_")
    target_user_id = int(parts[1])
    lang = parts[2] if len(parts) > 2 else "ru"
    context.user_data["reply_to_user"] = target_user_id
    context.user_data["reply_lang"] = lang
    await query.message.reply_text(
        f"{t(lang, 'reply_prompt')} <code>{target_user_id}</code>:",
        parse_mode="HTML"
    )
    return WAITING_REPLY


async def admin_reply_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user_id = context.user_data.get("reply_to_user")
    lang = context.user_data.get("reply_lang", "ru")
    if not target_user_id:
        await update.message.reply_text("❌ Не удалось определить получателя.")
        return ConversationHandler.END
    try:
        reply_text = t(lang, "reply_received") + update.message.text
        await context.bot.send_message(
            chat_id=target_user_id,
            text=reply_text,
            parse_mode="HTML"
        )
        await update.message.reply_text(
            f"{t(lang, 'reply_sent')} <code>{target_user_id}</code>.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка ответа: {e}")
        await update.message.reply_text(t(lang, "reply_failed"))
    return ConversationHandler.END


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not stats:
        await update.message.reply_text("📊 Статистики пока нет.")
        return
    total = 0
    text = "📊 <b>Статистика обращений</b>\n\n"
    for category, langs in stats.items():
        cat_total = sum(langs.values())
        total += cat_total
        cat_ru = CATEGORY_NAMES.get(category, {}).get("ru", category)
        cat_en = CATEGORY_NAMES.get(category, {}).get("en", category)
        text += f"<b>{cat_ru} / {cat_en}</b>: {cat_total}\n"
        if langs.get("ru"):
            text += f"  🇷🇺 {langs['ru']}\n"
        if langs.get("en"):
            text += f"  🇬🇧 {langs['en']}\n"
    text += f"\n📬 <b>Всего / Total: {total}</b>"
    await update.message.reply_text(text, parse_mode="HTML")


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    user_conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            CHOOSING_LANG: [CallbackQueryHandler(choose_language, pattern=r"^lang_")],
            CHOOSING_CATEGORY: [CallbackQueryHandler(choose_category, pattern=r"^cat_")],
            WAITING_FEEDBACK: [
                MessageHandler(
                    filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL,
                    receive_feedback
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
    )

    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_reply_start, pattern=r"^reply_\d+_")],
        states={
            WAITING_REPLY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, admin_reply_send)
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
    )

    app.add_handler(user_conv)
    app.add_handler(admin_conv)
    app.add_handler(CommandHandler("stats", show_stats))

    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
