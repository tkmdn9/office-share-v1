# 🥬 オフィシェアロッカー

会社で採れすぎた野菜をシェアするためのスマートロッカーシステム

## 📋 システム構成

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│  スマホ      │  WiFi   │ Raspberry Pi │  GPIO   │ ソレノイド   │
│  (ブラウザ)  │ ◄─────► │   FastAPI    │ ───────► │   ロック    │
└─────────────┘         └──────────────┘         └─────────────┘
```

## 🚀 クイックスタート

### 1. Raspberry Pi セットアップ

```bash
# リポジトリをクローン
git clone <repo-url>
cd yasai-locker/backend

# Python仮想環境を作成
python3 -m venv venv
source venv/bin/activate

# 依存関係をインストール
pip install -r requirements.txt

# Raspberry PiではGPIOライブラリも追加
pip install RPi.GPIO

# 削除処理
deactivate
rm -rf venv
```

### 2. サーバー起動

```bash
# 開発モード（ホットリロード有効）
python main.py

# または本番モード
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 3. 自動起動設定（systemd）

```bash
sudo nano /etc/systemd/system/yasai-locker.service
```

```ini
[Unit]
Description=Yasai Locker API Server
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/yasai-locker/backend
Environment=PATH=/home/pi/yasai-locker/backend/venv/bin
ExecStart=/home/pi/yasai-locker/backend/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# サービス有効化
sudo systemctl daemon-reload
sudo systemctl enable yasai-locker
sudo systemctl start yasai-locker

# ステータス確認
sudo systemctl status yasai-locker
```

## 🔌 配線

### GPIOピン割り当て

| ロッカー | GPIO | 物理ピン | 用途 |
|---------|------|----------|------|
| 上段 (1) | GPIO17 | Pin 11 | ソレノイド1 |
| 中段 (2) | GPIO27 | Pin 13 | ソレノイド2 |
| 下段 (3) | GPIO22 | Pin 15 | ソレノイド3 |
| - | 5V | Pin 2 | リレーVCC |
| - | GND | Pin 6 | リレーGND |

### 配線図

```
Raspberry Pi 4          3chリレー           ソレノイド
┌─────────┐            ┌────────┐          ┌────────┐
│ 5V (2)  ├────────────┤ VCC    │          │        │
│ GND (6) ├────────────┤ GND    │          │        │
│         │            │        │    12V   │        │
│GPIO17(11)├───────────┤ IN1────┼──────────┤ 上段    │
│GPIO27(13)├───────────┤ IN2────┼──────────┤ 中段    │
│GPIO22(15)├───────────┤ IN3────┼──────────┤ 下段    │
└─────────┘            └────────┘          └────────┘
                            │
                       DC 12V電源
```

## 📱 使い方

### Web UI から操作

1. スマホのブラウザで `http://<RaspberryPiのIP>:8000` にアクセス
2. サーバーURLを設定（初回のみ）
3. 開けたい引き出しのボタンをタップ
4. 2秒間解錠 → 自動施錠

### QRコード で操作

1. 各引き出しにQRコードを貼付
2. スマホでQRコードをスキャン
3. 自動的にWeb UIが開いて解錠

### QRコード生成

### QRコード生成

```bash
# qrencodeをインストール (macOS)
brew install qrencode

# qrencodeをインストール (Raspberry Pi/Linux)
# sudo apt install qrencode

# QRコード生成 (ngrok URL)
qrencode -o locker1.png -s 10 "https://arianne-flossy-supereloquently.ngrok-free.dev/?locker=1"
qrencode -o locker2.png -s 10 "https://arianne-flossy-supereloquently.ngrok-free.dev/?locker=2"
qrencode -o locker3.png -s 10 "https://arianne-flossy-supereloquently.ngrok-free.dev/?locker=3"
```

## 🔧 API リファレンス

### ロッカー解錠

```bash
curl http://192.168.1.100:8000/api/unlock/1
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

### 全ロッカー状態取得

```bash
curl http://192.168.1.100:8000/api/lockers
```

### API ドキュメント

- Swagger UI: `http://<IP>:8000/docs`
- ReDoc: `http://<IP>:8000/redoc`

## 📁 ファイル構成

```
yasai-locker/
├── SPECIFICATION.md    # 詳細技術仕様書
├── README.md           # このファイル
└── backend/
    ├── main.py          # FastAPIサーバー
    ├── requirements.txt # Python依存関係
    └── static/
        └── index.html   # Web UI
```

## 🔒 セキュリティ注意事項

現在の実装は**社内WiFi内での使用**を前提とした最小構成です。

本番運用時は以下を検討してください：

- APIキー認証の追加
- HTTPS化（Let's Encrypt等）
- 利用ログの記録
- ファイアウォール設定

## 🐛 トラブルシューティング

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

## 📄 ライセンス

MIT License
