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
The "tickers.txt" file lists the stocks, one per line, in a format 
like you'll get exporting a trading view list. EG: NYSE:IBM

The "bets.json" file is created to track any reminder bets you place.

The "caches" directory holds API request-results etc.

The "history" directory holds our daily price-history for each stock

Both dirs must be writeable, all the data is just JSON dumped into files.

Ticker Parameters
-----------------
You may adjust the default four MA/EMA values in the tickers.txt
file, with 4 or 8 numbers separated by spaces after the
ticker name. First the EMAs short to long, then the MAs short to long.

EG:
nasdaq:amzn 25 60 95 180 25 60 95 180

Safe-write by renaming
----------------------
By default we write files to ".new" and then rename them to
overwrite the old version. I'm told this may not work on 
Windows. You can override the behaviour with secrets.py 

You'll  want to create a secrets.py file to contain API keys
and SMTP email details etc.

Run --help to see the CLI params, 

Bets 
=====
You can add a new bet at the CLI:
```
stock.alert.py -t LSE:TUI -B Price/target/stop/days/confidence/startDate
```
Defaults exist for them all, type "X" to get:
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
don't take and >50 for bets I do actually put money on for now. I'd
suggest you do similar.

There is copious comments in the source-code for more about how
it works and what the various options are. It's really readable.


EXAMPLES
========

Daily Report
-------------
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

Course, if printing the email content isn't good
enough and you want to actually SEND it, then
hopefully your SMTP details are in secrets.py
then:

```
./pyPriceAgent.py  --email  true
```

And it'll send it. The output to the console
will just look the same though, but an email
should arrive in your inbox too.



Filter Tickers
------------------
Your ticker-list will likely grow bigger than this example,
and sometimes you might only care about one ticker. Especially
when back-testing later. 

We can filter to show only some or one ticker. 

```
./pyPriceAgent.py -t BTCUSD
```

Limited to only BTCUSD we only see things about BTCUSD

```
From: example@gmail.com
To: example@your.email.moo
Subject: Daily Stock Summary

2020-02-10

Nice looking things this time:


And some things looking bad:
-1:	BTCUSD.BINANCE	RSI Daily falling
./pyPriceAgent.py -t TSCO 
```

Or if we wanted to see everything about BTC we
could just include that, or just "LSE" to
see only London exchange stocks etc.



Basic Backtest
---------------
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

Back-testing With Results
------------------------

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


Limit or expand checks
-----------------------

We can limit which tests we decide to run,
or include some of those not run by default.

Imagine we wanted to know how long it takes
Tesco's price to go up by 20% after a
bullish weekly RSI signal in the last 2000
days.

```
./pyPriceAgent.py -t TSCO -b 2000 -c rsi_w -p 5
```

The output tells us that 2/45 times Tesco went
upby 5% within 5 days, and 10/45 times it was
up that high within 25 days.

```
From: example@gmail.com
To: example@your.email.moo
Subject: Daily Stock Summary

2020-02-10

Nice looking things this time:
1:	TSCO.L	281 days ago: RSI Weekly up


And some things looking bad:
-1:	TSCO.L	196 days ago: RSI Weekly falling


Average Gain After Signal:
Signal    Direction    1 Bar        5 Bar        10 Bar       15 Bar       20 Bar       25 Bar
--------  -----------  -----------  -----------  -----------  -----------  -----------  -----------
rsi_w     Bull         -0.8 % / 45  -2.6 % / 45  -2.0 % / 45  -1.1 % / 45  -2.9 % / 45  -5.1 % / 45
rsi_w     Bear         +0.6 % / 35  +1.9 % / 35  +0.8 % / 35  +2.1 % / 35  +1.8 % / 35  +0.7 % / 35

Number that Hit +/-5.0% gain/loss in bull/bear by:
Signal    Direction    1 Bar    5 Bar    10 Bar    15 Bar    20 Bar    25 Bar
--------  -----------  -------  -------  --------  --------  --------  --------
rsi_w     Bull         0 / 45   2 / 45   9 / 45    10 / 45   10 / 45   10 / 45
rsi_w     Bear         0 / 35   0 / 35   1 / 35    4 / 35    10 / 35   10 / 35

```


Multi-checks
------------
We can example what happened if more than one check triggered
on the same day if limit our checks to those we care about
and enable the multi-check check.

If there was a sequential nine on both the daily and
the weekly candles at once, what happened to the price?

```
 ./pyPriceAgent.py -t TSCO -b 2000 -c seq,seq_w,multi
```

Well, with Tesco it's only happened three times. The two
times it was a bullish signal, it went up an average of 0.5%
the next day. When it was a bearish signal it fell 1.3% the
next day, and was down 8.7% after 20 days.

