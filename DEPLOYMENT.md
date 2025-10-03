# 本番環境デプロイメントガイド

## 🚀 Renderでのデプロイメント

### Renderのスリープ対策

Renderの無料プランでは、一定時間アクセスがないとサーバーがスリープします。以下の対策を実装済みです：

1. **Keep-alive機能**: 15分ごとに自動的にサーバーにアクセス
2. **ヘルスチェックエンドポイント**: `/health`でサーバー状態を確認
3. **最適化された起動設定**: スリープからの復帰時間を短縮

### 必要な環境変数

```bash
FLASK_ENV=production
SECRET_KEY=your-very-secure-secret-key
BASE_URL=https://your-app-name.onrender.com
SECURE_HEADERS=True
FLASK_DEBUG=False
```

## 🔐 環境変数の設定

### 方法1: .envファイルを使用（推奨）

```bash
# 本番環境用の.envファイルをコピー
cp .env.production .env

# アプリケーション起動
python3 main.py
```

### 方法2: 環境変数で直接設定

```bash
export FLASK_ENV=production
export SECRET_KEY=your-very-secure-secret-key
export SECURE_HEADERS=True
export FLASK_DEBUG=False
python3 main.py
```

### 方法3: systemdサービスでの設定

```ini
[Unit]
Description=WikiGame
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/path/to/WikiGame
Environment=FLASK_ENV=production
Environment=SECRET_KEY=your-secret-key
Environment=SECURE_HEADERS=True
ExecStart=/usr/bin/python3 main.py
Restart=always

[Install]
WantedBy=multi-user.target
```

## 🚀 本番環境での起動

### Renderでの自動デプロイ

1. GitHubリポジトリをRenderに接続
2. 環境変数を設定（上記参照）
3. ビルドコマンド: `pip install -r requirements.txt`
4. スタートコマンド: `gunicorn -w 2 -b 0.0.0.0:$PORT main:app`

### Gunicornを使用（推奨）

```bash
# 本番環境用の.envファイルを設定
cp .env.production .env

# Gunicornで起動（Render用に最適化）
gunicorn -w 2 -b 0.0.0.0:$PORT main:app --timeout 30 --keep-alive 2
```

### Dockerを使用

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "main:app"]
```

## 🔒 セキュリティチェックリスト

- [ ] 強力なSECRET_KEYを設定
- [ ] FLASK_DEBUG=Falseに設定
- [ ] SECURE_HEADERS=Trueに設定
- [ ] HTTPSを使用
- [ ] ファイアウォールの設定
- [ ] 定期的なログ監視
- [ ] バックアップの設定

## 📊 監視とログ

```bash
# ログの監視
tail -f /var/log/wikigame.log

# セキュリティイベントの監視
grep "SECURITY_EVENT" /var/log/wikigame.log
```

## 🔄 追加のKeep-alive対策

### 外部Keep-aliveサービス

内蔵のKeep-alive機能に加えて、以下の外部サービスも利用できます：

1. **UptimeRobot** (無料)
   - 5分間隔でヘルスチェック
   - 無料プランで50個のモニター

2. **Pingdom** (有料)
   - より詳細な監視機能

3. **StatusCake** (無料)
   - 5分間隔でヘルスチェック
   - 無料プランで10個のモニター

### 設定例

```bash
# ヘルスチェックURL
https://your-app-name.onrender.com/health

# 期待されるレスポンス
{
  "status": "healthy",
  "timestamp": 1234567890,
  "version": "1.0.0"
}
```

### 手動Keep-aliveスクリプト

```bash
#!/bin/bash
# keep-alive.sh
while true; do
  curl -s https://your-app-name.onrender.com/health > /dev/null
  sleep 900  # 15分間隔
done
```
