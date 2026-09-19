import asyncio
import logging
from aiohttp import web
from datetime import datetime
import json

import config
import data
from bot import bot, notify_user_about_status

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

routes = web.RouteTableDef()


@routes.get('/')
async def index(request):
    """Главная страница mini-app"""
    import os
    html_path = os.path.join(os.path.dirname(__file__), 'webapp.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()
    return web.Response(text=html, content_type='text/html')


@routes.get('/api/posts/{status}')
async def get_posts(request):
    """API: получить посты по статусу"""
    status = request.match_info['status']

    if status not in ['pending', 'approved', 'rejected']:
        return web.json_response({'error': 'Invalid status'}, status=400)

    posts = data.get_posts_by_status(status)

    # Добавляем информацию о пользователях
    for post in posts:
        user = data.get_user(post['user_id'])
        if user:
            post['user_name'] = user.get('first_name') or user.get('username') or f"User {user['id']}"

    return web.json_response({'posts': posts})


@routes.post('/api/posts/{post_id}/approve')
async def approve_post(request):
    """API: одобрить публикацию"""
    try:
        post_id = int(request.match_info['post_id'])
        post = data.get_post(post_id)

        if not post:
            return web.json_response({'error': 'Post not found'}, status=404)

        if post['status'] != 'pending':
            return web.json_response({'error': 'Post already reviewed'}, status=400)

        # Обновляем статус
        data.update_post_status(post_id, 'approved')

        # Уведомляем пользователя
        await notify_user_about_status(post['user_id'], post_id, 'approved')

        return web.json_response({'success': True, 'message': 'Post approved'})

    except Exception as e:
        logger.error(f'Error approving post: {e}')
        return web.json_response({'error': str(e)}, status=500)


@routes.post('/api/posts/{post_id}/reject')
async def reject_post(request):
    """API: отклонить публикацию"""
    try:
        post_id = int(request.match_info['post_id'])
        post = data.get_post(post_id)

        if not post:
            return web.json_response({'error': 'Post not found'}, status=404)

        if post['status'] != 'pending':
            return web.json_response({'error': 'Post already reviewed'}, status=400)

        # Обновляем статус
        data.update_post_status(post_id, 'rejected')

        # Уведомляем пользователя
        await notify_user_about_status(post['user_id'], post_id, 'rejected')

        return web.json_response({'success': True, 'message': 'Post rejected'})

    except Exception as e:
        logger.error(f'Error rejecting post: {e}')
        return web.json_response({'error': str(e)}, status=500)


@routes.get('/api/stats')
async def get_stats(request):
    """API: получить статистику"""
    try:
        all_data = data.load_data()

        # Статистика за разные периоды
        periods = {
            'day': data.get_stats_by_period(1),
            'week': data.get_stats_by_period(7),
            'month': data.get_stats_by_period(30),
            'three_months': data.get_stats_by_period(90)
        }

        # Топ пользователей
        top_users = data.get_top_users(10)

        return web.json_response({
            'total': all_data['stats'],
            'periods': periods,
            'top_users': top_users
        })

    except Exception as e:
        logger.error(f'Error getting stats: {e}')
        return web.json_response({'error': str(e)}, status=500)


@routes.get('/api/settings')
async def get_settings(request):
    """API: получить настройки"""
    settings = data.load_settings()
    return web.json_response(settings)


@routes.post('/api/settings')
async def update_settings(request):
    """API: обновить настройки"""
    try:
        new_settings = await request.json()

        # Валидация
        if 'cooldown' in new_settings:
            cooldown = int(new_settings['cooldown'])
            if cooldown < 0:
                return web.json_response({'error': 'Cooldown must be >= 0'}, status=400)

        if 'stars_reward' in new_settings:
            stars = int(new_settings['stars_reward'])
            if stars < 0:
                return web.json_response({'error': 'Stars reward must be >= 0'}, status=400)

        # Загружаем текущие настройки
        settings = data.load_settings()

        # Обновляем только переданные поля
        if 'cooldown' in new_settings:
            settings['cooldown'] = new_settings['cooldown']

        if 'stars_reward' in new_settings:
            settings['stars_reward'] = new_settings['stars_reward']

        if 'messages' in new_settings:
            settings['messages'].update(new_settings['messages'])

        # Сохраняем
        data.save_settings(settings)

        return web.json_response({'success': True, 'settings': settings})

    except Exception as e:
        logger.error(f'Error updating settings: {e}')
        return web.json_response({'error': str(e)}, status=500)


@routes.get('/api/file/{post_id}')
async def get_file_url(request):
    """API: получить URL файла для предпросмотра"""
    try:
        post_id = int(request.match_info['post_id'])
        post = data.get_post(post_id)

        if not post:
            return web.json_response({'error': 'Post not found'}, status=404)

        file_id = post.get('file_id')
        file_type = post.get('file_type')

        if not file_id:
            return web.json_response({
                'type': 'text',
                'content': post.get('caption', '')
            })

        # Получаем файл от Telegram API
        file = await bot.get_file(file_id)
        file_url = f'https://api.telegram.org/file/bot{config.BOT_TOKEN}/{file.file_path}'

        return web.json_response({
            'type': file_type,
            'url': file_url,
            'caption': post.get('caption')
        })

    except Exception as e:
        logger.error(f'Error getting file: {e}')
        return web.json_response({'error': str(e)}, status=500)


async def start_web_server():
    """Запуск веб-сервера"""
    app = web.Application()
    app.add_routes(routes)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(runner, '0.0.0.0', config.WEB_PORT)
    await site.start()

    logger.info(f"Веб-сервер запущен на порту {config.WEB_PORT}")
    logger.info(f"Mini-app доступен по адресу: {config.WEBAPP_URL}")


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(start_web_server())
    loop.run_forever()
