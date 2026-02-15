"""
データベース接続管理モジュール
SQLiteを使用してユーザー・取引・メッセージ情報を管理
"""

import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Generator

# データベースファイルのパス
DB_PATH = Path(__file__).parent / "offishare.db"


def init_database() -> None:
    """
    データベースを初期化
    init_db.sqlを実行してテーブルを作成
    """
    sql_path = Path(__file__).parent / "init_db.sql"
    
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")
    
    with sqlite3.connect(DB_PATH) as conn:
        with open(sql_path, 'r', encoding='utf-8') as f:
            conn.executescript(f.read())
    
    print(f"✅ Database initialized: {DB_PATH}")


@contextmanager
def get_db_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    DB接続のコンテキストマネージャ
    自動的にコミット・ロールバック・クローズを処理
    
    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users")
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 辞書形式でアクセス可能に
    
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def reset_database() -> None:
    """
    データベースをリセット（開発用）
    警告: 全データが削除されます
    """
    if DB_PATH.exists():
        DB_PATH.unlink()
        print(f"🗑️ Database deleted: {DB_PATH}")
    
    init_database()
    print("🔄 Database reset complete")
