from sqlalchemy import Column, Integer, String, DateTime, create_engine  # type: ignore
from sqlalchemy.sql import func  # type: ignore
from sqlalchemy.orm import DeclarativeBase

DB_connect = "postgresql+psycopg2://myuser:password@localhost/postgres"

class Base(DeclarativeBase):
    pass


class Images(Base):  # type: ignore
    __tablename__ = "Images"

    id = Column(Integer, primary_key=True)
    Url = Column(String)
    CreateDate = Column(DateTime(timezone=True), server_default=func.now())


if __name__ == "__main__":
    engine = create_engine(DB_connect, echo=True, future=True)
    Base.metadata.create_all(engine)
