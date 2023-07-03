from __future__ import annotations
from typing import List, Dict, Tuple, Optional, Iterator, Union
from sqlalchemy import select
from sqlalchemy.orm import Session # type: ignore
import sys
import concurrent.futures
import requests
import urllib3
import os
import logging
import uuid
from bs4 import BeautifulSoup  # type: ignore
from dbModel import Images

urllib3.disable_warnings()
logging.basicConfig(level=logging.WARNING)


class PttSpider:
    rs: requests.Session = requests.session()
    ptt_head: str = "https://www.ptt.cc"
    ptt_middle: str = "bbs"
    parser_page_count: int = 5
    push_rate: int = 10

    def __init__(self, **kwargs) -> None:
        self._board: str = kwargs.get("board", None)
        self.parser_page: int = int(kwargs.get("parser_page", self.parser_page_count))
        self.push_rate: int = int(kwargs.get("push_rate", self.push_rate))

        self._soup: BeautifulSoup = None
        self._index_seqs: Iterator[str] = None  # type: ignore
        self._articles: List[ArticleInfo] = []

    @property
    def info(self) -> List[ArticleInfo]:
        return self._articles

    @property
    def board(self) -> str:
        return self._board.capitalize()

    def run(self) -> None:
        self._soup = self.check_board()
        self._index_seqs = self.parser_index()
        self._articles = self.parser_per_article_url()
        self.analyze_articles()
        self.crawler_img_urls()

    def run_specific_article(self, article) -> None:
        self._board = article.url.split("/")[-2]
        self.check_board_over18()
        self._articles = [article]
        self.analyze_articles()
        self.crawler_img_urls(True)

    def check_board(self) -> Optional[BeautifulSoup]:
        print("check board......")
        if self._board:
            return self.check_board_over18()
        else:
            print("請輸入看版名稱")
            sys.exit()

    def check_board_over18(self) -> Optional[BeautifulSoup]:
        load: Dict[str, str] = {
            "from": f"/{self.ptt_middle}/{self._board}/index.html",
            "yes": "yes",
        }
        try:
            res: requests.Response = self.rs.post(
                f"{self.ptt_head}/ask/over18", verify=False, data=load
            )
            res.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            logging.warning(
                f"HTTP error {exc.response.status_code} - {exc.response.reason}"
            )
            raise Exception("網頁有問題")
        return BeautifulSoup(res.text, "html.parser")

    def parser_index(self) -> Iterator[str]:
        print("parser index......")
        max_page: int = self.get_max_page(self._soup.select(".btn.wide")[1]["href"])
        return (
            f"{self.ptt_head}/{self.ptt_middle}/{self._board}/index{page}.html"
            for page in range(max_page - self.parser_page + 1, max_page + 1, 1)
        )

    def parser_per_article_url(self) -> List[ArticleInfo]:
        print("parser per article url......")
        articles: List[ArticleInfo] = []
        for page in self._index_seqs:
            try:
                res: requests.Response = self.rs.get(page, verify=False)
                res.raise_for_status()
            except requests.exceptions.HTTPError as exc:
                logging.warning(
                    f"HTTP error {exc.response.status_code} - {exc.response.reason}"
                )
            except requests.exceptions.ConnectionError:
                logging.error("Connection error")
            else:
                articles += self.crawler_info(res, self.push_rate)
        return articles

    def analyze_articles(self) -> None:
        for article in self._articles:
            try:
                logging.debug(f"{self.ptt_head}{article.url} ing......")
                res: requests.Response = self.rs.get(
                    f"{self.ptt_head}{article.url}", verify=False
                )
                res.raise_for_status()
            except requests.exceptions.HTTPError as exc:
                logging.warning(
                    f"HTTP error {exc.response.status_code} - {exc.response.reason}"
                )
            except requests.exceptions.ConnectionError:
                logging.error("Connection error")
            else:
                article.res = res  # type: ignore

    def crawler_img_urls(self, is_content_parser=False) -> None:
        for data in self._articles:
            print("crawler image urls......")
            soup: BeautifulSoup = BeautifulSoup(data.res.text, "html.parser")  # type: ignore
            title: str = str(uuid.uuid4())
            if is_content_parser:
                # 避免有些文章會被使用者自行刪除標題列
                try:
                    title = soup.select(".article-meta-value")[2].text
                except Exception as e:
                    logging.debug("自行刪除標題列:", e)
                finally:
                    data.title = title

            # 抓取圖片URL(img tag )
            for img in soup.find_all("a", rel="nofollow"):
                data.img_urls += self.image_url(img["href"])

    @staticmethod
    def image_url(link: str) -> List[str]:
        # 不抓相簿 和 .gif
        if (
            ("imgur.com/a/" in link)
            or ("imgur.com/gallery/" in link)
            or (".gif" in link)
        ):
            return []
        # 符合圖片格式的網址
        images_format: List[str] = [".jpg", ".png", ".jpeg"]
        for image in images_format:
            if link.endswith(image):
                return [link]
        # 有些網址會沒有檔案格式， "https://imgur.com/xxx"
        if "imgur" in link:
            return [f"{link}.jpg"]
        return []

    @staticmethod
    def crawler_info(res: requests.Response, push_rate: int) -> List[ArticleInfo]:
        logging.debug(f"crawler_info......{res.url}")
        soup: BeautifulSoup = BeautifulSoup(res.text, "html.parser")
        articles: List[ArticleInfo] = []
        for r_ent in soup.find_all(class_="r-ent"):
            try:
                # 先得到每篇文章的 url
                url: str = r_ent.find("a")["href"]
                if not url:
                    continue
                title: str = r_ent.find(class_="title").text.strip()
                rate_text: str = r_ent.find(class_="nrec").text
                author: str = r_ent.find(class_="author").text
                rate: Union[int, str]

                if "公告" in title:
                    continue

                if rate_text:
                    if rate_text.startswith("爆"):
                        rate = 100
                    elif rate_text.startswith("X"):
                        rate = -1 * int(rate_text[1])
                    else:
                        rate = rate_text
                else:
                    rate = 0

                # 比對推文數
                if int(rate) >= push_rate:
                    articles.append(
                        ArticleInfo(title=title, author=author, url=url, rate=rate)
                    )
            except Exception as e:
                logging.debug("本文已被刪除")
                logging.debug(e)
        return articles

    @staticmethod
    def get_max_page(content: str) -> int:
        start_index: int = content.find("index")
        end_index: int = content.find(".html")
        page_number: str = content[start_index + 5 : end_index]
        return int(page_number) + 1


