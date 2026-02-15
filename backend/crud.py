"""
CRUD操作モジュール
ユーザー・取引・メッセージのデータベース操作
"""

from database import get_db_connection
from typing import Optional, List, Dict, Tuple
from datetime import datetime


# ============================================
# User操作
# ============================================

def get_or_create_user(nickname: str, email: str) -> int:
    """
    ユーザーを取得または作成
    既存のメールアドレスがあれば既存ユーザーのIDを返す
    
    Args:
        nickname: ユーザーのニックネーム
        email: メールアドレス（一意）
    
    Returns:
        ユーザーID
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # メールアドレスで既存ユーザー検索
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        result = cursor.fetchone()
        
        if result:
            return result["id"]
        
        # 新規ユーザー作成
        cursor.execute(
            "INSERT INTO users (nickname, email) VALUES (?, ?)",
            (nickname, email)
        )
        return cursor.lastrowid


def get_user_by_id(user_id: int) -> Optional[Dict]:
    """
    ユーザーIDからユーザー情報を取得
    
    Args:
        user_id: ユーザーID
    
    Returns:
        ユーザー情報の辞書、存在しない場合はNone
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        result = cursor.fetchone()
        return dict(result) if result else None


def get_user_by_email(email: str) -> Optional[Dict]:
    """
    メールアドレスからユーザー情報を取得
    
    Args:
        email: メールアドレス
    
    Returns:
        ユーザー情報の辞書、存在しない場合はNone
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
        result = cursor.fetchone()
        return dict(result) if result else None


# ============================================
# Transaction操作
# ============================================

def create_transaction(
    locker_id: int,
    mode: str,
    user_id: int,
    item: Optional[str] = None,
    duration: Optional[int] = None
) -> int:
    """
    取引記録を作成
    
    Args:
        locker_id: ロッカーID (1-3)
        mode: 'deposit' または 'retrieve'
        user_id: ユーザーID
        item: 野菜の名前（depositモード時）
        duration: 保管期間（時間単位、depositモード時）
    
    Returns:
        作成された取引ID
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO transactions 
               (locker_id, mode, user_id, item, duration)
               VALUES (?, ?, ?, ?, ?)""",
            (locker_id, mode, user_id, item, duration)
        )
        return cursor.lastrowid


def get_transaction_by_id(transaction_id: int) -> Optional[Dict]:
    """
    取引IDから取引情報を取得
    
    Args:
        transaction_id: 取引ID
    
    Returns:
        取引情報の辞書、存在しない場合はNone
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT t.*, u.nickname, u.email
               FROM transactions t
               JOIN users u ON t.user_id = u.id
               WHERE t.id = ?""",
            (transaction_id,)
        )
        result = cursor.fetchone()
        return dict(result) if result else None


def get_transactions_by_locker(locker_id: int, limit: int = 50) -> List[Dict]:
    """
    特定のロッカーの取引履歴を取得
    
    Args:
        locker_id: ロッカーID
        limit: 取得件数上限
    
    Returns:
        取引情報のリスト
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT t.*, u.nickname, u.email
               FROM transactions t
               JOIN users u ON t.user_id = u.id
               WHERE t.locker_id = ?
               ORDER BY t.created_at DESC
               LIMIT ?""",
            (locker_id, limit)
        )
        return [dict(row) for row in cursor.fetchall()]


def get_recent_deposits(locker_id: int, limit: int = 10) -> List[Dict]:
    """
    特定のロッカーの最近の預け入れ記録を取得
    
    Args:
        locker_id: ロッカーID
        limit: 取得件数上限
    
    Returns:
        預け入れ記録のリスト
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT t.*, u.nickname, u.email
               FROM transactions t
               JOIN users u ON t.user_id = u.id
               WHERE t.locker_id = ? AND t.mode = 'deposit'
               ORDER BY t.created_at DESC
               LIMIT ?""",
            (locker_id, limit)
        )
        return [dict(row) for row in cursor.fetchall()]


def get_all_transactions(limit: int = 50) -> List[Dict]:
    """
    全取引履歴を取得（最新順）
    
    Args:
        limit: 取得件数上限
    
    Returns:
        取引情報のリスト
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT t.*, u.nickname, u.email
               FROM transactions t
               JOIN users u ON t.user_id = u.id
               ORDER BY t.created_at DESC
               LIMIT ?""",
            (limit,)
        )
        return [dict(row) for row in cursor.fetchall()]


# ============================================
# Message操作
# ============================================

def send_message(
    from_user_id: int,
    content: str,
    transaction_id: Optional[int] = None,
    to_user_id: Optional[int] = None
) -> int:
    """
    メッセージを送信
    
    Args:
        from_user_id: 送信者のユーザーID
        content: メッセージ本文
        transaction_id: 関連する取引ID（オプション）
        to_user_id: 受信者のユーザーID（オプション、NULLの場合は取引関係者全員）
    
    Returns:
        作成されたメッセージID
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO messages 
               (transaction_id, from_user_id, to_user_id, content)
               VALUES (?, ?, ?, ?)""",
            (transaction_id, from_user_id, to_user_id, content)
        )
        return cursor.lastrowid


def get_messages_by_transaction(transaction_id: int) -> List[Dict]:
    """
    特定の取引に関するメッセージ一覧を取得
    
    Args:
        transaction_id: 取引ID
    
    Returns:
        メッセージのリスト
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT m.*, 
                      u.nickname as sender_name,
                      u.email as sender_email
               FROM messages m
               JOIN users u ON m.from_user_id = u.id
               WHERE m.transaction_id = ?
               ORDER BY m.created_at ASC""",
            (transaction_id,)
        )
        return [dict(row) for row in cursor.fetchall()]


def get_messages_between_users(user_id_1: int, user_id_2: int, limit: int = 100) -> List[Dict]:
    """
    2人のユーザー間の全メッセージ履歴を取得
    
    Args:
        user_id_1: ユーザー1のID
        user_id_2: ユーザー2のID
        limit: 取得件数上限
    
    Returns:
        メッセージのリスト
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT m.*, 
                      u.nickname as sender_name,
                      u.email as sender_email,
                      t.item as related_item,
                      t.locker_id
               FROM messages m
               JOIN users u ON m.from_user_id = u.id
               LEFT JOIN transactions t ON m.transaction_id = t.id
               WHERE (m.from_user_id = ? AND m.to_user_id = ?)
                  OR (m.from_user_id = ? AND m.to_user_id = ?)
               ORDER BY m.created_at ASC
               LIMIT ?""",
            (user_id_1, user_id_2, user_id_2, user_id_1, limit)
        )
        return [dict(row) for row in cursor.fetchall()]


def mark_message_as_read(message_id: int) -> bool:
    """
    メッセージを既読にする
    
    Args:
        message_id: メッセージID
    
    Returns:
        成功した場合True
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE messages SET is_read = TRUE WHERE id = ?",
            (message_id,)
        )
        return cursor.rowcount > 0


