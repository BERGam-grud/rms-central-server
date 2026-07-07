-- 006_local_home_multi_posts.sql
-- Декілька постів для одного користувача + локальна головна сторінка

CREATE TABLE IF NOT EXISTS user_post_access (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    post_id UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, post_id)
);

-- Сумісність зі старою схемою users.post_id: переносимо наявні прив'язки.
INSERT INTO user_post_access(user_id, post_id)
SELECT id, post_id
FROM users
WHERE post_id IS NOT NULL
ON CONFLICT DO NOTHING;

CREATE INDEX IF NOT EXISTS idx_user_post_access_user_id ON user_post_access(user_id);
CREATE INDEX IF NOT EXISTS idx_user_post_access_post_id ON user_post_access(post_id);
