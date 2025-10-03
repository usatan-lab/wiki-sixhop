import os
import requests
from flask import Flask, render_template, redirect, url_for, request, jsonify, make_response
from urllib.parse import unquote
from bs4 import BeautifulSoup, SoupStrainer
from flask.views import MethodView
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
import logging
import time
import re
import html
import threading
import schedule
from functools import lru_cache
from config import config
import hashlib

# 設定の読み込み
config_name = os.environ.get('FLASK_ENV', 'development')
app = Flask(__name__, static_folder='static')
app.config.from_object(config[config_name])

# CSRF保護の有効化
csrf = CSRFProtect(app)

# レート制限の設定
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=[app.config['RATELIMIT_DEFAULT']],
    storage_uri=app.config['RATELIMIT_STORAGE_URL']
)

# ログの設定
logging.basicConfig(
    level=logging.DEBUG if app.config['DEBUG'] else logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# セキュリティヘッダーとキャッシュヘッダーの設定
@app.after_request
def after_request(response):
    # セキュリティヘッダーの設定
    if app.config['SECURE_HEADERS']:
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://ja.wikipedia.org;"
        
        # HTTPS環境でのみHSTSヘッダーを設定
        if request.is_secure:
            response.headers['Strict-Transport-Security'] = f'max-age={app.config["HSTS_MAX_AGE"]}; includeSubDomains'
    
    # 静的ファイルのキャッシュ設定
    if request.endpoint == 'static':
        response.cache_control.max_age = 3600  # 1時間
        response.cache_control.public = True
    # APIエンドポイントのキャッシュ設定
    elif request.endpoint == 'game_data':
        response.cache_control.max_age = 300  # 5分
        response.cache_control.private = True
    
    return response

# 共通の設定
TARGET_TITLE = app.config['TARGET_TITLE']
INITIAL_CLICKS = app.config['INITIAL_CLICKS']
WIKI_API_URL = app.config['WIKI_API_URL']

# セッション設定（接続プールとタイムアウト最適化）
session = requests.Session()
session.headers.update({
    'User-Agent': app.config['USER_AGENT'],
    'Accept': 'application/json',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive'
})

# 接続プールの設定
adapter = requests.adapters.HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=3,
    pool_block=False
)
session.mount('http://', adapter)
session.mount('https://', adapter)

# 除外するリンクのプレフィックスリスト
EXCLUDED_PREFIXES = app.config['EXCLUDED_PREFIXES']

# サーバーサイドキャッシュ
page_cache = {}
links_cache = {}  # 解析済みリンク情報のキャッシュ
CACHE_EXPIRY = 300  # 5分間キャッシュ

# セキュリティ関数
def sanitize_input(text):
    """入力文字列のサニタイゼーション"""
    if not text:
        return ""
    
    # HTMLエスケープ
    text = html.escape(str(text))
    
    # 危険な文字の除去
    text = re.sub(r'[<>"\']', '', text)
    
    # 長さ制限
    if len(text) > 200:
        text = text[:200]
    
    return text.strip()

def validate_page_title(title):
    """ページタイトルの検証"""
    if not title:
        return False
    
    # 基本的な文字チェック
    if not re.match(r'^[a-zA-Z0-9\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF\s\-_\(\)]+$', title):
        return False
    
    # 長さチェック
    if len(title) > 100:
        return False
    
    return True

def log_security_event(event_type, details, ip_address=None):
    """セキュリティイベントのログ記録"""
    if not ip_address:
        ip_address = get_remote_address()
    
    logger.warning(f"SECURITY_EVENT: {event_type} - IP: {ip_address} - Details: {details}")

def get_cache_key(page_title):
    """キャッシュキーを生成"""
    return hashlib.md5(page_title.encode('utf-8')).hexdigest()

def get_cached_page(page_title):
    """キャッシュからページデータを取得"""
    cache_key = get_cache_key(page_title)
    if cache_key in page_cache:
        cached_data, timestamp = page_cache[cache_key]
        if time.time() - timestamp < CACHE_EXPIRY:
            return cached_data
        else:
            # 期限切れのキャッシュを削除
            del page_cache[cache_key]
    return None

