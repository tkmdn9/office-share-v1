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
from typing import Optional, List
# from gpiozero import OutputDevice
from time import sleep
import os

# データベース関連のインポート
from database import init_database, get_db_connection
from crud import (
    get_or_create_user, 
    get_user_by_email,
    create_transaction, 
    get_transaction_by_id,
    get_transactions_by_locker,
    get_recent_deposits,
    get_all_transactions,
    send_message, 
    get_messages_by_transaction,
    get_messages_between_users,
    mark_message_as_read,
    get_unread_message_count,
    get_user_statistics
)

# ロック用リレーをつないだGPIOピン
LOCK_GPIO_PIN_1 = 22
LOCK_GPIO_PIN_2 = 27
LOCK_GPIO_PIN_3 = 17

# # GPIOピンへの通電の関数
# lock1 = OutputDevice(pin=LOCK_GPIO_PIN_1, active_high=True, initial_value=False)
# lock2 = OutputDevice(pin=LOCK_GPIO_PIN_2, active_high=True, initial_value=False)
# lock3 = OutputDevice(pin=LOCK_GPIO_PIN_3, active_high=True, initial_value=False)

# LOCK_RELAY_MAP = {
#     1: lock1,
#     2: lock2,
#     3: lock3,
# }

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
    init_database()  # データベース初期化
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
async def unlock_locker_with_user_info(locker_id: int, body: UnlockRequest):
    """
    ユーザー情報付きロック解除（データベース保存機能付き）
    """
    # ユーザー情報をデータベースに保存
    transaction_id = None
    if body.nickname and body.email:
        try:
            user_id = get_or_create_user(body.nickname, body.email)
            transaction_id = create_transaction(
                locker_id=locker_id,
                mode=body.mode,
                user_id=user_id,
                item=body.item,
                duration=body.duration
            )
            print(f"✅ Transaction saved: ID={transaction_id}, User={body.nickname}, Mode={body.mode}")
            if body.mode == "deposit" and body.item:
                print(f"   Item: {body.item}, Duration: {body.duration}h")
        except Exception as e:
            print(f"⚠️ Database error: {e}")
            # DB保存に失敗しても解錠処理は続行
    
    # 既存の解錠ロジック
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


# ============================================
# メッセージ機能 - 新規エンドポイント
# ============================================

class MessageSendRequest(BaseModel):
    transaction_id: Optional[int] = None
    from_user_email: str
    to_user_email: Optional[str] = None
    content: str


class MessageResponse(BaseModel):
    success: bool
    message_id: Optional[int] = None
    message: str


@app.post("/api/messages", response_model=MessageResponse)
async def post_message(body: MessageSendRequest):
    """
    メッセージを送信
    """
    try:
        # 送信者のユーザー情報を取得
        from_user = get_user_by_email(body.from_user_email)
        if not from_user:
            raise HTTPException(status_code=404, detail="送信者が見つかりません")
        
        # 受信者のユーザー情報を取得（オプション）
        to_user_id = None
        if body.to_user_email:
            to_user = get_user_by_email(body.to_user_email)
            if to_user:
                to_user_id = to_user["id"]
        
        # メッセージを保存
        message_id = send_message(
            from_user_id=from_user["id"],
            content=body.content,
            transaction_id=body.transaction_id,
            to_user_id=to_user_id
        )
        
        print(f"📨 Message sent: ID={message_id}, From={body.from_user_email}")
        
        return MessageResponse(
            success=True,
            message_id=message_id,
            message="メッセージを送信しました"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        return MessageResponse(
            success=False,
            message=f"エラー: {str(e)}"
        )


@app.get("/api/transactions/{transaction_id}/messages")
async def get_transaction_messages(transaction_id: int):
    """
    特定の取引に関するメッセージ一覧を取得
    """
    try:
        # 取引情報を確認
        transaction = get_transaction_by_id(transaction_id)
        if not transaction:
            raise HTTPException(status_code=404, detail="取引が見つかりません")
        
        # メッセージ一覧を取得
        messages = get_messages_by_transaction(transaction_id)
        
        return {
            "success": True,
            "transaction": transaction,
            "messages": messages,
            "message_count": len(messages)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/lockers/{locker_id}/transactions")
async def get_locker_transactions(locker_id: int, limit: int = 50):
    """
    特定のロッカーの取引履歴を取得
    """
    if locker_id not in LOCKERS:
        raise HTTPException(status_code=404, detail="ロッカーが見つかりません")
    
    try:
        transactions = get_transactions_by_locker(locker_id, limit)
        
        return {
            "success": True,
            "locker_id": locker_id,
            "locker_name": LOCKERS[locker_id]["name"],
            "transactions": transactions,
            "transaction_count": len(transactions)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/lockers/{locker_id}/deposits")
async def get_locker_deposits(locker_id: int, limit: int = 10):
    """
    特定のロッカーの最近の預け入れ記録を取得
    """
    if locker_id not in LOCKERS:
        raise HTTPException(status_code=404, detail="ロッカーが見つかりません")
    
    try:
        deposits = get_recent_deposits(locker_id, limit)
        
        return {
            "success": True,
            "locker_id": locker_id,
            "locker_name": LOCKERS[locker_id]["name"],
            "deposits": deposits,
            "deposit_count": len(deposits)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/users/{email}/messages")
async def get_user_messages(email: str, other_user_email: Optional[str] = None):
    """
    ユーザーのメッセージ履歴を取得
    other_user_emailが指定された場合は2人間の履歴のみ
    """
    try:
        user = get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
        
        if other_user_email:
            other_user = get_user_by_email(other_user_email)
            if not other_user:
                raise HTTPException(status_code=404, detail="相手ユーザーが見つかりません")
            
            messages = get_messages_between_users(user["id"], other_user["id"])
        else:
            # 全メッセージを取得（送信・受信両方）
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """SELECT m.*, 
                              u.nickname as sender_name,
                              u.email as sender_email
                       FROM messages m
                       JOIN users u ON m.from_user_id = u.id
                       WHERE m.from_user_id = ? OR m.to_user_id = ?
                       ORDER BY m.created_at DESC
                       LIMIT 100""",
                    (user["id"], user["id"])
                )
                messages = [dict(row) for row in cursor.fetchall()]
        
        return {
            "success": True,
            "user": user,
            "messages": messages,
            "message_count": len(messages)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/users/{email}/stats")
async def get_user_stats(email: str):
    """
    ユーザーの統計情報を取得
    """
    try:
        user = get_user_by_email(email)
        if not user:
            raise HTTPException(status_code=404, detail="ユーザーが見つかりません")
        
        stats = get_user_statistics(user["id"])
        
        return {
            "success": True,
            "user": {
                "nickname": user["nickname"],
                "email": user["email"]
            },
            "statistics": stats
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/transactions")
async def get_transactions(limit: int = 50):
    """
    全取引の一覧を取得（最新順）
    """
    try:
        transactions = get_all_transactions(limit)
        
        return {
            "success": True,
            "transactions": transactions,
            "transaction_count": len(transactions)
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