```
From: example@gmail.com
To: example@your.email.moo
Subject: Daily Stock Summary

2020-02-10

Nice looking things this time:
2:	TSCO.L	1067 days ago: SEQ Red 9 d, SEQ Red 9 w


And some things looking bad:
-2:	TSCO.L	201 days ago: SEQ Green 9 d, SEQ Green 9 w


Average Gain After Signal:
Signal    Direction    1 Bar        5 Bar        10 Bar       15 Bar       20 Bar       25 Bar
--------  -----------  -----------  -----------  -----------  -----------  -----------  -----------
seq_w     Bull         -0.4 % / 35  -1.6 % / 35  -3.7 % / 35  -6.3 % / 35  -8.1 % / 35  -8.6 % / 35
multi     Bull         +0.5 % / 2   -0.5 % / 2   -2.5 % / 2   -7.7 % / 2   -9.9 % / 2   -10.1 % / 2
seq       Bull         +0.1 % / 33  +0.4 % / 33  +1.0 % / 33  -0.3 % / 33  -0.0 % / 32  +0.1 % / 32
seq_w     Bear         +0.5 % / 40  +2.6 % / 40  +3.3 % / 40  +5.6 % / 40  +6.6 % / 40  +7.7 % / 40
multi     Bear         -1.3 % / 1   -0.3 % / 1   -4.4 % / 1   -4.7 % / 1   -8.7 % / 1   -10.0 % / 1
seq       Bear         -0.0 % / 27  +0.3 % / 27  +0.9 % / 27  +1.4 % / 27  +0.8 % / 27  +0.2 % / 27

Number that Hit +/-10.0% gain/loss in bull/bear by:
Signal    Direction    1 Bar    5 Bar    10 Bar    15 Bar    20 Bar    25 Bar
--------  -----------  -------  -------  --------  --------  --------  --------
seq_w     Bull         0 / 35   0 / 35   0 / 35    0 / 35    0 / 35    0 / 35
multi     Bull         0 / 2    0 / 2    0 / 2     0 / 2     0 / 2     0 / 2
seq       Bull         0 / 33   1 / 33   3 / 33    4 / 33    5 / 32    8 / 32
seq_w     Bear         0 / 40   0 / 40   0 / 40    0 / 40    0 / 40    2 / 40
multi     Bear         0 / 1    0 / 1    0 / 1     0 / 1     0 / 1     1 / 1
seq       Bear         0 / 27   0 / 27   0 / 27    1 / 27    2 / 27    3 / 27
```

Control Checks
----------------

Of course, in the last example a bearish signal warning
of an 8% drop sounds impressive, until you notice that
the bullish signal leads to an even bigger loss and on
more data-points.

We can add a control check, which just fires randomly, to give
a sort of background-level of price-changes to compare against.

```
./pyPriceAgent.py -b 2000 -c seq,seq_w,multi,ctrl 
```

Across this tiny data-set, a simultaneous weekly and a daily 
sequential-9 bull signal led to loss of 3.9% after fifteen
days, with four data points.

The equivalent bear signal led to a 0.4% less.

Just randomly picking a time led to a 4.3% gain
on a bearish signal and a 2.6% gain on a bullish
signal.

What are we to make of this?

Probably that the data-set is too small to mean
anything, there's eight data-points and six
control points. 

