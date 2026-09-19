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
    """Запуск бота и веб-сервера параллельно"""
    logger.info("=== Запуск бота-предложки ===")
 
    # Создаём задачи для параллельного выполнения
    web_task = asyncio.create_task(start_web_server())
    bot_task = asyncio.create_task(dp.start_polling(bot))
 
    # Ждём выполнения обеих задач
    await asyncio.gather(web_task, bot_task)
 
 
if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