class ArticleInfo:
    def __init__(self, **kwargs) -> None:
        self.title: str = kwargs.get("title", None)
        self.author: str = kwargs.get("author", None)
        self.url: str = kwargs.get("url", None)
        self.rate: int = kwargs.get("rate", None)
        self.img_urls: List[str] = []

    @staticmethod
    def data_process(
        info: List[ArticleInfo], crawler_time: str
    ) -> List[Tuple[str, str]]:
        result: List[Tuple[str, str]] = []
        for data in info:
            if not data.img_urls:
                continue
            name: str = ArticleInfo.remove_special_char(data.title, '\/:*?"<>|.')
            dir_name: str = f"{name}_{data.rate}" if data.rate else ""
            relative_path: str = os.path.join(crawler_time, dir_name)
            path: str = os.path.abspath(relative_path)
            try:
                if not os.path.exists(path):
                    os.makedirs(path)
                    result += [(img_url, path) for img_url in data]
            except Exception as e:
                logging.warning(e)
        return result

    @staticmethod
    def remove_special_char(value: str, deletechars: str) -> str:
        # 移除特殊字元（移除Windows上無法作為資料夾的字元）
        for c in deletechars:
            value = value.replace(c, "")
        return value.rstrip()

    def __iter__(self) -> Iterator[str]:
        for url in self.img_urls:
            yield url

    @staticmethod
    def write_data_to_db(
        articles: List[ArticleInfo], session: Session
    ) -> None:
        for article in articles:
            for image in article:
                statement = select(Images).filter_by(Url=image)
                is_exist = session.execute(statement).fetchone()
                if not is_exist:
                    data: Images = Images(Url=image)
                    session.add(data)
        session.commit()


class Download:
    rs: requests.Session = requests.session()

    def __init__(self, info: List[Tuple[str, str]]) -> None:
        self.info: List[Tuple[str, str]] = info

    def run(self) -> None:
        with concurrent.futures.ProcessPoolExecutor() as executor:
            executor.map(self.download, self.info)

    def download(self, image_info: Tuple[str, str]) -> None:
        url: str
        path: str
        url, path = image_info
        try:
            res_img: requests.Response = self.rs.get(url, stream=True, verify=False)
            logging.debug(f"download image {url} ......")
            res_img.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            logging.warning(
                f"HTTP error {exc.response.status_code} - {exc.response.reason}"
            )
            logging.warning(url)
        except requests.exceptions.ConnectionError:
            logging.error("Connection error")
        else:
            file_path: str = os.path.join(path, url.split("/")[-1])
            try:
                with open(file_path, "wb") as out_file:
                    out_file.write(res_img.content)
            except Exception as e:
                logging.warning(e)
