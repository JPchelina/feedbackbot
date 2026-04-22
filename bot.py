import logging
import os
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

WAITING_EMAIL = 1
WAITING_MESSAGE = 2
WAITING_REPLY = 3

WELCOME = (
    "👋 Привет! На связи команда Clarity Cult.\n\n"
    "Пиши сюда, если что-то непонятно или можно сделать лучше. "
    "Мы читаем всё и улучшаем продукт на основе этого.\n\n"
    "Напиши, пожалуйста, email, с которым ты заходишь в платформу."
)

ASK_MESSAGE = (
    "Опиши суть вопроса или проблемы.\n\n"
    "Добавь скрин или ссылку — так мы быстрее разберёмся. "
    "Можно отправить текст, ссылку, фото, видео или файл.\n\n"
    "Чтобы отменить — напиши /cancel"
)

CONFIRMED = "✅ Приняли. Посмотрим и вернёмся с ответом в рабочее время — будние дни с 10:00 до 19:00."

AGAIN_BUTTON = [[InlineKeyboardButton("✍️ Написать ещё", callback_data="write_again")]]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(WELCOME)
    return WAITING_EMAIL


async def receive_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    if "@" not in email or "." not in email.split("@")[-1]:
        await update.message.reply_text(
            "Похоже, это не email 🙈\n\n"
            "Напиши, пожалуйста, email в формате example@mail.com"
        )
        return WAITING_EMAIL
    context.user_data["email"] = email
    await update.message.reply_text(ASK_MESSAGE)
    return WAITING_MESSAGE


async def receive_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message
    email = context.user_data.get("email", "не указан")

    user_info = f"📨 <b>Новое обращение</b>\n\n"
    user_info += f"👤 {user.full_name}"
    if user.username:
        user_info += f" (@{user.username})"
    user_info += f"\n📧 Email: {email}"
    user_info += f"\n🆔 ID: <code>{user.id}</code>"

    if message.text:
        user_info += f"\n\n💬 <b>Сообщение:</b>\n{message.text}"

    keyboard = [[InlineKeyboardButton("↩️ Ответить", callback_data=f"reply_{user.id}")]]

    try:
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=user_info,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        if not message.text:
            await message.forward(chat_id=ADMIN_GROUP_ID)

        await message.reply_text(
            CONFIRMED,
            reply_markup=InlineKeyboardMarkup(AGAIN_BUTTON)
        )
    except Exception as e:
        logger.error(f"Ошибка отправки: {e}")
        await message.reply_text("❌ Произошла ошибка. Попробуйте позже.")

    return ConversationHandler.END


async def write_again(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(CONFIRMED)
    if context.user_data.get("email"):
        await query.message.reply_text(ASK_MESSAGE)
        return WAITING_MESSAGE
    else:
        await query.message.reply_text(WELCOME)
        return WAITING_EMAIL


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. Напишите /start чтобы начать снова.")
    return ConversationHandler.END


async def admin_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    target_user_id = int(query.data.split("_")[1])
    context.user_data["reply_to_user"] = target_user_id
    await query.message.reply_text(
        f"✏️ Введите ответ для пользователя <code>{target_user_id}</code>:",
        parse_mode="HTML"
    )
    return WAITING_REPLY


async def admin_reply_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user_id = context.user_data.get("reply_to_user")
    if not target_user_id:
        await update.message.reply_text("❌ Не удалось определить получателя.")
        return ConversationHandler.END
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"📬 <b>Ответ от команды Clarity Cult:</b>\n\n{update.message.text}",
            parse_mode="HTML"
        )
        await update.message.reply_text(
            f"✅ Ответ отправлен пользователю <code>{target_user_id}</code>.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка ответа: {e}")
        await update.message.reply_text("❌ Не удалось отправить. Возможно пользователь заблокировал бота.")
    return ConversationHandler.END


def main():
    app = Application.builder().token(BOT_TOKEN).build()

    user_conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(write_again, pattern=r"^write_again$"),
        ],
        states={
            WAITING_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_email)
            ],
            WAITING_MESSAGE: [
                MessageHandler(
                    filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL,
                    receive_message
                )
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
    )

    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_reply_start, pattern=r"^reply_\d+$")],
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

    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
