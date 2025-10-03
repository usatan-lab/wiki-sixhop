# セキュリティ設定ガイド

## 🔒 実装済みセキュリティ機能

### 1. レート制限
- **Flask-Limiter**を使用してAPIエンドポイントにレート制限を実装
- ゲーム開始: 10回/分
- ゲーム画面: 30回/分
- API呼び出し: 60回/分

### 2. 入力検証とサニタイゼーション
- 全てのユーザー入力に対して検証を実装
- HTMLエスケープによるXSS攻撃防止
- 危険な文字の除去
- 文字列長制限（200文字以内）

### 3. セキュリティヘッダー
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy`の設定
- `Strict-Transport-Security`（HTTPS環境のみ）

### 4. CSRF保護
- **Flask-WTF**によるCSRFトークン保護
- 全てのフォーム送信でCSRF検証

### 5. セキュリティログ
- セキュリティイベントの詳細ログ記録
- 不正な入力の検出と記録
- IPアドレスベースの追跡

### 6. クライアントサイドセキュリティ
- 右クリック禁止
- 開発者ツール検出
- キーボードショートカット制限
- ソース表示防止

## 🚀 本番環境での設定

### 環境変数の設定
```bash
# 本番環境用の設定例
export FLASK_ENV=production
export SECRET_KEY=your-very-secure-secret-key-here
export FLASK_DEBUG=False
export SECURE_HEADERS=True
export HSTS_MAX_AGE=31536000
```

### 推奨設定
1. **HTTPSの強制使用**
2. **強力なSECRET_KEYの設定**
3. **定期的なログ監視**
4. **レート制限の調整**（必要に応じて）

## 📊 セキュリティ監視

### ログ監視項目
- `SECURITY_EVENT`で始まるログエントリ
- レート制限の超過
- 不正な入力の検出
- APIエラーの発生

### アラート設定
以下のイベントでアラートを設定することを推奨：
- 同一IPからの大量リクエスト
- 不正な入力パターンの検出
- セキュリティヘッダーの欠如

## 🔧 追加のセキュリティ対策

### 推奨される追加実装
1. **WAF（Web Application Firewall）**の導入
2. **DDoS攻撃対策**
3. **IPホワイトリスト/ブラックリスト**
4. **セッション管理の強化**
5. **定期的なセキュリティ監査**

## ⚠️ 注意事項

- 開発者ツール検出は完全ではありません
- クライアントサイドのセキュリティは補助的なものです
- サーバーサイドの検証が最重要です
- 定期的なセキュリティアップデートを実施してください
