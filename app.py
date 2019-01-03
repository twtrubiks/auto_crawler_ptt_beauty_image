import schedule
import time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dbModel import DB_connect
from crawler import PttSpider, ArticleInfo


def connect_db(db_string):
    engine = create_engine(db_string)
    db_session = sessionmaker(bind=engine)
    session = db_session()
    return engine, session


def main(crawler_pages=2):
    engine, session = connect_db(DB_connect)
    # python beauty_spider2.py [版名]  [爬幾頁] [推文多少以上]
    board, page_term, push_rate = 'beauty', crawler_pages, 10
    spider = PttSpider(board=board,
                       parser_page=page_term,
                       push_rate=push_rate)
    spider.run()
    ArticleInfo.write_data_to_db(spider.info, session)

    # disconnect
    session.close()
    engine.dispose()


if __name__ == '__main__':
    print('main')
    main()
    schedule.every(30).minutes.do(main)
    while True:
        print('wating......')
        schedule.run_pending()
        time.sleep(1)
