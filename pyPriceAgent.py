#!/usr/bin/python

##############################################################
#
# PyPriceAgent keeps track of a history of stock and crypto
# prices and sends you apy lerts when various Technical Analysis
# type events happen on the charts. 
#
# It keeps a csv and html-table file with latest prices
# up to date, for import into a spreadsheet.
#
# It also allows some back-testing.
# 
# It'll keep track of bets you place and let you know when
# they win/lose/expire in the email each day too.
# 
# (C) pre@dalliance.net, but I don't care, do what thou wilt.
#
# For stock prices, you'll need an API key from worldtradingdata.com 
# They have daily rate limits for free accounts. The code here tries 
# to minimize calls by caching vigorously, but if you add too many 
# stocks you'll hit their limits.
#
# TODO:
# Ah bollocks: WorldTradiingData is closing down May 9th. Just over
# a month. Will need to find an alternative.
#
# BUILD:
# ------
# It'll need these modules.
# sudo pip install tabulate                 #Display results in tables
# sudo pip install pandas numpy             #moving averages, maths on series.
# sudo apt-get install python-matplotlib    #plotting graphs
# 
#
# CONFIG:
# ------
# You'll want to place a file "secrets.py" in the same
# directly as pyPriceAgent.py, to hold API keys and
# SMTP details etc. There's an example one with dummy
# data at secrets_example.py
#
# You should set a cron to run it some time after market close:
# Something like this probably:
# 00 21 * * * python -u /home/user/py/pyPriceAgent/pyPriceAgent.py --email true -l2 >> /home/user/log/stocks.log  2>&1
#
# Files
# -----
# The "tickers.txt" file lists the stocks, one per line, trading-view full-names.
# The "bets.json" file is created to track any reminder bets you place.
# The "caches" directory holds API request-results etc.
# The "history" directory holds our daily price-history for each stock
# Both dirs must be writeable, all the data is just JSON dumped into files.
#
# You may adjust the default four MA/EMA values in the tickers.txt
# file, with 4 or 8 numbers separated by spaces after the
# ticker name. First the EMAs short to long, then the MAs short to long.
#
# By default we write files to ".new" and then rename them to
# overwrite the old version. This may not work on Windows, I'm
# told. You can override the behaviour with secrets.py 
#
# You'll  want to create a secrets.py file to contain API keys
# and SMTP email details etc.
#
# Run --help to see the CLI params, 
#
# Bets!
# -----
# You can add one at the CLI:
# pyPriceAgnet.py -t LSE:TSCO -B Price/target/stop/days/confidence/startDate
# Defaults exist for them all:
#   Price -> Previous Day's Close
#   Target -> +15% on price
#   Stop -> -5% of price (or +5% if target<price)
#   Days -> 20
#   Confidence -> 33
#   StartDate->Today
#
# You'll have to just edit the JSON in bets.json if you screw up.
#
# There's more in ./pyPriceAgent --help
#
# See copious comments below these imports...

import os, sys, math, random
import getopt
import operator
import smtplib
import requests
import time
import hashlib
from datetime import date, datetime
import dateutil.parser
import json
from tabulate import tabulate
import pandas as pd
import numpy as np
import matplotlib.pyplot as pyplot


# Constants 
MAXCACHEAGEHOURS = 23   #Age to expire cache files.
ANALYSISPERIOD = 80     #Number of days to watch price after a check trigger

# Options, mostly can be changed at the CLI or over-witten in secrets.py
OUT_CSV_FILE = "export.csv"
OUT_HTML_FILE = "export.html"
GMAIL_USER = 'xxxxxxxxx@gmail.com'
GMAIL_PASSWORD = 'xxxxxxxxxxxxxxxx'
Email_Report_Address = ['xxxa@test.net']
API_KEY = 'demo'
TickersName = "tickers.txt"

# Back-test summary can tell you what proportion of times
# a trigger event was followed by a X% rise Y days later.
# This is the X, defaulting to 0.1=10%
TriggerPercent = 0.1

#This is the Y, a series, it puts them in a table.
TimeCheck_Periods = [1,5,10,15,20,25]

#We can ignore all tickers that don't contain a string. 
TickerFilter = ""

#Debug logging level.
LogLevel=0
#Debug graph-drawing after each stock:
ShowGraphs = 0
LogScale=True

#Should we send an email? Usually not, only on the cron.
Send_Email=False

# How many days to back-test.
BacktestDays = 0

#The email lists the checks which each ticker triggered,
#You may limit it to show only those that passed multiple
#triggers in the same day.
MinReportScore = 0

# The world trading data API lets us check five tickers
# for current-price in one request, but only one ticker
# in a full-history request. So usually we cram five into
# each request, but if we want to fetch a full history,
# which will need to be done at least one, we have a CLI
# option for that.
FetchHistory = False

# The "multi" check triggers if more than X other checks
# happened in the same day. More for back-testing than
# for the daily alert really.
MultiCheck = 2

# If the script is interrupted while writing a file it
# can end up corrupted. We avoid this by writing to 
# ".new" and then renaming to the old file. I'm told
# this may not work on Windows.
DoSafeFileWrite = True 

#The full list of all checks available.
AllChecks = {
  "rsi"    : "daily RSI crosses 30/70",
  "rsi_w"  : "weekly RSI crosses 30/70",
  "emax1"  : "short ema crosses",
  "emax2"  : "med ema crosses",
  "emax3"  : "long ema crosses",
  "emax4"  : "vlong ema crosses",
  "max1"   : "short ma crosses",
  "max2"   : "med ma crosses",
  "max3"   : "long ma crosses",
  "max4"   : "vlong ma crosses",
  "masort" : "ma sort-order changes",
  "emasort": "ema sort-order changes",
  "seq"    : "daily sequential 9 candles",
  "seq_w"  : "weekly sequential 9 candles",
  "multi"  : "look for multiple other-check hits",
  "bets"   : "alert the end/outcome of bets placed",
  "ctrl"   : "fire randomly, as a control check",
}

#Default enabled checks (override in secrets.py if you want)
Checks = ["rsi","rsi_w","seq","seq_w","emax1","emax4","emasort", "multi","bets"]


#Import the secrets.py file that can override any of that.
MyDirectory = os.path.abspath(os.path.dirname( __file__ ))
try: 
  
  execfile(MyDirectory+"/secrets.py")
except IOError:
  print("You should set the secrets")
  exit()

# Data store.
alerts = []
htmlCache = {}
uniqcodes = {}
bullishness={}
bullishness_tops={}
bullishness_bots={}
bullreason={}
bullreason_tops={}
bullreason_bots={}
resultLog={}
tickerParams = {}
tickers = None
unfilteredTickers = None
BetStore = []
PlaceBetArgs = None


def printHelp():
  """
  Print out the help page
  """
  print """
options:
-h --help            -> This page
-l --log X           -> Debug logging level, higher=more verbose
-e --email true      -> Send summary email
-b --backtest X      -> Days to lookback for backtesting
-s --score X         -> Report only tickers with > X indications
-g --graph X         -> Show graph of each ticker, higher=more detail
-c --checks XX,YY,ZZ -> List of checks to run
-m --multi 3         -> Checks needed to hit to trigger multi, 0=never
-t --ticker XX       -> Filter tickers to check, partial match
-p --percent X       -> Trigger winning percent for backtest report
-H --fetch-history   -> Pull data from 'past' api not 'realtime'
-B --bet price/target/stop/days/confidence/startDate -> bet 

Available Checks:
  """
  print "NAME\tALERTS WHEN"
  print "----\t-----------"
  for k in sorted(AllChecks):
    print "%s\t%s %s" % (k,AllChecks[k],"[default]" if k in Checks else "")



