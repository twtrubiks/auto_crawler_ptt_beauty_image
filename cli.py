"""Click CLI for auto_crawler_ptt_beauty_image.

提供 crawl / download / clean 三個子指令，完全重用 crawler.py / dbModel.py
中既有的實作。app.py 保留原狀，舊 cron 排程不受影響。
"""
import concurrent.futures
import datetime
import logging
import os
import shutil
import time
from glob import glob

import click
import sqlalchemy
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import sessionmaker

import crawler as crawler_mod
from crawler import ArticleInfo, Download, PttSpider, _build_session
from dbModel import DB_connect, Images

Download.rs = _build_session()


def _make_sessionmaker(db_url: str) -> sessionmaker:
    engine: sqlalchemy.Engine = create_engine(db_url)
    return sessionmaker(engine)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--db-url",
    envvar="DATABASE_URL",
    default=None,
    help="DB 連線字串。未指定則 fallback 到 $DATABASE_URL 或 dbModel.DB_connect。",
)
@click.option(
    "-v",
    "--verbose",
    count=True,
    help="-v 開 INFO log，-vv 開 DEBUG log。",
)
@click.pass_context
def cli(ctx: click.Context, db_url: str | None, verbose: int) -> None:
    """auto_crawler_ptt_beauty_image — PTT 看板爬蟲 CLI。"""
    level = logging.WARNING
    if verbose == 1:
        level = logging.INFO
    elif verbose >= 2:
        level = logging.DEBUG
    logging.getLogger().setLevel(level)

    ctx.ensure_object(dict)
    ctx.obj["db_url"] = db_url or DB_connect


@cli.command()
@click.option("-b", "--board", default="beauty", show_default=True, help="PTT 看板名稱。")
@click.option(
    "-p",
    "--pages",
    type=click.IntRange(1, 100),
    default=2,
    show_default=True,
    help="往回爬幾頁。",
)
@click.option(
    "-t",
    "--push-threshold",
    type=int,
    default=10,
    show_default=True,
    help="推文數門檻，低於此值的文章略過。",
)
@click.option(
    "--timeout",
    type=int,
    default=15,
    show_default=True,
    help="HTTP 請求 timeout（秒）。",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="只爬不寫 DB。",
)
@click.pass_context
def crawl(
    ctx: click.Context,
    board: str,
    pages: int,
    push_threshold: int,
    timeout: int,
    dry_run: bool,
) -> None:
    """爬 PTT 看板，把符合門檻的文章圖片 URL 寫入 DB。"""
    crawler_mod.REQUEST_TIMEOUT = timeout

    click.secho(
        f"crawl board={board} pages={pages} push>={push_threshold}",
        fg="cyan",
    )
    spider = PttSpider(board=board, parser_page=pages, push_rate=push_threshold)
    spider.run()

    article_count = len(spider.info)
    img_count = sum(len(a.img_urls) for a in spider.info)
    click.secho(
        f"  -> 找到 {article_count} 篇文章，共 {img_count} 張圖片 URL",
        fg="green",
    )

    if dry_run:
        click.secho("  -> --dry-run，跳過 DB 寫入", fg="yellow")
        return

    SessionLocal = _make_sessionmaker(ctx.obj["db_url"])
    with SessionLocal() as session:
        ArticleInfo.write_data_to_db(spider.info, session)
    click.secho("  -> 寫入完成", fg="green")


@cli.command()
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="輸出資料夾，未指定時為 ./ptt_images_<時間戳>。",
)
@click.option(
    "--limit",
    type=int,
    default=None,
    help="只下載 DB 中最新的 N 張，預設全部。",
)
@click.option(
    "--workers",
    type=int,
    default=2,
    show_default=True,
    help="平行下載的 thread 數。imgur 容易 429，建議 1~2。",
)
@click.option(
    "--delay",
    type=float,
    default=0.3,
    show_default=True,
    help="每張下載前的等待秒數（每個 thread 各自等），降低 429 機率。",
)
@click.pass_context
def download(
    ctx: click.Context,
    output: str | None,
    limit: int | None,
    workers: int,
    delay: float,
) -> None:
    """從 DB 撈出圖片 URL，下載到本地資料夾。"""
    if output is None:
        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        output = f"./ptt_images_{ts}"

    SessionLocal = _make_sessionmaker(ctx.obj["db_url"])
    with SessionLocal() as session:
        stmt = select(Images.Url).order_by(Images.CreateDate.desc())
        if limit:
            stmt = stmt.limit(limit)
        urls: list[str] = [row[0] for row in session.execute(stmt).all() if row[0]]

    if not urls:
        click.secho("DB 中沒有圖片 URL，請先跑 `crawl`。", fg="yellow")
        return

    os.makedirs(output, exist_ok=True)
    click.secho(f"下載 {len(urls)} 張圖片到 {output}", fg="cyan")

    downloader = Download([(url, output) for url in urls])

    def _download_with_delay(item: tuple[str, str]) -> None:
        if delay > 0:
            time.sleep(delay)
        downloader.download(item)

    with click.progressbar(length=len(urls), label="download") as bar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(_download_with_delay, item)
                for item in downloader.info
            ]
            for _ in concurrent.futures.as_completed(futures):
                bar.update(1)

    click.secho("  -> 下載完成", fg="green")


