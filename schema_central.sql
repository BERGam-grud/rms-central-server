-- ============================================================
--  РМС — Схема центральної БД (Railway PostgreSQL)
--  Запустіть один раз після деплою через Railway Shell
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ENUM типи
DO $$ BEGIN
  CREATE TYPE device_type  AS ENUM ('PFU','PAED_GAMMA','SPECTROMETER');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE alarm_level  AS ENUM ('INFO','WARNING','CRITICAL');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE alarm_status AS ENUM ('ACTIVE','RESOLVED','IGNORED');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE user_role    AS ENUM ('admin','operator','guest');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE sync_status  AS ENUM ('SUCCESS','PARTIAL','FAILED');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ПОСТИ
CREATE TABLE IF NOT EXISTS posts (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name       VARCHAR(128) NOT NULL,
    location   VARCHAR(256),
    region     VARCHAR(128),
    latitude   NUMERIC(9,6),
    longitude  NUMERIC(9,6),
    is_active  BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ПРИЛАДИ
CREATE TABLE IF NOT EXISTS devices (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id     UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    type        device_type NOT NULL,
    name        VARCHAR(128),
    serial_port VARCHAR(64),
    baud_rate   INTEGER DEFAULT 9600,
    is_online   BOOLEAN NOT NULL DEFAULT FALSE,
    last_seen   TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_devices_post ON devices(post_id);

-- ВИМІРЮВАННЯ (партиціонування по місяцях)
CREATE TABLE IF NOT EXISTS measurements (
    id          BIGSERIAL,
    post_id     UUID NOT NULL,
    device_id   UUID NOT NULL,
    parameter   VARCHAR(64) NOT NULL,
    value       NUMERIC(18,6) NOT NULL,
    unit        VARCHAR(32) NOT NULL,
    quality     SMALLINT DEFAULT 0,
    recorded_at TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    synced      BOOLEAN NOT NULL DEFAULT TRUE,
    PRIMARY KEY (id, recorded_at)
) PARTITION BY RANGE (recorded_at);

CREATE INDEX IF NOT EXISTS idx_meas_post_time   ON measurements(post_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_meas_device_time ON measurements(device_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_meas_parameter   ON measurements(parameter, recorded_at DESC);

-- Партиції 2025-2026
DO $$
DECLARE
  y INT; m INT; s DATE; e DATE; pname TEXT;
BEGIN
  FOR y IN 2025..2027 LOOP
    FOR m IN 1..12 LOOP
      s := make_date(y, m, 1);
      e := s + INTERVAL '1 month';
      pname := format('measurements_%s_%s', y, lpad(m::text,2,'0'));
      IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname=pname) THEN
        EXECUTE format(
          'CREATE TABLE %I PARTITION OF measurements FOR VALUES FROM (%L) TO (%L)',
          pname, s, e
        );
      END IF;
    END LOOP;
  END LOOP;
END $$;

-- КОРИСТУВАЧІ
CREATE TABLE IF NOT EXISTS users (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username      VARCHAR(64)  NOT NULL UNIQUE,
    email         VARCHAR(256) NOT NULL UNIQUE,
    password_hash VARCHAR(256) NOT NULL,
    role          user_role    NOT NULL DEFAULT 'guest',
    post_id       UUID REFERENCES posts(id) ON DELETE SET NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    last_login    TIMESTAMPTZ,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- АВАРІЇ
CREATE TABLE IF NOT EXISTS alarms (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    post_id        UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    device_id      UUID REFERENCES devices(id) ON DELETE SET NULL,
    measurement_id BIGINT,
    level          alarm_level  NOT NULL DEFAULT 'WARNING',
    status         alarm_status NOT NULL DEFAULT 'ACTIVE',
    message        TEXT NOT NULL,
    threshold      NUMERIC(18,6),
    actual_value   NUMERIC(18,6),
    triggered_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at    TIMESTAMPTZ,
    resolved_by    UUID REFERENCES users(id) ON DELETE SET NULL,
    notes          TEXT
);
CREATE INDEX IF NOT EXISTS idx_alarms_post    ON alarms(post_id);
CREATE INDEX IF NOT EXISTS idx_alarms_status  ON alarms(status);
CREATE INDEX IF NOT EXISTS idx_alarms_time    ON alarms(triggered_at DESC);

-- ПОРОГИ
CREATE TABLE IF NOT EXISTS thresholds (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    device_id   UUID REFERENCES devices(id) ON DELETE CASCADE,
    post_id     UUID REFERENCES posts(id)   ON DELETE CASCADE,
    device_type device_type NOT NULL,
    parameter   VARCHAR(64) NOT NULL,
    warn_value  NUMERIC(18,6) NOT NULL,
    crit_value  NUMERIC(18,6) NOT NULL,
    unit        VARCHAR(32),
    created_by  UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ЖУРНАЛ СИНХРОНІЗАЦІЙ
CREATE TABLE IF NOT EXISTS sync_log (
    id             BIGSERIAL PRIMARY KEY,
    post_id        UUID NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    alarm_id       UUID,
    started_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at    TIMESTAMPTZ,
    status         sync_status,
    records_sent   INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    error_msg      TEXT
);

-- Адмін за замовчуванням (пароль: Admin1234!)
INSERT INTO users (username, email, password_hash, role)
VALUES (
    'admin',
    'admin@rms.local',
    '$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW',
    'admin'
) ON CONFLICT (username) DO NOTHING;