def readBets():
  """
  Load in the JSON file representing bets we have recorded
  """
  global BetStore
  fileName = "bets.json"
  BetStore = checkForCache(fileName,expire=-1);
  if(BetStore==None):
    print("Creating new BetStore")
    BetStore = []


def saveBets():
  """
  Save out the JSON file representing bets we have recorded
  """
  fileName = "bets.json"
  out=json.dumps(BetStore, indent=2, sort_keys = True )
  writeFile(fileName, out)



def readTickers():
  """
  Read the list of tickers
  """
  global tickers, tickerParams, TickerFilter, LogLevel, unfilteredTickers, TickersName
  if(tickers==None):
    tickers = []
    unfilteredTickers = []
    ObjRead = open(TickersName, "r")
    allTickers = ObjRead.read();
    eachTicker = allTickers.split(u"\n")
    for ticker in eachTicker:
      params = ticker.split(" ")
      bits = params[0].split(":")
      if(len(bits)>1):
        symbol = bits[1]
        exchange = bits[0]

        if(exchange=="LSE"):
          exchange="L"
        if(exchange=="NASDAQ"):
          exchange="O"
        if(exchange=="NYSE"):
          exchange="N"
        if(exchange=="AMEX"):
          exchange="A"
        if(exchange=="LSIN"):
          exchange="TRE"
        if(exchange=="OTC"):
          exchange="PK"

        #Some cryptos that we haven't dealt with can try fall-backs elsewhere
        if(exchange=="BITMEX"):
          exchange="CRYPTO"
        if(exchange=="POLONIEX"):
          exchange="CRYPTO"

        t = symbol+"."+exchange

        unfilteredTickers.append(t)
        if(TickerFilter.lower() in ticker.lower()):
          tickers.append(t)
        if(len(params)>1):
          tickerParams[t] = params[1:]

  return tickers
  
  


def getTickerGroup(ticker,groupSize):
  """
  Some services limit how many requests we
  can do, and yet also let us ask for multiple
  stocks in a single request, so we want to 
  group them into groups of groupSize and
  return the whole group
  """
  global unfilteredTickers
  ret=[]
  for n in range(0,len(unfilteredTickers)):
    testticker = unfilteredTickers[n]
    if(testticker==ticker):
      groupNumber = n/groupSize
      index = groupNumber*groupSize
      for i in range(index,min(len(unfilteredTickers),index+groupSize)):
        t = unfilteredTickers[i]
        t = t.replace("..",".");
        if((t.endswith(".O")) or (t.endswith(".N"))):
          t = t[0:-2]
        ret.append(t)
      return ret
  return None 



def writeFile(filename,dat):
  """
  We have a function to write a file coz all our data 
  is in files, and on Unix at least we want to create
  new files then rename them to the old file in case
  something bad happens during the write
  (like me pressing CTRL-C, which apparently is often)
  """
  if(DoSafeFileWrite):
    ObjWrite = open(filename+".new", "w")
    ObjWrite.write(dat)
    ObjWrite.close()
    os.rename(filename+".new", filename)
  else:
    ObjWrite = open(filename, "w")
    ObjWrite.write(dat)
    ObjWrite.close()



def getHtml(url):
  """
  Get a page from the web
  """
  global htmlCache;
  if(url in htmlCache):
    return htmlCache[url]

  fn = "caches/web-"+str(hashlib.sha1(url).hexdigest());
  page = checkForCachePlain(fn)

  if(page==None):
    page=""
    resource = requests.get(url)
    for line in resource:
      page+=line
    resource.close()

    #Save it for cachiness
    writeFile(fn,page)

  htmlCache[url] = page
  return page



def checkForCache(cacheFileName,expire=0):
  """
  Check if we have a data-cache and
  return it if we do
  """
  if(expire==0):
    expire = MAXCACHEAGEHOURS*60*60;
  now = time.time()
  yesterday = now-expire;
  if((os.path.isfile(cacheFileName)) and ((expire<0) or (os.path.getmtime(cacheFileName)>yesterday))):
    try:
      data = json.load(open(cacheFileName))
    except Exception as e:
      print("Error Doing "+cacheFileName+":"+str(e))
      exit();
    return data
  else:
    return None



def checkForCachePlain(cacheFileName):
  """
  Check if we have a data-cache and
  return it if we do
  """
  now = time.time()
  yesterday = now-MAXCACHEAGEHOURS*60*60;
  if((os.path.isfile(cacheFileName)) and (os.path.getmtime(cacheFileName)>yesterday)):
    try:
      ObjRead = open(cacheFileName, "r")
      data = ObjRead.read()
      ObjRead.close()
    except Exception as e:
      print("Error Doing Plain Cache "+cacheFileName+":"+str(e))
      exit();
    return data
  else:
    return None



def getPrices(ticker):
  """
  Get the entire-history price-date for
  a given ticker in my format, and call
  on the API only if we seem to be out of
  date
  """
  ticker = str(ticker)
  cacheFileName = "history/"+ticker+".json"
  data = checkForCache(cacheFileName,expire=-1);
  if(data==None):
    data = {}

  now = date.today()
  nowkey = now.isoformat()
  if((not nowkey in data) or (FetchHistory==True)):
    data = appendLatestPriceData(ticker,data)
    savePriceData(ticker,data)

  return data



def savePriceData(ticker,data):
  """
  Save the price data of a ticker
  To avoid leaving files half-written
  when some moron (me) CTRL-C's during the
  write, we write to a "new" file and
  then do a more atomic "mv" to actually
  overwrite the old data.
  """
  cacheFileName = "history/"+ticker+".json"
  out=json.dumps(data, indent=2, sort_keys = True )
  writeFile(cacheFileName, out)
  

def getIndexInDateSeries(timestamp,dateSeries):
  """
  Check through a date-series to be sure
  if a given date is before or after that index
  """
  for i in range(0,len(dateSeries)):
    if(dateSeries[i] == timestamp):
      return i;
  return -1;

  
 

def updateTheCsv(filename,pricelist,outhtml):
  """
  Read in the CSV, update any of it's tickers
  which match this price. Order here is very
  important, so no dicts I'm afraid
  """
  tickerHash = {}
  for k in pricelist:
    ks = k.split(".");
    if(len(ks)>2):
      #Double-Dot is annoying
      ks = [ks[0]+".",ks[2]]
    tickerHash[ks[0]] = pricelist[k]
  
  ObjRead = open(filename, "r")
  wholeFile = ObjRead.read()
  ObjRead.close()
  lines = wholeFile.split(u"\n")
  symbols = []
  prices = []
  for line in lines:
    bits = line.split(",")
    symbol = bits[0]
    symbols.append(symbol)
    price=0;
    if((len(bits)>1) and (len(bits[1])>0)):
      price=float(bits[1])
    if(symbol in tickerHash):
      price = tickerHash[symbol]
      del tickerHash[symbol]
    prices.append(float(price)) 

  for key in tickerHash:
    symbols.append(key)
    prices.append(float(tickerHash[key]))

  #Write the CSV file.
  outString = ""
  for n in range(0,len(symbols)):
    if(symbols[n]!=""):
      outString+=str(symbols[n]) + "," + str(prices[n]) + "\n"
  writeFile(filename,outString)

  #Write the HTML file.
  outString = "<table>"
  for n in range(0,len(symbols)):
    if(symbols[n]!=""):
      outString+="<tr><td>"+str(symbols[n]) + "</td><td>" + str(prices[n]) + "</td></tr>"
  outString+="</table>"
  writeFile(outhtml,outString)



 
 
