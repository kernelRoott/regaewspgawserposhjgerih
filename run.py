import asyncio
import logging
from bot import dp, bot
from webapp import start_web_server

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def main():
    """Запуск бота и веб-сервера одновременно"""
    logger.info("=== Запуск бота-предложки ===")

    # Запускаем веб-сервер
    await start_web_server()

    # Запускаем бота
    logger.info("Запуск Telegram бота...")
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
