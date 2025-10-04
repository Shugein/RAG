
"""
- Сбор новостей по категориям: business, world, russia, culture, а также общий поток (all)
- Фильтрация по дате (диапазон дат)
- Пагинация страниц за день: /all/page_2, /all/page_3, ...
- Извлечение полного контента статьи, тегов, сущностей и даты публикации
- Сохранение в JSON в папку data/

- Все новости: https://www.interfax.ru/news/YYYY/MM/DD
- Пагинация всех новостей: https://www.interfax.ru/news/YYYY/MM/DD/all/page_2
- Категория business: https://www.interfax.ru/business/news/YYYY/MM/DD

  python 1_lap_parser/interfax_universal_collector.py --start 2025-10-01 --end 2025-10-31 --categories all,business,world,russia,culture --max-pages 10 --max-articles 0

"""

import argparse
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, Iterable, List, Optional, Set, Tuple

import requests
from bs4 import BeautifulSoup


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
LOGS_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOGS_DIR, 'interfax_universal_collector.log'), encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


SUPPORTED_CATEGORIES = {"business", "world", "russia", "culture", "all"}


@dataclass
class NewsItem:
    url: str
    title: str
    category: str
    day: str  # YYYY-MM-DD
    publish_date: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    tags: List[str] = None
    entities: List[str] = None
    hash: Optional[str] = None
    collected_at: Optional[str] = None
    content_length: int = 0

    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.entities is None:
            self.entities = []
        if self.hash is None:
            base = f"{self.url}|{self.category}|{self.day}"
            self.hash = hashlib.md5(base.encode("utf-8")).hexdigest()
        if self.collected_at is None:
            self.collected_at = datetime.now().isoformat()
        if self.content:
            self.content_length = len(self.content)
            if not self.summary:
                self.summary = self.content[:500] + ("..." if len(self.content) > 500 else "")


