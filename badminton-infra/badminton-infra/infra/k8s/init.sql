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

ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(32) DEFAULT 'member';
ALTER TABLE courts ADD COLUMN IF NOT EXISTS location VARCHAR(255);
ALTER TABLE courts ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS cost DOUBLE PRECISION DEFAULT 0.0;

INSERT INTO users (phone, email, name, role)
VALUES
  ('+10000000000', 'admin@example.com', 'Demo Admin', 'admin'),
  ('+10000000001', 'user@example.com', 'Demo User', 'member'),
  ('+31611111111', 'maya@example.com', 'Maya Janssen', 'member'),
  ('+31622222222', 'sam@example.com', 'Sam de Vries', 'member'),
  ('+31633333333', 'lina@example.com', 'Lina Bakker', 'member')
ON CONFLICT (phone) DO UPDATE SET
  email = EXCLUDED.email,
  name = EXCLUDED.name,
  role = EXCLUDED.role;

INSERT INTO courts (name, location, description, hourly_rate, is_active)
SELECT 'Court 1', 'Nieuwegein Sports Centre', 'Main indoor badminton court near reception', 25.0, TRUE
WHERE NOT EXISTS (SELECT 1 FROM courts WHERE name = 'Court 1');

INSERT INTO courts (name, location, description, hourly_rate, is_active)
SELECT 'Court 2', 'Nieuwegein Sports Centre', 'Second indoor court for doubles practice', 22.5, TRUE
WHERE NOT EXISTS (SELECT 1 FROM courts WHERE name = 'Court 2');

INSERT INTO courts (name, location, description, hourly_rate, is_active)
SELECT 'Training Court', 'Nieuwegein Sports Centre', 'Smaller court for warmups and junior sessions', 18.0, TRUE
WHERE NOT EXISTS (SELECT 1 FROM courts WHERE name = 'Training Court');

INSERT INTO family_members (user_id, name, relationship)
SELECT u.id, 'Noah Janssen', 'Child'
FROM users u
WHERE u.phone = '+31611111111'
  AND NOT EXISTS (SELECT 1 FROM family_members fm WHERE fm.user_id = u.id AND fm.name = 'Noah Janssen');

INSERT INTO family_members (user_id, name, relationship)
SELECT u.id, 'Eva Janssen', 'Partner'
FROM users u
WHERE u.phone = '+31611111111'
  AND NOT EXISTS (SELECT 1 FROM family_members fm WHERE fm.user_id = u.id AND fm.name = 'Eva Janssen');

INSERT INTO family_members (user_id, name, relationship)
SELECT u.id, 'Mila de Vries', 'Child'
FROM users u
WHERE u.phone = '+31622222222'
  AND NOT EXISTS (SELECT 1 FROM family_members fm WHERE fm.user_id = u.id AND fm.name = 'Mila de Vries');

INSERT INTO play_availability_votes (user_id, play_date, available, attendee_count, notes)
SELECT u.id, to_char((CURRENT_DATE + ((6 - EXTRACT(DOW FROM CURRENT_DATE)::int + 7) % 7))::date, 'YYYY-MM-DD'), TRUE, 3, 'Can play after lunch'
FROM users u
WHERE u.phone = '+31611111111'
ON CONFLICT (user_id, play_date) DO UPDATE SET
  available = EXCLUDED.available,
  attendee_count = EXCLUDED.attendee_count,
  notes = EXCLUDED.notes,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO play_availability_votes (user_id, play_date, available, attendee_count, notes)
SELECT u.id, to_char((CURRENT_DATE + ((6 - EXTRACT(DOW FROM CURRENT_DATE)::int + 7) % 7))::date, 'YYYY-MM-DD'), TRUE, 2, 'Prefers morning'
FROM users u
WHERE u.phone = '+31622222222'
ON CONFLICT (user_id, play_date) DO UPDATE SET
  available = EXCLUDED.available,
  attendee_count = EXCLUDED.attendee_count,
  notes = EXCLUDED.notes,
  updated_at = CURRENT_TIMESTAMP;

