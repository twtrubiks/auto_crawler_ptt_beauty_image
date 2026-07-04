"""crawler.py 純函式的單元測試。

執行方式：
    pip install pytest
    python3 -m pytest
"""
import os

import pytest

from crawler import ArticleInfo, PttSpider

WINDOWS_FORBIDDEN = r'\/:*?"<>|.'


class FakeResponse:
    """crawler_info 只會用到 res.text 與 res.url。"""

    def __init__(self, text: str) -> None:
        self.text = text
        self.url = "https://www.ptt.cc/bbs/beauty/index3999.html"


def _r_ent(nrec: str, title: str, author: str = "alice") -> str:
    return (
        '<div class="r-ent">'
        f'<div class="nrec"><span>{nrec}</span></div>'
        f'<div class="title"><a href="/bbs/Beauty/M.1.A.AAA.html">{title}</a></div>'
        f'<div class="meta"><div class="author">{author}</div></div>'
        "</div>"
    )


def _article(title: str, rate: int, img_urls: list[str]) -> ArticleInfo:
    article = ArticleInfo(title=title, author="alice", url="/bbs/x", rate=rate)
    article.img_urls = img_urls
    return article


def _crawler_info(html: str, push_rate: int) -> list[ArticleInfo]:
    return PttSpider.crawler_info(FakeResponse(html), push_rate)  # type: ignore[arg-type]


# ---------- PttSpider.image_url ----------

@pytest.mark.parametrize(
    ("link", "expected"),
    [
        ("https://imgur.com/a/abc123", []),  # 相簿不抓
        ("https://imgur.com/gallery/abc123", []),  # gallery 不抓
        ("https://i.imgur.com/abc.gif", []),  # gif 不抓
        ("https://i.imgur.com/abc.jpg", ["https://i.imgur.com/abc.jpg"]),
        ("https://i.imgur.com/abc.png", ["https://i.imgur.com/abc.png"]),
        ("https://i.imgur.com/abc.jpeg", ["https://i.imgur.com/abc.jpeg"]),
        # 沒有副檔名的 imgur 網址補上 .jpg
        ("https://imgur.com/abc", ["https://imgur.com/abc.jpg"]),
        ("https://example.com/page", []),  # 非圖片網址
    ],
)
def test_image_url(link: str, expected: list[str]) -> None:
    assert PttSpider.image_url(link) == expected


# ---------- PttSpider.get_max_page ----------

def test_get_max_page() -> None:
    assert PttSpider.get_max_page("/bbs/Beauty/index3942.html") == 3943


# ---------- ArticleInfo.remove_special_char ----------

@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ('[正妹] 測試: "標題"?', "[正妹] 測試 標題"),
        ("普通標題", "普通標題"),
        ("結尾空白   ", "結尾空白"),
    ],
)
def test_remove_special_char(value: str, expected: str) -> None:
    assert ArticleInfo.remove_special_char(value, WINDOWS_FORBIDDEN) == expected


# ---------- PttSpider.crawler_info ----------

def test_crawler_info_filters_by_push_rate() -> None:
    html = _r_ent("25", "[正妹] 高推文") + _r_ent("5", "[正妹] 低推文") + _r_ent("", "[正妹] 無推文")
    articles = _crawler_info(html, push_rate=10)
    assert [a.title for a in articles] == ["[正妹] 高推文"]
    assert articles[0].rate == 25
    assert isinstance(articles[0].rate, int)
    assert articles[0].author == "alice"
    assert articles[0].url == "/bbs/Beauty/M.1.A.AAA.html"


def test_crawler_info_bao_is_100() -> None:
    articles = _crawler_info(_r_ent("爆", "[正妹] 爆文"), push_rate=100)
    assert len(articles) == 1
    assert articles[0].rate == 100


def test_crawler_info_boo_articles_excluded() -> None:
    # X2＝-2、XX＝-10，低於門檻且不應讓解析炸掉
    html = _r_ent("X2", "[黑特] 噓文") + _r_ent("XX", "[黑特] 噓爆文") + _r_ent("30", "[正妹] 正常文")
    articles = _crawler_info(html, push_rate=0)
    assert [a.title for a in articles] == ["[正妹] 正常文"]


def test_crawler_info_skips_announcement_and_deleted() -> None:
    deleted = (
        '<div class="r-ent">'
        '<div class="nrec"></div>'
        '<div class="title"> (本文已被刪除) [bob] </div>'
        '<div class="meta"><div class="author">-</div></div>'
        "</div>"
    )
    html = _r_ent("50", "[公告] 板規") + deleted + _r_ent("50", "[正妹] 正常文")
    articles = _crawler_info(html, push_rate=10)
    assert [a.title for a in articles] == ["[正妹] 正常文"]


# ---------- ArticleInfo.data_process ----------

def test_data_process_returns_all_images(tmp_path) -> None:
    out = str(tmp_path / "out")
    articles = [_article("標題A", 20, ["https://i.imgur.com/a.jpg", "https://i.imgur.com/b.jpg"])]
    result = ArticleInfo.data_process(articles, out)
    assert [url for url, _ in result] == ["https://i.imgur.com/a.jpg", "https://i.imgur.com/b.jpg"]
    assert os.path.isdir(result[0][1])


def test_data_process_existing_dir_not_skipped(tmp_path) -> None:
    # 迴歸測試：資料夾已存在（或同批 title+rate 相同）時不能無聲丟圖
    out = str(tmp_path / "out")
    articles = [_article("撞名標題", 20, ["https://i.imgur.com/a.jpg"])]
    first = ArticleInfo.data_process(articles, out)
    second = ArticleInfo.data_process(articles, out)
    assert first == second
    assert len(second) == 1


def test_data_process_skips_articles_without_images(tmp_path) -> None:
    assert ArticleInfo.data_process([_article("沒圖", 20, [])], str(tmp_path / "out")) == []
