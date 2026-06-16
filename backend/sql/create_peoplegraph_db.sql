DO
$$
BEGIN
   IF NOT EXISTS (
      SELECT FROM pg_catalog.pg_roles WHERE rolname = 'admin'
   ) THEN
      CREATE ROLE admin LOGIN PASSWORD 'peoplegraph43211234';
   ELSE
      ALTER ROLE admin WITH LOGIN PASSWORD 'peoplegraph43211234';
   END IF;
END
$$;

SELECT 'CREATE DATABASE peoplegraph OWNER admin'
WHERE NOT EXISTS (
   SELECT FROM pg_database WHERE datname = 'peoplegraph'
)\gexec

GRANT ALL PRIVILEGES ON DATABASE peoplegraph TO admin;
