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
The output shows the email it'd send. In this case
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


What about in the last week? Use -b or --backtest

```
./pyPriceAgent.py -b 7
```

Now it tells us about a few more things, and tells us
how many days ago they happened.  There was a
Red-9 on DBCBTC yesterday, and four days ago the 
EMA cross meant that the moving averages were
sorted into fully-bullish order.

```
From: example@gmail.com
To: example@your.email.moo
Subject: Daily Stock Summary

2020-02-10

Nice looking things this time:
1:	DBCBTC.HUOBI	1 days ago: SEQ Red 9 d
1:	BTCUSD.BINANCE	4 days ago: EMA Sort Went Bullish
1:	IBM.N	3 days ago: EMA Sort Went Bullish


And some things looking bad:
-1:	BTCEUR.COINBASE	RSI Daily falling
-1:	BTCUSD.BINANCE	RSI Daily falling
-1:	IBM.N	1 days ago: RSI Daily falling
```

If we back-test even further then we start to
get to triggered that happened far enough ago
that we know what the price did after that trigger.
So we can start to build up some statistics 

```
./pyPriceAgent.py -b 1000
```

The output now contains tables showing the average
gain in price of the assets after a TA event happened.
In this case was can see that after a Bullish
RSI Weekly event, the price was up an average of
0.3% 1 day later, 0.4% two days later, 1.2% 10
days later etc.

Below that is a table telling us what proportion
of the triggers were followed by a gain of 10%
in the next 1 day / 5 days / 10 days.

We can see that a bullish RSI signal was followed
by a 10% rise within ten days 4 out of 40 times,
and within 15 days it'd hit that 10% target six
times.

Note that the email summary output only contains
one row for each ticker in the list. It shows the
one in which the most triggers happened on any
given day. TSCO had both a squention red 9 daily
and an increasing RSI daily signal 358 days ago.