def appendLatestPriceData(ticker,data):
  """
  Given our current data on the prices of a
  stock, append some new ones from the latest
  API call
  """
  if(ticker.endswith(".BINANCE")):
    return appendLatestPriceDataBinance(ticker,data)
  if(ticker.endswith(".BITFINEX")):
    return appendLatestPriceDataBitfinex(ticker,data)
  if(ticker.endswith(".BITSTAMP")):
    return appendLatestPriceDataBitstamp(ticker,data)
  if(ticker.endswith(".BITTREX")):
    return appendLatestPriceDataBittrex(ticker,data)
  if(ticker.endswith(".HUOBI")):
    return appendLatestPriceDataHuobi(ticker,data)
  if(ticker.endswith(".COINBASE")):
    return appendLatestPriceDataCoinbase(ticker,data)
  if(ticker.endswith(".CRYPTO")):
    return appendLatestPriceDataBinance(ticker,data)
  return appendLatestPriceDataWorldTradingData(ticker,data)



def appendLatestPriceDataWorldTradingData(ticker,data):
  """
  Given our current data on the prices,
  add the newest data we can get from
  World Trading Data
  """
  global FetchHistory   ##Maybe we wanna fetch historical data instead of realtime?
  if(FetchHistory):
    return appendOldHistoryToPriceDataWorldTradingData(ticker,data)

  tickerGroup = getTickerGroup(ticker,5)  #We can get five prices at once.
  tickerGroupString = ",".join(tickerGroup)
  ticker = ticker.replace("..",".");
  if((ticker.endswith(".O")) or (ticker.endswith(".N"))):
    ticker = ticker[0:-2]
   
  url = "https://api.worldtradingdata.com/api/v1/stock?symbol="+tickerGroupString+"&api_token="+API_KEY

  page = getHtml(url)
  jsondat = json.loads(page)
  if("data" in jsondat):
    for dat in jsondat['data']:
      if(dat['symbol']==ticker):
        dtkey = dat['last_trade_time'][0:10]
        data[dtkey] = {
         'o': dat['price_open'],
         'h': dat['day_high'],
         'l': dat['day_low'],
         'c': dat['price'],
         'v': dat['volume']
        }
  else:
   print("**Warning, can't find World Data: "+ticker)
  return data



def appendOldHistoryToPriceDataWorldTradingData(ticker,data):
  """
  Given our current data on the prices,
  get the history of the stock to fill in
  any gaps. We fetch the whole lot at once.
  """
  ticker = ticker.replace("..",".");
  if((ticker.endswith(".O")) or (ticker.endswith(".N"))):
    ticker = ticker[0:-2]

  url = u"https://api.worldtradingdata.com/api/v1/history?symbol="+ticker+"&api_token="+API_KEY

  page = getHtml(url)
  jsondat = json.loads(page)
  if("history" in jsondat):
    for dtkey in jsondat['history']:
        data[dtkey] = {
         'o': jsondat['history'][dtkey]['open'],
         'h': jsondat['history'][dtkey]['high'],
         'l': jsondat['history'][dtkey]['low'],
         'c': jsondat['history'][dtkey]['close'],
         'v': jsondat['history'][dtkey]['volume']
        }
  else:
   print("Warning, can't find World Data: "+ticker)
  return data



def appendLatestPriceDataBitstamp(ticker,data):
  """
  Given our current data on the prices,
  add the newest data we can get, crypto-
  currency version
  """
  ticker = ticker[:-9]
  url = u"https://www.bitstamp.net/api/v2/ticker/"+ticker+"/"
  page = getHtml(url)
  jsondat = json.loads(page)
  if(jsondat['high']):
    now = date.today()
    nowkey = now.isoformat()
    data[nowkey] = {
     'o': jsondat['open'],
     'h': jsondat['high'],
     'l': jsondat['low'],
     'c': jsondat['last'],
     'v': jsondat['volume'],
    }
    
  return data


def appendLatestPriceDataCoinbase(ticker,data):
  """
  Given our current data on the prices,
  add the newest data we can get, crypto-
  currency version
  """
  ticker = ticker[:-8]
  mkt = ticker[0:3]+"-"+ticker[3:6]
  url = "https://api.coinbase.com/v2/prices/"+mkt+"/buy"
  page = getHtml(url)
  jsondat = json.loads(page)
  # {"data":{"base":"BTC","currency":"EUR","amount":"7758.57"}}
  if('data' in jsondat):
    now = date.today()
    nowkey = now.isoformat() 
 
    data[nowkey] = {
     'o': jsondat['data']['amount'],
     'h': jsondat['data']['amount'],
     'l': jsondat['data']['amount'],
     'c': jsondat['data']['amount'],
     'v': 0,
    }
  else:
   print("Warning, can't find Coinbase Crypto: "+ticker)
    
  return data


def appendLatestPriceDataHuobi(ticker,data):
  """
  Given our current data on the prices,
  add the newest data we can get, crypto-
  currency version
  """
  ticker = ticker[:-6]
  url = "https://api.huobi.pro/market/history/kline?period=1day&size=200&symbol="+(ticker.lower())
  page = getHtml(url)
  jsondat = json.loads(page)
  ##First candle is most recent, and so today!?
  if("data" in jsondat):
    for d in jsondat['data']:
        ts = d['id']
        dt = date.fromtimestamp(ts)
        dtkey = dt.isoformat()

        data[dtkey] = {
         'o': jsondat['data'][0]['open'],
         'h': jsondat['data'][0]['high'],
         'l': jsondat['data'][0]['low'],
         'c': jsondat['data'][0]['close'],
         'v': jsondat['data'][0]['vol']
        }
  else:
   print("Warning, can't find Houbi Crypto: "+ticker)
  return data



def appendLatestPriceDataBittrex(ticker,data):
  """
  Given our current data on the prices,
  add the newest data we can get, crypto-
  currency version
  """
  ticker = ticker[:-8]
  mkt = ticker[3:6]+"-"+ticker[0:3]
  if(len(ticker)>6):
    mkt = ticker[4:7]+"-"+ticker[0:4]
  url = "https://api.bittrex.com/api/v1.1/public/getmarketsummary?market="+mkt
  page = getHtml(url)
  jsondat = json.loads(page)
  if((jsondat['success']=="true") or (jsondat['success']==True)):
    now = date.today()
    nowkey = now.isoformat()
    data[nowkey] = {
     'o': jsondat['result'][0]['PrevDay'],
     'h': jsondat['result'][0]['High'],
     'l': jsondat['result'][0]['Low'],
     'c': jsondat['result'][0]['Last'],
     'v': jsondat['result'][0]['Volume']
    }
  else:
   print("Warning, can't find Bittrex Crypto: "+ticker)
    
  return data



