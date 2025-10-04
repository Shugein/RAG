import requests
import time
import json
from bs4 import BeautifulSoup
from datetime import datetime

class MOEXParser:
    def __init__(self):
        self.base_url = "https://www.moex.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })
        
        self.news_page_url = "https://www.moex.com/ru/news/"
    
    def get_news_urls(self, limit=20):
        """Получаем URL новостей со страницы новостей MOEX"""
        try:
            print(f"Parsing MOEX news page: {self.news_page_url}")
            time.sleep(1)
            response = self.session.get(self.news_page_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            news_urls = []
            
            news_container = soup.find('div', class_='new-moex-news-list')
            if news_container:
                news_link_elements = news_container.find_all('a', class_='new-moex-news-list__link')
                
                for link in news_link_elements:
                    href = link.get('href')
                    if href:
                        if href.startswith('/n'):
                            full_url = f"https://www.moex.com{href}"
                            news_urls.append(full_url)
                            title = link.get_text().strip()[:50]
                            print(f"Найдена новость: {title}...")
                            
                            if len(news_urls) >= limit:
                                break
            
            print(f"Found {len(news_urls)} news URLs")
            return list(set(news_urls))  # Убираем дубликаты
            
        except Exception as e:
            print(f"Error getting MOEX news URLs: {e}")
            return []
    
    def _is_valid_news_url(self, url):
        """Проверяем что это валидная ссылка на новость"""
        if not url:
            return False
        
        exclude_patterns = [
            '/auth/', '/search/', '/download/', '/upload/',
            'javascript:', 'mailto:', '#', '.pdf', '.xlsx', '.doc'
        ]
        
        for pattern in exclude_patterns:
            if pattern in url.lower():
                return False
        
        return '/news/' in url or '/press/' in url
    
    def get_all_news(self, limit=10):
        """Получаем все новости - сначала URL, потом парсим каждую"""
        print("Starting MOEX news collection...")
        
        news_urls = self.get_news_urls(limit)
        
        if not news_urls:
            print("No news URLs found")
            return []
        
        all_news = []
        for i, url in enumerate(news_urls, 1):
            print(f"Parsing news {i}/{len(news_urls)}: {url}")
            news_data = self.parse_article(url)
            if news_data:
                all_news.append(news_data)
            
            time.sleep(0.5)  # Пауза между запросами
        
        print(f"Successfully parsed {len(all_news)} news articles")
        return all_news
    
    def parse_article(self, url):
        """Парсим отдельную новость MOEX"""
        try:
            time.sleep(1)
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title_elem = soup.find('h1')
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            if not title or len(title) < 5:
                return None
            
            content_parts = []
            paragraphs = soup.find_all('p')
            
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and len(text) > 20:
                    if not any(word in text.lower() for word in ['подписаться', 'реклама', 'cookie', 'javascript']):
                        content_parts.append(text)
            
            content = ' '.join(content_parts)
            
            if len(content) < 50:
                return None
            
            date = ""
            date_elem = soup.find('div', class_='news_date')
            if date_elem:
                date = date_elem.get_text(strip=True)
            
            if not date:
                date_selectors = [
                    'time[datetime]',
                    '.date', 
                    '.publish-date'
                ]
                
                for selector in date_selectors:
                    date_el = soup.select_one(selector)
                    if date_el:
                        date = date_el.get('datetime') or date_el.get_text(strip=True)
                        break
            
            tags = []
            tag_selectors = ['.tags a', '.keywords a', '.categories a']
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
                'tags': tags[:5],
                'source': 'moex.com',
                'content_length': len(content),
                'parsed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            print(f"Parse error for MOEX {url}: {e}")
            return None

def main():
    print("Starting MOEX News Parser...")
    print(f"Target page: https://www.moex.com/ru/news/")
    
    parser = MOEXParser()
    
    all_news = parser.get_all_news(limit=5)
    
    print(f"\n{'='*50}")
    print(f"MOEX NEWS COLLECTION COMPLETE")
    print(f"{'='*50}")
    print(f"Total news collected: {len(all_news)}")
    
    print(f"\nSample MOEX news:")
    for i, news in enumerate(all_news, 1):
        print(f"\n{i}. {news['title'][:60]}...")
        print(f"   Date: {news.get('date', 'N/A')}")
        print(f"   Content: {news['content_length']} chars") 
        print(f"   Tags: {', '.join(news.get('tags', []))}")
        print(f"   URL: {news['url']}")
    
    if all_news:
        # Основной файл с новостями
        with open('moex_news.json', 'w', encoding='utf-8') as f:
            json.dump(all_news, f, ensure_ascii=False, indent=2)
        
        summary = {
            'collection_date': datetime.now().isoformat(),
            'total_news': len(all_news),
            'source_url': 'https://www.moex.com/ru/news/',
            'sample_titles': [news['title'] for news in all_news[:5]]
        }
        
        with open('moex_summary.json', 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        
        print(f"\nFiles saved:")
        print(f"  - moex_news.json: {len(all_news)} news articles")
        print(f"  - moex_summary.json: collection summary")
    
    return all_news

if __name__ == "__main__":
    main()