from sqlalchemy.sql import func
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
DB_connect = 'postgresql+psycopg2://postgres:PASSWORD@localhost/database_name'


class Images(Base):
    __tablename__ = 'Images'

    id = Column(Integer, primary_key=True)
    Url = Column(String)
    CreateDate = Column(DateTime(timezone=True), server_default=func.now())


if __name__ == '__main__':
    engine = create_engine(DB_connect)
    session = sessionmaker()
    session.configure(bind=engine)
    Base.metadata.create_all(engine)