def appendLatestPriceDataBitfinex(ticker,data):
  """
  Given our current data on the prices,
  add the newest data we can get, crypto-
  currency version
  """
  ticker = ticker[:-9]
  page = getHtml("https://api-pub.bitfinex.com/v2/candles/trade:1D:t"+ticker+"/hist")
  jsondat = json.loads(str(page))
  if(len(jsondat)>0):
    for dat in jsondat:
      timestamp = dat[0]/1000
      dt = date.fromtimestamp(timestamp)
      dtkey = dt.isoformat()
      
      data[dtkey] = {
       'o': dat[1],
       'c': dat[2],
       'h': dat[3],
       'l': dat[4],
       'v': dat[5],
      }
  return data




def appendLatestPriceDataBinance(ticker,data):
  """
  Given our current data on the prices,
  add the newest data we can get, crypto-
  currency version
  """
  bits = ticker.split(".")
  if(len(bits)<2):
    return data

  symbol = bits[0]; 
  if(symbol.endswith("USD")):
    symbol+="T"
  url = u"https://api.binance.com/api/v1/klines?symbol="+symbol+"&interval=1d"
  page = getHtml(url)
  binanceJson = json.loads(page)

  if(len(binanceJson)>0):
    for dat in binanceJson:
      timestamp = dat[0]/1000
      dt = date.fromtimestamp(timestamp)
      dtkey = dt.isoformat()
      
      data[dtkey] = {
       'o': dat[1],
       'h': dat[2],
       'l': dat[3],
       'c': dat[4],
       'v': dat[5],
      }
  return data



def getSeries(prices,ohlc="c"):
  """
  Turn our price-data in to a simple
  series. We want a weekly series as
  well as the daily series, and best
  return the number of days in those
  weeks too.
  """
  addedWeek=False
  dseries = []
  wseries = []
  dateSeries = []
  lastDay = 0
  weekLen = 1
  lastp = 0
  p = 0
  for day in sorted(prices):
    addedWeek=False
    lastp = p
    dateSeries.append(day)
    p = float(prices[day][ohlc])
    dseries.append(p)

    #If a stock ceases trading, then get get N/A as 
    #a date
    if(day!="N/A"):
      d = dateutil.parser.isoparse(day)
      newDay = d.weekday()
      if(newDay < lastDay):
        #start of new week, so add the last week to the weekly series
        addedWeek=True
        wseries.append(lastp)
        if(weekLen<lastDay):
          weekLen = lastDay+1
      lastDay = newDay

  if(not addedWeek):
    wseries.append(lastp)

  return dseries, wseries, dateSeries, weekLen

  
def calculateEma(nseries,n=25):
  """
  Calculate an exponential Moving Average
  """
  if(len(nseries)<n):
    n=len(nseries)
  ret = pd.Series(nseries).ewm(span=n).mean().tolist()
  for i in range(0,min(n,len(nseries))):
    ret[i] = float("NaN")
  return ret
 


def calculateMa(nseries,n=25):
  """
  Calculate a Moving Average
  """
  if(len(nseries)<n):
    n=len(nseries)
  return pd.Series(nseries).rolling(n).mean().tolist()



def calculateSequential(series,n=4):
  """
  Calculate a basic TD (ish) sequential,
  We just count the main number
  """
  ret = []
  countup=0
  countdown=0
  seq = 0
  for i in range(0,n):
    ret.append(seq)
  for i in range(n, len(series)):
    if(series[i] > series[i-n]):
      countdown=0
      countup+=1
      if(countup>9):
       countup=1
      seq = countup
    else:
      countup=0
      countdown+=1
      if(countdown>9):
       countdown=1
      seq=-countdown
    ret.append(seq)
  return ret
   


def calculateRsi(nseries,n=14):
  """
  Calculate an RSI 
  """
  deltas = np.diff(nseries)
  seed = deltas[:n+1]
  up = seed[seed>=0].sum()/n
  down = -seed[seed<0].sum()/n
  rs = up
  if(down!=0): 
    rs = up/down
  rsi = np.zeros_like(nseries)
  rsi[:n] = 100.0 - 100.0/(1.0+rs)
  for i in range(n, len(nseries)):
    delta = deltas[i-1]
    if delta>0:
        upval = delta
        downval = 0.
    else:
        upval = 0.
        downval = -delta
    up = (up*(n-1) + upval)/n
    down = (down*(n-1) + downval)/n
    rs = up
    if(down!=0): 
      rs = up/down
    rsi[i] = 100. - 100./(1.+rs)
  return rsi
  


def doAlert(bullchange,ticker,uniqcode,message,daysAgo=0):
  """
  Send an alert
  """
  global bullishness, bullreason, uniqcodes, LogLevel
  uniqcode = ticker+":"+uniqcode
  if(uniqcode in uniqcodes):
    uniqcodes[uniqcode] += 1
    return False
  uniqcodes[uniqcode] = 1

  if(not ticker in bullishness_tops):
    bullishness_tops[ticker]=0
    bullreason_tops[ticker]=""
    bullishness_bots[ticker]=0
    bullreason_bots[ticker]=""

  if(not ticker in bullishness):
    bullishness[ticker]=0
    bullreason[ticker]=""
  else:
    bullreason[ticker]+=", "

  bullishness[ticker]+=bullchange
  bullreason[ticker]+= message

  if(bullishness_tops[ticker]<=bullishness[ticker]):
    bullishness_tops[ticker] = bullishness[ticker]
    bullreason_tops[ticker] = bullreason[ticker]
    if(daysAgo>0):
      bullreason_tops[ticker] = str(daysAgo)+" days ago: "+bullreason_tops[ticker]
  if(bullishness_bots[ticker]>=bullishness[ticker]):
    bullishness_bots[ticker] = bullishness[ticker]
    bullreason_bots[ticker] = bullreason[ticker]
    if(daysAgo>0):
      bullreason_bots[ticker] = str(daysAgo)+" days ago: "+bullreason_bots[ticker]

  if(bullchange>=0):
    string="+"
  else:
    string="-"
  string="%s %s \t [%s] %d ago" % (string,ticker,message,daysAgo)
  alerts.append(string)
  if(LogLevel>=1):
    print(string)
  return True


