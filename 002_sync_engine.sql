-- 002_sync_engine.sql — підготовка локальної БД до універсальної двосторонньої синхронізації

ALTER TABLE devices      ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE devices      ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE users        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE users        ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE alarms       ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE alarms       ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE thresholds   ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE posts        ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE measurements ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE TABLE IF NOT EXISTS sync_state (
    table_name   TEXT PRIMARY KEY,
    last_push    TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01 UTC',
    last_pull    TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01 UTC',
    last_success TIMESTAMPTZ,
    status       TEXT,
    error_msg    TEXT
);

CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_posts_updated_at ON posts;
CREATE TRIGGER trg_posts_updated_at BEFORE UPDATE ON posts
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS trg_devices_updated_at ON devices;
CREATE TRIGGER trg_devices_updated_at BEFORE UPDATE ON devices
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS trg_users_updated_at ON users;
CREATE TRIGGER trg_users_updated_at BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS trg_alarms_updated_at ON alarms;
CREATE TRIGGER trg_alarms_updated_at BEFORE UPDATE ON alarms
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

DROP TRIGGER IF EXISTS trg_thresholds_updated_at ON thresholds;
CREATE TRIGGER trg_thresholds_updated_at BEFORE UPDATE ON thresholds
FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE INDEX IF NOT EXISTS idx_devices_updated_at      ON devices(updated_at);
CREATE INDEX IF NOT EXISTS idx_users_updated_at        ON users(updated_at);
CREATE INDEX IF NOT EXISTS idx_alarms_updated_at       ON alarms(updated_at);
CREATE INDEX IF NOT EXISTS idx_thresholds_updated_at   ON thresholds(updated_at);
CREATE INDEX IF NOT EXISTS idx_posts_updated_at        ON posts(updated_at);
CREATE INDEX IF NOT EXISTS idx_measurements_updated_at ON measurements(updated_at);