def get_unread_message_count(user_id: int) -> int:
    """
    未読メッセージ数を取得
    
    Args:
        user_id: ユーザーID
    
    Returns:
        未読メッセージ数
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT COUNT(*) as count
               FROM messages
               WHERE to_user_id = ? AND is_read = FALSE""",
            (user_id,)
        )
        result = cursor.fetchone()
        return result["count"] if result else 0


# ============================================
# 統計・分析用
# ============================================

def get_user_statistics(user_id: int) -> Dict:
    """
    ユーザーの統計情報を取得
    
    Args:
        user_id: ユーザーID
    
    Returns:
        統計情報の辞書
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 預け入れ回数
        cursor.execute(
            "SELECT COUNT(*) as count FROM transactions WHERE user_id = ? AND mode = 'deposit'",
            (user_id,)
        )
        deposit_count = cursor.fetchone()["count"]
        
        # 取り出し回数
        cursor.execute(
            "SELECT COUNT(*) as count FROM transactions WHERE user_id = ? AND mode = 'retrieve'",
            (user_id,)
        )
        retrieve_count = cursor.fetchone()["count"]
        
        # 送信メッセージ数
        cursor.execute(
            "SELECT COUNT(*) as count FROM messages WHERE from_user_id = ?",
            (user_id,)
        )
        message_sent = cursor.fetchone()["count"]
        
        # 受信メッセージ数
        cursor.execute(
            "SELECT COUNT(*) as count FROM messages WHERE to_user_id = ?",
            (user_id,)
        )
        message_received = cursor.fetchone()["count"]
        
        return {
            "deposit_count": deposit_count,
            "retrieve_count": retrieve_count,
            "message_sent": message_sent,
            "message_received": message_received,
            "total_transactions": deposit_count + retrieve_count
        }