```
From: example@gmail.com
To: example@your.email.moo
Subject: Daily Stock Summary

2020-02-10

Nice looking things this time:
2:	TSCO.L	358 days ago: RSI Daily up, SEQ Red 9 d
2:	AMZN.O	128 days ago: RSI Daily up, SEQ Red 9 d
2:	DBCBTC.HUOBI	46 days ago: SEQ Red 9 d, SEQ Red 9 w
2:	IBM.N	321 days ago: SEQ Red 9 d, RSI Weekly up
1:	BTCUSD.BINANCE	4 days ago: EMA Sort Went Bullish
1:	DGBBTC.BITFINEX	40 days ago: SEQ Red 9 d


And some things looking bad:
-1:	BTCEUR.COINBASE	RSI Daily falling
-2:	BTCUSD.BINANCE	239 days ago: RSI Weekly falling, SEQ Green 9 w
-2:	TSCO.L	201 days ago: SEQ Green 9 d, SEQ Green 9 w
-2:	AMZN.O	204 days ago: RSI Daily falling, SEQ Green 9 w
-2:	IBM.N	240 days ago: RSI Daily falling, SEQ Green 9 w


Average Gain After Signal:
Signal    Direction    1 Bar        5 Bar        10 Bar       15 Bar        20 Bar        25 Bar
--------  -----------  -----------  -----------  -----------  ------------  ------------  ------------
seq_w     Bull         -0.3 % / 49  -2.3 % / 49  -4.0 % / 49  -3.6 % / 49   -3.7 % / 49   -4.2 % / 49
rsi       Bull         +0.0 % / 40  -0.8 % / 40  -0.9 % / 40  -1.4 % / 40   +0.8 % / 40   +1.2 % / 40
seq       Bull         +0.3 % / 60  +0.4 % / 60  +1.2 % / 60  +0.4 % / 59   +0.4 % / 57   +0.2 % / 57
multi     Bull         -1.1 % / 13  -2.6 % / 13  -2.2 % / 13  -3.2 % / 13   -3.4 % / 13   -3.5 % / 13
emax14    Bull         -0.7 % / 20  -0.5 % / 20  +0.8 % / 20  +0.7 % / 19   +0.8 % / 19   +1.3 % / 18
rsi_w     Bull         -0.7 % / 40  -1.0 % / 40  +0.9 % / 40  -1.0 % / 40   -1.9 % / 40   -2.2 % / 40
emasort   Bull         +1.0 % / 22  +1.4 % / 22  +0.3 % / 22  +1.7 % / 21   +3.2 % / 21   +4.0 % / 20
seq_w     Bear         +0.4 % / 99  +2.1 % / 99  +5.4 % / 99  +7.1 % / 99   +7.1 % / 99   +8.9 % / 99
rsi       Bear         +0.5 % / 80  +0.5 % / 80  +1.9 % / 80  +2.2 % / 77   +3.3 % / 77   +4.5 % / 76
seq       Bear         -0.1 % / 66  +0.7 % / 66  +1.2 % / 66  +1.6 % / 66   +2.3 % / 66   +1.7 % / 65
multi     Bear         +0.9 % / 26  +3.1 % / 26  +9.4 % / 26  +12.7 % / 26  +10.6 % / 26  +12.5 % / 26
emax14    Bear         -0.0 % / 17  -1.2 % / 17  -0.6 % / 17  -0.7 % / 17   -0.9 % / 17   -1.5 % / 17
rsi_w     Bear         +0.6 % / 98  +3.0 % / 98  +3.9 % / 98  +4.9 % / 98   +4.8 % / 98   +3.8 % / 98
emasort   Bear         +0.2 % / 19  +1.6 % / 19  +1.9 % / 19  +3.3 % / 19   +1.4 % / 19   +0.8 % / 19

Number that Hit +/-10.0% gain/loss in bull/bear by:
Signal    Direction    1 Bar    5 Bar    10 Bar    15 Bar    20 Bar    25 Bar
--------  -----------  -------  -------  --------  --------  --------  --------
seq_w     Bull         0 / 49   0 / 49   0 / 49    0 / 49    0 / 49    0 / 49
rsi       Bull         0 / 40   2 / 40   3 / 40    4 / 40    8 / 40    10 / 40
seq       Bull         0 / 60   4 / 60   6 / 60    6 / 59    7 / 57    9 / 57
multi     Bull         0 / 13   0 / 13   0 / 13    0 / 13    0 / 13    0 / 13
emax14    Bull         0 / 20   0 / 20   1 / 20    1 / 19    3 / 19    3 / 18
rsi_w     Bull         0 / 40   0 / 40   4 / 40    6 / 40    6 / 40    6 / 40
emasort   Bull         0 / 22   1 / 22   1 / 22    3 / 21    4 / 21    4 / 20
seq_w     Bear         0 / 99   0 / 99   0 / 99    0 / 99    0 / 99    2 / 99
rsi       Bear         0 / 80   0 / 80   2 / 80    3 / 77    5 / 77    9 / 76
seq       Bear         0 / 66   1 / 66   2 / 66    5 / 66    8 / 66    10 / 65
multi     Bear         0 / 26   0 / 26   0 / 26    0 / 26    0 / 26    2 / 26
emax14    Bear         0 / 17   0 / 17   2 / 17    3 / 17    3 / 17    4 / 17
rsi_w     Bear         1 / 98   1 / 98   4 / 98    7 / 98    10 / 98   16 / 98
emasort   Bear         0 / 19   0 / 19   1 / 19    1 / 19    2 / 19    3 / 19

```

Your ticker-list will likely grow bigger than this example
one, and perhaps be slow to update or give more information
than you want or can handle. We can filter to show only
some or one ticker. 

```
./pyPriceAgent.py -t TSCO -b 1000
```

