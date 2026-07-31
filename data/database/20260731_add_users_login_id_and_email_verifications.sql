-- Apply this migration to the existing dabom database once.
-- Do NOT run init_schema.sql in production: it drops the entire database.

USE dabom;

ALTER TABLE users
  ADD COLUMN login_id VARCHAR(20) NULL AFTER email;

-- Existing users receive a deterministic temporary ID based on their already
-- unique employee number. New users choose their own ID during registration.
UPDATE users
SET login_id = CONCAT('emp', employee_number)
WHERE login_id IS NULL;

ALTER TABLE users
  MODIFY COLUMN login_id VARCHAR(20) NOT NULL,
  ADD UNIQUE KEY UK_USERS_LOGIN_ID (login_id),
  ADD KEY IDX_USERS_LOGIN_ID (login_id);

CREATE TABLE email_verifications (
  verification_id CHAR(36) NOT NULL,
  email VARCHAR(100) NOT NULL,
  code_hash CHAR(64) NOT NULL,
  expires_at DATETIME NOT NULL,
  attempts TINYINT UNSIGNED NOT NULL DEFAULT 0,
  verified_at DATETIME DEFAULT NULL,
  consumed_at DATETIME DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (verification_id),
  KEY IDX_EMAIL_VERIFICATIONS_EMAIL_CREATED (email, created_at),
  KEY IDX_EMAIL_VERIFICATIONS_EMAIL_STATE (email, verified_at, consumed_at, expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
