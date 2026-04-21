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

# --- НАСТРОЙКИ ---
BOT_TOKEN = "YOUR_BOT_TOKEN"          # Токен от @BotFather
ADMIN_GROUP_ID = -1001234567890       # ID группы администраторов (отрицательное число)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
WAITING_FEEDBACK = 1
WAITING_REPLY = 2


# --- КОМАНДА /start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("✍️ Оставить отзыв", callback_data="leave_feedback")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 Привет! Это бот обратной связи.\n\n"
        "Вы можете отправить нам любой отзыв, вопрос или предложение — "
        "мы обязательно его рассмотрим.",
        reply_markup=reply_markup
    )


# --- КНОПКА «Оставить отзыв» ---
async def ask_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    await query.edit_message_text(
        "📝 Напишите ваш отзыв или вопрос.\n\n"
        "Можно отправить текст, фото, видео или документ.\n\n"
        "Для отмены введите /cancel"
    )
    return WAITING_FEEDBACK


# --- ПОЛУЧЕНИЕ ОТЗЫВА ---
async def receive_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message

    # Формируем заголовок сообщения для группы
    user_info = (
        f"📨 <b>Новый отзыв</b>\n\n"
        f"👤 От: {user.full_name}"
    )
    if user.username:
        user_info += f" (@{user.username})"
    user_info += f"\n🆔 ID: <code>{user.id}</code>\n\n"

    keyboard = [[InlineKeyboardButton("↩️ Ответить", callback_data=f"reply_{user.id}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        # Пересылаем сообщение в группу админов с заголовком
        await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=user_info,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

        # Пересылаем само сообщение
        await message.forward(chat_id=ADMIN_GROUP_ID)

        await message.reply_text(
            "✅ Спасибо! Ваш отзыв успешно отправлен.\n"
            "Мы постараемся ответить как можно скорее."
        )
    except Exception as e:
        logger.error(f"Ошибка отправки в группу: {e}")
        await message.reply_text(
            "❌ Произошла ошибка при отправке. Попробуйте позже."
        )

    return ConversationHandler.END


# --- ОТМЕНА ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено. Введите /start чтобы начать снова.")
    return ConversationHandler.END


# --- ОТВЕТ АДМИНИСТРАТОРА ---
async def admin_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Извлекаем ID пользователя из callback_data
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
        admin = update.effective_user
        reply_text = (
            f"📬 <b>Ответ от администратора</b>\n\n"
            f"{update.message.text}"
        )

        await context.bot.send_message(
            chat_id=target_user_id,
            text=reply_text,
            parse_mode="HTML"
        )

        await update.message.reply_text(
            f"✅ Ответ успешно отправлен пользователю <code>{target_user_id}</code>.",
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Ошибка отправки ответа: {e}")
        await update.message.reply_text(
            "❌ Не удалось отправить ответ. Возможно, пользователь заблокировал бота."
        )

    return ConversationHandler.END


# --- ЗАПУСК ---
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    # Диалог для пользователей (отправка отзыва)
    user_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_feedback, pattern="^leave_feedback$")],
        states={
            WAITING_FEEDBACK: [
                MessageHandler(
                    filters.TEXT | filters.PHOTO | filters.VIDEO | filters.Document.ALL,
                    receive_feedback
                )
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True,
        per_chat=True,
    )

    # Диалог для администраторов (ответ пользователю)
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

    app.add_handler(CommandHandler("start", start))
    app.add_handler(user_conv)
    app.add_handler(admin_conv)

    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
