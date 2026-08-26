-- Extend user_role enum to include admin
-- Postgres requires a new value to be added to an existing enum
alter type user_role add value if not exists 'admin';
