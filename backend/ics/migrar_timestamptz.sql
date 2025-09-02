BEGIN;

-- FICHAJES
ALTER TABLE fichajes
  ALTER COLUMN timestamp TYPE timestamptz
    USING (timestamp AT TIME ZONE 'UTC'),
  ALTER COLUMN timestamp SET NOT NULL,
  ALTER COLUMN timestamp SET DEFAULT now();

CREATE INDEX IF NOT EXISTS ix_fichajes_timestamp ON fichajes (timestamp);

-- LOGS
ALTER TABLE logs
  ALTER COLUMN timestamp TYPE timestamptz
    USING (timestamp AT TIME ZONE 'UTC'),
  ALTER COLUMN timestamp SET NOT NULL,
  ALTER COLUMN timestamp SET DEFAULT now();

CREATE INDEX IF NOT EXISTS ix_logs_timestamp ON logs (timestamp);

-- SOLICITUDES
ALTER TABLE solicitudes
  ALTER COLUMN timestamp TYPE timestamptz,
  ALTER COLUMN timestamp SET NOT NULL,
  ALTER COLUMN timestamp SET DEFAULT now();

COMMIT;
