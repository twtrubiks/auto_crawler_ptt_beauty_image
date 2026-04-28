# auto_crawler_ptt_beauty_image

Auto Crawler Ptt Beauty Image with Linux Crontab

* [Youtube Demo](https://youtu.be/IBOhQFeFDPg)

本專案是經由 [PTT_Beauty_Spider](https://github.com/twtrubiks/PTT_Beauty_Spider) 小修改而成，排程改由 Linux 內建的 crontab 觸發執行

~~[線上 Demo 網站](https://ptt-beauty-images.herokuapp.com/)~~

~~我是使用 Django 並且佈署在 [heroku](https://dashboard.heroku.com/) 上，教學以及程式碼可參考 [Deploying_Django_To_Heroku_Tutorial](https://github.com/twtrubiks/Deploying_Django_To_Heroku_Tutorial)~~

> P.S. **Heroku 已於 2022 年 11 月 28 日停止免費方案**，原本的線上 Demo 網站與部署說明已不再適用，故以刪除線標示，僅作歷史紀錄保留。

## 特色

* 每半小時自動爬取 [https://www.ptt.cc/bbs/beauty/index.html](https://www.ptt.cc/bbs/beauty/index.html) 兩頁大於 10 推的文章圖片 URL，並存到資料庫。

## 安裝套件

確定電腦有安裝 [Python](https://www.python.org/) 之後

請在  cmd (命令提示字元) 輸入以下指令

```cmd
pip install -r requirements.txt
```

## 排程 (crontab)

直接使用 Linux 內建的 `crontab` 來定時觸發 `python app.py`

crontab 的詳細用法可參考 [twtrubiks/linux-note - crontab-tutorual](https://github.com/twtrubiks/linux-note/tree/master/crontab-tutorual)。

簡要使用方式：

```bash
# 編輯目前使用者的 crontab
crontab -e

# 加入下面這行（每 30 分鐘執行一次）
*/30 * * * * cd /path/to/auto_crawler_ptt_beauty_image && /usr/bin/python3 app.py >> /var/log/ptt_beauty.log 2>&1

# 列出目前的 crontab 設定
crontab -l
```

cron 欄位順序為「分 時 日 月 週 指令」，常用範例：

| 表達式 | 意義 |
|---|---|
| `*/30 * * * *` | 每 30 分鐘執行一次 |
| `0 * * * *` | 每小時整點執行一次 |
| `0 8 * * *` | 每天早上 8 點執行 |
| `0 8 * * 1` | 每週一早上 8 點執行 |

注意事項：

* `python3` / 專案路徑請填**絕對路徑**，cron 環境變數很乾淨，不會繼承使用者 shell 的 `PATH`。
* 將 stdout / stderr 重導到 log 檔（`>> ... 2>&1`）方便事後排錯。

## CLI 進階用法（cli.py）

除了原本的 `python3 app.py`，本專案另外提供以 [Click](https://click.palletsprojects.com/) 實作的 `cli.py`

`app.py` 仍然完全可用，現有的 cron 排程不會受影響。

```bash
# 看所有指令
python3 cli.py --help

# 爬 beauty 板 3 頁、推文 >= 15 才寫進 DB
python3 cli.py crawl --board beauty --pages 3 --push-threshold 15

# 只爬不寫 DB（測試用）
python3 cli.py crawl --pages 1 --dry-run

# 從 DB 撈最新 50 張圖下載到指定資料夾（扁平輸出，無資料夾結構）
python3 cli.py download --limit 50 --output ./images

# 直接爬+下載（不經 DB），每篇文章一個獨立子資料夾
python3 cli.py fetch --pages 2 --push-threshold 30 --skip-db

# 清掉 30 天以上的 DB 紀錄與下載資料夾（會問確認，加 --yes 跳過）
python3 cli.py clean --days 30 --yes
```

DB 連線字串可由 `--db-url` 或 `DATABASE_URL` 環境變數覆寫，未指定時會 fallback 到 `dbModel.DB_connect`。

### 為什麼用 Click（而不是 argparse / sys.argv）

Click 把每個 CLI 都會重複寫的雜事抽成 decorator，本專案實際用到的：

| 功能 | argparse | Click |
|---|---|---|
| 子指令（crawl/download/fetch/clean） | subparsers（冗長） | `@cli.command()` |
| 範圍驗證 `--pages 1~100` | `choices=range(...)` | `IntRange(1, 100)` |
| 列舉驗證 `--target db/images/all` | `choices=[...]` | `Choice([...])` |
| 資料夾驗證 `--output` | 手刻 | `click.Path(file_okay=False)` |
| 環境變數 fallback `DATABASE_URL` | 自己接 | `envvar='DATABASE_URL'` |
| 確認 prompt（clean 防呆） | 沒有 | `@confirmation_option` |
| 進度條 | 沒有 | `click.progressbar` |
| 彩色輸出 | 沒有 | `click.secho(fg='green')` |
| Group 共享 option（`--db-url`） | parent parser（複雜） | `@click.pass_context` |

`cli.py` 約 380 行就涵蓋 4 個子指令 + 驗證 + 彩色 + 進度條 + 確認 prompt；用 `argparse` 寫等價功能粗估 500~600 行，且 confirmation / progressbar / color 都得自己刻。

這也是為什麼 **Flask CLI / Black / mkdocs / rich-cli 都用 Click**——他們的開發者不是不會寫 argparse，而是覺得每次重造輪子很煩。

### 下載速率與 imgur 429

PTT Beauty 板的圖片絕大多數放在 imgur，imgur 對單一 IP 的 hotlink 限流非常嚴格，過於頻繁的請求會收到 `HTTP 429 Too Many Requests`，甚至被 IP 軟封鎖數十分鐘到數小時。

`download` / `fetch` 提供兩個降速參數：

| Option | 預設 | 建議 |
|---|---|---|
| `--workers` | `2` | 平行下載 thread 數，imgur 場景建議 `1` ~ `2` |
| `--delay` | `0.3` | 每張下載前的等待秒數，被 429 時可拉到 `0.5` ~ `1.0` |

被 429 時的處置順序：

1. **降速重跑**：`--workers 1 --delay 1.0`
2. **等 30 分鐘 ~ 數小時** 讓 imgur 解除 IP 限流
3. **換網路換 IP**（手機熱點 / VPN）
4. **長期解**：申請 [imgur API](https://api.imgur.com/oauth2/addclient) 拿 Client-ID，每日配額 12,500，遠寬於 hotlink

> CLI 已強制 `Download` 套用帶 `User-Agent` 與 `Retry(429, backoff=1.5)` 的 session，但 IP-level 限流仍然只能靠降速或換 IP 解決。

### 進階 cron 範例

```bash
# 每 30 分鐘爬一次（取代原本的 app.py）
*/30 * * * * cd /path/to/auto_crawler_ptt_beauty_image && /usr/bin/python3 cli.py crawl --pages 3 --push-threshold 15 >> /var/log/ptt_beauty.log 2>&1

# 每小時整點下載 DB 中最新 50 張圖
0 * * * * cd /path/to/auto_crawler_ptt_beauty_image && /usr/bin/python3 cli.py download --limit 50 >> /var/log/ptt_beauty.log 2>&1

# 每天凌晨 4 點清理 30 天以上的舊資料
0 4 * * * cd /path/to/auto_crawler_ptt_beauty_image && /usr/bin/python3 cli.py clean --days 30 --yes >> /var/log/ptt_beauty.log 2>&1
```

## database 字串設定

請在 [dbModel.py](https://github.com/twtrubiks/auto_crawler_ptt_beauty_image/blob/master/dbModel.py) 中設定資料庫連線字串，自架 PostgreSQL（含本機 / VPS / Docker）皆可使用。

[docker-compose.yml](https://github.com/twtrubiks/auto_crawler_ptt_beauty_image/blob/master/docker-compose.yml) 可直接 `docker compose up -d` 起一個本機 Postgres。

db 字串設定可在 [dbModel.py](https://github.com/twtrubiks/auto_crawler_ptt_beauty_image/blob/master/dbModel.py) 裡面設定

```python
 DB_connect = 'DB URI'
```

如果你也是使用 Postgres 格式如下

```python
 DB_connect = 'postgresql+psycopg2://postgres:PASSWORD@localhost/database_name'
```

## 執行環境

* Python 3.13

## Reference

* [sqlalchemy](https://www.sqlalchemy.org/)
* [Click](https://click.palletsprojects.com/)

## Donation

文章都是我自己研究內化後原創，如果有幫助到您，也想鼓勵我的話，歡迎請我喝一杯咖啡:laughing:

![alt tag](https://i.imgur.com/LRct9xa.png)

[贊助者付款](https://payment.opay.tw/Broadcaster/Donate/9E47FDEF85ABE383A0F5FC6A218606F8)

## License

MIT license
