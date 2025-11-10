-- Create database if not exists
CREATE DATABASE IF NOT EXISTS newsdb;

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For fuzzy text search

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE newsdb TO newsuser;