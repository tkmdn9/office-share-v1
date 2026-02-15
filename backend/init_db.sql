-- オフィシェアロッカー データベース初期化スクリプト
-- SQLite用テーブル定義

-- ユーザーテーブル
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nickname TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- メールアドレスでの検索を高速化
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- 取引記録テーブル
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    locker_id INTEGER NOT NULL,
    mode TEXT NOT NULL CHECK(mode IN ('deposit', 'retrieve')),
    user_id INTEGER NOT NULL,
    item TEXT,
    duration INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ロッカー・ユーザーでの検索用インデックス
CREATE INDEX IF NOT EXISTS idx_transactions_locker ON transactions(locker_id);
CREATE INDEX IF NOT EXISTS idx_transactions_user ON transactions(user_id);
CREATE INDEX IF NOT EXISTS idx_transactions_created ON transactions(created_at DESC);

-- メッセージテーブル
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_id INTEGER,
    from_user_id INTEGER NOT NULL,
    to_user_id INTEGER,
    content TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
    FOREIGN KEY (from_user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (to_user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- メッセージ取得の高速化
CREATE INDEX IF NOT EXISTS idx_messages_transaction ON messages(transaction_id);
CREATE INDEX IF NOT EXISTS idx_messages_from_user ON messages(from_user_id);
CREATE INDEX IF NOT EXISTS idx_messages_to_user ON messages(to_user_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at DESC);
