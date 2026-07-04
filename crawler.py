from collections.abc import Iterator
import sqlalchemy  # type: ignore
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
import sys
import concurrent.futures
import requests
import os
import logging
from bs4 import BeautifulSoup  # type: ignore
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dbModel import Images

logging.basicConfig(level=logging.WARNING)

REQUEST_TIMEOUT: int = 15
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class CrawlerError(Exception):
    """爬蟲執行期間可預期的錯誤，訊息可直接顯示給使用者。"""


def _build_session() -> requests.Session:
    session = requests.session()
    retry = Retry(
        total=5,
        connect=5,
        read=3,
        backoff_factor=1.5,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset(["GET", "HEAD", "POST"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({"User-Agent": USER_AGENT})
    return session


class PttSpider:
    rs: requests.Session = _build_session()
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
        self._articles: list["ArticleInfo"] = []

    @property
    def info(self) -> list["ArticleInfo"]:
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

    def check_board(self) -> BeautifulSoup:
        print("check board......")
        if self._board:
            return self.check_board_over18()
        else:
            print("請輸入看版名稱")
            sys.exit()

    def check_board_over18(self) -> BeautifulSoup:
        self.rs.cookies.set("over18", "1", domain="www.ptt.cc")
        try:
            res: requests.Response = self.rs.get(
                f"{self.ptt_head}/{self.ptt_middle}/{self._board}/index.html",
                timeout=REQUEST_TIMEOUT,
            )
            res.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            logging.warning(
                f"HTTP error {exc.response.status_code} - {exc.response.reason}"
            )
            raise CrawlerError(
                f"無法開啟看板 {self._board}"
                f"（HTTP {exc.response.status_code} {exc.response.reason}），"
                "請確認看板名稱是否正確"
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            logging.error(f"Connection error on check_board_over18: {exc}")
            raise CrawlerError(f"連線 www.ptt.cc 失敗：{exc}") from exc
        return BeautifulSoup(res.text, "html.parser")

    def parser_index(self) -> Iterator[str]:
        print("parser index......")
        max_page: int = self.get_max_page(self._soup.select(".btn.wide")[1]["href"])
        return (
            f"{self.ptt_head}/{self.ptt_middle}/{self._board}/index{page}.html"
            for page in range(max_page - self.parser_page + 1, max_page + 1, 1)
        )

    def parser_per_article_url(self) -> list["ArticleInfo"]:
        print("parser per article url......")
        articles: list["ArticleInfo"] = []
        for page in self._index_seqs:
            try:
                res: requests.Response = self.rs.get(
                    page, timeout=REQUEST_TIMEOUT
                )
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
                    f"{self.ptt_head}{article.url}",
                    timeout=REQUEST_TIMEOUT,
                )
                res.raise_for_status()
            except requests.exceptions.TooManyRedirects:
                logging.warning(f"Too many redirects for article: {self.ptt_head}{article.url}, skipping...")
                continue  # Skip the current iteration and move to the next article
            except requests.exceptions.HTTPError as exc:
                logging.warning(
                    f"HTTP error {exc.response.status_code} - {exc.response.reason}"
                )
            except requests.exceptions.ConnectionError:
                logging.error("Connection error")
            else:
                article.res = res  # type: ignore

    def crawler_img_urls(self) -> None:
        for data in self._articles:
            if not getattr(data, "res", None):
                continue
            soup: BeautifulSoup = BeautifulSoup(data.res.text, "html.parser")  # type: ignore
            # 抓取圖片URL(img tag )
            for img in soup.find_all("a", rel="nofollow"):
                data.img_urls += self.image_url(img["href"])

    @staticmethod
    def image_url(link: str) -> list[str]:
        # 不抓相簿 和 .gif
        if (
            ("imgur.com/a/" in link)
            or ("imgur.com/gallery/" in link)
            or (".gif" in link)
        ):
            return []
        # 符合圖片格式的網址
        images_format: list[str] = [".jpg", ".png", ".jpeg"]
        for image in images_format:
            if link.endswith(image):
                return [link]
        # 有些網址會沒有檔案格式， "https://imgur.com/xxx"
        if "imgur" in link:
            return [f"{link}.jpg"]
        return []

    @staticmethod
    def crawler_info(res: requests.Response, push_rate: int) -> list["ArticleInfo"]:
        logging.debug(f"crawler_info......{res.url}")
        soup: BeautifulSoup = BeautifulSoup(res.text, "html.parser")
        articles: list["ArticleInfo"] = []
        for r_ent in soup.find_all(class_="r-ent"):
            try:
                # 先得到每篇文章的 url
                url: str = r_ent.find("a")["href"]
                if not url:
                    continue
                title: str = r_ent.find(class_="title").text.strip()
                rate_text: str = r_ent.find(class_="nrec").text
                author: str = r_ent.find(class_="author").text
                rate: int | str

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
        self.img_urls: list[str] = []

    @staticmethod
    def data_process(
        info: list["ArticleInfo"], crawler_time: str
    ) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        for data in info:
            if not data.img_urls:
                continue
            name: str = ArticleInfo.remove_special_char(data.title, r'\/:*?"<>|.')
            dir_name: str = f"{name}_{data.rate}" if data.rate else ""
            relative_path: str = os.path.join(crawler_time, dir_name)
            path: str = os.path.abspath(relative_path)
            try:
                os.makedirs(path, exist_ok=True)
            except OSError as e:
                logging.warning(e)
                continue
            result += [(img_url, path) for img_url in data]
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
        articles: list["ArticleInfo"], session: sqlalchemy.orm.Session
    ) -> None:
        urls: set[str] = {image for article in articles for image in article}
        if not urls:
            return
        # 一次撈出已存在的 URL（取代逐筆 SELECT 的 N+1 查詢）
        statement = select(Images.Url).where(Images.Url.in_(urls))
        existing: set[str] = set(session.scalars(statement))
        new_urls: set[str] = urls - existing
        if new_urls:
            # ON CONFLICT DO NOTHING：兩個排程重疊時靠 unique constraint 擋掉重複
            session.execute(
                pg_insert(Images)
                .values([{"Url": url} for url in new_urls])
                .on_conflict_do_nothing()
            )
        session.commit()


class Download:
    rs: requests.Session = requests.session()

    def __init__(self, info: list[tuple[str, str]]) -> None:
        self.info: list[tuple[str, str]] = info

    def run(self) -> None:
        with concurrent.futures.ProcessPoolExecutor() as executor:
            executor.map(self.download, self.info)

    def download(self, image_info: tuple[str, str]) -> None:
        url: str
        path: str
        url, path = image_info
        try:
            res_img: requests.Response = self.rs.get(
                url, stream=True, timeout=REQUEST_TIMEOUT
            )
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
