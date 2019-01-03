import sys
import concurrent.futures
import requests
import urllib3
import os
import logging
import uuid
from bs4 import BeautifulSoup
from dbModel import Images

urllib3.disable_warnings()
logging.basicConfig(level=logging.WARNING)
HTTP_ERROR_MSG = 'HTTP error {res.status_code} - {res.reason}'


class PttSpider:
    rs = requests.session()
    ptt_head = 'https://www.ptt.cc'
    ptt_middle = 'bbs'
    parser_page_count = 5
    push_rate = 10

    def __init__(self, **kwargs):
        self._board = kwargs.get('board', None)
        self.parser_page = int(kwargs.get('parser_page', self.parser_page_count))
        self.push_rate = int(kwargs.get('push_rate', self.push_rate))

        self._soup = None
        self._index_seqs = None
        self._articles = []

    @property
    def info(self):
        return self._articles

    @property
    def board(self):
        return self._board.capitalize()

    def run(self):
        self._soup = self.check_board()
        self._index_seqs = self.parser_index()
        self._articles = self.parser_per_article_url()
        self.analyze_articles()
        self.crawler_img_urls()

    def run_specific_article(self, article):
        self._board = article.url.split('/')[-2]
        self.check_board_over18()
        self._articles = [article]
        self.analyze_articles()
        self.crawler_img_urls(True)

    def check_board(self):
        print('check board......')
        if self._board:
            return self.check_board_over18()
        else:
            print("請輸入看版名稱")
            sys.exit()

    def check_board_over18(self):
        load = {
            'from': '/{}/{}/index.html'.format(self.ptt_middle, self._board),
            'yes': 'yes'
        }
        try:
            res = self.rs.post('{}/ask/over18'.format(self.ptt_head), verify=False, data=load)
            res.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            logging.warning(HTTP_ERROR_MSG.format(res=exc.response))
            raise Exception('網頁有問題')
        return BeautifulSoup(res.text, 'html.parser')

    def parser_index(self):
        print('parser index......')
        max_page = self.get_max_page(self._soup.select('.btn.wide')[1]['href'])
        return (
            '{}/{}/{}/index{}.html'.format(self.ptt_head, self.ptt_middle, self._board, page)
            for page in range(max_page - self.parser_page + 1, max_page + 1, 1)
        )

    def parser_per_article_url(self):
        print('parser per article url......')
        articles = []
        for page in self._index_seqs:
            try:
                res = self.rs.get(page, verify=False)
                res.raise_for_status()
            except requests.exceptions.HTTPError as exc:
                logging.warning(HTTP_ERROR_MSG.format(res=exc.response))
            except requests.exceptions.ConnectionError:
                logging.error('Connection error')
            else:
                articles += self.crawler_info(res, self.push_rate)
        return articles

    def analyze_articles(self):
        for article in self._articles:
            try:
                logging.debug('{}{} ing......'.format(self.ptt_head, article.url))
                res = self.rs.get('{}{}'.format(self.ptt_head, article.url), verify=False)
                res.raise_for_status()
            except requests.exceptions.HTTPError as exc:
                logging.warning(HTTP_ERROR_MSG.format(res=exc.response))
            except requests.exceptions.ConnectionError:
                logging.error('Connection error')
            else:
                article.res = res

    def crawler_img_urls(self, is_content_parser=False):
        for data in self._articles:
            print('crawler image urls......')
            soup = BeautifulSoup(data.res.text, 'html.parser')
            title = str(uuid.uuid4())
            if is_content_parser:
                # 避免有些文章會被使用者自行刪除標題列
                try:
                    title = soup.select('.article-meta-value')[2].text
                except Exception as e:
                    logging.debug('自行刪除標題列:', e)
                finally:
                    data.title = title

            # 抓取圖片URL(img tag )
            for img in soup.find_all("a", rel='nofollow'):
                data.img_urls += self.image_url(img['href'])

    @staticmethod
    def image_url(link):
        # 不抓相簿 和 .gif
        if ('imgur.com/a/' in link) or ('imgur.com/gallery/' in link) or ('.gif' in link):
            return []
        # 符合圖片格式的網址
        images_format = ['.jpg', '.png', '.jpeg']
        for image in images_format:
            if link.endswith(image):
                return [link]
        # 有些網址會沒有檔案格式， "https://imgur.com/xxx"
        if 'imgur' in link:
            return ['{}.jpg'.format(link)]
        return []

    @staticmethod
    def crawler_info(res, push_rate):
        logging.debug('crawler_info......{}'.format(res.url))
        soup = BeautifulSoup(res.text, 'html.parser')
        articles = []
        for r_ent in soup.find_all(class_="r-ent"):
            try:
                # 先得到每篇文章的 url
                url = r_ent.find('a')['href']
                if not url:
                    continue
                title = r_ent.find(class_="title").text.strip()
                rate_text = r_ent.find(class_="nrec").text
                author = r_ent.find(class_="author").text

                if rate_text:
                    if rate_text.startswith('爆'):
                        rate = 100
                    elif rate_text.startswith('X'):
                        rate = -1 * int(rate_text[1])
                    else:
                        rate = rate_text
                else:
                    rate = 0

                # 比對推文數
                if int(rate) >= push_rate:
                    articles.append(ArticleInfo(
                        title=title, author=author, url=url, rate=rate))
            except Exception as e:
                logging.debug('本文已被刪除')
                logging.debug(e)
        return articles

    @staticmethod
    def get_max_page(content):
        start_index = content.find('index')
        end_index = content.find('.html')
        page_number = content[start_index + 5: end_index]
        return int(page_number) + 1


