-- Esquema de referência MySQL 8.4. A instalação executa python -m app.db migrate
-- para utilizar os mesmos modelos SQLAlchemy. Charset: utf8mb4.
CREATE TABLE IF NOT EXISTS event_settings (
 id INTEGER NOT NULL PRIMARY KEY, venue VARCHAR(240), edit_deadline_utc DATETIME,
 buffet_limit INTEGER NOT NULL DEFAULT 40
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS families (
 id VARCHAR(36) PRIMARY KEY, contact_name VARCHAR(160) NOT NULL,
 attending BOOL NOT NULL, revision INTEGER NOT NULL,
 submission_key_hash VARCHAR(64) NOT NULL UNIQUE,
 payload_hash VARCHAR(64) NOT NULL, edit_token_hash VARCHAR(64) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS participants (
 id INTEGER NOT NULL AUTO_INCREMENT PRIMARY KEY,
 family_id VARCHAR(36) NOT NULL, position INTEGER NOT NULL,
 name VARCHAR(160) NOT NULL, kind VARCHAR(12) NOT NULL,
 age_years INTEGER NULL,
 CONSTRAINT uq_family_position UNIQUE (family_id, position),
 CONSTRAINT fk_participants_family FOREIGN KEY (family_id)
 REFERENCES families(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY)
 ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT IGNORE INTO schema_migrations (version) VALUES (1);
INSERT IGNORE INTO event_settings (id, venue, edit_deadline_utc, buffet_limit)
 VALUES (1, NULL, NULL, 40);