def set_cached_page(page_title, data):
    """ページデータをキャッシュに保存"""
    cache_key = get_cache_key(page_title)
    page_cache[cache_key] = (data, time.time())

def get_cached_links(page_title):
    """キャッシュから解析済みリンク情報を取得"""
    cache_key = get_cache_key(page_title)
    if cache_key in links_cache:
        cached_links, timestamp = links_cache[cache_key]
        if time.time() - timestamp < CACHE_EXPIRY:
            return cached_links
        else:
            # 期限切れのキャッシュを削除
            del links_cache[cache_key]
    return None

def set_cached_links(page_title, links_data):
    """解析済みリンク情報をキャッシュに保存"""
    cache_key = get_cache_key(page_title)
    links_cache[cache_key] = (links_data, time.time())

def process_links_in_html(parsed_html, page_title, target_title, clicks_remaining, difficulty, start_time):
    """HTML内のリンクを処理してURLを書き換える"""
    # リンク情報キャッシュをチェック
    cached_links = get_cached_links(page_title)
    if cached_links:
        logger.debug(f"Using cached links for page: {page_title}")
        # キャッシュされたリンク情報を使用してHTMLを再構築
        soup = BeautifulSoup(parsed_html, 'lxml')
        for a in soup.find_all('a', href=True):
            link = a['href']
            if link.startswith('/wiki/'):
                title = link.replace('/wiki/', '')
                title = unquote(title).strip()
                
                # キャッシュされたリンク情報からページタイトルを確認
                if title in cached_links:
                    # 現在のクリック数に基づいてURLを動的生成
                    new_clicks = clicks_remaining - 1
                    
                    if title == target_title:
                        # ターゲットページへのリンクはクリック数に関係なく飛べる
                        a['href'] = url_for('game', page=title, clicks=new_clicks,
                                          mytarget=target_title, difficulty=difficulty,
                                          start_time=start_time)
                    elif new_clicks <= 0:
                        a['href'] = url_for('game_over')
                    else:
                        a['href'] = url_for('game', page=title, clicks=new_clicks,
                                          mytarget=target_title, difficulty=difficulty,
                                          start_time=start_time)
                else:
                    # キャッシュにないリンクは無効化
                    a['href'] = 'javascript:void(0);'
                    a['onclick'] = 'alert("このリンクは使用できません。"); return false;'
                    a['style'] = 'color: #999; cursor: not-allowed;'
        
        return f'<div id="mw-content-text">{str(soup)}</div>'
    
    # キャッシュがない場合は従来通り処理
    soup = BeautifulSoup(parsed_html, 'lxml')
    links_data = {}  # キャッシュ用のリンク情報
    
    for a in soup.find_all('a', href=True):
        link = a['href']
        
        # Wikipedia内のリンクのみを許可
        if not link.startswith('/wiki/'):
            # 外部リンクの場合はクリックを無効化
            a['href'] = 'javascript:void(0);'
            a['onclick'] = 'alert("外部リンクはクリックできません。Wikipedia内のリンクのみ使用できます。"); return false;'
            a['style'] = 'color: #999; cursor: not-allowed; text-decoration: line-through;'
            continue

        # 除外プレフィックスのチェック
        if any(link.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            # 除外されたリンクもクリックを無効化
            a['href'] = 'javascript:void(0);'
            a['onclick'] = 'alert("このリンクは使用できません。"); return false;'
            a['style'] = 'color: #999; cursor: not-allowed; text-decoration: line-through;'
            continue

        title = link.replace('/wiki/', '')
        title = unquote(title).strip()

        # 現在のページへのリンクは無効化
        if title == page_title:
            a['href'] = 'javascript:void(0);'
            a['onclick'] = 'alert("現在のページです。"); return false;'
            a['style'] = 'color: #999; cursor: not-allowed;'
            continue

        new_clicks = clicks_remaining - 1

        if title == target_title:
            # ターゲットページへのリンクはクリック数に関係なく飛べる
            new_url = url_for('game', page=title, clicks=new_clicks,
                            mytarget=target_title, difficulty=difficulty,
                            start_time=start_time)
            a['href'] = new_url
            links_data[title] = new_url
        elif new_clicks <= 0:
            a['href'] = url_for('game_over')
            links_data[title] = url_for('game_over')
        else:
            new_url = url_for('game', page=title, clicks=new_clicks,
                            mytarget=target_title, difficulty=difficulty,
                            start_time=start_time)
            a['href'] = new_url
            links_data[title] = new_url
    
    # リンク情報をキャッシュに保存
    set_cached_links(page_title, links_data)
    
    return f'<div id="mw-content-text">{str(soup)}</div>'

def process_links_for_api(parsed_html, page_title, target_title, clicks_remaining, difficulty, start_time):
    """API用の軽量版リンク処理（リンク情報のみを返す）"""
    # リンク情報キャッシュをチェック
    cached_links = get_cached_links(page_title)
    if cached_links:
        logger.debug(f"Using cached links for API: {page_title}")
        # キャッシュされたリンク情報からAPI用のデータを構築
        links = []
        for title in cached_links.keys():
            if title != page_title:  # 現在のページへのリンクは除外
                new_clicks = clicks_remaining - 1
                links.append({
                    'title': title,
                    'href': f'/wiki/{title}',
                    'clicks': new_clicks
                })
        return links[:50]  # 最初の50個のリンクのみ返す
    
    # キャッシュがない場合は従来通り処理
    only_links = SoupStrainer('a')
    soup = BeautifulSoup(parsed_html, 'lxml', parse_only=only_links)
    links = []
    links_data = {}  # キャッシュ用のリンク情報
    
    for a in soup.find_all('a', href=True):
        link = a['href']
        
        # Wikipedia内のリンクのみを許可
        if not link.startswith('/wiki/'):
            continue

        # 除外プレフィックスのチェック
        if any(link.startswith(prefix) for prefix in EXCLUDED_PREFIXES):
            continue

        title = link.replace('/wiki/', '')
        title = unquote(title).strip()

        # 現在のページへのリンクはスキップ
        if title == page_title:
            continue

        new_clicks = clicks_remaining - 1
        
        # URLを生成してキャッシュ用データに保存
        if title == target_title:
            new_url = url_for('game', page=title, clicks=new_clicks,
                            mytarget=target_title, difficulty=difficulty,
                            start_time=start_time)
        elif new_clicks <= 0:
            new_url = url_for('game_over')
        else:
            new_url = url_for('game', page=title, clicks=new_clicks,
                            mytarget=target_title, difficulty=difficulty,
                            start_time=start_time)
        
        links_data[title] = new_url
        links.append({
            'title': title,
            'href': link,
            'clicks': new_clicks
        })
    
    # リンク情報をキャッシュに保存
    set_cached_links(page_title, links_data)
    
    return links[:50]  # 最初の50個のリンクのみ返す

# ハードモード用のカテゴリ別ページリスト
HARD_MODE_CATEGORIES = {
    'animals': [
        'ネコ', 'イヌ', 'ライオン', 'パンダ', 'キリン', 'ゾウ', 'ペンギン', 'イルカ',
        'クマ', 'ウサギ', 'ハムスター', 'カメ', 'ヘビ', 'ワニ', 'フクロウ', 'フラミンゴ',
        'シマウマ', 'カンガルー', 'コアラ', 'サル', 'ゴリラ', 'チンパンジー', 'トラ',
        'ヒョウ', 'ジャガー', 'チーター', 'オオカミ', 'キツネ', 'タヌキ', 'リス','ブラキオサウルス'
    ],
    'food': [
        'ラーメン', '寿司', 'パスタ', 'ピザ', 'ハンバーガー', 'フライドチキン',
        'カレー', 'うどん', 'そば', 'たこ焼き', 'お好み焼き', '餃子', '焼肉',
        'すき焼き', 'しゃぶしゃぶ', '天ぷら', 'とんかつ', '唐揚げ', 'チキン南蛮',
        'パン', 'ケーキ', 'アイスクリーム', 'チョコレート', 'クッキー', 'ドーナツ','梅干し'
    ],
    'places': [
        '東京', 'パリ', 'ニューヨーク', '富士山', 'エッフェル塔', '自由の女神',
        'ロンドン', 'ローマ', 'バルセロナ', 'アムステルダム', 'ベルリン', 'ウィーン',
        'プラハ', 'イスタンブール', 'カイロ', 'ケープタウン', 'シドニー', 'メルボルン',
        'バンクーバー', 'トロント', 'サンフランシスコ', 'ロサンゼルス', 'シカゴ',
        'ハワイ', 'バリ島', 'シンガポール', '香港', 'ソウル', '台北','ニュージーランド','ドミニカ共和国'
    ]
}

def get_random_page():
    """
    ランダムなページタイトルを返すユーティリティ関数
    """
    params = {
        'action': 'query',
        'list': 'random',
        'rnlimit': 1,
        'rnnamespace': 0,
        'format': 'json'
    }
    try:
        response = session.get(WIKI_API_URL, params=params, timeout=5)
        if response.status_code != 200:
            raise Exception(f"Status code: {response.status_code}")
        data = response.json()
        return data['query']['random'][0]['title']
    except Exception as e:
        app.logger.error(f"get_random_page Error: {e}")
        return "ネコ"

def get_hard_mode_target():
    """
    ハードモード用のターゲットページを返す関数
    3つのカテゴリ（動物、食べ物、場所）からランダムに選択
    """
    import random
    
    # 全てのカテゴリのページを統合
    all_pages = []
    for category, pages in HARD_MODE_CATEGORIES.items():
        all_pages.extend(pages)
    
    # ランダムに選択
    return random.choice(all_pages)


class OpeningView(MethodView):
    def get(self):
        error = request.args.get('error', '')
        return render_template('opening.html', error=error)
        
class StartGameView(MethodView):
    @limiter.limit("10 per minute")
    def get(self):
        difficulty = request.args.get('difficulty', 'easy')
        
        # 入力検証
        if difficulty not in ['easy', 'hard']:
            log_security_event("INVALID_DIFFICULTY", f"Invalid difficulty: {difficulty}")
            return redirect(url_for('opening', error='無効な難易度です'))
        
        logger.debug(f"StartGameView: difficulty = {difficulty}")

        if difficulty == 'easy':
            target_title = "ネコ"
        else:
            target_title = get_hard_mode_target()

        # 複数回試行して異なるページを取得
        start_page = get_random_page()
        attempts = 0
        while start_page == target_title and attempts < 10:
            start_page = get_random_page()
            attempts += 1
        
        if start_page == target_title:
            # フォールバック: 確実に異なるページ
            if difficulty == 'easy':
                start_page = "イヌ"
            else:
                import random
                all_pages = []
                for category, pages in HARD_MODE_CATEGORIES.items():
                    all_pages.extend(pages)
                start_page = random.choice([p for p in all_pages if p != target_title])

        # ゲーム開始時刻を記録
        import time
        start_time = int(time.time() * 1000)  # ミリ秒で記録

        return redirect(url_for('game', page=start_page, clicks=INITIAL_CLICKS,
                                mytarget=target_title, difficulty=difficulty, 
                                start_time=start_time))

class ResetView(MethodView):
    def get(self):
        # 現在の difficulty をクエリから取得。無ければ easy
        difficulty = request.args.get('difficulty', 'easy')
        app.logger.debug(f"ResetView: difficulty={difficulty}")

        # 難易度によってターゲットとスタートページを決める
        if difficulty == 'hard':
            target_title = get_hard_mode_target()
            # 複数回試行して異なるページを取得
            start_page = get_random_page()
            attempts = 0
            while start_page == target_title and attempts < 10:
                start_page = get_random_page()
                attempts += 1
            if start_page == target_title:
                # フォールバック: ハードモードのリストから選択
                import random
                all_pages = []
                for category, pages in HARD_MODE_CATEGORIES.items():
                    all_pages.extend(pages)
                start_page = random.choice([p for p in all_pages if p != target_title])
        else:
            target_title = "ネコ"
            # 複数回試行して異なるページを取得
            start_page = get_random_page()
            attempts = 0
            while start_page == target_title and attempts < 10:
                start_page = get_random_page()
                attempts += 1
            if start_page == target_title:
                # フォールバック: 確実に異なるページ
                start_page = "イヌ"

        app.logger.debug(f"ResetView: start='{start_page}', target='{target_title}'")

        # ゲーム開始時刻を記録
        import time
        start_time = int(time.time() * 1000)  # ミリ秒で記録

        # クリック数をリセットして、/game に飛ばす
        return redirect(url_for('game', page=start_page, clicks=INITIAL_CLICKS,
                                mytarget=target_title, difficulty=difficulty, 
                                start_time=start_time))

class GameView(MethodView):
    @limiter.limit("30 per minute")
    def get(self):
        # difficultyに応じたターゲット切り替えのため、difficultyも受け取る
        difficulty = request.args.get('difficulty', 'easy')
        # デフォルトはネコ
        target_title = sanitize_input(request.args.get('mytarget', TARGET_TITLE))
        page_title = sanitize_input(request.args.get('page', 'ネコ'))  # デフォルトは「ネコ」
        clicks_remaining = request.args.get('clicks', str(INITIAL_CLICKS))
        start_time = request.args.get('start_time', '0')
        
        # 入力検証
        if difficulty not in ['easy', 'hard']:
            log_security_event("INVALID_DIFFICULTY", f"Invalid difficulty: {difficulty}")
            return redirect(url_for('opening', error='無効な難易度です'))
        
        if not validate_page_title(page_title):
            log_security_event("INVALID_PAGE_TITLE", f"Invalid page title: {page_title}")
            return redirect(url_for('opening', error='無効なページタイトルです'))
        
        if not validate_page_title(target_title):
            log_security_event("INVALID_TARGET_TITLE", f"Invalid target title: {target_title}")
            return redirect(url_for('opening', error='無効なターゲットタイトルです'))

        try:
            clicks_remaining = int(clicks_remaining)
        except ValueError:
            clicks_remaining = INITIAL_CLICKS

        app.logger.debug(
            f"GameView: page_title = '{page_title}', target_title = '{target_title}', clicks_remaining = {clicks_remaining}, difficulty={difficulty}")

        # ゲームクリア判定
        if page_title == target_title:
            app.logger.debug("GameView: Game Clear")
            # スコアデータを計算
            used_clicks = INITIAL_CLICKS - clicks_remaining
            
            # 正確な時間計算
            import time
            try:
                start_time_ms = int(start_time)
                current_time_ms = int(time.time() * 1000)
                elapsed_time = current_time_ms - start_time_ms
            except (ValueError, TypeError):
                # フォールバック: クリック数から推定
                elapsed_time = used_clicks * 2000
            
            # URLパラメータとしてリダイレクト
            app.logger.debug(f"GameView: Redirecting to game_clear with clicks={used_clicks}, time={elapsed_time}, target={target_title}")
            return redirect(url_for('game_clear', 
                                  clicks=used_clicks, 
                                  time=elapsed_time, 
                                  target=target_title))

        # ゲームオーバー判定
        if clicks_remaining <= 0:
            app.logger.debug("GameView: Game Over")
            return redirect(url_for('game_over'))

        try:
            # キャッシュからページデータを取得
            cached_data = get_cached_page(page_title)
            if cached_data:
                logger.debug(f"Using cached data for page: {page_title}")
                data = cached_data
            else:
                # ページ内容の取得（最適化版）
                params = {
                    'action': 'parse',
                    'page': page_title,
                    'format': 'json',
                    'prop': 'text',
                    'redirects': 1,
                    'disableeditsection': 1,  # 編集セクションを無効化してレスポンスを軽量化
                    'disabletoc': 1,  # 目次を無効化
                    'disablelimitreport': 1,  # 制限レポートを無効化
                    'disablepp': 1  # 前処理を無効化
                }
                
                # セッションを使用してタイムアウトを短縮（さらに短縮）
                response = session.get(WIKI_API_URL, params=params, timeout=2)
                data = response.json()
                
                # データをキャッシュに保存
                set_cached_page(page_title, data)

            if 'parse' not in data:
                raise KeyError("'parse' キーがレスポンスに存在しません。")

            parsed_html = data['parse']['text']['*']

            # リンク書き換え（キャッシュ機能付き）
            parsed_html = process_links_in_html(parsed_html, page_title, target_title, 
                                              clicks_remaining, difficulty, start_time)

        except KeyError as e:
            logger.error(f"GameView KeyError: {e}")
            log_security_event("WIKI_API_ERROR", f"KeyError in GameView: {e}")
            parsed_html = f'<div id="mw-content-text"><p>エラーが発生しました。しばらく時間をおいてから再度お試しください。</p></div>'
        except Exception as e:
            logger.error(f"GameView Exception: {e}")
            log_security_event("GAME_VIEW_ERROR", f"Exception in GameView: {e}")
            parsed_html = f'<div id="mw-content-text"><p>エラーが発生しました。しばらく時間をおいてから再度お試しください。</p></div>'

        return render_template(
            'game.html',
            target_title=target_title,
            page_title=page_title,
            clicks_remaining=clicks_remaining,
            parsed_html=parsed_html,
            difficulty=difficulty
        )

class GameClearView(MethodView):
    def get(self):
        # URLパラメータからゲームデータを取得
        clicks = request.args.get('clicks', 0)
        time_ms = request.args.get('time', 0)
        target = request.args.get('target', 'ネコ')
        
        # デバッグ用ログ
        app.logger.debug(f"GameClearView: clicks={clicks}, time={time_ms}, target={target}")
        app.logger.debug(f"GameClearView: request.args = {dict(request.args)}")
        
        return render_template('game_clear.html', 
                             clicks=clicks, 
                             time_ms=time_ms, 
                             target=target)

class GameOverView(MethodView):
    def get(self):
        return render_template('game_over.html')

class GameDataView(MethodView):
    @limiter.limit("60 per minute")
    def get(self):
        """
        AJAX用のゲームデータ取得エンドポイント（プリロード用）
        """
        # パラメータの取得
        difficulty = request.args.get('difficulty', 'easy')
        target_title = sanitize_input(request.args.get('mytarget', TARGET_TITLE))
        page_title = sanitize_input(request.args.get('page', 'ネコ'))
        clicks_remaining = request.args.get('clicks', str(INITIAL_CLICKS))
        start_time = request.args.get('start_time', '0')
        
        # 入力検証
        if difficulty not in ['easy', 'hard']:
            log_security_event("INVALID_DIFFICULTY_API", f"Invalid difficulty: {difficulty}")
            return jsonify({'status': 'error', 'message': '無効な難易度です'})
        
        if not validate_page_title(page_title):
            log_security_event("INVALID_PAGE_TITLE_API", f"Invalid page title: {page_title}")
            return jsonify({'status': 'error', 'message': '無効なページタイトルです'})
        
        if not validate_page_title(target_title):
            log_security_event("INVALID_TARGET_TITLE_API", f"Invalid target title: {target_title}")
            return jsonify({'status': 'error', 'message': '無効なターゲットタイトルです'})

        try:
            clicks_remaining = int(clicks_remaining)
        except ValueError:
            clicks_remaining = INITIAL_CLICKS

        # ゲームクリア判定
        if page_title == target_title:
            return jsonify({
                'status': 'clear',
                'clicks': INITIAL_CLICKS - clicks_remaining,
                'target': target_title
            })

        # ゲームオーバー判定
        if clicks_remaining <= 0:
            return jsonify({'status': 'over'})

        try:
            # キャッシュからページデータを取得
            cached_data = get_cached_page(page_title)
            if cached_data:
                data = cached_data
            else:
                # ページ内容の取得（軽量版）
                params = {
                    'action': 'parse',
                    'page': page_title,
                    'format': 'json',
                    'prop': 'text',
                    'redirects': 1,
                    'disableeditsection': 1,
                    'disabletoc': 1,
                    'disablelimitreport': 1,
                    'disablepp': 1
                }
                
                response = session.get(WIKI_API_URL, params=params, timeout=2)
                data = response.json()
                
                # データをキャッシュに保存
                set_cached_page(page_title, data)

            if 'parse' not in data:
                raise KeyError("'parse' キーがレスポンスに存在しません。")

            parsed_html = data['parse']['text']['*']

            # リンク書き換え（キャッシュ機能付き軽量版）
            links = process_links_for_api(parsed_html, page_title, target_title, 
                                        clicks_remaining, difficulty, start_time)

            return jsonify({
                'status': 'success',
                'page_title': page_title,
                'target_title': target_title,
                'clicks_remaining': clicks_remaining,
                'links': links
            })

        except Exception as e:
            logger.error(f"GameDataView Exception: {e}")
            log_security_event("GAME_DATA_ERROR", f"Exception in GameDataView: {e}")
            return jsonify({'status': 'error', 'message': 'エラーが発生しました。しばらく時間をおいてから再度お試しください。'})

# Keep-alive機能
def keep_alive():
    """サーバーを常時稼働させるためのKeep-alive機能"""
    try:
        # 自分自身にリクエストを送信
        base_url = os.environ.get('BASE_URL', 'http://localhost:5000')
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            logger.info("Keep-alive ping successful")
        else:
            logger.warning(f"Keep-alive ping failed with status: {response.status_code}")
    except Exception as e:
        logger.error(f"Keep-alive ping error: {e}")

def run_scheduler():
    """スケジューラーを実行する関数"""
    while True:
        schedule.run_pending()
        time.sleep(60)  # 1分ごとにチェック

# 本番環境でのみKeep-aliveを有効化
if config_name == 'production':
    # 15分ごとにKeep-aliveを実行
    schedule.every(15).minutes.do(keep_alive)
    
    # スケジューラーを別スレッドで実行
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    logger.info("Keep-alive scheduler started")

class HealthCheckView(MethodView):
    """ヘルスチェック用のエンドポイント"""
    def get(self):
        return jsonify({
            'status': 'healthy',
            'timestamp': int(time.time()),
            'version': '1.0.0'
        })

# ルート登録
app.add_url_rule('/', view_func=OpeningView.as_view('opening'))
app.add_url_rule('/start_game', view_func=StartGameView.as_view('start_game'))
app.add_url_rule('/reset', view_func=ResetView.as_view('reset'))
app.add_url_rule('/game', view_func=GameView.as_view('game'))
app.add_url_rule('/game_data', view_func=GameDataView.as_view('game_data'))
app.add_url_rule('/gameclear', view_func=GameClearView.as_view('game_clear'))
app.add_url_rule('/gameover', view_func=GameOverView.as_view('game_over'))
app.add_url_rule('/health', view_func=HealthCheckView.as_view('health'))

###########################
# Quick tests (basic)     #
###########################
# def run_tests():
#     print("Running tests...")
#     with app.test_client() as client:
#         # 1) Test the root (opening)
#         rv = client.get('/')
#         assert rv.status_code == 200, "Root / should return 200"
#         print("Test 1 passed: GET / => 200")
#
#         # 2) Test start_game (GET)
#         rv = client.get('/start_game')
#         assert rv.status_code in (200, 302), "start_game should redirect or succeed"
#         print("Test 2 passed: GET /start_game => OK (Redirect or 200)")
#
#         # 3) Test reset
#         rv = client.get('/reset')
#         assert rv.status_code in (200, 302), "reset should redirect"
#         print("Test 3 passed: GET /reset => OK (Redirect)")
#
#     print("All tests completed!")

if __name__ == '__main__':
    # run_tests()  # 必要があればテスト
    # 本番環境では最適化された設定で起動
    if config_name == 'production':
        # 本番環境用の最適化設定
        app.run(
            host='0.0.0.0',
            port=int(os.environ.get('PORT', 5000)),
            debug=False,
            use_reloader=False,
            threaded=True
        )
    else:
        # 開発環境用の設定
        app.run(debug=True, use_reloader=True)
