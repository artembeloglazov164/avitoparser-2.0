import logging
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from config import Config
from database.db_manager import DatabaseManager
from parsers.avito_parser import AvitoParser

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# Инициализация менеджеров
db_manager = DatabaseManager(Config.DATABASE_PATH)

@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    """Поиск объявлений"""
    query = request.form.get('query', '').strip()
    
    if not query:
        flash('Введите поисковый запрос', 'error')
        return redirect(url_for('index'))
    
    if len(query) < 2:
        flash('Запрос должен содержать минимум 2 символа', 'error')
        return redirect(url_for('index'))
    
    # Сохраняем сессию
    session['current_query'] = query
    
    # Определяем количество страниц
    parser = AvitoParser(Config)
    try:
        total_pages = parser.get_total_pages(query)
        parser.close()
        
        if total_pages == 0:
            flash('По вашему запросу ничего не найдено', 'warning')
            return redirect(url_for('index'))
        
        session['total_pages'] = total_pages
        return render_template('search_settings.html', 
                             query=query, 
                             total_pages=total_pages,
                             max_pages=Config.MAX_PAGES)
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        flash('Ошибка при поиске. Попробуйте позже.', 'error')
        return redirect(url_for('index'))

@app.route('/parse', methods=['POST'])
def parse():
    """Запуск парсинга"""
    if 'current_query' not in session:
        flash('Сначала выполните поиск', 'error')
        return redirect(url_for('index'))
    
    query = session['current_query']
    
    try:
        pages_to_parse = int(request.form.get('pages', 1))
        total_pages = session.get('total_pages', 1)
        pages_to_parse = min(pages_to_parse, total_pages, Config.MAX_PAGES)
        
        if pages_to_parse <= 0:
            flash('Введите корректное количество страниц', 'error')
            return redirect(url_for('index'))
            
    except ValueError:
        flash('Введите число от 1 до 10', 'error')
        return redirect(url_for('index'))
    
    # Очищаем предыдущие данные
    db_manager.clear_old_data()
    
    # Запускаем парсинг
    parser = AvitoParser(Config)
    try:
        all_items = parser.parse_multiple_pages(query, pages_to_parse)
        parser.close()
        
        if not all_items:
            flash('Не удалось получить данные. Попробуйте позже.', 'error')
            return redirect(url_for('index'))
        
        # Сохраняем в базу
        search_id = db_manager.save_search(query, pages_to_parse, len(all_items))
        db_manager.save_items(search_id, all_items)
        
        session['current_search_id'] = search_id
        flash(f'Найдено {len(all_items)} объявлений', 'success')
        return redirect(url_for('results'))
        
    except Exception as e:
        logger.error(f"Parsing error: {e}")
        flash('Ошибка при парсинге. Попробуйте позже.', 'error')
        return redirect(url_for('index'))

@app.route('/results')
def results():
    """Страница с результатами"""
    search_id = session.get('current_search_id')
    if not search_id:
        flash('Сначала выполните поиск', 'error')
        return redirect(url_for('index'))
    
    items = db_manager.get_items_by_search(search_id)
    
    # Форматируем цены
    formatted_items = []
    for item in items:
        formatted_items.append({
            'id': item['id'],
            'title': item['title'],
            'price': f"{item['price']:,}".replace(',', ' ') if item['price'] > 0 else "Цена не указана",
            'city': item['city'],
            'description': item['description'],
            'url': item['url'],
            'image_url': item['image_url']
        })
    
    return render_template('results.html', items=formatted_items)

@app.route('/history')
def history():
    """История поиска"""
    searches = db_manager.get_search_history()
    return render_template('history.html', searches=searches)

if __name__ == '__main__':
    # Создаем необходимые папки
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/css', exist_ok=True)
    os.makedirs('database', exist_ok=True)
    os.makedirs('parsers', exist_ok=True)
    
    print("=" * 50)
    print("Avito Parser (Firefox) запущен!")
    print("Доступно по адресу: http://127.0.0.1:5000")
    print("=" * 50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
