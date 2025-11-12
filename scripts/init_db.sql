-- All-Thing-Eye Database Initialization Script
-- This script is run when PostgreSQL container is first created

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm"; -- For text search

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE allthingeye TO allthingeye;

-- Create schemas (if needed for future organization)
-- CREATE SCHEMA IF NOT EXISTS analytics;
-- CREATE SCHEMA IF NOT EXISTS reports;

-- Tables will be created by SQLAlchemy/Alembic migrations
-- This script is just for initial database setup

