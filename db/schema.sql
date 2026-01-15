-- =========================
-- Studio8 Backend Schema
-- =========================

CREATE TABLE IF NOT EXISTS clients (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_code TEXT UNIQUE NOT NULL,
  full_name TEXT NOT NULL,
  pin_hash TEXT NOT NULL,
  status TEXT CHECK(status IN ('ACTIVE','INACTIVE','PENDING','EXPIRED')) DEFAULT 'PENDING',
  date_registered DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS memberships (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL,
  plan_type TEXT CHECK(plan_type IN ('MONTHLY','TRANSIENT','ANNUAL')),
  credits INTEGER DEFAULT 0,
  start_date DATE,
  end_date DATE,
  active INTEGER DEFAULT 1,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL,
  service TEXT,
  login_time DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL,
  amount REAL,
  method TEXT,
  proof_file TEXT,
  verified INTEGER DEFAULT 0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(client_id) REFERENCES clients(id)
);
