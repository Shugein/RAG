# src/utils/text_utils.py
"""
Утилиты для работы с текстом
"""

import re
import html
from typing import Optional
from bs4 import BeautifulSoup
import hashlib


def clean_html(html_text: str) -> str:
    """
    Очищает HTML от потенциально опасных тегов
    
    Args:
        html_text: HTML текст
        
    Returns:
        Очищенный HTML
    """
    if not html_text:
        return ""
    
    # Парсим HTML
    soup = BeautifulSoup(html_text, "html.parser")
    
    # Удаляем опасные теги
    for tag in soup.find_all(["script", "style", "iframe", "embed", "object"]):
        tag.decompose()
    
    # Удаляем опасные атрибуты
    for tag in soup.find_all(True):
        for attr in ["onclick", "onload", "onerror", "onmouseover"]:
            if attr in tag.attrs:
                del tag.attrs[attr]
    
    return str(soup)


def extract_plain_text(html_text: str) -> str:
    """
    Извлекает чистый текст из HTML
    
    Args:
        html_text: HTML текст
        
    Returns:
        Чистый текст без тегов
    """
    if not html_text:
        return ""
    
    # Парсим HTML
    soup = BeautifulSoup(html_text, "html.parser")
    
    # Извлекаем текст
    text = soup.get_text(separator=" ", strip=True)
    
    # Очищаем от лишних пробелов
    text = re.sub(r'\s+', ' ', text)
    
    return text.strip()


def normalize_whitespace(text: str) -> str:
    """Нормализует пробелы в тексте"""
    if not text:
        return ""
    
    # Заменяем все виды пробелов на обычные
    text = re.sub(r'[\xa0\u2000-\u200b\u2028\u2029\u202f\u205f\u3000]', ' ', text)
    
    # Убираем множественные пробелы
    text = re.sub(r'\s+', ' ', text)
    
    # Убираем пробелы в начале и конце строк
    lines = [line.strip() for line in text.split('\n')]
    text = '\n'.join(line for line in lines if line)
    
    return text.strip()


def truncate_text(text: str, max_length: int = 200, suffix: str = "...") -> str:
    """
    Обрезает текст до указанной длины
    
    Args:
        text: Исходный текст
        max_length: Максимальная длина
        suffix: Суффикс для обрезанного текста
        
    Returns:
        Обрезанный текст
    """
    if not text or len(text) <= max_length:
        return text
    
    # Обрезаем до последнего полного слова
    truncated = text[:max_length - len(suffix)]
    last_space = truncated.rfind(' ')
    
    if last_space > 0:
        truncated = truncated[:last_space]
    
    return truncated + suffix


def calculate_content_hash(title: str, text: str) -> str:
    """
    Вычисляет хеш контента для дедупликации
    
    Args:
        title: Заголовок
        text: Текст
        
    Returns:
        SHA-256 хеш
    """
    content = f"{title or ''}\n{text or ''}"
    content = normalize_whitespace(content)
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def extract_urls(text: str) -> list[str]:
    """
    Извлекает URLs из текста
    
    Args:
        text: Текст
        
    Returns:
        Список URL
    """
    if not text:
        return []
    
    # Паттерн для поиска URL
    url_pattern = re.compile(
        r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[/\w\-._~:/?#[\]@!$&\'()*+,;=.]*',
        re.IGNORECASE
    )
    
    urls = url_pattern.findall(text)
    
    # Убираем дубликаты и сортируем
    return sorted(set(urls))


def is_cyrillic(text: str) -> bool:
    """Проверяет, содержит ли текст кириллицу"""
    if not text:
        return False
    
    cyrillic_pattern = re.compile(r'[а-яА-ЯёЁ]')
    return bool(cyrillic_pattern.search(text))


def detect_language(text: str) -> str:
    """
    Простое определение языка текста
    
    Returns:
        'ru' для русского, 'en' для английского
    """
    if not text:
        return 'unknown'
    
    # Считаем кириллические и латинские символы
    cyrillic_count = len(re.findall(r'[а-яА-ЯёЁ]', text))
    latin_count = len(re.findall(r'[a-zA-Z]', text))
    
    if cyrillic_count > latin_count:
        return 'ru'
    elif latin_count > cyrillic_count:
        return 'en'
    else:
        return 'unknown'