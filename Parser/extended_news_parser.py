#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import undetected_chromedriver as uc
import time
import json
import csv
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import re

class ExtendedNewsParser:
    def __init__(self, headless=False):
        self.driver = None
        self.headless = headless
        self.news_data = []
        
    def create_driver(self):
        try:
            options = uc.ChromeOptions()
            
            if self.headless:
                options.add_argument('--headless')
            
            options.add_argument('--no-first-run')
            options.add_argument('--no-service-autorun')
            options.add_argument('--no-default-browser-check')
            options.add_argument('--disable-default-apps')
            options.add_argument('--disable-popup-blocking')
            options.add_argument('--disable-translate')
            options.add_argument('--disable-background-timer-throttling')
            options.add_argument('--disable-renderer-backgrounding')
            options.add_argument('--disable-backgrounding-occluded-windows')
            options.add_argument('--disable-client-side-phishing-detection')
            options.add_argument('--disable-sync')
            options.add_argument('--disable-features=TranslateUI')
            
            self.driver = uc.Chrome(
                options=options,
                version_main=140
            )
            
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.driver.execute_script("Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]})")
            self.driver.execute_script("Object.defineProperty(navigator, 'languages', {get: () => ['ru-RU', 'ru']})")
            
            return True
            
        except Exception as e:
            print(f" Ошибка создания драйвера: {e}")
            return False
    
    def navigate_to_page(self, page_num):
        """Переходим на указанную страницу через клик по пагинации"""
        try:
            if page_num == 1:
                self.driver.get("https://www.e-disclosure.ru/vse-novosti")
                time.sleep(3)
                return True
            
            paging_div = self.driver.find_element(By.CSS_SELECTOR, ".paging")
            page_links = paging_div.find_elements(By.CSS_SELECTOR, "a.page")
            
            for link in page_links:
                data_page = link.get_attribute("data-link-page")
                if data_page and int(data_page) == page_num:
                    print(f" Кликаем на страницу {page_num}")
                    self.driver.execute_script("arguments[0].click();", link)
                    time.sleep(3)  # Ждем загрузки после клика
                    return True
            
            print(f" Не найдена кнопка для страницы {page_num}")
            return False
            
        except Exception as e:
            print(f" Ошибка навигации на страницу {page_num}: {e}")
            return False
    
    def parse_news_page(self, page_num=1):
        """Парсим страницу новостей (только базовая информация)"""
        try:
            print(f" Парсим страницу {page_num}")
            
            if not self.navigate_to_page(page_num):
                return False
            
            # Проверяем защиту
            if "servicepipe" in self.driver.page_source.lower():
                print(" ServicePipe блокирует")
                return False
                
            # Ищем новости
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "newsList"))
                )
                
                news_container = self.driver.find_element(By.ID, "newsList")
                
                time_elements = news_container.find_elements(By.CSS_SELECTOR, ".time")
                listitem_elements = news_container.find_elements(By.CSS_SELECTOR, ".listitem")
                
                print(f"Найдено дат: {len(time_elements)}, новостей: {len(listitem_elements)}")
                
                page_news = []
                for i in range(min(len(time_elements), len(listitem_elements))):
                    try:
                        news_item = self.extract_news_from_elements(time_elements[i], listitem_elements[i])
                        if news_item:
                            page_news.append(news_item)
                    except Exception as e:
                        print(f" Ошибка извлечения новости {i}: {e}")
                        continue
                
                print(f" Извлечено новостей на странице {page_num}: {len(page_news)}")
                self.news_data.extend(page_news)
                return len(page_news) > 0
                
            except TimeoutException:
                print(" Таймаут ожидания контента")
                return False
                
        except Exception as e:
            print(f" Ошибка парсинга страницы {page_num}: {e}")
            return False
    
    def extract_news_from_elements(self, time_element, listitem_element):
        try:
            date_element = time_element.find_element(By.CSS_SELECTOR, ".date")
            date_text = date_element.text.strip()
            
            link_element = listitem_element.find_element(By.CSS_SELECTOR, "a.blacklink")
            news_title = link_element.text.strip()
            news_url = link_element.get_attribute("href")
            
            news_item = {
                'date': date_text,
                'title': news_title,
                'url': news_url,
                'full_url': f"https://www.e-disclosure.ru{news_url}" if news_url.startswith('/') else news_url,
                'content': None,  # Будет заполнено позже
                'content_extracted': False,
                'parsed_at': datetime.now().isoformat()
            }
            
            return news_item
            
        except Exception as e:
            print(f" Ошибка извлечения данных из элементов: {e}")
            return None
    
    def extract_news_content(self, news_item):
        try:
            print(f" Получаем содержание: {news_item['title'][:50]}...")
            
            self.driver.get(news_item['full_url'])
            time.sleep(2)
            
            content_text = ""
            
            content_selectors = [
                ".news-content",
                ".article-content", 
                ".content",
                ".news-text",
                ".article-text",
                "div[class*='content']",
                "div[class*='text']",
                ".main-content p",
                "article p",
                "main p"
            ]
            
            for selector in content_selectors:
                try:
                    content_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if content_elements:
                        texts = []
                        for elem in content_elements:
                            text = elem.text.strip()
                            if text and len(text) > 20:  # Игнорируем слишком короткие тексты
                                texts.append(text)
                        
                        if texts:
                            content_text = "\n\n".join(texts)
                            print(f" Найден контент через селектор: {selector}")
                            break
                            
                except Exception as e:
                    continue
            
            if not content_text:
                try:
                    paragraphs = self.driver.find_elements(By.TAG_NAME, "p")
                    texts = []
                    for p in paragraphs:
                        text = p.text.strip()
                        if len(text) > 50:  # Берем только содержательные параграфы
                            texts.append(text)
                    
                    if texts:
                        content_text = "\n\n".join(texts)
                        print(" Найден контент через параграфы")
                        
                except Exception as e:
                    print(f" Ошибка поиска параграфов: {e}")
            
            news_item['content'] = content_text if content_text else "Содержание не найдено"
            news_item['content_extracted'] = bool(content_text)
            news_item['content_length'] = len(content_text) if content_text else 0
            
            return True
            
        except Exception as e:
            print(f" Ошибка извлечения содержания: {e}")
            news_item['content'] = f"Ошибка извлечения: {str(e)}"
            news_item['content_extracted'] = False
            return False
    
    def check_next_page_available(self, target_page):
        try:
            paging_div = self.driver.find_element(By.CSS_SELECTOR, ".paging")
            page_links = paging_div.find_elements(By.CSS_SELECTOR, "a.page")
            
            for link in page_links:
                page_number = link.get_attribute("data-link-page")
                if page_number and int(page_number) == target_page:
                    return True
                    
            for link in page_links:
                img = link.find_elements(By.CSS_SELECTOR, "img[src*='next.png']")
                if img:
                    return True
                    
            return False
            
        except Exception as e:
            print(f" Ошибка проверки пагинации: {e}")
            return False
    
    def parse_all_news_with_content(self, max_pages=5):
        print(f" Начинаем полный парсинг новостей (макс. {max_pages} страниц)")
        
        if not self.create_driver():
            return False
        
        try:
            print("\n ЭТАП 1: Сбор списка новостей")
            print("-" * 50)
            
            page = 1
            success = self.parse_news_page(page)
            
            if not success:
                print(f" Не удалось спарсить первую страницу")
                return False
            
            page = 2
            while page <= max_pages:
                if not self.check_next_page_available(page):
                    print(f" Достигнута последняя страница: {page-1}")
                    break
                
                success = self.parse_news_page(page)
                
                if not success:
                    print(f" Не удалось спарсить страницу {page}")
                    break
                
                page += 1
                time.sleep(2)  # Пауза между страницами
            
            print(f"\n Собрано новостей: {len(self.news_data)}")
            
            print(f"\n📖 ЭТАП 2: Получение содержания новостей")
            print("-" * 50)
            
            successful_extractions = 0
            failed_extractions = 0
            
            for i, news_item in enumerate(self.news_data, 1):
                print(f"[{i}/{len(self.news_data)}] ", end="")
                
                try:
                    success = self.extract_news_content(news_item)
                    if success and news_item['content_extracted']:
                        successful_extractions += 1
                    else:
                        failed_extractions += 1
                        
                    time.sleep(1)
                    
                except Exception as e:
                    print(f" Ошибка обработки новости {i}: {e}")
                    failed_extractions += 1
                    continue
            
            print(f"\n СТАТИСТИКА ИЗВЛЕЧЕНИЯ СОДЕРЖАНИЯ:")
            print(f" Успешно: {successful_extractions}")
            print(f" Ошибки: {failed_extractions}")
            print(f" Успешность: {successful_extractions/len(self.news_data)*100:.1f}%")
            
            return True
            
        except Exception as e:
            print(f" Ошибка парсинга: {e}")
            return False
        finally:
            if self.driver:
                self.driver.quit()
    
    def save_data(self, filename_prefix="extended_news"):
        """Сохраняем данные в JSON и CSV"""
        if not self.news_data:
            print(" Нет данных для сохранения")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        json_filename = f"{filename_prefix}_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(self.news_data, f, ensure_ascii=False, indent=2)
        print(f" Сохранено в JSON: {json_filename}")
        
        csv_filename = f"{filename_prefix}_{timestamp}.csv"
        if self.news_data:
            with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self.news_data[0].keys())
                writer.writeheader()
                writer.writerows(self.news_data)
            print(f" Сохранено в CSV: {csv_filename}")

def main():
    """Основная функция"""
    print(" E-disclosure.ru Extended News Parser")
    print("=" * 60)
    
    parser = ExtendedNewsParser(headless=False)  # Пока видимый режим
    
    success = parser.parse_all_news_with_content(max_pages=3)  # Начнем с 3 страниц
    
    if success:
        parser.save_data()
        
        # Статистика
        total_news = len(parser.news_data)
        with_content = sum(1 for item in parser.news_data if item['content_extracted'])
        
        print(f"\n Парсинг успешно завершен!")
        print(f" Всего новостей: {total_news}")
        print(f" С содержанием: {with_content}")
        print(f" Полнота данных: {with_content/total_news*100:.1f}%")
    else:
        print(" Парсинг не удался")

if __name__ == "__main__":
    main()