class InterfaxUniversalCollector:
    BASE = "https://www.interfax.ru"

    def __init__(self, max_pages: int = 15, max_articles: int = 0, delay: float = 0.4):

        self.max_pages = max_pages
        self.max_articles = max_articles
        self.delay = delay
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        })

    def day_list_url(self, category: str, day: datetime) -> str:
        y, m, d = day.strftime('%Y'), day.strftime('%m'), day.strftime('%d')
        if category == "all":
            return f"{self.BASE}/news/{y}/{m}/{d}"
        else:
            return f"{self.BASE}/{category}/news/{y}/{m}/{d}"

    def day_list_page_url(self, category: str, day: datetime, page: int) -> str:
        # Сохранено для обратной совместимости — возвращает вариант с '/all/page_N'
        base = self.day_list_url(category, day)
        if page <= 1:
            return base
        return base.rstrip('/') + f"/all/page_{page}"

    # ---------- Listing parsing ----------
    def collect_day_links(self, category: str, day: datetime, max_pages: Optional[int] = None) -> List[Tuple[str, str]]:
        page = 1
        found: Dict[str, str] = {}
        limit_pages = max_pages if max_pages is not None else self.max_pages
        hard_limit = 50  # safety

        while True:
            if limit_pages and page > limit_pages:
                break
            if page > hard_limit:
                logger.warning("Превышен жёсткий лимит страниц (50) — остановка пагинации")
                break

            urls_to_try: List[str] = []
            if page == 1:
                urls_to_try = [self.day_list_page_url(category, day, page)]
            else:
                base = self.day_list_url(category, day).rstrip('/')
                urls_to_try = [
                    base + f"/all/page_{page}",
                    base + f"/page_{page}",
                ]

            page_ok = False
            links: List[Tuple[str, str]] = []
            last_status: Optional[int] = None
            for url in urls_to_try:
                try:
                    resp = self.session.get(url, timeout=20)
                except Exception as e:
                    logger.warning(f"Сбой запроса списка: {url} -> {e}")
                    continue

                last_status = resp.status_code
                if resp.status_code != 200:
                    continue

                if resp.encoding == 'ISO-8859-1':
                    resp.encoding = 'windows-1251'

                soup = BeautifulSoup(resp.text, 'html.parser')
                links = self._extract_article_links_from_listing(soup)
                if links:
                    page_ok = True
                    break

            if not page_ok:
                msg = f"Нет страницы или ссылок: page {page} (последний статус: {last_status})"
                logger.info(msg)
                break

            new_count = 0
            for href, title in links:
                full = self._full_url(href)
                if full not in found:
                    found[full] = title
                    new_count += 1

            logger.info(f"[{category}:{day.date()}] стр.{page}: найдено {len(links)}, новых {new_count}, всего {len(found)}")

            page += 1
            time.sleep(self.delay)

        return [(u, t) for u, t in found.items()]

    def _extract_article_links_from_listing(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        results: List[Tuple[str, str]] = []
        anchors = soup.find_all('a', href=True)
        for a in anchors:
            href = a['href']
            if not href:
                continue
            if re.search(r'^/(?:business|world|russia|culture)/\d+(?:[/?#].*)?$', href):
                title = a.get_text(strip=True) or "Без заголовка"
                results.append((href, title))
        return results

    def _full_url(self, href: str) -> str:
        if href.startswith('http://') or href.startswith('https://'):
            return href
        if not href.startswith('/'):
            href = '/' + href
        return f"{self.BASE}{href}"

    def fetch_article(self, url: str, fallback_title: str = "Без заголовка") -> Tuple[Optional[str], Optional[str], List[str]]:
        try:
            resp = self.session.get(url, timeout=25)
        except Exception as e:
            logger.warning(f"Ошибка запроса статьи: {url} -> {e}")
            return None, None, []

        if resp.status_code != 200:
            logger.info(f"HTTP {resp.status_code} для {url}")
            return None, None, []

        if resp.encoding == 'ISO-8859-1':
            resp.encoding = 'windows-1251'

        soup = BeautifulSoup(resp.text, 'html.parser')

        h1 = soup.find('h1')
        title = h1.get_text(strip=True) if h1 else fallback_title

        # Контент
        content = self._extract_best_content(soup)

        # Теги
        tags = self._extract_all_tags(soup)

        return title, content, tags

    def _extract_best_content(self, soup: BeautifulSoup) -> Optional[str]:
        article = soup.find('article')
        if article:
            for tag in article.find_all(['script', 'style', 'noscript', 'aside']):
                tag.decompose()
            text = article.get_text(separator='\n', strip=True)
            if len(text) > 120:
                return self._clean_content(text)

        paragraphs = []
        for p in soup.find_all('p'):
            t = p.get_text(strip=True)
            if len(t) > 25 and not any(x in t.lower() for x in [
                'читайте также', 'подписаться', 'материалы по теме', 'реклама', '©', 'загрузить еще', 'выбрать дату'
            ]):
                paragraphs.append(t)
        if paragraphs:
            content = '\n\n'.join(paragraphs)
            if len(content) > 120:
                return self._clean_content(content)
        return None

    def _clean_content(self, text: str) -> str:
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        lines = [ln.strip() for ln in text.split('\n')]
        cleaned: List[str] = []
        for ln in lines:
            if len(ln) > 10 and not any(x in ln.lower() for x in [
                'загрузить еще', 'подписаться на новости', 'самое читаемое', 'фотогалереи', 'выбор редакции'
            ]):
                cleaned.append(ln)
        return '\n'.join(cleaned)

    def _extract_all_tags(self, soup: BeautifulSoup) -> List[str]:
        tags: Set[str] = set()
        selectors = [
            '.tags a', '.article-tags a', '[rel="tag"]',
            'a[href*="/tags/"]', 'a[href*="/company/"]',
            '.related a', '.keywords a'
        ]
        for css in selectors:
            for el in soup.select(css):
                t = el.get_text(strip=True)
                if t and 2 <= len(t) <= 50:
                    tags.add(t)
        return list(tags)[:25]

    def _extract_best_datetime(self, soup: BeautifulSoup, html_text: str, time_hint: Optional[str] = None) -> Optional[str]:
        if time_hint:
            return time_hint
        for time_elem in soup.find_all('time'):
            dt = time_elem.get('datetime')
            if dt:
                return dt
        patterns = [
            r'(\d{2}:\d{2}),?\s*(\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4})',
            r'\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}',
        ]
        for pat in patterns:
            m = re.search(pat, html_text)
            if m:
                return m.group()
        return None

    def _extract_financial_entities(self, text: Optional[str]) -> List[str]:
        if not text:
            return []
        ents: Set[str] = set()
        patterns = [
            r'(?:ПАО|АО|ООО|ОАО|ЗАО)\s+"[^"]{3,40}"',
            r'(?:Сбербанк|Газпром|Роснефт|ВТБ|Лукойл|Новатэк|НЛМК|Северсталь|Ростех|Росатом|МТС)',
            r'(?:ЦБ РФ|Банк России|Минфин|Минэкономразвития|ФНС|Роскомнадзор)',
            r'[А-Я][А-Яёа-яё]{2,15}\s+(?:банк|группа|холдинг|компания|корпорация)',
            r'\d+(?:,\d+)?\s*(?:млрд|млн|тыс\.?)*\s*(?:рублей|долларов|евро)',
            r'(?:доллар США|евро|рубль|юань)',
            r'(?:ключевая ставка|инфляция|ВВП|курс валют|биржа)'
        ]
        for pat in patterns:
            for m in re.findall(pat, text, re.IGNORECASE):
                s = m.strip()
                if len(s) > 2:
                    ents.add(s)
        return list(ents)[:20]

    def collect(self, categories: Iterable[str], start: datetime, end: datetime) -> List[NewsItem]:
        categories = [c.strip().lower() for c in categories]
        for c in categories:
            if c not in SUPPORTED_CATEGORIES:
                raise ValueError(f"Неизвестная категория: {c}. Поддерживаются: {', '.join(sorted(SUPPORTED_CATEGORIES))}")

        day = start
        total_results: List[NewsItem] = []
        seen_urls: Set[str] = set()

        while day <= end:
            for category in categories:
                logger.info(f"=== Сбор {category} за {day.date()} ===")
                links = self.collect_day_links(category, day)
                logger.info(f"Найдено ссылок: {len(links)}")

                for url, fallback_title in links:
                    if self.max_articles and len(total_results) >= self.max_articles:
                        logger.info("Достигнут общий лимит статей — остановка")
                        return total_results
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)

                    title, content, tags = self.fetch_article(url, fallback_title)

                    publish_date = None
                    try:
                        resp = self.session.get(url, timeout=25)
                        if resp.status_code == 200:
                            if resp.encoding == 'ISO-8859-1':
                                resp.encoding = 'windows-1251'
                            soup = BeautifulSoup(resp.text, 'html.parser')
                            publish_date = self._extract_best_datetime(soup, resp.text)
                    except Exception:
                        pass

                    item = NewsItem(
                        url=url,
                        title=title or fallback_title,
                        category=category,
                        day=day.strftime('%Y-%m-%d'),
                        publish_date=publish_date,
                        content=content,
                        tags=tags,
                        entities=self._extract_financial_entities(content)
                    )
                    total_results.append(item)

                    logger.info(f"+ {category} | {item.title[:70]} ({item.content_length} симв.)")
                    time.sleep(self.delay)

            day += timedelta(days=1)

        return total_results

    def save(self, items: List[NewsItem], start: datetime, end: datetime, categories: Iterable[str]) -> str:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        cats = '-'.join(sorted(set([c for c in categories])))
        name = f"interfax_universal_{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}_{cats}_{ts}.json"
        path = os.path.join(DATA_DIR, name)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump([asdict(x) for x in items], f, ensure_ascii=False, indent=2)

        # Короткая статистика
        if items:
            total_content = sum(len(x.content or '') for x in items)
            logger.info("ИТОГО:")
            logger.info(f"  Статей: {len(items)}")
            logger.info(f"  Общий объём текста: {total_content:,} символов")
            logger.info(f"  Средняя длина: {total_content // max(1, len(items)):,} символов")
        logger.info(f"Сохранено: {path}")
        return path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Универсальный сборщик Интерфакс")
    p.add_argument('--start', required=True, help='Дата начала в формате YYYY-MM-DD')
    p.add_argument('--end', required=True, help='Дата окончания в формате YYYY-MM-DD (включительно)')
    p.add_argument('--categories', default='all,business,world,russia,culture', help='Список категорий через запятую')
    p.add_argument('--max-pages', type=int, default=15, help='Лимит страниц пагинации на день (0 = без лимита)')
    p.add_argument('--max-articles', type=int, default=0, help='Общий лимит статей на весь забег (0 = без лимита)')
    p.add_argument('--delay', type=float, default=0.4, help='Задержка между запросами, сек')
    p.add_argument('--allow-future', action='store_true', help='Разрешить сбор будущих дат (по умолчанию — запрещено, конец диапазона будет ограничен сегодняшним днем)')
    return p.parse_args()


def main():
    args = parse_args()
    start = datetime.strptime(args.start, '%Y-%m-%d')
    end = datetime.strptime(args.end, '%Y-%m-%d')

    if not args.allow_future:
        today = datetime.now().date()
        if end.date() > today:
            logger.info(f"Конечная дата {end.date()} в будущем — ограничиваем сегодняшним днем {today}")
            end = datetime.combine(today, datetime.min.time())
    categories = [c.strip() for c in args.categories.split(',') if c.strip()]

    collector = InterfaxUniversalCollector(max_pages=args.max_pages, max_articles=args.max_articles, delay=args.delay)
    logger.info(f"Старт сбора: {start.date()}..{end.date()} | категории: {categories} | max-pages={args.max_pages} | max-articles={args.max_articles}")

    t0 = datetime.now()
    items = collector.collect(categories, start, end)
    t1 = datetime.now()

    path = collector.save(items, start, end, categories)
    logger.info(f"Время выполнения: {(t1 - t0).total_seconds():.1f} сек | сохранено в {path}")
    print(path)


if __name__ == '__main__':
    main()
