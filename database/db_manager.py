import sqlite3
import logging
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()
    
    def init_db(self):
        with self.get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS searches (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT NOT NULL,
                    total_pages INTEGER DEFAULT 0,
                    total_items INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    search_id INTEGER,
                    title TEXT NOT NULL,
                    price INTEGER,
                    city TEXT,
                    description TEXT,
                    url TEXT NOT NULL,
                    image_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (search_id) REFERENCES searches (id)
                )
            ''')
    
    def save_search(self, query, total_pages=0, total_items=0):
        with self.get_connection() as conn:
            cursor = conn.execute(
                'INSERT INTO searches (query, total_pages, total_items) VALUES (?, ?, ?)',
                (query, total_pages, total_items)
            )
            return cursor.lastrowid
    
    def save_items(self, search_id, items):
        with self.get_connection() as conn:
            for item in items:
                conn.execute('''
                    INSERT INTO items (search_id, title, price, city, description, url, image_url)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    search_id, item['title'], item['price'], 
                    item['city'], item.get('description', ''),
                    item['url'], item.get('image_url', '')
                ))
    
    def get_search_history(self, limit=10):
        with self.get_connection() as conn:
            return conn.execute('''
                SELECT * FROM searches 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (limit,)).fetchall()
    
    def get_items_by_search(self, search_id):
        with self.get_connection() as conn:
            return conn.execute('''
                SELECT * FROM items 
                WHERE search_id = ? 
                ORDER BY price DESC
            ''', (search_id,)).fetchall()
    
    def clear_old_data(self):
        """Очистка предыдущих результатов"""
        with self.get_connection() as conn:
            conn.execute('DELETE FROM items')
