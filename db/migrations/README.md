# Alembic migrations

Initialize with:

    uv run alembic init migrations

then point `sqlalchemy.url` at the EDS database (env var
`EDS_DATABASE_URL`) and autogenerate the first revision from
`db.models`.