class ArticleInfo:
    def __init__(self, **kwargs):
        self.title = kwargs.get('title', None)
        self.author = kwargs.get('author', None)
        self.url = kwargs.get('url', None)
        self.rate = kwargs.get('rate', None)
        self.img_urls = []
        self.res = None

    @staticmethod
    def data_process(info, crawler_time):
        result = []
        for data in info:
            if not data.img_urls:
                continue
            dir_name = '{}'.format(ArticleInfo.remove_special_char(data.title, '\/:*?"<>|.'))
            dir_name += '_{}'.format(data.rate) if data.rate else ''
            relative_path = os.path.join(crawler_time, dir_name)
            path = os.path.abspath(relative_path)
            try:
                if not os.path.exists(path):
                    os.makedirs(path)
                    result += [(img_url, path) for img_url in data]
            except Exception as e:
                logging.warning(e)
        return result

    @staticmethod
    def remove_special_char(value, deletechars):
        # 移除特殊字元（移除Windows上無法作為資料夾的字元）
        for c in deletechars:
            value = value.replace(c, '')
        return value.rstrip()

    def __iter__(self):
        for url in self.img_urls:
            yield url

    @staticmethod
    def write_data_to_db(articles, session):
        for article in articles:
            for image in article:
                is_exist = session.query(Images).filter(Images.Url == image).first()
                if not is_exist:
                    data = Images(Url=image)
                    session.add(data)
            session.commit()


class Download:
    rs = requests.session()

    def __init__(self, info):
        self.info = info

    def run(self):
        with concurrent.futures.ProcessPoolExecutor() as executor:
            executor.map(self.download, self.info)

    def download(self, image_info):
        url, path = image_info
        try:
            res_img = self.rs.get(url, stream=True, verify=False)
            logging.debug('download image {} ......'.format(url))
            res_img.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            logging.warning(HTTP_ERROR_MSG.format(res=exc.response))
            logging.warning(url)
        except requests.exceptions.ConnectionError:
            logging.error('Connection error')
        else:
            file_name = url.split('/')[-1]
            file = os.path.join(path, file_name)
            try:
                with open(file, 'wb') as out_file:
                    out_file.write(res_img.content)
            except Exception as e:
                logging.warning(e)
