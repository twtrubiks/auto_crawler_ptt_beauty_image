from __future__ import annotations
import schedule  # type: ignore
import time  # type: ignore
import datetime
from sqlalchemy import create_engine  # type: ignore
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session  # type: ignore
from dbModel import DB_connect
from crawler import PttSpider, ArticleInfo, Download
from typing import Tuple


def connect_db(db_string: str) -> Tuple[Engine, Session]:
    engine: Engine = create_engine(db_string)
    return sessionmaker(engine)


def main(crawler_pages: int = 2) -> None:
    session = connect_db(DB_connect)
    board: str
    page_term: int
    push_rate: int
    # python app.py [版名] [爬幾頁] [推文多少以上]
    board, page_term, push_rate = "beauty", crawler_pages, 10
    spider = PttSpider(board=board, parser_page=page_term, push_rate=push_rate)
    spider.run()

    with session() as session:
        ArticleInfo.write_data_to_db(spider.info, session)

    # download images
    # crawler_datetime = datetime.datetime.now()
    # crawler_time = f"{spider.board}_PttImg_{crawler_datetime:%Y%m%d%H%M%S}"
    # data = ArticleInfo.data_process(spider.info, crawler_time)
    # download = Download(data)
    # download.run()

    # disconnect
    # session.close()
    # engine.dispose()


if __name__ == "__main__":
    main()

    # schedule.every(30).minutes.do(main)
    # while True:
    #     schedule.run_pending()
    #     time.sleep(1)
