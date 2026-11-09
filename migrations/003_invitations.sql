-- V3: convites pré-gerados. Não altera nem apaga confirmações existentes.
CREATE TABLE IF NOT EXISTS invitations (
 id VARCHAR(36) NOT NULL PRIMARY KEY,
 family_name VARCHAR(160) NOT NULL,
 contact_name VARCHAR(160) NOT NULL,
 whatsapp VARCHAR(16) NOT NULL,
 expected_guests INTEGER NOT NULL,
 token_hash VARCHAR(64) NOT NULL UNIQUE,
 status VARCHAR(24) NOT NULL DEFAULT 'LINK_GENERATED',
 created_at_utc DATETIME NOT NULL,
 sent_at_utc DATETIME NULL,
 revoked_at_utc DATETIME NULL,
 linked_family_id VARCHAR(36) NULL UNIQUE,
 CONSTRAINT fk_invitations_family FOREIGN KEY (linked_family_id)
 REFERENCES families(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
INSERT IGNORE INTO schema_migrations (version) VALUES (3);
