from alpaca_trade_api.rest import TimeFrame, TimeFrameUnit

api_timeframe_mapping = {
    '1min':  TimeFrame(1, TimeFrameUnit.Minute),
    '5min':  TimeFrame(5, TimeFrameUnit.Minute),
    '15min': TimeFrame(15, TimeFrameUnit.Minute),
    '30min': TimeFrame(30, TimeFrameUnit.Minute),
    '1hr':   TimeFrame(1, TimeFrameUnit.Hour),
    '4hr':   TimeFrame(4, TimeFrameUnit.Hour),
    '1day':  TimeFrame(1, TimeFrameUnit.Day),
}

df_timeframe_mapping = {
    '1min':  '1T',
    '5min':  '5T',
    '15min': '15T',
    '30min': '30T',
    '1hr':   '1H',
    '4hr':   '4H',
    '1day':  '1D',
}