INSERT INTO play_availability_votes (user_id, play_date, available, attendee_count, notes)
SELECT u.id, to_char((CURRENT_DATE + ((7 - EXTRACT(DOW FROM CURRENT_DATE)::int) % 7))::date, 'YYYY-MM-DD'), TRUE, 1, 'Sunday works'
FROM users u
WHERE u.phone = '+31633333333'
ON CONFLICT (user_id, play_date) DO UPDATE SET
  available = EXCLUDED.available,
  attendee_count = EXCLUDED.attendee_count,
  notes = EXCLUDED.notes,
  updated_at = CURRENT_TIMESTAMP;


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
FROM settled_bookings
ON CONFLICT (booking_id) DO UPDATE SET
  total_amount = EXCLUDED.total_amount,
  split_count = EXCLUDED.split_count,
  status = 'settled';

DO $$
DECLARE
  court_one_id INTEGER;
  court_two_id INTEGER;
  training_court_id INTEGER;
  booking_one_id INTEGER;
  booking_two_id INTEGER;
BEGIN
  SELECT id INTO court_one_id FROM courts WHERE name = 'Court 1' LIMIT 1;
  SELECT id INTO court_two_id FROM courts WHERE name = 'Court 2' LIMIT 1;
  SELECT id INTO training_court_id FROM courts WHERE name = 'Training Court' LIMIT 1;

  IF court_one_id IS NOT NULL
    AND NOT EXISTS (
      SELECT 1 FROM bookings
      WHERE court_id = court_one_id
        AND booking_date = to_char(CURRENT_DATE + INTERVAL '1 day', 'YYYY-MM-DD')
        AND start_time = '19:00'
        AND end_time = '20:00'
    )
  THEN
    INSERT INTO bookings (court_id, booking_date, start_time, end_time, cost, notes, status)
    VALUES (court_one_id, to_char(CURRENT_DATE + INTERVAL '1 day', 'YYYY-MM-DD'), '19:00', '20:00', 25.0, 'Evening doubles practice', 'confirmed')
    RETURNING id INTO booking_one_id;

    INSERT INTO booking_participants (booking_id, phone)
    VALUES
      (booking_one_id, '+31611111111'),
      (booking_one_id, '+31622222222');

    INSERT INTO invoices (booking_id, total_amount, split_count, status)
    VALUES (booking_one_id, 25.0, 2, 'generated')
    ON CONFLICT (booking_id) DO NOTHING;
  END IF;

  IF court_two_id IS NOT NULL
    AND NOT EXISTS (
      SELECT 1 FROM bookings
      WHERE court_id = court_two_id
        AND booking_date = to_char(CURRENT_DATE + INTERVAL '3 days', 'YYYY-MM-DD')
        AND start_time = '10:00'
        AND end_time = '12:00'
    )
  THEN
    INSERT INTO bookings (court_id, booking_date, start_time, end_time, cost, notes, status)
    VALUES (court_two_id, to_char(CURRENT_DATE + INTERVAL '3 days', 'YYYY-MM-DD'), '10:00', '12:00', 45.0, 'Weekend family session', 'confirmed')
    RETURNING id INTO booking_two_id;

    INSERT INTO booking_participants (booking_id, phone)
    VALUES
      (booking_two_id, '+31611111111'),
      (booking_two_id, '+31633333333');
  END IF;

  IF training_court_id IS NOT NULL
    AND NOT EXISTS (
      SELECT 1 FROM bookings
      WHERE court_id = training_court_id
        AND booking_date = to_char(CURRENT_DATE + INTERVAL '7 days', 'YYYY-MM-DD')
        AND start_time = '18:30'
        AND end_time = '19:30'
    )
  THEN
    INSERT INTO bookings (court_id, booking_date, start_time, end_time, cost, notes, status)
    VALUES (training_court_id, to_char(CURRENT_DATE + INTERVAL '7 days', 'YYYY-MM-DD'), '18:30', '19:30', 18.0, 'Junior warmup slot', 'confirmed');
  END IF;
END $$;
