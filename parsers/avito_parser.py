import re
import time
import logging
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

class AvitoParser:
    def __init__(self, config):
        self.config = config
        self.driver = None
        self.setup_driver()
    
    def setup_driver(self):
        """Настройка Firefox драйвера"""
        try:
            firefox_options = Options()
            for option in self.config.FIREFOX_OPTIONS:
                firefox_options.add_argument(option)
            
            service = Service(GeckoDriverManager().install())
            self.driver = webdriver.Firefox(service=service, options=firefox_options)
            self.driver.implicitly_wait(10)
            logger.info("Firefox WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firefox WebDriver: {e}")
            raise
    
    def get_total_pages(self, query, location="rossiya"):
        """Получение количества страниц"""
        try:
            url = f"https://www.avito.ru/{location}?q={query}"
            logger.info(f"Checking pages for: {query}")
            
            self.driver.get(url)
            
            # Увеличиваем время ожидания и используем более надежные селекторы
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-marker='item'], .iva-item-root"))
            )
            
            time.sleep(2)  # Дополнительная задержка
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            
            # Проверяем есть ли результаты
            no_results = soup.find('div', class_=re.compile('emptySuggestion'))
            if no_results:
                logger.info("No results found")
                return 0
            
            # Ищем пагинацию - исправленный селектор
            pagination = soup.find('div', {'data-marker': 'pagination'})
            if pagination:
                page_links = pagination.find_all('a', {'data-marker': re.compile('pagination-button')})
                if page_links:
                    page_numbers = []
                    for link in page_links:
                        try:
                            page_num = int(link.text.strip())
                            page_numbers.append(page_num)
                        except ValueError:
                            continue
                    
                    if page_numbers:
                        total_pages = max(page_numbers)
                        return min(total_pages, self.config.MAX_PAGES)
            
            # Если пагинации нет, но есть товары
            items = soup.find_all('div', {'data-marker': 'item'})
            return 1 if items else 0
            
        except Exception as e:
            logger.error(f"Error getting total pages: {e}")
            return 1
    
    def parse_page(self, query, page_num, location="rossiya"):
        """Парсинг одной страницы"""
        try:
            url = f"https://www.avito.ru/{location}?p={page_num}&q={query}"
            logger.info(f"Parsing page {page_num}")
            
            self.driver.get(url)
            
            # Увеличиваем время ожидания
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "[data-marker='item']"))
            )
            
            time.sleep(2)  # Увеличиваем задержку
            
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            items = soup.find_all('div', {'data-marker': 'item'})
            
            parsed_items = []
            base_url = 'https://www.avito.ru'
            
            logger.info(f"Found {len(items)} items on page {page_num}")
            
            for item in items:
                try:
                    item_data = self._parse_item(item, base_url)
                    if item_data:
                        parsed_items.append(item_data)
                except Exception as e:
                    logger.warning(f"Error parsing item: {e}")
                    continue
            
            return parsed_items
            
        except Exception as e:
            logger.error(f"Error parsing page {page_num}: {e}")
            return []
    
    def _parse_item(self, item, base_url):
        """Парсинг одного объявления - исправленная версия"""
        try:
            # Заголовок - исправленный поиск
            title_elem = item.find('h3', {'itemprop': 'name'}) or item.find('a', {'data-marker': 'item-title'})
            if not title_elem:
                return None
            
            title = title_elem.text.strip()
            
            # Цена - улучшенный поиск
            price = 0
            price_elem = item.find('meta', {'itemprop': 'price'})
            if price_elem and price_elem.get('content'):
                price = int(price_elem.get('content'))
            else:
                # Альтернативный поиск цены
                price_selector = item.find('span', {'data-marker': 'item-price'}) or item.find('p', {'data-marker': 'item-price'})
                if price_selector:
                    price_text = price_selector.text.strip()
                    if price_text:
                        # Более надежное извлечение чисел из цены
                        price_clean = re.sub(r'[^\d]', '', price_text)
                        if price_clean:
                            price = int(price_clean)
            
            # Ссылка
            link_elem = item.find('a', {'data-marker': 'item-title'}) or item.find('a', {'itemprop': 'url'})
            if not link_elem:
                return None
            
            url_path = link_elem.get('href', '')
            url = base_url + url_path if url_path.startswith('/') else url_path
            
            # Город - улучшенный поиск
            city = "Не указан"
            location_elem = item.find('div', {'data-marker': 'item-location'}) or item.find('span', class_=re.compile('geo-root'))
            if location_elem:
                city_text = location_elem.text.strip()
                if city_text:
                    city = city_text.split(',')[0].strip()
            
            # Описание
            description = ""
            desc_elem = item.find('div', class_=re.compile('iva-item-description'))
            if desc_elem:
                description = desc_elem.text.strip()
            
            # Изображение
            image_url = ""
            img_elem = item.find('img', {'data-marker': 'item-image'}) or item.find('img', {'itemprop': 'image'})
            if img_elem and img_elem.get('src'):
                image_url = img_elem.get('src')
            
            return {
                'title': title,
                'price': price,
                'city': city,
                'description': description,
                'url': url,
                'image_url': image_url
            }
            
        except Exception as e:
            logger.warning(f"Error in _parse_item: {e}")
            return None
    
    def parse_multiple_pages(self, query, pages_to_parse, location="rossiya"):
        """Парсинг нескольких страниц"""
        all_items = []
        
        for page in range(1, pages_to_parse + 1):
            logger.info(f"Parsing page {page} of {pages_to_parse}")
            items = self.parse_page(query, page, location)
            all_items.extend(items)
            
            if page < pages_to_parse:
                time.sleep(self.config.REQUEST_DELAY)
        
        logger.info(f"Total items parsed: {len(all_items)}")
        return all_items
    
    def close(self):
        """Закрытие драйвера"""
        if self.driver:
            self.driver.quit()
            logger.info("Firefox WebDriver closed")