def runChecks(tickers):
  """
  Update all our data and run the checks,
  return a full list of most recent price
  for all tickers.
  """
  global LogLevel, Backtestdays, ShowGraphs, Checks
  global BetStore, PlaceBetArgs, tickerParams, bullishness, bullreason
  outTable = []
  latestPrices = {}
  for ticker in tickers:
    ema1 = 20
    ema2 = 50
    ema3 = 100
    ema4 = 200
    ma1 = 25
    ma2 = 50
    ma3 = 100
    ma4 = 200

    if(ticker in tickerParams):
      p = tickerParams[ticker]
      l = len(p)
      if(l>0):ema1=int(p[0]);
      if(l>1):ema2=int(p[1]);
      if(l>2):ema3=int(p[2]);
      if(l>3):ema4=int(p[3]);
      if(l>4):ma1=int(p[4]);
      if(l>5):ma2=int(p[5]);
      if(l>6):ma3=int(p[6]);
      if(l>7):ma4=int(p[7]);

    price = -1
    score = 0
    highestDayscore = 0
    highestDayscoreDay = 0
    prices = getPrices(ticker)
    dseries, wseries, dateSeries, wlen = getSeries(prices,"c")


    if(PlaceBetArgs!=None):
      placeBet(ticker,dseries,PlaceBetArgs);


    if(len(dseries)>2):
      #Set the latest price for export
      price = latestPrices[ticker] = dseries[-1]

      #Some indicators
      rsi  = calculateRsi(dseries,14);
      w_rsi= calculateRsi(wseries,14);
      ma1s = calculateMa(dseries,ma1);
      ma2s = calculateMa(dseries,ma2);
      ma3s = calculateMa(dseries,ma3);
      ma4s = calculateMa(dseries,ma4);
      ema1s = calculateEma(dseries,ema1);
      ema2s = calculateEma(dseries,ema2);
      ema3s = calculateEma(dseries,ema3);
      ema4s = calculateEma(dseries,ema4);
      seq  = calculateSequential(dseries,4)
      w_seq= calculateSequential(wseries,4)

      #Check every day in the range.
      for d in range(BacktestDays,-1,-1):   #d = daysAgo
        bullishness={}
        bullreason ={}

        dayscore=0
        #TODO: this date calculation is aproximate. Calendars are a fucking nightmare.
        #we need to account for holidays and otherwise hissing data etc.
        w = int(math.ceil(float(d)/float(wlen)))

        #Daily-candles checks if we have enough data 
        if(len(dseries)>0):
          #RSI
          if("rsi" in Checks):
            diff,isNew = checkRsi(rsi,d,ticker,"Daily",d)
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"rsi",diff,dseries)

          #MA cross
          if(("max1" in Checks) and ("max2" in Checks)):
            diff,isNew = checkMaCross(ma1s,ma2s,d,ticker,"Short %d vs Med %d"%(ma1,ma2))
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"max12",diff,dseries)
          if(("max1" in Checks) and ("max3" in Checks)):
            diff,isNew = checkMaCross(ma1s,ma3s,d,ticker,"Short %d vs %d Long"%(ma1,ma2))
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"max13",diff,dseries)
          if(("max1" in Checks) and ("max4" in Checks)):
            diff,isNew = checkMaCross(ma1s,ma4s,d,ticker,"Short %d vs %d VLong"%(ma1,ma4))
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"max14",diff,dseries)
          if(("max2" in Checks) and ("max3" in Checks)):
            diff,isNew = checkMaCross(ma2s,ma3s,d,ticker,"Med %d vs %d Long"%(ma2,ma3))
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"max23",diff,dseries)
          if(("max2" in Checks) and ("max4" in Checks)):
            diff,isNew = checkMaCross(ma2s,ma4s,d,ticker,"Med %d vs %d VLong"%(ma2,ma4))
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"max24",diff,dseries)
          if(("max3" in Checks) and ("max4" in Checks)):
            diff,isNew = checkMaCross(ma3s,ma4s,d,ticker,"Long %d vs %d VLong"%(ma3,ma4))
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"max34",diff,dseries)

          #EMA cross
          if(("emax1" in Checks) and ("emax2" in Checks)):
            diff,isNew = checkMaCross(ema1s,ema2s,d,ticker,"Exp-Short %d vs Med %d"%(ema1,emas))
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"emax12",diff,dseries)
          if(("emax1" in Checks) and ("emax3" in Checks)):
            diff,isNew = checkMaCross(ema1s,ema3s,d,ticker,"Exp-Short %d vs Long %d"%(ema11,ema3))
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"emax13",diff,dseries)
          if(("emax1" in Checks) and ("emax4" in Checks)):
            diff,isNew = checkMaCross(ema1s,ema4s,d,ticker,"Exp-Short %d vs VLong %d"%(ema1,ema4))
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"emax14",diff,dseries)
          if(("emax2" in Checks) and ("emax3" in Checks)):
            diff,isNew = checkMaCross(ema2s,ema3s,d,ticker,"Exp-Med %d vs Long %d"%(ema2,ema3))
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"emax23",diff,dseries)
          if(("emax2" in Checks) and ("emax4" in Checks)):
            diff,isNew = checkMaCross(ema2s,ema4s,d,ticker,"Exp-Med %d vs VLong %d"%(ema2,ema4))
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"emax24",diff,dseries)
          if(("emax3" in Checks) and ("emax4" in Checks)):
            diff,isNew = checkMaCross(ema3s,ema4s,d,ticker,"Exp-Long %d vs %d Vlong"%(ema3,ema4))
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"emax34",diff,dseries)

          #Sequential Nines
          if("seq" in Checks):
            diff,isNew = checkSequential(seq,d,ticker,"d",d)
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"seq",diff,dseries)

          #MASort -> Are the moving averages sorted into bull/bear order?
          if("masort" in Checks):
            diff,isNew = checkMASort(ma1s,ma2s,ma3s,ma4s,d,ticker,"MA")
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"masort",diff,dseries)

          #MASort -> Are the moving averages sorted into bull/bear order?
          if("emasort" in Checks):
            diff,isNew = checkMASort(ema1s,ema2s,ema3s,ema4s,d,ticker,"EMA")
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"emasort",diff,dseries)

         
        #Weekly-candles checks if we have enough data, cecking weekly candles every day.
        if(len(wseries)>0):
          #Weekly RSI
          if("rsi_w" in Checks):
            diff,isNew = checkRsi(w_rsi,w,ticker,"Weekly",d)
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"rsi_w",diff,dseries)

          #Weekly Sequential Nines
          if("seq_w" in Checks):
            diff,isNew = checkSequential(w_seq,w,ticker,"w",d)
            score += diff
            dayscore += diff
            if(isNew):
              logResult(ticker,d,"seq_w",diff,dseries)

        #Multi doesn't add to score, can only be checked after all tests
        if("multi" in Checks):
          if(dayscore>=MultiCheck):
            logResult(ticker,d,"multi",+1,dseries)
          if(dayscore<=-MultiCheck):
            logResult(ticker,d,"multi",-1,dseries)

        #Bet-alerting doesn't add to scores coz it's the *end* of the bet.
        if("bets" in Checks):
          diff,isNew = checkBetExpire(dateSeries,dseries,d,ticker)
          if(isNew):
            logResult(ticker,d,"bet_%s"%("w" if diff>1 else "l"),diff,dseries)
          

        #Control randomness doesn't add to score either.
        if("ctrl" in Checks):
          diff,isNew = checkCtrl(ticker,d)
          if(isNew):
            logResult(ticker,d,"ctrl",diff,dseries)

        #High-Score list
        if(abs(dayscore)>highestDayscore):
          highestDayscore = dayscore
          highestDayscoreDay = d

        if(LogLevel>0):
            print(ticker+", "+str(d)+" days ago. Score: "+str(dayscore))


      #Back to once per ticker, Draw the graph
      if(ShowGraphs>0):
          ax1 = pyplot.subplot(2,1,1) # 2rows, 1cols, It's the first, Ie across top
          ax1.margins(0.,0.)
          ax1.plot(ema1s, color="#00ff00")
          ax1.plot(ema2s, color="#88ff00")
          ax1.plot(ema3s, color="#ff8800")
          ax1.plot(ema4s, color="#ff0000")
          ax1.plot(ma1s, color="#008800")
          ax1.plot(ma2s, color="#448800")
          ax1.plot(ma3s, color="#884400")
          ax1.plot(ma4s, color="#880000")
          ax1.plot(dseries, color="#000000")
          ax1.set_title(ticker+', '+str(len(dseries))+" days")

          ax2 = pyplot.subplot(2,2,3) #2x2 grid, 3rd pos, bottom left
          ax2.margins(0.,0.)
          ax2.plot(rsi, color="#ff0000")
          ax2.plot(w_rsi, color="#880000")
          ax2.plot(seq, color="#00ff00")
          ax2.plot(w_seq, color="#008800")
          ax2.axhline(y=50, xmin=0.0, xmax=1.0, color='#550000')
          ax2.axhline(y=30, xmin=0.0, xmax=1.0, color='#550000')
          ax2.axhline(y=70, xmin=0.0, xmax=1.0, color='#550000')
          ax2.axhline(y=-9, xmin=0.0, xmax=1.0, color='#005500')
          ax2.axhline(y=0, xmin=0.0, xmax=1.0, color='#005500')
          ax2.axhline(y=9, xmin=0.0, xmax=1.0, color='#005500')
          ax2.set_title('RSI')

          ax3 = pyplot.subplot(2,2,4) # 2x2 grid, it's the 4th, bottom right
          ax3.margins(0.,0.)
          ax3.plot(ema1s[-30:], color="#00ff00")
          ax3.plot(ema2s[-30:], color="#88ff00")
          ax3.plot(ema3s[-30:], color="#ff8800")
          ax3.plot(ema4s[-30:], color="#ff0000")
          ax3.plot(ma1s[-30:], color="#008800")
          ax3.plot(ma2s[-30:], color="#448800")
          ax3.plot(ma3s[-30:], color="#884400")
          ax3.plot(ma4s[-30:], color="#880000")
          ax3.plot(dseries[-30:], color="#000000")
          ax3.set_title('Last 30 day')
          pyplot.subplots_adjust(left=0.07, bottom=0.05, 
                                 right=0.98, top=0.95, 
                                 wspace=0.2, hspace=0.25)

          pyplot.show()

      #Save for debug if debug level?
      outTable.append([ticker,price,score,highestDayscore,highestDayscoreDay])

      #Log if you wanna log
      if(LogLevel>=2):
        print("%s \t price: %f \t score: %i \t high: %i \t day: %i"%(ticker,price,score,highestDayscore,highestDayscoreDay))

  if(LogLevel>=1):
    print(tabulate(outTable,["Ticker","Price","Indic Sum","Best score", "On day"]))
  return latestPrices



