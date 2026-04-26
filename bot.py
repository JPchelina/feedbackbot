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

TAGS = ["🐛 Баг", "💳 Оплата", "📚 Контент", "🔧 Тех", "💡 Идея", "❓ Вопрос", "🌟 Похвала", "🎓 Консульт"]


def make_admin_keyboard(user_id, priority=False, closed=False, active_tags=None):
    if active_tags is None:
        active_tags = []

    priority_text = "⭐ Приоритет ✓" if priority else "⭐ Приоритет"

    if closed:
        action_row = [InlineKeyboardButton("🔄 Открыть заново", callback_data=f"open_{user_id}")]
    else:
        action_row = [
            InlineKeyboardButton("↩️ Ответить", callback_data=f"reply_{user_id}"),
            InlineKeyboardButton(priority_text, callback_data=f"priority_{user_id}"),
            InlineKeyboardButton("✅ Закрыть", callback_data=f"close_{user_id}"),
        ]

    keyboard = [action_row]

    if not closed:
        # Разделитель тегов
        keyboard.append([InlineKeyboardButton("— Теги —", callback_data="noop")])

        # Теги по 3 в ряд
        tag_row = []
        for tag in TAGS:
            tag_key = tag.split(" ", 1)[1]
            is_active = tag in active_tags
            label = f"{tag} ✓" if is_active else tag
            tag_row.append(InlineKeyboardButton(label, callback_data=f"tag_{user_id}_{tag_key}"))
            if len(tag_row) == 3:
                keyboard.append(tag_row)
                tag_row = []
        if tag_row:
            keyboard.append(tag_row)

    return InlineKeyboardMarkup(keyboard)


def make_card_text(user, email, message_text=None, priority=False, closed=False, active_tags=None):
    if active_tags is None:
        active_tags = []

    status = "🔒 Закрыто" if closed else ("⭐ Приоритет" if priority else "📨 Новое обращение")
    tags_line = " ".join(active_tags) if active_tags else ""

    text = f"{status}\n\n"
    text += f"👤 {user['name']}"
    if user.get("username"):
        text += f" (@{user['username']})"
    text += f"\n📧 Email: {user['email']}"
    text += f"\n🆔 ID: <code>{user['id']}</code>"

    if message_text:
        text += f"\n\n💬 <b>Сообщение:</b>\n{message_text}"

    if tags_line:
        text += f"\n\n🏷 {tags_line}"

    return text


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

    user_data = {
        "name": user.full_name,
        "username": user.username,
        "email": email,
        "id": user.id,
    }

    card_text = make_card_text(user_data, email, message_text=message.text if message.text else None)
    keyboard = make_admin_keyboard(user.id)

    try:
        sent = await context.bot.send_message(
            chat_id=ADMIN_GROUP_ID,
            text=card_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )

        # Сохраняем данные карточки для последующего редактирования
        context.bot_data[f"card_{sent.message_id}"] = {
            "user": user_data,
            "message_text": message.text if message.text else None,
            "priority": False,
            "closed": False,
            "tags": [],
        }

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


async def handle_priority(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split("_")[1])
    msg_id = query.message.message_id
    card = context.bot_data.get(f"card_{msg_id}")
    if not card:
        return

    card["priority"] = not card["priority"]
    new_text = make_card_text(card["user"], card["user"]["email"],
                               message_text=card["message_text"],
                               priority=card["priority"],
                               closed=card["closed"],
                               active_tags=card["tags"])
    keyboard = make_admin_keyboard(user_id, priority=card["priority"],
                                    closed=card["closed"], active_tags=card["tags"])
    await query.edit_message_text(new_text, parse_mode="HTML", reply_markup=keyboard)


async def handle_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split("_")[1])
    msg_id = query.message.message_id
    card = context.bot_data.get(f"card_{msg_id}")
    if not card:
        return

    card["closed"] = True
    new_text = make_card_text(card["user"], card["user"]["email"],
                               message_text=card["message_text"],
                               priority=card["priority"],
                               closed=True,
                               active_tags=card["tags"])
    keyboard = make_admin_keyboard(user_id, priority=card["priority"],
                                    closed=True, active_tags=card["tags"])
    await query.edit_message_text(new_text, parse_mode="HTML", reply_markup=keyboard)


async def handle_open(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split("_")[1])
    msg_id = query.message.message_id
    card = context.bot_data.get(f"card_{msg_id}")
    if not card:
        return

    card["closed"] = False
    new_text = make_card_text(card["user"], card["user"]["email"],
                               message_text=card["message_text"],
                               priority=card["priority"],
                               closed=False,
                               active_tags=card["tags"])
    keyboard = make_admin_keyboard(user_id, priority=card["priority"],
                                    closed=False, active_tags=card["tags"])
    await query.edit_message_text(new_text, parse_mode="HTML", reply_markup=keyboard)


async def handle_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    parts = query.data.split("_", 2)
    user_id = int(parts[1])
    tag_key = parts[2]
    msg_id = query.message.message_id
    card = context.bot_data.get(f"card_{msg_id}")
    if not card:
        return

    # Найти полный тег по ключу
    full_tag = next((t for t in TAGS if t.split(" ", 1)[1] == tag_key), None)
    if not full_tag:
        return

    if full_tag in card["tags"]:
        card["tags"].remove(full_tag)
    else:
        card["tags"].append(full_tag)

    new_text = make_card_text(card["user"], card["user"]["email"],
                               message_text=card["message_text"],
                               priority=card["priority"],
                               closed=card["closed"],
                               active_tags=card["tags"])
    keyboard = make_admin_keyboard(user_id, priority=card["priority"],
                                    closed=card["closed"], active_tags=card["tags"])
    await query.edit_message_text(new_text, parse_mode="HTML", reply_markup=keyboard)


async def admin_reply_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = int(query.data.split("_")[1])
    context.user_data["reply_to_user"] = user_id
    admin = query.from_user
    context.user_data["admin_name"] = admin.first_name or admin.full_name
    await query.message.reply_text(
        f"✏️ Введите ответ для пользователя <code>{user_id}</code>:",
        parse_mode="HTML"
    )
    return WAITING_REPLY


async def admin_reply_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_user_id = context.user_data.get("reply_to_user")
    admin_name = context.user_data.get("admin_name", "команды Clarity Cult")
    if not target_user_id:
        await update.message.reply_text("❌ Не удалось определить получателя.")
        return ConversationHandler.END
    try:
        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"📬 <b>Ответ от {admin_name}:</b>\n\n{update.message.text}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(AGAIN_BUTTON)
        )
        again_admin = [[InlineKeyboardButton(
            "↩️ Ответить ещё раз", callback_data=f"reply_{target_user_id}"
        )]]
        await update.message.reply_text(
            f"✅ Ответ отправлен пользователю <code>{target_user_id}</code>.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(again_admin)
        )
    except Exception as e:
        logger.error(f"Ошибка ответа: {e}")
        await update.message.reply_text("❌ Не удалось отправить. Возможно пользователь заблокировал бота.")
    return ConversationHandler.END


async def noop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()


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
    app.add_handler(CallbackQueryHandler(handle_priority, pattern=r"^priority_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_close, pattern=r"^close_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_open, pattern=r"^open_\d+$"))
    app.add_handler(CallbackQueryHandler(handle_tag, pattern=r"^tag_\d+_.+$"))
    app.add_handler(CallbackQueryHandler(noop, pattern=r"^noop$"))

    logger.info("Бот запущен...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
