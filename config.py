import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'secret_key'
    DATABASE_PATH = 'avito_parser.db'
    MAX_PAGES = 5
    REQUEST_DELAY = 2
    BROWSER = 'firefox'  # Используем Firefox
    FIREFOX_OPTIONS = [
        '--headless',
        '--no-sandbox',
        '--disable-dev-shm-usage'
    ]