def checkMASort(seq1,seq2,seq3,seq4,daysAgo,ticker,t="XA"):
  """
  Check for the sort-order of the moving-averages
  Today is the LAST element of the array,
  """
  if((len(seq1)<=daysAgo+1) or
     (len(seq2)<=daysAgo+1) or
     (len(seq3)<=daysAgo+1) or
     (len(seq4)<=daysAgo+1)):
    return 0,False

  nowIdx = min(len(seq1),len(seq2),len(seq3),len(seq4)) - daysAgo -1

  isBull=False; wasBull=False;
  if((seq1[nowIdx] >= seq2[nowIdx]) and
     (seq2[nowIdx] >= seq3[nowIdx]) and
     (seq3[nowIdx] >= seq4[nowIdx])):
       isBull=True
  if((seq1[nowIdx-1] >= seq2[nowIdx-1]) and
     (seq2[nowIdx-1] >= seq3[nowIdx-1]) and
     (seq3[nowIdx-1] >= seq4[nowIdx-1])):
       wasBull=True
  if(isBull and not wasBull):
    x=doAlert(+1,ticker,"mas"+t+str(daysAgo),"%s Sort Went Bullish" % (t),daysAgo)
    return +1,x
  if(wasBull and not isBull):
    x=doAlert(-1,ticker,"mas"+t+str(daysAgo),"%s Sort Ended Bullish" % (t),daysAgo)
    return -1,x

  isBear=False; wasBear=False;
  if((seq1[nowIdx] >= seq2[nowIdx]) and
     (seq2[nowIdx] >= seq3[nowIdx]) and
     (seq3[nowIdx] >= seq4[nowIdx])):
       isBear=True
  if((seq1[nowIdx-1] >= seq2[nowIdx-1]) and
     (seq2[nowIdx-1] >= seq3[nowIdx-1]) and
     (seq3[nowIdx-1] >= seq4[nowIdx-1])):
       wasBear=True
  if(isBear and not wasBear):
    x=doAlert(-1,ticker,"mas"+t+str(daysAgo),"%s Sort Went Bearish" % (t),daysAgo)
    return -1,x
  if(wasBear and not isBear):
    x=doAlert(+1,ticker,"mas"+t+str(daysAgo),"%s Sort Ended Bearish" % (t),daysAgo)
    return +1,x
  return 0,False


def checkBetExpire(dateSeries,priceSeries,daysAgo,ticker):
  """
  Check if this ticker has just won or lost any of 
  the bets that have been placed.
  """
  retScore = 0
  nowIdx = len(priceSeries) - daysAgo-1

  hitTarget=False
  for b in BetStore:                                              ##Check each bet
    if(b['tk']==ticker):                                          ##Has the right ticker
      startBetIndex = getIndexInDateSeries(b['ts'],dateSeries)
      if((startBetIndex>=0)and(startBetIndex <= nowIdx)):         ##Passed the start-date
        for i in range(startBetIndex+1,min(len(priceSeries),startBetIndex+b['dy'])):
          if(b['pr'] < b['bt']):   ##Long bet
            if(priceSeries[i]>=b['bt']):
              #Bet hit target on day i
              if(nowIdx==i):
                doAlert(+1,ticker,"bet_w","Long Win: %0.2f beats target"%(priceSeries[i]),daysAgo)
                retScore+=1;
              hitTarget=True
              break;
            if(priceSeries[i]<=b['st']):
              #Stop hit on day i
              if(nowIdx==i):
                doAlert(-1,ticker,"bet_w","Long Loss: Stop Reached",daysAgo)
                retScore-=1;
              hitTarget=True
              break;

          else:                    ##Short bet
            if(priceSeries[i]<=b['bt']):
              #Bet hit target on day i
              if(nowIdx==i):
                doAlert(+1,ticker,"bet_w","Short Win: %0.2f beats target"%(priceSeries[i]),daysAgo)
                retScore+=1;
              hitTarget=True
              break;
            if(priceSeries[i]>=b['st']):
              #Stop hit on day i
              if(nowIdx==i):
                doAlert(-1,ticker,"bet_w","Short Loss: Stop Reached",daysAgo)
                retScore-=1;
              hitTarget=True
              break;

        ##Bet timed out?
        if((not hitTarget) and (nowIdx==startBetIndex+b['dy'])):
          if(b['pr'] < b['bt']):   ##Long bet
            if(priceSeries[nowIdx]>=b['pr']):
              doAlert(+1,ticker,"bet_w","Long Win: Timed Out In Profit",daysAgo)
              retScore+=1;
            else:
              doAlert(-1,ticker,"bet_l","Long Loss: Timed Out In Loss",daysAgo)
              retScore-=1;
          else:                    ##Short bet
            if(priceSeries[nowIdx]>=b['pr']):
              doAlert(-1,ticker,"bet_w","Short Loss: Timed Out In Loss",daysAgo)
              retScore-=1;
            else:
              doAlert(+1,ticker,"bet_l","Short Win: Timed Out In Profit",daysAgo)
              retScore+=1;

  if(retScore==0):
    return 0,False
  return retScore,True





