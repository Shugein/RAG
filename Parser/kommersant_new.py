#!/usr/bin/env python3
import requests
import time
import json
from bs4 import BeautifulSoup
from datetime import datetime

class KommersantNewParser:
    def __init__(self):
        self.base_url = "https://www.kommersant.ru"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        self.categories = {
            'economics': 'https://www.kommersant.ru/rubric/2',
            'business': 'https://www.kommersant.ru/rubric/3', 
            'politics': 'https://www.kommersant.ru/rubric/4',
            'society': 'https://www.kommersant.ru/rubric/5',
            'finance': 'https://www.kommersant.ru/rubric/40'
        }
    
    def get_articles_from_category(self, category_url, limit=10):
        """Собирает URL статей из категории"""
        try:
            print(f"Parsing category: {category_url}")
            time.sleep(1)
            response = self.session.get(category_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            article_urls = []
            
            links = soup.find_all('a', href=True)
            for link in links:
                href = link.get('href')
                if href and '/doc/' in href:
                    if href.startswith('/'):
                        full_url = self.base_url + href
                    else:
                        full_url = href
                    
                    # Избегаем дубликатов
                    if full_url not in article_urls:
                        article_urls.append(full_url)
                        if len(article_urls) >= limit:
                            break
            
            print(f"Found {len(article_urls)} article URLs in category")
            return article_urls
            
        except Exception as e:
            print(f"Error getting articles from {category_url}: {e}")
            return []
    
    def get_all_articles(self, limit_per_category=5):
        """Собирает статьи из всех категорий"""
        all_articles = []
        
        for category_name, category_url in self.categories.items():
            print(f"\n--- Processing category: {category_name} ---")
            
            # Получаем URL статей из категории
            article_urls = self.get_articles_from_category(category_url, limit_per_category)
            
            # Парсим каждую статью
            category_articles = []
            for i, url in enumerate(article_urls, 1):
                print(f"Parsing article {i}/{len(article_urls)}: {url}")
                article_data = self.parse_article(url)
                if article_data:
                    article_data['category'] = category_name
                    category_articles.append(article_data)
                    all_articles.append(article_data)
                
                time.sleep(0.5)  # Пауза между статьями
            
            print(f"Successfully parsed {len(category_articles)} articles from {category_name}")
        
        return all_articles
    
    def parse_article(self, url):
        """Парсит отдельную статью по URL"""
        try:
            time.sleep(1)
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Заголовок
            title = ""
            title_selectors = ['h1.doc_headline__text', 'h1.doc__title', 'h1']
            for selector in title_selectors:
                title_elem = soup.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break
            
            if not title or len(title) < 5:
                return None
            
            # Основной контент статьи
            content_parts = []
            
            # Селекторы для контента Коммерсанта
            content_selectors = [
                'p.doc__text',
                '.article_text_wrapper p',
                'article.doc p',
                '.doc__content p'
            ]
            
            for selector in content_selectors:
                paragraphs = soup.select(selector)
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if text and len(text) > 20:
                        # Фильтруем служебную информацию
                        if not any(word in text.lower() for word in ['подписывайтесь', 'реклама', 'cookie', 'коммерсантъ']):
                            content_parts.append(text)
            
            # Если основные селекторы не сработали, пробуем общий поиск
            if not content_parts:
                paragraphs = soup.find_all('p')
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if text and len(text) > 20:
                        if not any(word in text.lower() for word in ['подписывайтесь', 'реклама', 'cookie']):
                            content_parts.append(text)
            
            content = ' '.join(content_parts)
            
            if len(content) < 100:
                return None
            
            # Дата публикации
            date = ""
            date_selectors = ['time[datetime]', '.doc__date', '.article__date']
            for selector in date_selectors:
                date_elem = soup.select_one(selector)
                if date_elem:
                    date = date_elem.get('datetime') or date_elem.get_text(strip=True)
                    break
            
            # Автор
            author = ""
            author_selectors = ['.doc__author', '.article__author', '.author_name']
            for selector in author_selectors:
                author_elem = soup.select_one(selector)
                if author_elem:
                    author = author_elem.get_text(strip=True)
                    if len(author) < 100:  # Фильтруем слишком длинные строки
                        break
            
            # Теги
            tags = []
            tag_selectors = ['.doc__tags a', '.article__tags a', '.tags a']
            for selector in tag_selectors:
                tag_elements = soup.select(selector)
                for elem in tag_elements:
                    tag = elem.get_text(strip=True)
                    if tag and tag not in tags:
                        tags.append(tag)
            
            return {
                'url': url,
                'title': title,
                'content': content,
                'date': date,
                'author': author,
                'tags': tags[:5],  # Ограничиваем количество тегов
                'source': 'kommersant.ru',
                'content_length': len(content),
                'parsed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Parse error for {url}: {e}")
            return None

def main():
    print("Starting Kommersant Full Parser...")
    print("Will collect articles from all categories:")
    
    parser = KommersantNewParser()
    
    # Показываем все категории
    for name, url in parser.categories.items():
        print(f"  - {name}: {url}")
    
    print("\nStarting collection...")
    
    # Собираем статьи из всех категорий
    all_articles = parser.get_all_articles(limit_per_category=3)
    
    print(f"\n{'='*60}")
    print(f"COLLECTION COMPLETE")
    print(f"{'='*60}")
    print(f"Total articles collected: {len(all_articles)}")
    
    # Группируем по категориям для отчета
    by_category = {}
    for article in all_articles:
        category = article.get('category', 'unknown')
        if category not in by_category:
            by_category[category] = []
        by_category[category].append(article)
    
    print("\nArticles by category:")
    for category, articles in by_category.items():
        print(f"  {category}: {len(articles)} articles")
    
    # Показываем примеры статей
    print(f"\nSample articles:")
    for i, article in enumerate(all_articles[:5], 1):
        print(f"\n{i}. [{article.get('category', 'unknown').upper()}] {article['title'][:50]}...")
        print(f"   Author: {article.get('author', 'N/A')}")
        print(f"   Date: {article.get('date', 'N/A')}")
        print(f"   Content: {article['content_length']} chars")
        print(f"   Tags: {', '.join(article.get('tags', []))}")
        print(f"   URL: {article['url']}")
    
    # Сохраняем результаты
    if all_articles:
        # Основной файл с всеми статьями
        with open('parsers/kommersant/full_results.json', 'w', encoding='utf-8') as f:
            json.dump(all_articles, f, ensure_ascii=False, indent=2)
        
        # Отдельные файлы по категориям
        for category, articles in by_category.items():
            filename = f'parsers/kommersant/{category}_articles.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(articles, f, ensure_ascii=False, indent=2)
        
        # Сводка
        summary = {
            'collection_date': datetime.now().isoformat(),
            'total_articles': len(all_articles),
            'categories': {cat: len(arts) for cat, arts in by_category.items()},
            'sample_titles': [art['title'] for art in all_articles[:10]]
        }
        
        with open('parsers/kommersant/collection_summary.json', 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"\nFiles saved:")
        print(f"  - full_results.json: {len(all_articles)} articles")
        print(f"  - collection_summary.json: summary stats")
        for category in by_category.keys():
            print(f"  - {category}_articles.json: {len(by_category[category])} articles")
    
    return all_articles

if __name__ == "__main__":
    main()