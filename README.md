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

## database 字串設定

請在 [dbModel.py](https://github.com/twtrubiks/auto_crawler_ptt_beauty_image/blob/master/dbModel.py) 中設定資料庫連線字串，自架 PostgreSQL（含本機 / VPS / Docker）皆可使用。本專案附有 [docker-compose.yml](https://github.com/twtrubiks/auto_crawler_ptt_beauty_image/blob/master/docker-compose.yml)，可直接 `docker compose up -d` 起一個本機 Postgres。

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

## Donation

文章都是我自己研究內化後原創，如果有幫助到您，也想鼓勵我的話，歡迎請我喝一杯咖啡:laughing:

![alt tag](https://i.imgur.com/LRct9xa.png)

[贊助者付款](https://payment.opay.tw/Broadcaster/Donate/9E47FDEF85ABE383A0F5FC6A218606F8)

## License

MIT license