def checkCtrl(ticker,daysAgo):
  """
  Check for just a random 1% chance, to use as a control
  to compare other checks against
  """
  if(random.random() > 0.99):
    x=doAlert(+1,ticker,"rndbull","Random Bull",daysAgo)
    return +1,x
  if(random.random() > 0.99):
    x=doAlert(-1,ticker,"rndbear","Random Bear",daysAgo)
    return -1,x
  return 0,False


def checkSequential(seq,daysAgo,ticker,t="d",realDaysAgo=-1):
  """
  Check for a sequential nine
  Today is the LAST element of the array,
  """
  if(realDaysAgo==-1):
    realDaysAgo = daysAgo

  if(len(seq)<daysAgo):
    return 0,False
  nowIdx = len(seq) - daysAgo -1

  if(seq[nowIdx]==9):
    x=doAlert(-1,ticker,"g9"+t+str(realDaysAgo), "SEQ Green 9 %s" % (t),realDaysAgo)
    return -1,x
  if(seq[nowIdx]==-9):
    x=doAlert(+1,ticker,"r9"+t+str(realDaysAgo), "SEQ Red 9 %s" % (t),realDaysAgo)
    return +1,x
  return 0,False
  


def checkMaCross(ma1s,ma2s,daysAgo,ticker,txt):
  """
  Check for the point two averages cross
  Today is the LAST element of the array,
  """
  if((len(ma1s)<daysAgo+1) or (len(ma2s)<daysAgo+1)):
    return 0,False
  nowIdx = len(ma1s) - daysAgo-1

  if((ma1s[nowIdx] > ma2s[nowIdx]) and (ma1s[nowIdx-1] <= ma2s[nowIdx-1])):
    x=doAlert(+1,ticker,txt+"x"+str(daysAgo),"GCross %s" % (txt),daysAgo)
    return +1,x

  if((ma1s[nowIdx] < ma2s[nowIdx]) and (ma1s[nowIdx-1] >= ma2s[nowIdx-1])):
    x=doAlert(-1,ticker,txt+"x"+str(daysAgo),"DCross %s" % (txt),daysAgo)
    return -1,x

  return 0,False





def checkRsi(rsi,daysAgo,ticker,t="Daily",realDaysAgo=-1):
  """
  Check for the RSI to cross the 70/30 border
  Today is the LAST element of the array,
  """
  if(realDaysAgo==-1):
    realDaysAgo = daysAgo

  if(len(rsi)<daysAgo+1):
    return 0,False
  nowIdx = len(rsi) - daysAgo-1

  if((rsi[nowIdx] > 30) and (rsi[nowIdx-1] < 30)):
    x=doAlert(+1,ticker,"du_rsi_"+str(realDaysAgo),"RSI "+t+" up",realDaysAgo)
    return +1,x
  if((rsi[nowIdx] < 70) and (rsi[nowIdx-1] > 70)):
    x=doAlert(-1,ticker,"dd_rsi_"+str(realDaysAgo),"RSI "+t+" falling",realDaysAgo)
    return -1,x
  return 0,False




def logResult(ticker, daysAgo, indicode, prediction, prices):
  """
  Log a result to the global stats-tracker.
  When we are back-testing and find a signal
  that happened more than 7 days ago we should
  be able to sell if it paid off or not and
  keep track of that.
  Today is the LAST element of the price array,
  """
  global resultLog

  if(prediction==0):
    return

  if(daysAgo<5):
    return

  if(daysAgo>=len(prices)):
    return

  if(not indicode in resultLog):
    resultLog[indicode] = {}

  if(not ticker in resultLog[indicode]):
    resultLog[indicode][ticker] = {}
    resultLog[indicode][ticker][-1] = []
    resultLog[indicode][ticker][+1] = []
  

  nowIdx = len(prices) - daysAgo-1
  startPrice = prices[nowIdx];
  if(startPrice<=0):
    print("Ticker %s has a price of zero %d days ago (%d index into list %d long). Weird!?"%(ticker,daysAgo,nowIdx,len(prices)))
    return
  keepTill = nowIdx+ANALYSISPERIOD+1
  if(keepTill>len(prices)):
    keepTill = len(prices)
  gains = []
  for newprice in prices[nowIdx:keepTill]:
    gains.append(((newprice-startPrice)/startPrice))
  logEntry = {
    'o': startPrice,
    'p': prediction,
    'd': daysAgo,
    's': prices[nowIdx:nowIdx+keepTill],
    'g': gains
  }
  resultLog[indicode][ticker][prediction].append(logEntry)


   


def showResultLog():
  """
  Summarize the results log in tables.
  """
  global resultLog, ANALYSISPERIOD, TriggerPercent
  if(len(resultLog)<=0):
    return

  #We build a table showing the average gain found after indicator triggering
  avgGainDisplay = []

  #We build a table showing how many days until the price jumps/drops by X percent following a signal
  daysTillXPercentDisplay = []

  #Display Bull Indicators, then Bearish
  for prediction in ([+1,-1]):
    bullbear = "Bull" if (prediction>=0) else "Bear"
    #For every indicator's code
    for indicode in resultLog:
      avgGains = [0] * (ANALYSISPERIOD+1)
      avgCnts  = [0] * (ANALYSISPERIOD+1)
      sumHitX  = [0] * (ANALYSISPERIOD+1)

      #For every ticker it was applied to
      for ticker in resultLog[indicode]:
        if(prediction in resultLog[indicode][ticker]):
          #For every time that was trggered and logged...
          for logEntry in resultLog[indicode][ticker][prediction]:
            fmtStg ="%s %s %s:\t %d %0.2f -> ";
            fmtPrm =[indicode,ticker,bullbear,logEntry['d'], logEntry['o']]
            startPrice = logEntry['o']

            #Work out the average gains (Well, total for now, we'll divide shortly)
            hasHitX=False
            for i in range(0,ANALYSISPERIOD+1):
              if(i < len(logEntry['g'])):
                avgGains[i]+=logEntry['g'][i]
                avgCnts[i]+=1
                if(i in TimeCheck_Periods):
                  fmtStg+="\t%0.2f(%0.2f)"
                  fmtPrm.append(logEntry['s'][i])
                  fmtPrm.append(logEntry['g'][i])
                if(logEntry['p']>0):
                  if((logEntry['g'][i]>TriggerPercent)or(hasHitX)):
                    hasHitX=True
                    sumHitX[i]+=1
                else:
                  if((logEntry['g'][i]<-TriggerPercent)or(hasHitX)):
                    hasHitX=True
                    sumHitX[i]+=1

            if(LogLevel>0):
              print(fmtStg % tuple(fmtPrm))

      #Divide the sums of gains to get averages..
      for i in range(0,len(avgGains)):
        if(avgCnts[i]>0): 
          avgGains[i] /= avgCnts[i]

      #Build ouput rows for this indicator's Average Gain
      newRow = [indicode,bullbear]
      for i in TimeCheck_Periods:
        if(i <= len(avgGains)):
          newRow.append("%+0.1f %% / %d" % (avgGains[i]*100,avgCnts[i]))
      avgGainDisplay.append(newRow)

      #Build output rows for this indicator's NumHitX
      newRow = [indicode,bullbear]
      for i in TimeCheck_Periods:
        if(i <= len(sumHitX)):
          newRow.append("%d / %d" % (sumHitX[i],avgCnts[i]))
      daysTillXPercentDisplay.append(newRow)

  print("\nAverage Gain After Signal:")   
  headers = ["Signal","Direction"]
  for i in TimeCheck_Periods:
    headers.append(str(i)+" Bar") 
  print(tabulate(avgGainDisplay,headers))
 

  print("\nNumber that Hit +/-"+str(TriggerPercent*100)+"% gain/loss in bull/bear by:")   
  headers = ["Signal","Direction"]
  for i in TimeCheck_Periods:
    headers.append(str(i)+" Bar") 
  print(tabulate(daysTillXPercentDisplay,headers))


 
