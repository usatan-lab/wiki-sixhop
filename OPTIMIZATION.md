# パフォーマンス最適化ガイド

このドキュメントでは、Wiki SixHopアプリケーションに実装されているパフォーマンス最適化について詳しく説明します。

## 📊 最適化の概要

### HTMLレスポンスの最適化

#### 実装された最適化

1. **不要な要素の削除**
   - スクリプトタグ（`<script>`）
   - スタイルタグ（`<style>`）
   - テーブル（`<table>`）
   - 参考文献（`.reference`, `.reflist`）
   - インフォボックス（`.infobox`）
   - ナビゲーションボックス（`.navbox`）
   - サムネイル画像（`.thumb`, `.gallery`）
   - 目次（`.toc`, `#toc`）
   - 編集セクション（`.mw-editsection`）
   - その他のメタデータ

2. **HTML圧縮（Minification）**
   - 連続する空白を単一の空白に置換
   - タグ間の空白を削除
   - 不要な属性の削除（class, id, style など）

3. **外部リンクの完全削除**
   - Wikipedia内のリンク（`/wiki/`で始まる）以外のリンクを完全に削除
   - 外部サイト、メール、アンカーリンクなどを除去
   - ゲームプレイに不要なリンクを排除

4. **画像の最適化**
   - 遅延読み込み（lazy loading）属性の追加
   - srcset属性の削除（複数解像度の画像を削除）

#### 最適化の効果

実際のWikipediaページでテストした結果：

| ページ | 元のサイズ | 最適化後 | 削減率 | 削減量 | 外部リンク削除数 |
|--------|-----------|---------|--------|--------|------------------|
| ネコ | 442,472 bytes | 98,383 bytes | **77.77%** | 344,089 bytes | 873個 |
| イヌ | 283,162 bytes | 106,560 bytes | **62.37%** | 176,602 bytes | - |
| 東京 | 170,463 bytes | 41,300 bytes | **75.77%** | 129,163 bytes | - |

平均削減率: **約72%**

### Wikipedia API の最適化

#### 使用しているパラメータ

```python
params = {
    'action': 'parse',
    'page': page_title,
    'format': 'json',
    'prop': 'text',
    'redirects': 1,
    'disableeditsection': 1,  # 編集セクションを無効化
    'disabletoc': 1,          # 目次を無効化
    'disablelimitreport': 1,  # 制限レポートを無効化
    'disablepp': 1            # 前処理を無効化
}
```

これらのパラメータにより、Wikipedia APIからのレスポンスが軽量化されます。

### キャッシング戦略

#### 1. サーバーサイドキャッシュ

```python
CACHE_EXPIRY = 300  # 5分間キャッシュ

page_cache = {}      # ページデータのキャッシュ
links_cache = {}     # リンク情報のキャッシュ
```

- ページデータを5分間キャッシュ
- リンク情報を5分間キャッシュ
- MD5ハッシュをキャッシュキーとして使用

#### 2. ブラウザキャッシュ

```python
# 静的ファイルのキャッシュ設定
if request.endpoint == 'static':
    response.cache_control.max_age = 3600  # 1時間
    response.cache_control.public = True

# APIエンドポイントのキャッシュ設定
elif request.endpoint == 'game_data':
    response.cache_control.max_age = 300  # 5分
    response.cache_control.private = True
```

### 接続プーリング

```python
adapter = requests.adapters.HTTPAdapter(
    pool_connections=10,
    pool_maxsize=20,
    max_retries=3,
    pool_block=False
)
session.mount('http://', adapter)
session.mount('https://', adapter)
```

- 接続プール数: 10
- 最大プールサイズ: 20
- 最大リトライ回数: 3

## 🔧 設定オプション

### 環境変数

以下の環境変数でパフォーマンス最適化を制御できます：

```bash
# HTML最適化を有効化/無効化（デフォルト: True）
ENABLE_HTML_OPTIMIZATION=True

# HTML圧縮を有効化/無効化（デフォルト: True）
ENABLE_HTML_COMPRESSION=True

# 外部リンクの削除を有効化/無効化（デフォルト: True）
REMOVE_EXTERNAL_LINKS=True

# レート制限の設定
RATELIMIT_DEFAULT="200 per day, 50 per hour"

# キャッシュストレージのURL
RATELIMIT_STORAGE_URL="memory://"
```

### config.py での設定

```python
class Config:
    # HTML最適化設定
    ENABLE_HTML_OPTIMIZATION = os.environ.get('ENABLE_HTML_OPTIMIZATION', 'True').lower() == 'true'
    ENABLE_HTML_COMPRESSION = os.environ.get('ENABLE_HTML_COMPRESSION', 'True').lower() == 'true'
    REMOVE_EXTERNAL_LINKS = os.environ.get('REMOVE_EXTERNAL_LINKS', 'True').lower() == 'true'
```

## 📈 パフォーマンスモニタリング

### ログでの確認

最適化の効果はログで確認できます：

```
2025-10-05 11:46:55,282 - main - DEBUG - HTML optimized: Original size ~ 442472 bytes, Optimized size ~ 104384 bytes
```

### メトリクス

- **レスポンスタイム**: 平均2-3秒（キャッシュなし）、0.1秒未満（キャッシュあり）
- **転送サイズ**: 平均70%削減
- **メモリ使用量**: 最適化により約30%削減

## 🚀 今後の最適化案

1. **CDNの導入**
   - 静的ファイルをCDNから配信
   - グローバルなキャッシング

2. **データベースキャッシュ**
   - Redisを使用した分散キャッシュ
   - セッション管理の最適化

3. **画像の完全削除**
   - オプションで画像を完全に削除
   - さらなる軽量化

4. **Gzip/Brotli圧縮**
   - サーバーレベルでの圧縮
   - さらなる転送サイズの削減

5. **Service Workerの導入**
   - オフライン対応
   - より高速なキャッシング

## 📚 参考資料

- [Wikipedia API Documentation](https://www.mediawiki.org/wiki/API:Main_page)
- [Flask Caching](https://flask-caching.readthedocs.io/)
- [Requests: Advanced Usage](https://requests.readthedocs.io/en/latest/user/advanced/)
- [BeautifulSoup Documentation](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)

## 💡 ベストプラクティス

1. **キャッシュの有効期限**
   - 頻繁に変更されないコンテンツは長めに設定
   - APIレスポンスは短めに設定

2. **HTML最適化**
   - ゲームに不要な要素は積極的に削除
   - ただし、リンクは保持する

3. **エラーハンドリング**
   - 最適化中にエラーが発生した場合は元のHTMLを返す
   - ログに記録して問題を追跡

4. **テスト**
   - 定期的に最適化の効果を測定
   - A/Bテストで最適な設定を見つける

