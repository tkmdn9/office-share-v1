# 🥬 オフィシェアロッカー

会社で採れすぎた野菜をシェアするためのスマートロッカーシステム

## 📋 システム構成

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  スマホ      │  WiFi   │ Raspberry Pi │  GPIO   │ ソレノイド   │
│  (ブラウザ)  │ ◄─────► │   FastAPI    │ ───────► │   ロック    │
└─────────────┘         └──────────────┘         └─────────────┘
```

## ✨ 主な機能

- **QRコード読み取り**: 各ロッカーのQRコードをスマホで読み取り
- **ユーザー情報入力**: ニックネーム、メールアドレス、野菜情報を入力
- **自動解錠**: 情報送信後、2秒間自動で解錠
- **モード選択**: 「野菜を入れる」「野菜を取り出す」の2モード
- **外部公開**: ngrokを使用して外部からアクセス可能

## 🚀 クイックスタート

### 1. Raspberry Pi セットアップ

```bash
# リポジトリをクローン
git clone <repo-url>
cd offishare-locker_v1/backend

# Python仮想環境を作成
python3 -m venv venv
source venv/bin/activate

# 依存関係をインストール
pip install -r requirements.txt

# 削除処理（必要な場合）
deactivate
rm -rf venv
```

### 2. サーバー起動

```bash
# 開発モード（ホットリロード有効）
cd backend
source venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 3. 外部公開（ngrok）

```bash
# 別のターミナルで実行
ngrok http 8000
```

ngrokが生成したURLをメモしてください（例: `https://arianne-flossy-supereloquently.ngrok-free.dev`）

### 4. QRコード生成

```bash
# qrencodeをインストール (macOS)
brew install qrencode

# QRコード生成（ngrok URLを使用）
qrencode -o locker1.png -s 20 "https://your-ngrok-url.ngrok-free.dev/?locker=1"
qrencode -o locker2.png -s 20 "https://your-ngrok-url.ngrok-free.dev/?locker=2"
qrencode -o locker3.png -s 20 "https://your-ngrok-url.ngrok-free.dev/?locker=3"
```

> **注意**: `-s 20` でサイズを大きくすることで、QRコードが読み取りやすくなります。

### 5. 自動起動設定（systemd）

```bash
sudo nano /etc/systemd/system/offishare-locker.service
```

```ini
[Unit]
Description=Offishare Locker API Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/offishare-locker_v1/backend
Environment=PATH=/home/pi/offishare-locker_v1/backend/venv/bin
ExecStart=/home/pi/offishare-locker_v1/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# サービス有効化
sudo systemctl daemon-reload
sudo systemctl enable offishare-locker
sudo systemctl start offishare-locker

# ステータス確認
sudo systemctl status offishare-locker
```

## 🔌 配線

### GPIOピン割り当て

| ロッカー | GPIO | 物理ピン | 用途 |
|---------|------|----------|------|
| 上段 (1) | GPIO22 | Pin 15 | ソレノイド1 |
| 中段 (2) | GPIO27 | Pin 13 | ソレノイド2 |
| 下段 (3) | GPIO17 | Pin 11 | ソレノイド3 |
| - | 5V | Pin 2 | リレーVCC |
| - | GND | Pin 6 | リレーGND |

### 配線図

```
Raspberry Pi 4          3chリレー           ソレノイド
┌─────────┐            ┌────────┐          ┌────────┐
│ 5V (2)  ├────────────┤ VCC    │          │        │
│ GND (6) ├────────────┤ GND    │          │        │
│         │            │        │    12V   │        │
│GPIO22(15)├───────────┤ IN1────┼──────────┤ 上段    │
│GPIO27(13)├───────────┤ IN2────┼──────────┤ 中段    │
│GPIO17(11)├───────────┤ IN3────┼──────────┤ 下段    │
└─────────┘            └────────┘          └────────┘
                            │
                       DC 12V電源
```

## 📱 使い方

### QRコードから操作（推奨）

1. **QRコードを読み取る**
   - 各ロッカーに貼られたQRコードをスマホのカメラで読み取り

2. **モードを選択**
   - 🥦 **野菜を入れる**: 野菜を預ける場合
   - 🍲 **野菜を取り出す**: 野菜を受け取る場合

