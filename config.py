import os
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

class Config:
    """アプリケーション設定クラス"""
    
    # 基本設定
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Wikipedia API設定
    WIKI_API_URL = os.environ.get('WIKI_API_URL', 'https://ja.wikipedia.org/w/api.php')
    USER_AGENT = os.environ.get('USER_AGENT', 'WikiSixBot/1.0 (https://example.com)')
    
    # アプリケーションURL設定
    BASE_URL = os.environ.get('BASE_URL', 'http://localhost:5000')
    
    # レート制限設定
    RATELIMIT_STORAGE_URL = os.environ.get('RATELIMIT_STORAGE_URL', 'memory://')
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '200 per day, 50 per hour')
    
    # セキュリティヘッダー設定
    SECURE_HEADERS = os.environ.get('SECURE_HEADERS', 'True').lower() == 'true'
    HSTS_MAX_AGE = int(os.environ.get('HSTS_MAX_AGE', '31536000'))
    
    # ゲーム設定
    TARGET_TITLE = "ネコ"
    INITIAL_CLICKS = 6
    
    # HTML最適化設定
    ENABLE_HTML_OPTIMIZATION = os.environ.get('ENABLE_HTML_OPTIMIZATION', 'True').lower() == 'true'
    ENABLE_HTML_COMPRESSION = os.environ.get('ENABLE_HTML_COMPRESSION', 'True').lower() == 'true'
    REMOVE_EXTERNAL_LINKS = os.environ.get('REMOVE_EXTERNAL_LINKS', 'True').lower() == 'true'
    
    # 除外するリンクのプレフィックスリスト
    EXCLUDED_PREFIXES = [
        '/wiki/Special:',
        '/wiki/Help:',
        '/wiki/Category:',
        '/wiki/File:',
        '/wiki/Template:',
        '/wiki/Template_talk:',
        '/wiki/Portal:',
        '/wiki/Book:',
        '/wiki/Draft:',
        '/wiki/Education_Program:',
        '/wiki/TimedText:',
        '/wiki/Wikipedia:',
        '/wiki/MediaWiki:',
        '/wiki/Module:',
        '/wiki/Gadget:',
        '/wiki/Topic:'
    ]

class ProductionConfig(Config):
    """本番環境用設定"""
    DEBUG = False
    SECURE_HEADERS = True

class DevelopmentConfig(Config):
    """開発環境用設定"""
    DEBUG = True
    SECURE_HEADERS = False

# 設定の選択
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
