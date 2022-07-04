from __future__ import annotations
import schedule  # type: ignore
import time  # type: ignore
import datetime
import sqlalchemy  # type: ignore
from sqlalchemy import create_engine  # type: ignore
from sqlalchemy.orm import sessionmaker  # type: ignore
from dbModel import DB_connect
from crawler import PttSpider, ArticleInfo, Download
from typing import Tuple


def connect_db(db_string: str) -> Tuple[sqlalchemy.orm.Engine, sqlalchemy.orm.Session]:
    engine: sqlalchemy.orm.Engine = create_engine(db_string)
    db_session = sessionmaker(bind=engine)
    session = db_session()
    return engine, session


def main(crawler_pages: int = 2) -> None:
    engine, session = connect_db(DB_connect)
    board: str
    page_term: int
    push_rate: int
    # python beauty_spider2.py [版名] [爬幾頁] [推文多少以上]
    board, page_term, push_rate = "beauty", crawler_pages, 10
    spider = PttSpider(board=board, parser_page=page_term, push_rate=push_rate)
    spider.run()
    ArticleInfo.write_data_to_db(spider.info, session)

    # download images
    # crawler_datetime = datetime.datetime.now()
    # crawler_time = f"{spider.board}_PttImg_{crawler_datetime:%Y%m%d%H%M%S}"
    # data = ArticleInfo.data_process(spider.info, crawler_time)
    # download = Download(data)
    # download.run()

    # disconnect
    session.close()
    engine.dispose()


if __name__ == "__main__":
    main()

    # schedule.every(30).minutes.do(main)
    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)
