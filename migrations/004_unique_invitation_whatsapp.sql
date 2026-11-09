-- V4: impede duplicidade de WhatsApp inclusive em importações concorrentes.
-- Falha com segurança se já houver números duplicados; não remove nem altera registros.
CREATE UNIQUE INDEX uq_invitations_whatsapp ON invitations (whatsapp);
INSERT IGNORE INTO schema_migrations (version) VALUES (4);
