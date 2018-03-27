# auto_crawler_ptt_beauty_image

Auto Crawler Ptt Beauty Image Use Python Schedule

* [Youtube Demo](https://youtu.be/IBOhQFeFDPg)

本專案是經由 [PTT_Beauty_Spider](https://github.com/twtrubiks/PTT_Beauty_Spider) 小修改 + [schedule](https://github.com/dbader/schedule) 完成的。

[線上 Demo 網站](https://ptt-beauty-images.herokuapp.com/)

我是使用 Django 並且佈署在 [heroku](https://dashboard.heroku.com/) 上，教學以及程式碼可參考   [Deploying_Django_To_Heroku_Tutorial](https://github.com/twtrubiks/Deploying_Django_To_Heroku_Tutorial)

P.S
目前佈署在 [heroku](https://dashboard.heroku.com/) 上，因為免費版有24小時一定要休息6小時的規定，所以比較慢請多多包涵。

## 特色

* 每半小時自動爬取 [https://www.ptt.cc/bbs/beauty/index.html](https://www.ptt.cc/bbs/beauty/index.html) 兩頁大於 10 推的文章圖片 URL，並存到資料庫。
* 透過 [Deploying_Django_To_Heroku_Tutorial](https://github.com/twtrubiks/Deploying_Django_To_Heroku_Tutorial) 將圖片呈現到網頁上 [Demo 網站](https://ptt-beauty-images.herokuapp.com/)。

## 安裝套件

確定電腦有安裝 [Python](https://www.python.org/) 之後

請在  cmd (命令提示字元) 輸入以下指令

```cmd
pip install -r requirements.txt
```

## schedule

由於要每半小時爬取網頁一次，所以我用了 [schedule](https://github.com/dbader/schedule) , 讓程式依照我們設定的 schedule 下去執行

## database 字串設定

因為要佈署在 [Heroku](https://dashboard.heroku.com/)  , 所以我使用 Heroku Postgres ，

詳細教學可參考 [如何在 heroku 上使用 database](https://github.com/twtrubiks/Deploying-Flask-To-Heroku#%E5%A6%82%E4%BD%95%E5%9C%A8-heroku-%E4%B8%8A%E4%BD%BF%E7%94%A8-database)

db 字串設定可在 [dbModel.py](https://github.com/twtrubiks/auto_crawler_ptt_beauty_image/blob/master/dbModel.py) 裡面設定

```python
 DB_connect = 'DB URI'
```

如果你也是使用 Postgres 格式如下

```python
 DB_connect = 'postgresql+psycopg2://postgres:PASSWORD@localhost/database_name'
```

## Deploy

佈署空間 - [Heroku](https://dashboard.heroku.com/)

教學請參考 [Deploying-Flask-To-Heroku](https://github.com/twtrubiks/Deploying-Flask-To-Heroku)

因為我們這次並沒有要建立一個網站

所以我們要將 [Procfile](https://github.com/twtrubiks/auto_crawler_ptt_beauty_image/blob/master/Procfile) 修改為

```python
worker: python app.py
```

## 執行環境

* Python 3.5.2

## Reference

* [sqlalchemy](http://docs.sqlalchemy.org/en/latest/intro.html)
* [schedule](https://github.com/dbader/schedule)

## Donation

文章都是我自己研究內化後原創，如果有幫助到您，也想鼓勵我的話，歡迎請我喝一杯咖啡:laughing:

![alt tag](https://i.imgur.com/LRct9xa.png)

[贊助者付款](https://payment.opay.tw/Broadcaster/Donate/9E47FDEF85ABE383A0F5FC6A218606F8)

## License

MIT license
