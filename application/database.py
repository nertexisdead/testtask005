import os

from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


engine = create_engine(
    URL.create(
        "postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["DB_HOST"],
        database=os.environ["POSTGRES_DB"],
    ),
    pool_pre_ping=True,
)
Session = sessionmaker(engine)
