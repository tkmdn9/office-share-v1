"""
オフィシェアロッカー - バックエンドAPIサーバー
Raspberry Pi 4 + FastAPI + GPIO制御
"""

import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
# from gpiozero import OutputDevice
from time import sleep
import os

# ロック用リレーをつないだGPIOピン
LOCK_GPIO_PIN_1 = 22
LOCK_GPIO_PIN_2 = 27
LOCK_GPIO_PIN_3 = 17

# GPIOピンへの通電の関数
lock1 = OutputDevice(pin=LOCK_GPIO_PIN_1, active_high=True, initial_value=False)
lock2 = OutputDevice(pin=LOCK_GPIO_PIN_2, active_high=True, initial_value=False)
lock3 = OutputDevice(pin=LOCK_GPIO_PIN_3, active_high=True, initial_value=False)

LOCK_RELAY_MAP = {
    1: lock1,
    2: lock2,
    3: lock3,
}

# --- GPIO設定 ---
# 本番環境ではRPi.GPIOを使用、開発環境ではモック
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
except ImportError:
    GPIO_AVAILABLE = False
    print("⚠️ RPi.GPIO not available - running in mock mode")


# --- ロッカー設定 ---
LOCKERS = {
    1: {"name": "上段", "gpio": 22},
    2: {"name": "中段", "gpio": 27},
    3: {"name": "下段", "gpio": 17},
}

UNLOCK_DURATION = 2  # 解錠時間（秒）

# ロック状態管理
locker_status = {1: "locked", 2: "locked", 3: "locked"}


# --- GPIO初期化 ---
def setup_gpio():
    """GPIOピンを初期化"""
    if not GPIO_AVAILABLE:
        return
    
    GPIO.setmode(GPIO.BCM)
    GPIO.setwarnings(False)
    
    for locker_id, config in LOCKERS.items():
        GPIO.setup(config["gpio"], GPIO.OUT)
        GPIO.output(config["gpio"], GPIO.LOW)  # 初期状態: 施錠
        print(f"✅ GPIO{config['gpio']} initialized for locker {locker_id} ({config['name']})")


def cleanup_gpio():
    """GPIO終了処理"""
    if GPIO_AVAILABLE:
        GPIO.cleanup()

# --- FastAPIアプリケーション ---
app = FastAPI(
    title="オフィシェアロッカー API",
    description="会社で野菜をシェアするためのスマートロッカーシステム",
    version="1.0.0"
)

# staticディレクトリをマウント
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS設定（同一ネットワーク内のブラウザからアクセス可能に）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Request Model ---
class UnlockRequest(BaseModel):
    mode: str                 # 'deposit' or 'retrieve'
    nickname: str | None = None
    email: str | None = None
    item: str | None = None   # deposit のとき
    duration: int | None = None

# --- Reponse Model ---
class UnlockResponse(BaseModel):
    success: bool
    locker_id: Optional[int] = None
    message: str
    unlock_duration: Optional[int] = None



class LockerInfo(BaseModel):
    id: int
    name: str
    gpio: int
    status: str


class LockersResponse(BaseModel):
    lockers: list[LockerInfo]


# --- 起動・終了イベント ---
@app.on_event("startup")
async def startup_event():
    setup_gpio()
    print("🥬 オフィシェアロッカーAPIサーバー起動")


@app.on_event("shutdown")
async def shutdown_event():
    cleanup_gpio()
    print("👋 サーバー終了")


# --- APIエンドポイント ---
@app.get("/", response_class=HTMLResponse)
async def root():
    """ヘルスチェック & Web UI"""
    # HTMLファイルを読み込んで返す
    html_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    
    # staticフォルダがない場合はインラインHTML
    return HTMLResponse(content="""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>オフィシェアロッカー</title>
        <style>
            body { font-family: sans-serif; text-align: center; padding: 20px; }
            .btn { padding: 20px 40px; font-size: 18px; margin: 10px; cursor: pointer; }
        </style>
    </head>
    <body>
        <h1>🥬 オフィシェアロッカー</h1>
        <p>APIサーバー稼働中</p>
        <p>Web UIは /static/index.html を配置してください</p>
    </body>
    </html>
    """)


@app.get("/api/lockers", response_model=LockersResponse)
async def get_lockers():
    """全ロッカーの状態を取得"""
    lockers = [
        LockerInfo(
            id=locker_id,
            name=config["name"],
            gpio=config["gpio"],
            status=locker_status[locker_id]
        )
        for locker_id, config in LOCKERS.items()
    ]
    return LockersResponse(lockers=lockers)


