configs = {
    "30minute_PARALLEL_EMA_NEXT_WEEK": {
        "INTERVAL": "30minute",
        "QTY": 75,
        "NEAREST_LTP": 50,
        "INTRADAY": "no", #yes or no
        "NEW_TRADE" : "yes", #yes or no--yes will allow new trades , no will stop new trades
        "TRADE": "yes", #yes or no--yes will allow trades , no will stop trades
        "EXPIRY": "NEXT_WEEK", #NEXT_WEEK, NEXT_TO_NEXT_WEEK, LAST
        "ROLLOVER": True, #True or False
        "ROLLOVER_WITH_NEXT_EXPIRY": False, #True or False
        "STRATEGY": "PARALLEL_EMA" #GOD_EMA, PARALLEL_EMA, HDSTRATEGY 
    },
    "30minute_PARALLEL_EMA_LAST": {
        "INTERVAL": "30minute",
        "QTY": 75,
        "NEAREST_LTP": 100,
        "INTRADAY": "no", #yes or no
        "NEW_TRADE" : "yes", #yes or no--yes will allow new trades , no will stop new trades
        "TRADE": "yes", #yes or no--yes will allow trades , no will stop trades
        "EXPIRY": "LAST", #NEXT_WEEK, NEXT_TO_NEXT_WEEK, LAST
        "ROLLOVER": True, #True or False
        "ROLLOVER_WITH_NEXT_EXPIRY": False, #True or False
        "STRATEGY": "PARALLEL_EMA" #GOD_EMA, PARALLEL_EMA, HDSTRATEGY 
    },
    "60minute_PARALLEL_EMA_NEXT_WEEK": {
        "INTERVAL": "60minute",
        "QTY": 75,
        "NEAREST_LTP": 40,
        "INTRADAY": "no", #yes or no
        "NEW_TRADE" : "yes", #yes or no--yes will allow new trades , no will stop new trades
        "TRADE": "yes", #yes or no--yes will allow trades , no will stop trades
        "EXPIRY": "NEXT_WEEK", #NEXT_WEEK, NEXT_TO_NEXT_WEEK, LAST
        "ROLLOVER": True, #True or False
        "ROLLOVER_WITH_NEXT_EXPIRY": False, #True or False
        "STRATEGY": "PARALLEL_EMA" #GOD_EMA, PARALLEL_EMA, HDSTRATEGY 
    }

}