@cli.command()
@click.option("-b", "--board", default="beauty", show_default=True, help="PTT 看板名稱。")
@click.option(
    "-p",
    "--pages",
    type=click.IntRange(1, 100),
    default=2,
    show_default=True,
    help="往回爬幾頁。",
)
@click.option(
    "-t",
    "--push-threshold",
    type=int,
    default=10,
    show_default=True,
    help="推文數門檻。",
)
@click.option(
    "--timeout",
    type=int,
    default=15,
    show_default=True,
    help="HTTP 請求 timeout（秒）。",
)
@click.option(
    "-o",
    "--output",
    type=click.Path(file_okay=False, dir_okay=True),
    default=None,
    help="輸出資料夾，未指定為 ./<Board>_PttImg_<時間戳>。每篇文章會獨立成一個子資料夾。",
)
@click.option(
    "--skip-db",
    is_flag=True,
    default=False,
    help="不寫入 DB，只下載到本地。",
)
@click.option(
    "--workers",
    type=int,
    default=2,
    show_default=True,
    help="平行下載的 thread 數。imgur 容易 429，建議 1~2。",
)
@click.option(
    "--delay",
    type=float,
    default=0.3,
    show_default=True,
    help="每張下載前的等待秒數（每個 thread 各自等），降低 429 機率。",
)
@click.pass_context
def fetch(
    ctx: click.Context,
    board: str,
    pages: int,
    push_threshold: int,
    timeout: int,
    output: str | None,
    skip_db: bool,
    workers: int,
    delay: float,
) -> None:
    """爬 PTT 並直接下載圖片到本地（每篇文章獨立資料夾），可同步寫 DB。"""
    crawler_mod.REQUEST_TIMEOUT = timeout

    click.secho(
        f"fetch board={board} pages={pages} push>={push_threshold}",
        fg="cyan",
    )
    spider = PttSpider(board=board, parser_page=pages, push_rate=push_threshold)
    spider.run()

    article_count = len(spider.info)
    img_count = sum(len(a.img_urls) for a in spider.info)
    click.secho(
        f"  -> 找到 {article_count} 篇文章，共 {img_count} 張圖片 URL",
        fg="green",
    )

    if img_count == 0:
        click.secho("  -> 沒有圖片可下載", fg="yellow")
        return

    if not skip_db:
        SessionLocal = _make_sessionmaker(ctx.obj["db_url"])
        with SessionLocal() as session:
            ArticleInfo.write_data_to_db(spider.info, session)
        click.secho("  -> DB 寫入完成", fg="green")

    if output is None:
        ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        output = f"./{spider.board}_PttImg_{ts}"

    data = ArticleInfo.data_process(spider.info, output)

    if not data:
        click.secho(
            "  -> 沒有產生新的下載項目（資料夾可能已存在，請換 --output）",
            fg="yellow",
        )
        return

    click.secho(f"下載 {len(data)} 張圖片到 {output}", fg="cyan")
    downloader = Download(data)

    def _download_with_delay(item: tuple[str, str]) -> None:
        if delay > 0:
            time.sleep(delay)
        downloader.download(item)

    with click.progressbar(length=len(data), label="download") as bar:
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(_download_with_delay, item) for item in data]
            for _ in concurrent.futures.as_completed(futures):
                bar.update(1)

    click.secho("  -> 下載完成", fg="green")


@cli.command()
@click.option(
    "--days",
    type=int,
    default=30,
    show_default=True,
    help="保留最近 N 天內的資料，更舊的清掉。",
)
@click.option(
    "--target",
    type=click.Choice(["db", "images", "all"]),
    default="all",
    show_default=True,
    help="清理目標。",
)
@click.option(
    "--images-dir",
    type=click.Path(),
    default=".",
    show_default=True,
    help="掃描圖片資料夾的根目錄（比對 *_PttImg_<時間戳>/）。",
)
@click.confirmation_option(prompt="確定要清理舊資料？")
@click.pass_context
def clean(
    ctx: click.Context,
    days: int,
    target: str,
    images_dir: str,
) -> None:
    """清掉超過 N 天的 DB 紀錄與下載資料夾。"""
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    click.secho(f"清理 {cutoff:%Y-%m-%d %H:%M} 之前的資料", fg="cyan")

    if target in ("db", "all"):
        SessionLocal = _make_sessionmaker(ctx.obj["db_url"])
        with SessionLocal() as session:
            stmt = delete(Images).where(Images.CreateDate < cutoff)
            result = session.execute(stmt)
            session.commit()
            click.secho(f"  -> DB 刪除 {result.rowcount} 筆", fg="green")

    if target in ("images", "all"):
        candidates = glob(os.path.join(images_dir, "*_PttImg_*"))
        removed = 0
        for path in candidates:
            if not os.path.isdir(path):
                continue
            try:
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(path))
                if mtime < cutoff:
                    shutil.rmtree(path)
                    removed += 1
            except OSError as exc:
                click.secho(f"  -> 略過 {path}: {exc}", fg="yellow")
        click.secho(f"  -> 圖片資料夾刪除 {removed} 個", fg="green")


if __name__ == "__main__":
    cli(obj={})