@app.get("/api/lockers/{locker_id}", response_model=LockerInfo)
async def get_locker(locker_id: int):
    """特定のロッカー状態を取得"""
    if locker_id not in LOCKERS:
        raise HTTPException(
            status_code=404,
            detail=f"Locker {locker_id} not found. Valid IDs: {list(LOCKERS.keys())}"
        )
    
    config = LOCKERS[locker_id]
    return LockerInfo(
        id=locker_id,
        name=config["name"],
        gpio=config["gpio"],
        status=locker_status[locker_id]
    )

@app.get("/api/unlock/{locker_id}", response_model=UnlockResponse)
async def unlock_locker(locker_id: int):
    """
    ロッカーを解錠する
    
    - locker_id: 1=上段, 2=中段, 3=下段
    - 2秒間解錠した後、自動的に施錠
    """
    # バリデーション
    if locker_id not in LOCKERS:
        return UnlockResponse(
            success=False,
            message=f"Invalid locker ID. Valid IDs: {list(LOCKERS.keys())}"
        )
    
    config = LOCKERS[locker_id]
    gpio_pin = config["gpio"]
    locker_name = config["name"]
    
    # すでに解錠中の場合
    if locker_status[locker_id] == "unlocked":
        return UnlockResponse(
            success=True,
            locker_id=locker_id,
            message=f"引き出し{locker_id}（{locker_name}）は既に解錠中です",
            unlock_duration=UNLOCK_DURATION
        )
    
    # 解錠処理
    try:
        # GPIO HIGH → 解錠
        if GPIO_AVAILABLE:
            relay = LOCK_RELAY_MAP[locker_id]   # locker_id に応じて lock1/2/3 を取得
            relay.on()
            print(relay)
            sleep(2.0)
            relay.off()
            GPIO.output(gpio_pin, GPIO.HIGH)
        
        locker_status[locker_id] = "unlocked"
        print(f"🔓 Locker {locker_id} ({locker_name}) UNLOCKED - GPIO{gpio_pin} HIGH")
        
        # 非同期で自動施錠をスケジュール
        asyncio.create_task(auto_lock(locker_id))
        
        return UnlockResponse(
            success=True,
            locker_id=locker_id,
            message=f"引き出し{locker_id}（{locker_name}）を解錠しました",
            unlock_duration=UNLOCK_DURATION
        )
        
    except Exception as e:
        return UnlockResponse(
            success=False,
            locker_id=locker_id,
            message=f"Error: {str(e)}"
        )

@app.post("/api/unlock/{locker_id}", response_model=UnlockResponse)
async def unlock_locker(locker_id: int, body: UnlockRequest):
    # ここで body.mode / body.nickname / body.email / body.item / body.duration が使える
    # 例: ログ保存・DB保存など
    print(f"[{body.mode}] locker={locker_id}, user={body.nickname} <{body.email}>")
    if body.mode == "deposit":
        print(f"item={body.item}, duration={body.duration}h")

    # あとは今までの解錠ロジックをそのまま
    if locker_id not in LOCKERS:
        return UnlockResponse(
            success=False,
            message=f"Invalid locker ID. Valid IDs: {list(LOCKERS.keys())}"
        )

    config = LOCKERS[locker_id]
    gpio_pin = config["gpio"]
    locker_name = config["name"]

    if locker_status[locker_id] == "unlocked":
        return UnlockResponse(
            success=True,
            locker_id=locker_id,
            message=f"引き出し{locker_id}（{locker_name}）は既に解錠中です",
            unlock_duration=UNLOCK_DURATION
        )

    try:
        if GPIO_AVAILABLE:
            relay = LOCK_RELAY_MAP[locker_id]
            relay.on()
            sleep(2.0)
            relay.off()
            # GPIO.output(gpio_pin, GPIO.HIGH)

        locker_status[locker_id] = "unlocked"
        asyncio.create_task(auto_lock(locker_id))

        return UnlockResponse(
            success=True,
            locker_id=locker_id,
            message=f"引き出し{locker_id}（{locker_name}）を解錠しました",
            unlock_duration=UNLOCK_DURATION
        )

    except Exception as e:
        return UnlockResponse(
            success=False,
            locker_id=locker_id,
            message=f"Error: {str(e)}"
        )


async def auto_lock(locker_id: int):
    """指定時間後に自動施錠"""
    await asyncio.sleep(UNLOCK_DURATION)
    
    config = LOCKERS[locker_id]
    gpio_pin = config["gpio"]
    
    # GPIO LOW → 施錠
    if GPIO_AVAILABLE:
        GPIO.output(gpio_pin, GPIO.LOW)
    
    locker_status[locker_id] = "locked"
    print(f"🔒 Locker {locker_id} ({config['name']}) AUTO-LOCKED - GPIO{gpio_pin} LOW")


# --- メイン実行 ---
if __name__ == "__main__":
    import uvicorn
    
    # Raspberry Piの場合は0.0.0.0でバインド
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