```
From: example@gmail.com
To: example@your.email.moo
Subject: Daily Stock Summary

2020-02-10

Nice looking things this time:
2:	TSCO.L	1067 days ago: SEQ Red 9 d, SEQ Red 9 w
2:	DBCBTC.HUOBI	46 days ago: SEQ Red 9 d, SEQ Red 9 w
1:	BTCUSD.BINANCE	55 days ago: SEQ Red 9 d
1:	DGBBTC.BITFINEX	40 days ago: SEQ Red 9 d
1:	LBCBTC.BITTREX	1996 days ago: Random Bull
1:	AMZN.O	55 days ago: SEQ Red 9 d
1:	BTCEUR.COINBASE	1951 days ago: Random Bull
1:	IBM.N	126 days ago: SEQ Red 9 d


And some things looking bad:
-1:	BTCUSD.BINANCE	186 days ago: SEQ Green 9 d
-1:	DGBBTC.BITFINEX	1981 days ago: Random Bear
-1:	LBCBTC.BITTREX	1970 days ago: Random Bear
-1:	DBCBTC.HUOBI	1972 days ago: Random Bear
-1:	BTCEUR.COINBASE	1800 days ago: Random Bear
-1:	IBM.N	104 days ago: SEQ Green 9 d
-2:	TSCO.L	201 days ago: SEQ Green 9 d, SEQ Green 9 w
-2:	AMZN.O	770 days ago: SEQ Green 9 d, SEQ Green 9 w


Average Gain After Signal:
Signal    Direction    1 Bar         5 Bar         10 Bar        15 Bar        20 Bar        25 Bar
--------  -----------  ------------  ------------  ------------  ------------  ------------  ------------
seq_w     Bull         -0.2 % / 99   -1.4 % / 99   -2.7 % / 99   -3.5 % / 99   -5.1 % / 99   -6.3 % / 99
multi     Bull         +0.2 % / 4    -0.3 % / 4    -1.3 % / 4    -3.9 % / 4    -5.0 % / 4    -5.1 % / 4
seq       Bull         +0.1 % / 108  +0.2 % / 108  +0.7 % / 108  +0.1 % / 107  +0.1 % / 105  +0.3 % / 105
ctrl      Bull         +2.0 % / 3    -0.8 % / 3    +3.3 % / 3    +2.6 % / 3    +1.8 % / 3    +0.9 % / 3
seq_w     Bear         +0.4 % / 154  +1.7 % / 154  +4.2 % / 154  +5.7 % / 154  +6.7 % / 154  +8.7 % / 154
multi     Bear         +0.1 % / 4    +0.2 % / 4    -0.9 % / 4    -0.4 % / 4    +1.2 % / 4    +2.3 % / 4
seq       Bear         -0.0 % / 112  +0.4 % / 112  +0.8 % / 112  +1.0 % / 112  +1.4 % / 112  +0.9 % / 111
ctrl      Bear         +1.0 % / 3    +5.8 % / 3    +4.6 % / 3    +4.3 % / 3    +3.6 % / 3    +4.0 % / 3

Number that Hit +/-10.0% gain/loss in bull/bear by:
Signal    Direction    1 Bar    5 Bar    10 Bar    15 Bar    20 Bar    25 Bar
--------  -----------  -------  -------  --------  --------  --------  --------
seq_w     Bull         0 / 99   0 / 99   0 / 99    0 / 99    0 / 99    0 / 99
multi     Bull         0 / 4    0 / 4    0 / 4     0 / 4     0 / 4     0 / 4
seq       Bull         0 / 108  4 / 108  8 / 108   11 / 107  12 / 105  17 / 105
ctrl      Bull         0 / 3    0 / 3    0 / 3     0 / 3     0 / 3     1 / 3
seq_w     Bear         0 / 154  0 / 154  0 / 154   0 / 154   0 / 154   2 / 154
multi     Bear         0 / 4    0 / 4    0 / 4     0 / 4     0 / 4     1 / 4
seq       Bear         0 / 112  2 / 112  3 / 112   8 / 112   15 / 112  17 / 111
ctrl      Bear         0 / 3    0 / 3    0 / 3     0 / 3     0 / 3     0 / 3

```


Reminder Bets
--------------

Often you may see a signal in your daily report and
wonder how it will turn out. We can tell pyPriceAgent
to remind us when a position we take, or are just 
curious about but not confident enough to bet on.

We saw that the RSI signalled bearish on BTCUSD,
so we figure it's going to go down. We can place
a bet:

```
./pyPriceAgent.py -t BTCUSD -B X/9500/5%/20/30
```

PyPriceAgent will tells us that it understood we
wanted to bet that the price of BTCUSD would go
from it's last close down to 9500, but that if it went up
by five percent (to 10321.50, it calculated)
then you'd call it a loss. 

You'd also call it a day at 20 days, regardless
of how things looked.

```
Placing Bet: 2020-02-10, BTCUSD.BINANCE
		->From 9851.23 To 9500.00 with a stop of 10343.79 or 20 days (Conf: 30.00
``` 

When the script runs each night after close from then
on it'll check if your bet has won or lost or timed
out yet and add that to your daily report when it
happens.

You can use X to get a default on any field, and
use percents or direct numbers in the ones where
that makes sense.


List Of Checks Available
==========================

```
./pyPriceAgent.py --help
```
 
 
|NAME|ALERTS WHEN|
|----|-----------|
|bets|	alert the end/outcome of bets placed [default]|
|ctrl|	fire randomly, as a control check |
|emasort	|ema sort-order changes [default]|
|emax1|	short ema crosses [default]|
|emax2|	med ema crosses |
|emax3|	long ema crosses |
|emax4|	vlong ema crosses [default]|
|masort|	ma sort-order changes |
|max1	|short ma crosses| 
|max2	|med ma crosses |
|max3	|long ma crosses |
|max4	|vlong ma crosses |
|multi|	look for multiple other-check hits [default]|
|rsi	|	daily RSI crosses 30/70 [default]|
|rsi_w|weekly RSI crosses 30/70 [default]|
|seq	| daily sequential 9 candles [default]|
|seq_w|	weekly sequential 9 candles [default]|
