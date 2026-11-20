from alembic import context

import campaigns  # Register the ORM models.
from database import Base, engine

with engine.connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