Now limiting only to Tesco, we know that over the nine times 
an RSI bull signal happened, the price rose by an average
of 0.7% the next day, but was down an average of 0.7% five 
days later. 
```
From: example@gmail.com
To: example@your.email.moo
Subject: Daily Stock Summary

2020-02-10

Nice looking things this time:
2:	TSCO.L	358 days ago: RSI Daily up, SEQ Red 9 d


And some things looking bad:
-2:	TSCO.L	201 days ago: SEQ Green 9 d, SEQ Green 9 w


Average Gain After Signal:
Signal    Direction    1 Bar        5 Bar        10 Bar       15 Bar       20 Bar       25 Bar
--------  -----------  -----------  -----------  -----------  -----------  -----------  -----------
seq_w     Bull         -0.6 % / 15  -3.7 % / 15  -7.4 % / 15  -8.5 % / 15  -7.5 % / 15  -6.6 % / 15
rsi       Bull         +0.7 % / 9   -0.7 % / 9   +0.1 % / 9   -1.1 % / 9   -3.0 % / 9   -1.6 % / 9
seq       Bull         +0.8 % / 11  +1.2 % / 11  +2.5 % / 11  +2.0 % / 11  +2.0 % / 10  +2.4 % / 10
multi     Bull         -1.5 % / 1   -2.2 % / 1   -0.4 % / 1   -1.5 % / 1   -12.6 % / 1  -10.1 % / 1
emax14    Bull         -0.4 % / 6   +0.5 % / 6   +2.5 % / 6   +3.6 % / 6   +4.8 % / 6   +4.1 % / 6
rsi_w     Bull         -0.2 % / 10  +0.8 % / 10  +5.2 % / 10  +6.1 % / 10  +6.0 % / 10  +7.1 % / 10
emasort   Bull         +0.8 % / 7   +2.2 % / 7   +1.8 % / 7   +1.9 % / 7   +3.2 % / 7   +3.1 % / 7
seq_w     Bear         +0.4 % / 20  +1.7 % / 20  +2.0 % / 20  +5.6 % / 20  +5.0 % / 20  +5.9 % / 20
rsi       Bear         +0.2 % / 20  +0.6 % / 20  +1.5 % / 20  +0.7 % / 20  +1.0 % / 20  +0.9 % / 20
seq       Bear         -0.0 % / 12  +0.5 % / 12  +1.1 % / 12  +1.3 % / 12  +0.8 % / 12  +0.5 % / 12
multi     Bear         +0.3 % / 4   -1.0 % / 4   -2.0 % / 4   -1.7 % / 4   -3.5 % / 4   -5.1 % / 4
emax14    Bear         +0.2 % / 5   -1.5 % / 5   -0.9 % / 5   -0.7 % / 5   +2.5 % / 5   +1.9 % / 5
rsi_w     Bear         +0.7 % / 24  +2.6 % / 24  +1.4 % / 24  +2.1 % / 24  +1.6 % / 24  -0.4 % / 24
emasort   Bear         -0.1 % / 6   +2.9 % / 6   +1.6 % / 6   +3.1 % / 6   +3.0 % / 6   +2.6 % / 6

Number that Hit +/-10.0% gain/loss in bull/bear by:
Signal    Direction    1 Bar    5 Bar    10 Bar    15 Bar    20 Bar    25 Bar
--------  -----------  -------  -------  --------  --------  --------  --------
seq_w     Bull         0 / 15   0 / 15   0 / 15    0 / 15    0 / 15    0 / 15
rsi       Bull         0 / 9    0 / 9    0 / 9     0 / 9     1 / 9     1 / 9
seq       Bull         0 / 11   1 / 11   2 / 11    2 / 11    3 / 10    4 / 10
multi     Bull         0 / 1    0 / 1    0 / 1     0 / 1     0 / 1     0 / 1
emax14    Bull         0 / 6    0 / 6    1 / 6     1 / 6     1 / 6     1 / 6
rsi_w     Bull         0 / 10   0 / 10   3 / 10    5 / 10    5 / 10    5 / 10
emasort   Bull         0 / 7    1 / 7    1 / 7     1 / 7     1 / 7     1 / 7
seq_w     Bear         0 / 20   0 / 20   0 / 20    0 / 20    0 / 20    2 / 20
rsi       Bear         0 / 20   0 / 20   0 / 20    0 / 20    0 / 20    1 / 20
seq       Bear         0 / 12   0 / 12   0 / 12    0 / 12    0 / 12    1 / 12
multi     Bear         0 / 4    0 / 4    0 / 4     0 / 4     0 / 4     1 / 4
emax14    Bear         0 / 5    0 / 5    1 / 5     1 / 5     1 / 5     1 / 5
rsi_w     Bear         0 / 24   0 / 24   0 / 24    0 / 24    0 / 24    1 / 24
emasort   Bear         0 / 6    0 / 6    0 / 6     0 / 6     0 / 6     1 / 6
```



