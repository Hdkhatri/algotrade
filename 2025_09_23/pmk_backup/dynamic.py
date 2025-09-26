configs = {
    "60minute_PARALLEL_EMA": {
        "INTERVAL": "5minute",
        "QTY": 75,
        "NEAREST_LTP": 60,
        "INTRADAY": "no", #yes or no
        "NEW_TRADE" : "yes", #yes or no
        "TRADE": "no", #yes or no
        "EXPIRY": "LAST", #NEXT_WEEK, NEXT_TO_NEXT_WEEK, LAST
        "ROLLOVER": True, #True or False
        "ROLLOVER_WITH_NEXT_EXPIRY": False, #True or False
        "STRATEGY": "PARALLEL_EMA" #GOD_EMA, PARALLEL_EMA, HDSTRATEGY 
    },
    "60minute_GOD_EMA": {
        "INTERVAL": "5minute",
        "QTY": 75,
        "NEAREST_LTP": 60,
        "INTRADAY": "no", #yes or no
        "NEW_TRADE" : "yes", #yes or no
        "TRADE": "no", #yes or no
        "EXPIRY": "LAST", #NEXT_WEEK, NEXT_TO_NEXT_WEEK, LAST
        "ROLLOVER": True, #True or False
        "ROLLOVER_WITH_NEXT_EXPIRY": False, #True or False
        "STRATEGY": "GOD_EMA" #GOD_EMA, PARALLEL_EMA, HDSTRATEGY 
    },
    "60minute_HDSTRATEGY": {
        "INTERVAL": "5minute",
        "QTY": 75,
        "NEAREST_LTP": 60,
        "INTRADAY": "no", #yes or no
        "NEW_TRADE" : "yes", #yes or no
        "TRADE": "no", #yes or no
        "EXPIRY": "LAST", #NEXT_WEEK, NEXT_TO_NEXT_WEEK, LAST
        "ROLLOVER": True, #True or False
        "ROLLOVER_WITH_NEXT_EXPIRY": False, #True or False
        "STRATEGY": "HDSTRATEGY" #GOD_EMA, PARALLEL_EMA, HDSTRATEGY 
    }   
}