3. **情報を入力**
   - ニックネーム（例: やさい太郎）
   - メールアドレス
   - **「野菜を入れる」の場合のみ**:
     - 何を入れますか？（例: キャベツ 2個）
     - 保管期間（1時間〜12時間）

4. **解錠する**
   - 「解錠する」ボタンをタップ
   - 2秒間自動で解錠 → 自動施錠

### Web UIから直接操作（開発用）

現在、手動ボタンは非表示になっています。QRコードからのアクセスを推奨します。

## 🔧 API リファレンス

### エンドポイント一覧

| メソッド | エンドポイント | 説明 |
|----------|---------------|------|
| GET | `/` | Web UI表示 |
| GET | `/api/lockers` | 全ロッカー状態取得 |
| GET | `/api/lockers/{id}` | 個別ロッカー状態取得 |
| GET | `/api/unlock/{id}` | ロック解除（シンプル） |
| POST | `/api/unlock/{id}` | ロック解除（ユーザー情報付き） |

### POST `/api/unlock/{id}` - ユーザー情報付きロック解除

**リクエスト**
```bash
curl -X POST http://localhost:8000/api/unlock/1 \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "deposit",
    "nickname": "やさい太郎",
    "email": "yasai@example.com",
    "item": "キャベツ 2個",
    "duration": 3
  }'
```

**レスポンス**
```json
{
  "success": true,
  "locker_id": 1,
  "message": "引き出し1（上段）を解錠しました",
  "unlock_duration": 2
}
```

### GET `/api/unlock/{id}` - シンプルなロック解除

```bash
curl http://localhost:8000/api/unlock/1
```

### 全ロッカー状態取得

```bash
curl http://localhost:8000/api/lockers
```

### API ドキュメント

- Swagger UI: `http://<IP>:8000/docs`
- ReDoc: `http://<IP>:8000/redoc`

## 📁 ファイル構成

```
offishare-locker_v1/
├── .gitignore           # Git除外設定
├── SPECIFICATION.md     # 詳細技術仕様書
├── README.md            # このファイル
├── setup.txt            # セットアップコマンド集
└── backend/
    ├── main.py          # FastAPIサーバー
    ├── requirements.txt # Python依存関係
    └── static/
        ├── index.html   # Web UI
        └── style.css    # スタイルシート
```

## 🔒 セキュリティ注意事項

現在の実装は**社内WiFi + ngrok経由での使用**を前提とした構成です。

本番運用時は以下を検討してください：

- APIキー認証の追加
- HTTPS化（ngrokは自動的にHTTPS）
- 利用ログの記録（現在はコンソール出力のみ）
- ファイアウォール設定

## 🐛 トラブルシューティング

### `ModuleNotFoundError: No module named 'gpiozero'`

**原因**: macOSなどの開発環境で `gpiozero` がインストールされていない

**解決方法**:
1. Raspberry Pi上で実行する場合: `pip install gpiozero RPi.GPIO`
2. macOSで開発する場合: `main.py` でモッククラスを使用（現在は未実装）

### QRコードが読み取れない

**原因**: QRコードのサイズが小さすぎる、またはURLが長すぎる

**解決方法**:
```bash
# サイズを大きくする（-s 20 以上を推奨）
qrencode -o locker1.png -s 20 "https://your-url/?locker=1"

# エラー訂正レベルを上げる
qrencode -o locker1.png -s 20 -l M "https://your-url/?locker=1"
```

### GPIOエラーが出る

```bash
# GPIOグループに追加
sudo usermod -a -G gpio $USER
# 再ログインが必要
```

### ポート8000が使えない

```bash
# 別のポートで起動
uvicorn main:app --host 0.0.0.0 --port 3000
```

### WiFiのIPアドレスを確認

```bash
hostname -I
# または
ip addr show wlan0
```

## 🆕 変更履歴

### v1.1 (2026-01-29)
- QRコード読み取り後、ユーザー情報入力フォームを表示する仕様に変更
- POSTエンドポイントを追加（ユーザー情報付きロック解除）
- 手動ロック解除ボタンを非表示化（QRコード専用運用）
- ngrok対応（外部公開機能）
- QRコード生成時のサイズ推奨値を追加（`-s 20`）

### v1.0 (2026-01-25)
- 初回リリース
- 基本的なロック解除機能
- Web UI実装

## 📄 ライセンス

MIT License
