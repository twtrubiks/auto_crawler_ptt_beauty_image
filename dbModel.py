import datetime
from sqlalchemy import String, DateTime, create_engine  # type: ignore
from sqlalchemy.sql import func  # type: ignore
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column  # type: ignore

DB_connect = "postgresql+psycopg2://myuser:password@localhost/postgres"


class Base(DeclarativeBase):
    pass


class Images(Base):
    __tablename__ = "Images"

    id: Mapped[int] = mapped_column(primary_key=True)
    Url: Mapped[str | None] = mapped_column(String)
    CreateDate: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


if __name__ == "__main__":
    engine = create_engine(DB_connect, echo=True, future=True)
    Base.metadata.create_all(engine)
