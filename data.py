import json
import os
from datetime import datetime
from typing import Optional, List, Dict

DATA_FILE = 'data.json'
SETTINGS_FILE = 'settings.json'


def load_data() -> dict:
    """Загрузить данные из JSON файла"""
    if not os.path.exists(DATA_FILE):
        return {
            'posts': {},
            'users': {},
            'stats': {
                'total_users': 0,
                'total_posts': 0,
                'approved_posts': 0,
                'rejected_posts': 0
            }
        }

    with open(DATA_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_data(data: dict):
    """Сохранить данные в JSON файл"""
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_settings() -> dict:
    """Загрузить настройки"""
    if not os.path.exists(SETTINGS_FILE):
        from config import DEFAULT_COOLDOWN, DEFAULT_STARS_REWARD, MESSAGES
        return {
            'cooldown': DEFAULT_COOLDOWN,
            'stars_reward': DEFAULT_STARS_REWARD,
            'messages': MESSAGES
        }

    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_settings(settings: dict):
    """Сохранить настройки"""
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def add_user(user_id: int, username: Optional[str] = None, first_name: Optional[str] = None):
    """Добавить нового пользователя"""
    data = load_data()

    if str(user_id) not in data['users']:
        data['users'][str(user_id)] = {
            'id': user_id,
            'username': username,
            'first_name': first_name,
            'joined_at': datetime.now().isoformat(),
            'last_post_time': None,
            'posts_count': 0,
            'approved_count': 0,
            'rejected_count': 0
        }
        data['stats']['total_users'] += 1
        save_data(data)


def get_user(user_id: int) -> Optional[dict]:
    """Получить данные пользователя"""
    data = load_data()
    return data['users'].get(str(user_id))


def update_user_last_post(user_id: int):
    """Обновить время последней публикации пользователя"""
    data = load_data()
    if str(user_id) in data['users']:
        data['users'][str(user_id)]['last_post_time'] = datetime.now().isoformat()
        save_data(data)


def add_post(user_id: int, file_id: str, file_type: str, caption: Optional[str] = None) -> int:
    """Добавить новую публикацию"""
    data = load_data()

    # Генерируем ID публикации
    post_id = len(data['posts']) + 1

    data['posts'][str(post_id)] = {
        'id': post_id,
        'user_id': user_id,
        'file_id': file_id,
        'file_type': file_type,
        'caption': caption,
        'status': 'pending',  # pending, approved, rejected
        'created_at': datetime.now().isoformat(),
        'reviewed_at': None
    }

    # Обновляем статистику пользователя
    if str(user_id) in data['users']:
        data['users'][str(user_id)]['posts_count'] += 1

    data['stats']['total_posts'] += 1
    save_data(data)

    return post_id


def get_post(post_id: int) -> Optional[dict]:
    """Получить публикацию по ID"""
    data = load_data()
    return data['posts'].get(str(post_id))


def get_posts_by_status(status: str) -> List[dict]:
    """Получить все публикации с определенным статусом"""
    data = load_data()
    return [post for post in data['posts'].values() if post['status'] == status]


def update_post_status(post_id: int, status: str) -> bool:
    """Обновить статус публикации"""
    data = load_data()

    if str(post_id) not in data['posts']:
        return False

    post = data['posts'][str(post_id)]
    old_status = post['status']
    post['status'] = status
    post['reviewed_at'] = datetime.now().isoformat()

    # Обновляем статистику пользователя
    user_id = str(post['user_id'])
    if user_id in data['users']:
        if status == 'approved':
            data['users'][user_id]['approved_count'] += 1
            if old_status == 'pending':
                data['stats']['approved_posts'] += 1
        elif status == 'rejected':
            data['users'][user_id]['rejected_count'] += 1
            if old_status == 'pending':
                data['stats']['rejected_posts'] += 1

    save_data(data)
    return True


def get_top_users(limit: int = 10) -> List[dict]:
    """Получить топ пользователей по количеству публикаций"""
    data = load_data()
    users = list(data['users'].values())
    users.sort(key=lambda u: u['posts_count'], reverse=True)
    return users[:limit]


def get_stats_by_period(period_days: int) -> dict:
    """Получить статистику за период"""
    data = load_data()
    now = datetime.now()

    users_count = 0
    posts_count = 0

    # Подсчитываем пользователей
    for user in data['users'].values():
        joined = datetime.fromisoformat(user['joined_at'])
        if (now - joined).days <= period_days:
            users_count += 1

    # Подсчитываем посты
    for post in data['posts'].values():
        created = datetime.fromisoformat(post['created_at'])
        if (now - created).days <= period_days:
            posts_count += 1

    return {
        'users': users_count,
        'posts': posts_count
    }
