import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import config
import data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN))
dp = Dispatcher()


def can_post(user_id: int) -> tuple[bool, int]:
    """Проверить, может ли пользователь отправить публикацию (кулдаун)"""
    user = data.get_user(user_id)
    if not user or not user['last_post_time']:
        return True, 0

    settings = data.load_settings()
    cooldown = settings.get('cooldown', config.DEFAULT_COOLDOWN)

    try:
        # Парсим дату из ISO формата
        last_post_str = user['last_post_time'].replace('Z', '+00:00')
        if '.' in last_post_str and '+' not in last_post_str and 'Z' not in user['last_post_time']:
            # Если есть микросекунды но нет таймзоны, добавляем UTC
            last_post_str = last_post_str.split('.')[0]

        last_post = datetime.fromisoformat(last_post_str.split('.')[0])
        now = datetime.now()
        elapsed = (now - last_post).total_seconds()

        if elapsed >= cooldown:
            return True, 0

        return False, int(cooldown - elapsed)
    except (ValueError, AttributeError) as e:
        logger.error(f"Ошибка парсинга даты: {e}, дата: {user['last_post_time']}")
        # В случае ошибки разрешаем пост
        return True, 0


async def notify_admin_new_post(post_id: int):
    """Уведомить администратора о новой публикации"""
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📱 Открыть Mini App", web_app={'url': config.WEBAPP_URL})]
        ])

        await bot.send_message(
            config.ADMIN_ID,
            f"🔔 Новая публикация на рассмотрении!\n\n"
            f"📋 Номер: #{post_id}\n"
            f"Откройте Mini App для просмотра.",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {e}")


@dp.message(Command('start'))
async def cmd_start(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    # Добавляем пользователя, если его еще нет
    data.add_user(user_id, username, first_name)

    settings = data.load_settings()
    stars = settings.get('stars_reward', config.DEFAULT_STARS_REWARD)
    text = settings['messages']['start'].format(stars=stars)

    await message.answer(text)


@dp.message(Command('check'))
async def cmd_check(message: Message):
    """Обработчик команды /check для проверки статуса публикации"""
    try:
        # Извлекаем номер из команды (/check #123 или /check 123)
        text = message.text.replace('/check', '').strip().replace('#', '')
        if not text:
            await message.answer('❌ Укажите номер публикации: /check #номер')
            return

        post_id = int(text)
        post = data.get_post(post_id)

        if not post:
            await message.answer(f'❌ Публикация #{post_id} не найдена.')
            return

        if post['user_id'] != message.from_user.id:
            await message.answer('❌ Это не ваша публикация.')
            return

        status_text = {
            'pending': '⏳ На рассмотрении',
            'approved': '✅ Одобрена',
            'rejected': '❌ Отклонена'
        }

        await message.answer(
            f'📋 Публикация #{post_id}\n'
            f'Статус: {status_text.get(post["status"], "Неизвестно")}'
        )

    except ValueError:
        await message.answer('❌ Неверный формат. Используйте: /check #номер')
    except Exception as e:
        logger.error(f'Ошибка в /check: {e}')
        await message.answer('❌ Произошла ошибка при проверке статуса.')


@dp.message(F.content_type.in_({
    'photo', 'video', 'document', 'audio',
    'voice', 'video_note', 'animation', 'sticker'
}))
async def handle_media(message: Message):
    """Обработчик медиа-файлов от пользователей"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    # Добавляем пользователя, если его еще нет
    data.add_user(user_id, username, first_name)

    # Проверяем кулдаун
    can, wait_seconds = can_post(user_id)
    if not can:
        settings = data.load_settings()
        text = settings['messages']['cooldown'].format(seconds=wait_seconds)
        await message.answer(text)
        return

    # Определяем тип файла и ID
    file_id = None
    file_type = message.content_type

    if message.photo:
        file_id = message.photo[-1].file_id
        file_type = 'photo'
    elif message.video:
        file_id = message.video.file_id
        file_type = 'video'
    elif message.document:
        file_id = message.document.file_id
        file_type = 'document'
    elif message.audio:
        file_id = message.audio.file_id
        file_type = 'audio'
    elif message.voice:
        file_id = message.voice.file_id
        file_type = 'voice'
    elif message.video_note:
        file_id = message.video_note.file_id
        file_type = 'video_note'
    elif message.animation:
        file_id = message.animation.file_id
        file_type = 'animation'
    elif message.sticker:
        file_id = message.sticker.file_id
        file_type = 'sticker'

    if not file_id:
        await message.answer('❌ Не удалось обработать файл.')
        return

    # Сохраняем публикацию
    caption = message.caption or message.text
    post_id = data.add_post(user_id, file_id, file_type, caption)
    data.update_user_last_post(user_id)

    # Отправляем подтверждение пользователю
    settings = data.load_settings()
    text = settings['messages']['submitted'].format(number=post_id)
    await message.answer(text)

    # Уведомляем администратора
    await notify_admin_new_post(post_id)


@dp.message()
async def handle_text(message: Message):
    """Обработчик текстовых сообщений"""
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    # Добавляем пользователя, если его еще нет
    data.add_user(user_id, username, first_name)

    # Проверяем кулдаун
    can, wait_seconds = can_post(user_id)
    if not can:
        settings = data.load_settings()
        text = settings['messages']['cooldown'].format(seconds=wait_seconds)
        await message.answer(text)
        return

    # Сохраняем текстовую публикацию
    post_id = data.add_post(user_id, '', 'text', message.text)
    data.update_user_last_post(user_id)

    # Отправляем подтверждение пользователю
    settings = data.load_settings()
    text = settings['messages']['submitted'].format(number=post_id)
    await message.answer(text)

    # Уведомляем администратора
    await notify_admin_new_post(post_id)


async def notify_user_about_status(user_id: int, post_id: int, status: str):
    """Уведомить пользователя об изменении статуса публикации"""
    try:
        settings = data.load_settings()

        if status == 'approved':
            text = settings['messages']['approved'].format(number=post_id)
        elif status == 'rejected':
            text = settings['messages']['rejected'].format(number=post_id)
        else:
            return

        await bot.send_message(user_id, text)
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")


async def main():
    """Запуск бота"""
    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
