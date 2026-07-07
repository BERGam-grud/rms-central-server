-- 002_sync_engine.sql
-- Universal two-way sync support for RMS central database.
-- Safe to run more than once.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

ALTER TABLE IF EXISTS posts        ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE IF EXISTS devices      ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE IF EXISTS devices      ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE IF EXISTS users        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE IF EXISTS users        ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE IF EXISTS alarms       ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
ALTER TABLE IF EXISTS alarms       ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE IF EXISTS thresholds   ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;
ALTER TABLE IF EXISTS measurements ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

CREATE TABLE IF NOT EXISTS sync_state (
    table_name    TEXT PRIMARY KEY,
    last_push     TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01 00:00:00+00',
    last_pull     TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01 00:00:00+00',
    last_sync     TIMESTAMPTZ,
    status        TEXT,
    error         TEXT
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

-- Measurements are inserted very often. We still keep updated_at for sync ordering,
-- but normally measurements should not be updated by UI.

CREATE INDEX IF NOT EXISTS idx_posts_updated_at        ON posts(updated_at);
CREATE INDEX IF NOT EXISTS idx_devices_updated_at      ON devices(updated_at);
CREATE INDEX IF NOT EXISTS idx_users_updated_at        ON users(updated_at);
CREATE INDEX IF NOT EXISTS idx_alarms_updated_at       ON alarms(updated_at);
CREATE INDEX IF NOT EXISTS idx_thresholds_updated_at   ON thresholds(updated_at);
CREATE INDEX IF NOT EXISTS idx_measurements_updated_at ON measurements(updated_at);
