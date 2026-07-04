CREATE TABLE IF NOT EXISTS users (
  id SERIAL PRIMARY KEY,
  phone VARCHAR(64) NOT NULL UNIQUE,
  email VARCHAR(255),
  name VARCHAR(128),
  role VARCHAR(32) DEFAULT 'member',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS courts (
  id SERIAL PRIMARY KEY,
  name VARCHAR(64) NOT NULL,
  location VARCHAR(255),
  description TEXT,
  hourly_rate DOUBLE PRECISION DEFAULT 25.0,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS bookings (
  id SERIAL PRIMARY KEY,
  court_id INTEGER NOT NULL REFERENCES courts(id),
  booking_date VARCHAR(10) NOT NULL,
  start_time VARCHAR(5) NOT NULL,
  end_time VARCHAR(5) NOT NULL,
  cost DOUBLE PRECISION DEFAULT 0.0,
  notes TEXT,
  status VARCHAR(32) DEFAULT 'confirmed',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS booking_participants (
  id SERIAL PRIMARY KEY,
  booking_id INTEGER NOT NULL REFERENCES bookings(id),
  phone VARCHAR(64) NOT NULL,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS invoices (
  id SERIAL PRIMARY KEY,
  booking_id INTEGER NOT NULL UNIQUE REFERENCES bookings(id),
  total_amount DOUBLE PRECISION DEFAULT 0.0,
  split_count INTEGER DEFAULT 1,
  status VARCHAR(32) DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS family_members (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  name VARCHAR(128) NOT NULL,
  relationship VARCHAR(64),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS play_availability_votes (
  id SERIAL PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id),
  play_date VARCHAR(10) NOT NULL,
  available BOOLEAN DEFAULT FALSE,
  attendee_count INTEGER DEFAULT 0,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT uq_play_availability_user_date UNIQUE (user_id, play_date)
);

CREATE TABLE IF NOT EXISTS admin_audit_logs (
  id SERIAL PRIMARY KEY,
  occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
  admin_user_id INTEGER REFERENCES users(id),
  admin_name VARCHAR(255),
  admin_email VARCHAR(255),
  admin_phone VARCHAR(64),
  event_type VARCHAR(64) NOT NULL,
  entity_type VARCHAR(64) NOT NULL,
  entity_id VARCHAR(64),
  summary VARCHAR(512) NOT NULL,
  details TEXT
);

CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_occurred_at ON admin_audit_logs (occurred_at);
CREATE INDEX IF NOT EXISTS ix_admin_audit_logs_entity ON admin_audit_logs (entity_type, entity_id);

ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(32) DEFAULT 'member';
ALTER TABLE courts ADD COLUMN IF NOT EXISTS location VARCHAR(255);
ALTER TABLE courts ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS cost DOUBLE PRECISION DEFAULT 0.0;

-- Historical invoiced bookings are inserted as completed bookings with settled invoices
-- so they appear on the Costs page without changing the booking schema.
INSERT INTO courts (name, location, description, hourly_rate, is_active)
SELECT court_name, court_name, 'Historical booking location', hourly_rate, TRUE
FROM (VALUES
  ('Gymzaal de Driemaster', 19.25),
  ('Sportzaal De Sluis', 25.50),
  ('Sportzaal Wijkersloot', 25.50),
  ('Gymzaal de Triangel', 19.25)
) AS historical_courts(court_name, hourly_rate)
WHERE NOT EXISTS (SELECT 1 FROM courts WHERE courts.name = historical_courts.court_name);

WITH historical_bookings (booking_date, start_time, end_time, court_name, cost, created_at) AS (
  VALUES
    ('2025-10-19', '17:00', '18:30', 'Gymzaal de Driemaster', 28.88, TIMESTAMP '2025-10-12 19:19'),
    ('2025-10-26', '16:00', '18:00', 'Gymzaal de Driemaster', 38.50, TIMESTAMP '2025-10-19 18:11'),
    ('2025-11-08', '18:00', '20:00', 'Sportzaal De Sluis', 51.00, TIMESTAMP '2025-11-01 19:32'),
    ('2025-11-15', '17:30', '19:30', 'Sportzaal De Sluis', 51.00, TIMESTAMP '2025-11-08 19:48'),
    ('2025-11-23', '16:00', '18:00', 'Sportzaal Wijkersloot', 51.00, TIMESTAMP '2025-11-15 20:10'),
    ('2025-11-29', '17:00', '18:30', 'Sportzaal De Sluis', 38.25, TIMESTAMP '2025-11-24 20:48'),
    ('2025-12-06', '17:00', '19:00', 'Sportzaal Wijkersloot', 51.00, TIMESTAMP '2025-11-30 22:07'),
    ('2025-12-13', '18:00', '19:00', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2025-12-12 20:50'),
    ('2026-01-03', '17:00', '18:00', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2025-12-31 17:30'),
    ('2026-01-17', '17:00', '18:30', 'Sportzaal De Sluis', 38.25, TIMESTAMP '2026-01-15 09:43'),
    ('2026-01-24', '16:00', '17:00', 'Sportzaal De Sluis', 25.50, TIMESTAMP '2026-01-22 16:28'),
    ('2026-01-31', '17:30', '19:00', 'Sportzaal De Sluis', 38.25, TIMESTAMP '2026-01-28 08:52'),
    ('2026-02-07', '17:30', '18:30', 'Sportzaal De Sluis', 25.50, TIMESTAMP '2026-02-03 16:16'),
    ('2026-02-07', '19:00', '20:00', 'Sportzaal De Sluis', 25.50, TIMESTAMP '2026-02-03 16:18'),
    ('2026-02-14', '18:00', '19:00', 'Sportzaal De Sluis', 25.50, TIMESTAMP '2026-02-09 21:56'),
    ('2026-02-14', '19:30', '20:30', 'Sportzaal De Sluis', 25.50, TIMESTAMP '2026-02-09 21:58'),
    ('2026-02-17', '21:00', '22:00', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2026-02-15 18:54'),
    ('2026-02-21', '18:00', '19:00', 'Sportzaal De Sluis', 25.50, TIMESTAMP '2026-02-18 20:54'),
    ('2026-02-21', '19:30', '20:30', 'Sportzaal De Sluis', 25.50, TIMESTAMP '2026-02-18 20:55'),
    ('2026-02-27', '21:00', '22:00', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2026-02-24 16:21'),
    ('2026-02-28', '17:30', '18:30', 'Sportzaal De Sluis', 25.50, TIMESTAMP '2026-02-26 15:16'),
    ('2026-03-07', '20:00', '21:00', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2026-03-03 20:15'),
    ('2026-03-15', '16:30', '18:00', 'Gymzaal de Triangel', 28.88, TIMESTAMP '2026-03-10 09:04'),
    ('2026-03-21', '17:00', '18:00', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2026-03-18 17:35'),
    ('2026-03-28', '17:30', '19:00', 'Sportzaal De Sluis', 38.25, TIMESTAMP '2026-03-25 13:43'),
    ('2026-04-11', '18:00', '19:00', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2026-04-09 10:15'),
    ('2026-04-18', '18:30', '19:30', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2026-04-16 21:34'),
    ('2026-05-03', '18:00', '19:00', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2026-05-02 14:23'),
    ('2026-05-04', '18:00', '19:00', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2026-05-03 23:33'),
    ('2026-05-10', '18:30', '20:00', 'Sportzaal De Sluis', 38.25, TIMESTAMP '2026-05-09 19:59'),
    ('2026-05-16', '18:30', '19:30', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2026-05-16 13:34'),
    ('2026-06-07', '16:00', '18:00', 'Sportzaal Wijkersloot', 51.00, TIMESTAMP '2026-06-04 10:09'),
    ('2026-06-13', '17:30', '19:00', 'Sportzaal De Sluis', 38.25, TIMESTAMP '2026-06-09 20:17'),
    ('2026-06-19', '18:00', '19:00', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2026-06-19 17:33'),
    ('2026-06-20', '17:00', '18:00', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2026-06-17 20:34'),
    ('2026-06-20', '18:00', '19:00', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2026-06-18 19:01'),
    ('2026-06-26', '20:00', '21:00', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2026-06-26 09:23'),
    ('2026-06-28', '17:00', '18:00', 'Gymzaal de Driemaster', 19.25, TIMESTAMP '2026-06-27 21:00')
), historical_rows AS (
  SELECT hb.*, c.id AS court_id
  FROM historical_bookings hb
  JOIN LATERAL (SELECT id FROM courts WHERE name = hb.court_name ORDER BY id LIMIT 1) c ON TRUE
), inserted_bookings AS (
  INSERT INTO bookings (court_id, booking_date, start_time, end_time, cost, notes, status, created_at)
  SELECT hr.court_id, hr.booking_date, hr.start_time, hr.end_time, hr.cost,
         'Historical booking imported from invoiced rental data', 'completed', hr.created_at
  FROM historical_rows hr
  WHERE NOT EXISTS (
    SELECT 1
    FROM bookings existing
    WHERE existing.court_id = hr.court_id
      AND existing.booking_date = hr.booking_date
      AND existing.start_time = hr.start_time
      AND existing.end_time = hr.end_time
  )
  RETURNING id, cost
), settled_bookings AS (
  UPDATE bookings existing
  SET cost = hr.cost,
      status = 'completed'
  FROM historical_rows hr
  WHERE existing.court_id = hr.court_id
    AND existing.booking_date = hr.booking_date
    AND existing.start_time = hr.start_time
    AND existing.end_time = hr.end_time
  RETURNING existing.id, existing.cost
)
INSERT INTO invoices (booking_id, total_amount, split_count, status, created_at)
SELECT id, cost, 1, 'settled', CURRENT_TIMESTAMP
FROM inserted_bookings
UNION ALL
SELECT id, cost, 1, 'settled', CURRENT_TIMESTAMP
FROM settled_bookings
ON CONFLICT (booking_id) DO UPDATE SET
  total_amount = EXCLUDED.total_amount,
  split_count = EXCLUDED.split_count,
  status = 'settled';
