Py Price Agent
==============

PyPriceAgent keeps track of a history of stock and crypto
prices and sends you alerts when various Technical Analysis
type events happen on the charts. 

It keeps a csv and html-table file with latest prices
up to date, for import into a spreadsheet.

It also allows some back-testing.

It'll keep track of bets you place and let you know when
they win/lose/expire in the email each day too.

(C) pre@dalliance.net, but I don't care, do what thou wilt.

For stock prices, you'll need an API key from worldtradingdata.com 
They have daily rate limits for free accounts. The code here tries 
to minimize calls by caching vigorously, but if you add too many 
stocks you'll hit their limits.

BUILD:
======
It'll need these modules.

```
sudo pip install tabulate                 #Display results in tables
sudo pip install pandas numpy             #moving averages, maths on series.
sudo apt-get install python-matplotlib    #plotting graphs
```


CONFIG:
======
You'll want to place a file "secrets.py" in the same
directly as pyPriceAgent.py, to hold API keys and
SMTP details etc. There's an example one with dummy
data at secrets_example.py

You should set a cron to run it some time after market close:
Something like this probably:
```
00 21 * * * python -u /home/user/py/pyPriceAgent/pyPriceAgent.py --email true -l2 >> /home/user/log/stocks.log  2>&1
```

Files
=====
The "tickers.txt" file lists the stocks, one per line, trading-view full-names.
The "bets.json" file is created to track any reminder bets you place.
The "caches" directory holds API request-results etc.
The "history" directory holds our daily price-history for each stock
Both dirs must be writeable, all the data is just JSON dumped into files.

You may adjust the default four MA/EMA values in the tickers.txt
file, with 4 or 8 numbers separated by spaces after the
ticker name. First the EMAs short to long, then the MAs short to long.

By default we write files to ".new" and then rename them to
overwrite the old version. This may not work on Windows, I'm
told. You can override the behaviour with secrets.py 

You'll  want to create a secrets.py file to contain API keys
and SMTP email details etc.

Run --help to see the CLI params, 

Bets 
=====
You can add one at the CLI:
```
stock.alert.py -t LSE:TUI -B Price/target/stop/days/confidence/startDate
```
Defaults exist for them all:
```
  Price -> Previous Day's Close
  Target -> +15% on price
  Stop -> -5% of price (or +5% if target<price)
  Days -> 20
  Confidence -> 33
  StartDate->Today
```

You'll have to just edit the JSON in bets.json if you screw up.
There's more planned here that I haven't gotten to yet. 

Confidence is more or less ignored, but I'm sticking to <50 for bets I
don't take and >50 for bets I do actually put money on for now.

See copious comments in the source-code for more about how
it works and what the various options are.


EXAMPLES
========

Just fetch today's prices and print the email alert:
```
./pyPriceAgent.py 
```
The output shows the email it'd send. IN this case
no bullish alerts, but two worrisome RSI daily
indicators on Bitcoin.
```
From: example@gmail.com
To: example@your.email.moo
Subject: Daily Stock Summary

2020-02-10

Nice looking things this time:


And some things looking bad:
-1:	BTCEUR.COINBASE	RSI Daily falling
-1:	BTCUSD.BINANCE	RSI Daily falling

```




