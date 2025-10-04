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

class EDisclosureMessagesParser:
    def __init__(self, headless=False):
        self.driver = None
        self.headless = headless
        self.messages_data = []
        self.search_initiated = False
        
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
            print(f"Ошибка создания драйвера: {e}")
            return False
    
    def initiate_search(self):
        try:
            print("Инициируем поиск сообщений...")
            
            self.driver.get("https://www.e-disclosure.ru/poisk-po-soobshheniyam")
            time.sleep(3)
            
            if "servicepipe" in self.driver.page_source.lower():
                print("ServicePipe блокирует")
                return False
            
            try:
                search_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.ID, "sendButton"))
                )
                
                print("Нажимаем кнопку 'Искать'...")
                self.driver.execute_script("arguments[0].click();", search_button)
                
                time.sleep(5)
                
                print("Поиск инициирован, результаты загружены")
                self.search_initiated = True
                return True
                
            except TimeoutException:
                print("Не найдена кнопка 'Искать'")
                return False
                
        except Exception as e:
            print(f"Ошибка инициации поиска: {e}")
            return False
    
    def navigate_to_page(self, page_num):
        """Переходим на указанную страницу через клик по пагинации"""
        try:
            if page_num == 1:
                return True
            
            try:
                paging_div = self.driver.find_element(By.CSS_SELECTOR, ".paging")
                page_links = paging_div.find_elements(By.CSS_SELECTOR, "a.page")
                
                for link in page_links:
                    data_page = link.get_attribute("data-link-page")
                    if data_page and int(data_page) == page_num:
                        print(f"🖱️ Кликаем на страницу {page_num}")
                        self.driver.execute_script("arguments[0].click();", link)
                        time.sleep(3)  # Ждем загрузки после клика
                        return True
                
                print(f"Не найдена кнопка для страницы {page_num}")
                return False
            except:
                print(f"Пагинация не найдена - возможно только одна страница")
                return False
            
        except Exception as e:
            print(f"Ошибка навигации на страницу {page_num}: {e}")
            return False
    
    def parse_messages_page(self, page_num=1):
        try:
            print(f"Парсим страницу сообщений {page_num}")
            
            if page_num == 1 and not self.search_initiated:
                if not self.initiate_search():
                    return False
            else:
                if not self.navigate_to_page(page_num):
                    return False
            
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table"))
                )
                
                tables = self.driver.find_elements(By.CSS_SELECTOR, "table")
                print(f"Найдено таблиц: {len(tables)}")
                
                target_table = None
                rows = []
                
                for i, table in enumerate(tables):
                    tbody = table.find_elements(By.CSS_SELECTOR, "tbody")
                    if tbody:
                        table_rows = tbody[0].find_elements(By.TAG_NAME, "tr")
                        if len(table_rows) > 0:
                            first_row = table_rows[0]
                            cells = first_row.find_elements(By.TAG_NAME, "td")
                            if len(cells) >= 2:
                                cell_text = cells[0].text.strip()
                                if cell_text and len(cell_text) > 5:  # Проверяем что есть реальные данные
                                    target_table = table
                                    rows = table_rows
                                    print(f"Найдена таблица с данными (таблица {i}): {len(rows)} строк")
                                    break
                
                if not target_table:
                    print("Не найдена таблица с данными")
                    return False
                
                page_messages = []
                for i, row in enumerate(rows):
                    try:
                        message_item = self.extract_message_item(row, i)
                        if message_item:
                            page_messages.append(message_item)
                    except Exception as e:
                        print(f"Ошибка извлечения сообщения {i}: {e}")
                        continue
                
                print(f"Извлечено сообщений на странице {page_num}: {len(page_messages)}")
                self.messages_data.extend(page_messages)
                return len(page_messages) > 0
                
            except TimeoutException:
                print("Таймаут ожидания таблицы")
                return False
                
        except Exception as e:
            print(f"Ошибка парсинга страницы {page_num}: {e}")
            return False
    
    def extract_message_item(self, row, row_index):
        try:
            cells = row.find_elements(By.TAG_NAME, "td")
            
            if len(cells) < 2:  # Минимум 2 ячейки для сообщений
                return None
            
            datetime_text = cells[0].text.strip()
            company_event_text = cells[1].text.strip()
            
            if not datetime_text or not company_event_text:
                return None
            
            date_part = None
            time_part = None
            if datetime_text:
                # Формат: "03.10.2025 19:55"
                parts = datetime_text.split(' ')
                if len(parts) >= 2:
                    date_part = parts[0]
                    time_part = parts[1]
                else:
                    date_part = datetime_text
            
            company_name = None
            event_description = None
            if company_event_text:
                lines = company_event_text.split('\n')
                if len(lines) >= 2:
                    company_name = lines[0].strip()
                    event_description = lines[1].strip()
                else:
                    company_name = company_event_text
            
            links = []
            link_elements = row.find_elements(By.TAG_NAME, "a")
            for link in link_elements:
                href = link.get_attribute("href")
                text = link.text.strip()
                if href and text:
                    links.append({
                        'url': href,
                        'text': text
                    })
            
            message_data = {
                'date': date_part,
                'time': time_part,
                'datetime': datetime_text,
                'company': company_name,
                'event_description': event_description,
                'full_text': company_event_text,
                'links': links if links else None,
                'row_index': row_index,
                'parsed_at': datetime.now().isoformat(),
                'columns_count': len(cells)
            }
            
            return message_data
            
        except Exception as e:
            print(f"Ошибка извлечения данных из строки {row_index}: {e}")
            return None
    
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
            print(f"Ошибка проверки пагинации: {e}")
            return False
    
    def extract_event_id_from_url(self, url):
        try:
            match = re.search(r'EventId=([^&]+)', url)
            if match:
                return match.group(1)
            return None
        except Exception as e:
            print(f"Ошибка извлечения EventId: {e}")
            return None

    def extract_full_content(self, event_url):
        try:
            print(f"Переходим к полному содержимому: {event_url[:60]}...")
            
            self.driver.get(event_url)
            time.sleep(3)
            
            if "servicepipe" in self.driver.page_source.lower():
                print("ServicePipe блокирует доступ к EventId")
                return None
            
            try:
                content_div = WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((
                        By.CSS_SELECTOR, 
                        'div[style*="word-break: break-word"][style*="word-wrap: break-word"][style*="white-space: pre-wrap"]'
                    ))
                )
                
                full_content = content_div.text.strip()
                
                if full_content:
                    print(f"Извлечено содержимое: {len(full_content)} символов")
                    return {
                        'full_content': full_content,
                        'content_length': len(full_content),
                        'extraction_success': True
                    }
                else:
                    print("Содержимое пустое")
                    return {'extraction_success': False, 'error': 'empty_content'}
                    
            except TimeoutException:
                print("Таймаут поиска блока содержимого")
                
                try:
                    content_divs = self.driver.find_elements(By.CSS_SELECTOR, 'div[style*="pre-wrap"]')
                    
                    for div in content_divs:
                        content = div.text.strip()
                        if content and len(content) > 50:  # Минимальная длина для значимого содержимого
                            print(f"Найдено содержимое альтернативным способом: {len(content)} символов")
                            return {
                                'full_content': content,
                                'content_length': len(content),
                                'extraction_success': True,
                                'extraction_method': 'alternative'
                            }
                    
                    print("Не найден блок с содержимым")
                    return {'extraction_success': False, 'error': 'content_not_found'}
                    
                except Exception as e:
                    print(f"Ошибка альтернативного поиска: {e}")
                    return {'extraction_success': False, 'error': str(e)}
                    
        except Exception as e:
            print(f"Ошибка извлечения полного содержимого: {e}")
            return {'extraction_success': False, 'error': str(e)}

    def enhance_messages_with_content(self):
        if not self.messages_data:
            print("Нет сообщений для дополнения")
            return
        
        print(f"Дополняем {len(self.messages_data)} сообщений полным содержимым...")
        
        enhanced_count = 0
        failed_count = 0
        
        for i, message in enumerate(self.messages_data):
            try:
                print(f"\nОбрабатываем сообщение {i+1}/{len(self.messages_data)}")
                
                event_url = None
                if message.get('links'):
                    for link in message['links']:
                        if 'EventId=' in link.get('url', ''):
                            event_url = link['url']
                            break
                
                if not event_url:
                    print(" Не найдена ссылка с EventId")
                    message['content_enhancement'] = {'success': False, 'error': 'no_event_url'}
                    failed_count += 1
                    continue
                
                event_id = self.extract_event_id_from_url(event_url)
                message['event_id'] = event_id
                
                content_data = self.extract_full_content(event_url)
                
                if content_data and content_data.get('extraction_success'):
                    message.update(content_data)
                    enhanced_count += 1
                    print(f"Сообщение {i+1} дополнено содержимым")
                else:
                    message['content_enhancement'] = content_data
                    failed_count += 1
                    print(f" Не удалось дополнить сообщение {i+1}")
                
                time.sleep(2)
                
            except Exception as e:
                print(f" Ошибка обработки сообщения {i+1}: {e}")
                message['content_enhancement'] = {'success': False, 'error': str(e)}
                failed_count += 1
                continue
        
        print(f"\n Дополнение завершено:")
        print(f" Успешно дополнено: {enhanced_count}")
        print(f" Не удалось дополнить: {failed_count}")
        print(f" Процент успеха: {enhanced_count/len(self.messages_data)*100:.1f}%")
    
    def parse_all_messages(self, max_pages=5, enhance_with_content=True):
        print(f" Начинаем парсинг сообщений (макс. {max_pages} страниц)")
        
        if not self.create_driver():
            return False
        
        try:
            page = 1
            success = self.parse_messages_page(page)
            
            if not success:
                print(f" Не удалось спарсить первую страницу")
                return False
            
            page = 2
            while page <= max_pages:
                if not self.check_next_page_available(page):
                    print(f"📄 Достигнута последняя страница: {page-1}")
                    break
                
                success = self.parse_messages_page(page)
                
                if not success:
                    print(f" Не удалось спарсить страницу {page}")
                    break
                
                page += 1
                time.sleep(2)  # Пауза между страницами
            
            print(f" Базовый парсинг завершен. Всего сообщений: {len(self.messages_data)}")
            
            if enhance_with_content and self.messages_data:
                print(f"\n Переходим к извлечению полного содержимого...")
                self.enhance_messages_with_content()
            
            return True
            
        except Exception as e:
            print(f" Ошибка парсинга: {e}")
            return False
        finally:
            if self.driver:
                self.driver.quit()
    
    def save_data(self, filename_prefix="edisclosure_messages"):
        """Сохраняем данные в JSON и CSV"""
        if not self.messages_data:
            print(" Нет данных для сохранения")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        json_filename = f"{filename_prefix}_{timestamp}.json"
        with open(json_filename, 'w', encoding='utf-8') as f:
            json.dump(self.messages_data, f, ensure_ascii=False, indent=2)
        print(f" Сохранено в JSON: {json_filename}")
        
        if self.messages_data:
            csv_filename = f"{filename_prefix}_{timestamp}.csv"
            
            all_keys = set()
            for item in self.messages_data:
                all_keys.update(item.keys())
            
            csv_keys = [key for key in all_keys if not isinstance(self.messages_data[0].get(key), (list, dict))]
            
            with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=csv_keys, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(self.messages_data)
            print(f" Сохранено в CSV: {csv_filename}")

def main():
    """Основная функция"""
    print(" E-disclosure.ru Enhanced Messages Parser")
    print("=" * 60)
    
    parser = EDisclosureMessagesParser(headless=False)  # Видимый режим для отладки
    
    success = parser.parse_all_messages(max_pages=2, enhance_with_content=True)
    
    if success:
        parser.save_data("edisclosure_messages_enhanced")
        
        total_messages = len(parser.messages_data)
        enhanced_messages = sum(1 for msg in parser.messages_data if msg.get('extraction_success'))
        
        print(f"\n Расширенный парсинг завершен!")
        print(f" Всего сообщений: {total_messages}")
        print(f" С полным содержимым: {enhanced_messages}")
        if total_messages > 0:
            print(f" Успешность дополнения: {enhanced_messages/total_messages*100:.1f}%")
        
        if enhanced_messages > 0:
            total_content = sum(msg.get('content_length', 0) for msg in parser.messages_data if msg.get('extraction_success'))
            avg_content = total_content / enhanced_messages
            print(f" Общий объем содержимого: {total_content:,} символов")
            print(f" Средняя длина содержимого: {avg_content:.0f} символов")
    else:
        print(" Расширенный парсинг не удался")

if __name__ == "__main__":
    main()