

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from parser.base_parser import BaseNewsParser
import requests
from bs4 import BeautifulSoup
import time
import json
from datetime import datetime
from urllib.parse import urljoin, urlparse
import re

class ForbesParser(BaseNewsParser):
    """Парсер для Forbes.ru"""
    
    def __init__(self):
        self.base_url = "https://www.forbes.ru"
        self.name = "forbes"
        super().__init__(source_name="forbes.ru", base_url=self.base_url)
        
        # Специальные headers для обхода защиты Forbes
        self.session = requests.Session()
        
        # Пробуем разные user-agent для обхода защиты
        mobile_agents = [
            'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
            'Mozilla/5.0 (Android 13; Mobile; rv:109.0) Gecko/120.0 Firefox/120.0',
            'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
        ]
        
        self.current_agent = mobile_agents[0]
        self.mobile_agents = mobile_agents
        
        self.session.headers.update({
            'User-Agent': self.current_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        })
        
        # Увеличиваем задержку для Forbes
        self.delay = 2.0
        
        # Доступные разделы (по результатам анализа)
        self.sections = {
            'biznes': {
                'url': '/biznes/',
                'name': 'Бизнес'
            },
            'investicii': {
                'url': '/investicii/', 
                'name': 'Инвестиции'
            }
        }
        
        print(f"🚀 Инициализация парсера Forbes.ru")
        print(f"   Доступные разделы: {list(self.sections.keys())}")
    
    def get_section_urls(self, section_name: str, max_articles: int = 50) -> list:
        """
        Получает список URL статей из указанного раздела Forbes
        
        Args:
            section_name: Название раздела (biznes, investicii)
            max_articles: Максимальное количество статей для сбора
            
        Returns:
            list: Список URL статей
        """
        if section_name not in self.sections:
            print(f"❌ Неизвестный раздел: {section_name}")
            return []
        
        section_info = self.sections[section_name]
        section_url = self.base_url + section_info['url']
        
        print(f"🔍 Сбор URL из раздела {section_info['name']}: {section_url}")
        
        try:
            # Попробуем несколько раз с разными user-agent
            response = None
            
            for attempt in range(len(self.mobile_agents)):
                # Меняем user-agent
                self.session.headers['User-Agent'] = self.mobile_agents[attempt]
                
                print(f"   Попытка {attempt + 1} с agent: {self.mobile_agents[attempt][:50]}...")
                
                # Пауза перед запросом
                time.sleep(2)
                
                response = self.session.get(section_url, timeout=20)
                
                print(f"   Статус: {response.status_code}, размер: {len(response.content)} байт")
                
                if response.status_code == 200:
                    # Проверяем на капчу
                    content_lower = response.text.lower()
                    if ('captcha' not in content_lower and 
                        'yandex' not in content_lower and 
                        len(response.content) > 20000):
                        print(f"   ✅ Успешный запрос с попытки {attempt + 1}")
                        break
                    else:
                        print(f"   ❌ Обнаружена капча или блокировка")
                        response = None
                else:
                    print(f"   ❌ Ошибка статуса: {response.status_code}")
                    response = None
            
            if not response or response.status_code != 200:
                print(f"❌ Не удалось получить доступ к {section_url} после всех попыток")
                return []
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Поиск ссылок на статьи
            article_urls = set()
            
            # Ищем все ссылки
            all_links = soup.find_all('a', href=True)
            
            for link in all_links:
                href = link.get('href', '').strip()
                text = link.get_text(strip=True)
                
                # Пропускаем пустые ссылки и без текста
                if not href or not text or len(text) < 10:
                    continue
                
                # Преобразуем относительные ссылки в абсолютные
                if href.startswith('/'):
                    href = self.base_url + href
                elif not href.startswith('http'):
                    continue
                
                # Фильтруем по паттернам Forbes статей
                if self._is_article_url(href):
                    article_urls.add(href)
                    
                    if len(article_urls) >= max_articles:
                        break
            
            # Дополнительный поиск по специфичным селекторам
            article_selectors = [
                'article a[href*="/"]',
                '.article-item a[href*="/"]',
                '.news-item a[href*="/"]',
                '.story-item a[href*="/"]',
                '[class*="article"] a[href*="/"]',
                '[class*="story"] a[href*="/"]'
            ]
            
            for selector in article_selectors:
                try:
                    links = soup.select(selector)
                    for link in links:
                        href = link.get('href', '').strip()
                        
                        if href.startswith('/'):
                            href = self.base_url + href
                        
                        if self._is_article_url(href):
                            article_urls.add(href)
                            
                            if len(article_urls) >= max_articles:
                                break
                                
                    if len(article_urls) >= max_articles:
                        break
                        
                except Exception as e:
                    continue
            
            urls_list = list(article_urls)[:max_articles]
            print(f"✅ Найдено {len(urls_list)} URL статей в разделе {section_info['name']}")
            
            return urls_list
            
        except Exception as e:
            print(f"Ошибка при получении URL из раздела {section_name}: {e}")
            return []
    
    def _is_article_url(self, url: str) -> bool:
        """Проверяет, является ли URL ссылкой на статью Forbes"""
        if not url or 'forbes.ru' not in url:
            return False
            
        # Исключаем служебные страницы
        exclude_patterns = [
            '/forbes-heroes',
            '/sustainability/',
            '/about',
            '/contacts',
            '/advertising',
            '/subscription',
            '/rss',
            '/sitemap',
            '/privacy',
            '/terms'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url.lower():
                return False
        
        # Ищем паттерны статей Forbes
        article_patterns = [
            r'/[a-z-]+/\d+',  # /biznes/547083-...
            r'/article/',
            r'/news/',
            r'/story/',
            r'/post/'
        ]
        
        for pattern in article_patterns:
            if re.search(pattern, url):
                return True
        
        # Дополнительная проверка: URL должен содержать цифры (ID статьи)
        if re.search(r'/\d{4,}', url):
            return True
            
        return False
    
    def parse_article(self, url: str) -> dict:
        """
        Парсит отдельную статью Forbes
        
        Args:
            url: URL статьи
            
        Returns:
            dict: Данные статьи или None при ошибке
        """
        try:
            # Пробуем разные user-agent для статьи
            response = None
            
            for attempt in range(len(self.mobile_agents)):
                # Меняем user-agent
                self.session.headers['User-Agent'] = self.mobile_agents[attempt]
                
                # Пауза между запросами
                time.sleep(self.delay)
                
                response = self.session.get(url, timeout=20)
                
                if response.status_code == 200:
                    # Проверка на капчу
                    content_lower = response.text.lower()
                    if ('captcha' not in content_lower and 
                        'yandex' not in content_lower and 
                        len(response.content) > 10000):
                        break
                    else:
                        response = None
                        
                time.sleep(1)
            
            if not response or response.status_code != 200:
                print(f"Не удалось получить доступ к статье: {url}")
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title = self._extract_title(soup)
            content = self._extract_content(soup)
            date = self._extract_date(soup)
            
            if not title or not content:
                return None
            
            source_url = urlparse(url).netloc
            
            return {
                'title': title,
                'content': content,
                'url': url,
                'source': source_url,
                'date': date,
                'parser': self.name
            }
            
        except Exception as e:
            print(f"Ошибка парсинга статьи {url}: {e}")
            return None
    
    def _extract_title(self, soup: BeautifulSoup) -> str:
        """Извлекает заголовок статьи"""
        title_selectors = [
            'h1',
            '.article-title',
            '.headline',
            '.title',
            '[class*="title"]',
            'title'  # fallback
        ]
        
        for selector in title_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    title = element.get_text(strip=True)
                    if title and len(title) > 10:
                        return title
            except:
                continue
        
        return ""
    
    def _extract_content(self, soup: BeautifulSoup) -> str:
        """Извлекает основной текст статьи Forbes"""
        content_selectors = [
            '.article-content p',
            '.article-body p',
            '.content p',
            '.text p',
            'article p',
            '.article p',
            '[class*="content"] p',
            '[class*="text"] p',
            '[class*="body"] p',
            '.story-content p',
            '.post-content p'
        ]
        
        for selector in content_selectors:
            try:
                paragraphs = soup.select(selector)
                if paragraphs:
                    content_parts = []
                    for p in paragraphs:
                        text = p.get_text(strip=True)
                        if text and len(text) > 20:  # Минимальная длина параграфа
                            content_parts.append(text)
                    
                    if content_parts:
                        full_content = ' '.join(content_parts)
                        # Проверяем, что получили достаточно контента
                        if len(full_content) > 100:
                            return full_content
            except:
                continue
        
        try:
            # Удаляем ненужные элементы
            for unwanted in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                unwanted.decompose()
            
            # Ищем все параграфы
            all_paragraphs = soup.find_all('p')
            content_parts = []
            
            for p in all_paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 30:
                    content_parts.append(text)
            
            if content_parts:
                return ' '.join(content_parts)
                
        except:
            pass
        
        return ""
    
    def _extract_date(self, soup: BeautifulSoup) -> str:
        """Извлекает дату публикации"""
        date_selectors = [
            'time[datetime]',
            '.date',
            '.publish-date',
            '.article-date',
            '[class*="date"]',
            '[class*="time"]'
        ]
        
        for selector in date_selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    # Пробуем атрибут datetime
                    datetime_attr = element.get('datetime')
                    if datetime_attr:
                        return datetime_attr
                    
                    # Пробуем текст элемента
                    date_text = element.get_text(strip=True)
                    if date_text and len(date_text) < 50:
                        return date_text
            except:
                continue
        
        # Возвращаем текущую дату как fallback
        return datetime.now().strftime('%Y-%m-%d')
    
    def get_article_urls(self, max_articles: int = 100) -> list:
        """
        Получает URL статей из всех доступных разделов
        
        Args:
            max_articles: Максимальное количество статей
            
        Returns:
            list: Список URL статей
        """
        all_urls = []
        articles_per_section = max_articles // len(self.sections)
        
        for section_name in self.sections.keys():
            section_urls = self.get_section_urls(section_name, articles_per_section)
            all_urls.extend(section_urls)
            
            if len(all_urls) >= max_articles:
                break
        
        return all_urls[:max_articles]
    
    def extract_metadata(self, soup: BeautifulSoup, url: str) -> dict:
        """
        Извлекает метаданные статьи
        
        Args:
            soup: BeautifulSoup объект страницы
            url: URL статьи
            
        Returns:
            dict: Метаданные статьи
        """
        metadata = {}
        
        # Извлекаем meta теги
        meta_tags = {
            'description': soup.find('meta', attrs={'name': 'description'}),
            'keywords': soup.find('meta', attrs={'name': 'keywords'}),
            'author': soup.find('meta', attrs={'name': 'author'}),
            'og:title': soup.find('meta', attrs={'property': 'og:title'}),
            'og:description': soup.find('meta', attrs={'property': 'og:description'}),
        }
        
        for key, tag in meta_tags.items():
            if tag:
                content = tag.get('content', '').strip()
                if content:
                    metadata[key] = content
        
        # Определяем категорию по URL
        if '/biznes/' in url:
            metadata['category'] = 'Бизнес'
        elif '/investicii/' in url:
            metadata['category'] = 'Инвестиции'
        else:
            metadata['category'] = 'Общее'
        
        return metadata

if __name__ == "__main__":
    # Тестирование парсера
    parser = ForbesParser()
    
    # Тест получения URL
    urls = parser.get_section_urls('biznes', max_articles=5)
    print(f"\n📋 Получено URL для тестирования: {len(urls)}")
    
    # Тест парсинга статьи
    if urls:
        print(f"\n🔍 Тестирование парсинга первой статьи...")
        article = parser.parse_article(urls[0])
        
        if article:
            print(f"✅ Статья успешно спаршена:")
            print(f"   Заголовок: {article['title'][:60]}...")
            print(f"   Контент: {len(article['content'])} символов")
            print(f"   URL: {article['url']}")
        else:
            print(f"❌ Не удалось спарсить статью")
    else:
        print(f"❌ Не удалось получить URL для тестирования")