def emailAlerts():
  """
  Send an email with the alerts from today.
  Well, send if it says to send in the Global
  option, but definitely print it anyway.
  """
  global alerts, bullishness_tops, bullreason_tops, bullishness_bots, bullreason_bots, Send_Email, Email_Report_Address, MinReportScore
  now = date.today()
  nowkey = now.isoformat()

  bulls =  sorted(bullishness_tops.items(),key=operator.itemgetter(1), reverse=True)

  body = nowkey+"\n\nNice looking things this time:\n"
  for pair in bulls:
    if((pair[1]>0) and (pair[1]>=MinReportScore)):
      body+="%i:\t%s\t%s\n" % (pair[1],pair[0],bullreason_tops[pair[0]][0:120])

  bears =  sorted(bullishness_bots.items(),key=operator.itemgetter(1), reverse=True)

  body+= "\n\nAnd some things looking bad:\n"
  for pair in bears:
    if((pair[1]<0) and (pair[1]<=-MinReportScore)):
      body+="%i:\t%s\t%s\n" % (pair[1],pair[0],bullreason_bots[pair[0]][0:120])

  email_text = "From: %s\nTo: %s\nSubject: %s\n\n%s" % (
    GMAIL_USER, 
    ", ".join(Email_Report_Address), 
    "Daily Stock Summary", 
    body
  )
  print email_text

  if(Send_Email):
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.ehlo()
        server.login(GMAIL_USER, GMAIL_PASSWORD)
        server.sendmail(GMAIL_USER, Email_Report_Address, email_text)
        server.close()
    except:
        print "\n\nWARNING: EMAIL FAILED!\n\n"
   


def placeBet(ticker,prices,params_string):
  """
  Add a bet to the bet-file
  """
  global BetStore
  params = params_string.split("/")
  now = date.today()
  nowkey = now.isoformat()
  price = prices[-1]
  bet = price*1.1
  stop = price*0.95
  days = 20
  confidence = 33
  comment = None
  if(len(params)>0):
    try:
      price = float(params[0])
    except:
      None
  if(len(params)>1):
    try:
      if(params[1][-1]=="%"):
        bet = float(params[1][0:-1])
        bet = price + (price * bet/100)
      else:
        bet = float(params[1])
    except:
      None
  if(len(params)>2):
    try:
      if(params[2][-1]=="%"):
        stop = float(params[2][0:-1])
        stop = price - (price * stop/100)
      else:
        stop = float(params[2])
    except:
      None
  if(len(params)>3):
    try:
      days = int(params[3])
    except:
      None
  if(len(params)>4):
    try:
      if(params[4][-1]=="%"):
        confidence = float(params[4][0:-1])
      else:
        confidence = float(params[4])
    except:
      None
  if(len(params)>5):
    t = params[5]
    if((len(t)==10) and (t[4]=="-") and (t[7]=="-")):
      nowkey = t
  if(len(params)>6):
    comment = params[6];

  newBet = {
    "tk":ticker,
    "ts":nowkey,
    "pr":price,
    "dy":days,
    "bt":bet,
    "st":stop,
    "cn":confidence,
    "rp":None,
    "rc":'P',
  }
  if(comment!=None):
    newBet['cm'] = comment
  BetStore.append(newBet)
  print("Placing Bet: %s, %s\n    ->From %0.2f To %0.2f with a stop of %0.2f or %d days (Conf: %0.2f)\n "%(nowkey,ticker,price,bet,stop,days,confidence))



########################
# Exectuion start
########################

#Process CLI Args
try:
  opts, args = getopt.getopt(sys.argv[1:],"Hhl:e:b:s:g:c:t:p:m:B:",["log=","email=","backtest=","score=","graph=","checks=","ticker=","percent=","multi=","bet=","fetch-history"])
except getopt.GetoptError:
  printHelp()
  sys.exit(2)

for opt,arg in opts:
  #Help
  if(opt=="-h"):
    printHelp()
    sys.exit()

  #Fetch History rather than latest prices.
  elif opt in ("-H","--fetch-history"):
    FetchHistory = True

  #List Checks
  elif(opt == "--list-checks"):
    print "NAME\tALERTS WHEN"
    print "----\t-----------"
    for k in sorted(AllChecks):
      print "%s\t%s" % (k,AllChecks[k])
    sys.exit()

  #Log Level
  elif opt in ("-l","--log"):
    LogLevel = int(arg)

  #Percent Growth to trigger backtest-win
  elif opt in ("-p","--percent"):
    TriggerPercent = (float(arg))/100

  #Multi-check, need X check-hits in a day to trigger:
  elif opt in ("-m","--multi"):
    MultiCheck = (int(arg))

  #Email
  elif opt in ("-e","--email"):
    if(("false" in arg.lower()) or (arg=="0") or ("no" in arg.lower())):
      Send_Email = False
    else:
      Send_Email = True

  #ShowGraphis
  elif opt in ("-g","--graphs"):
    ShowGraphs = int(arg)

  #Ticker Filter
  elif opt in ("-t","--ticker-filter"):
    TickerFilter = str(arg)

  #Backtest Days
  elif opt in ("-b","--backtest"):
    BacktestDays = int(arg)

  #Checks to run
  elif opt in ("-c","--checks"):
    if(arg=="all"):
      Checks = AllChecks.keys() 
    else:
      Checks = arg.replace(" ","").split(",")

  #Min Report Score
  elif opt in ("-s","--score"):
    MinReportScore = int(arg)

  #Min Report Score
  elif opt in ("-B","--bet"):
    PlaceBetArgs = arg;


#Print a header to the log.
if(LogLevel>=1):
  now = date.today()
  nowkey = now.isoformat()
  print("\n\nChecking stocks at %s%s:" % (nowkey, ", Sending Email" if Send_Email else ""))

#Init
os.chdir(MyDirectory) #Start in the right directory
readTickers()
readBets()

#Update prices and run checks...
latestPrices = runChecks(tickers)

saveBets()

#Send out the accumulated alerts.
emailAlerts()

#Re-save the Libre-Office import...
updateTheCsv(OUT_CSV_FILE,
             latestPrices,
             OUT_HTML_FILE)

#If there was a backtest-result, show that.
showResultLog()  


