from io import StringIO
import pandas as pd
import json
import os
from dateutil import parser

from services.aws.ssm import SSMService
from services.aws.s3 import S3Service

skip_sizes = {
    '1min': 350000,
    '5min': 75000,
    '15min': 25000
}


def divide_price_files():
    env = SSMService.build().get_param('/cointosis/forex_trader_v2')
    s3 = S3Service.build(env, None)
    _backtest_env = s3.read_from_s3(
        'forex_trader_v2/backtest_forex_trader_v2.json',
        'cointosis-backtest')
    backtest_env = json.loads(_backtest_env)
    for tf in ['5min', '15min', '30min', '1hr', '4hr', '1day']:
        for p in [
            {"symbol": "GBP_USD", "start": "2005-01-01", "end": "2015-01-01"},
            {"symbol": "EUR_JPY", "start": "2005-01-01", "end": "2015-01-01"},
            {"symbol": "CAD_CHF", "start": "2005-01-01", "end": "2015-01-01"}
        ]:
            symbol = p.get('symbol')
            filename = 'forex_trader_v2/prices/{start}-{end}/{syear}-{eyear}_{symbol}_{tf}.csv'.format(
                start=p.get('start').split('-')[0],
                end=p.get('end').split('-')[0],
                syear=''.join(p.get('start').split('-')),
                eyear=''.join(p.get('end').split('-')),
                symbol=''.join(symbol.split('_')),
                tf=tf)
            if not os.path.exists(filename.split('/')[-1]) and s3.s3_file_exists(filename, 'cointosis-backtest'):
                obj = s3.client.get_object(Bucket='cointosis-backtest', Key=filename)
                price_df = pd.read_csv(obj['Body'])
            else:
                price_df = pd.read_csv(filename.split('/')[-1])
            batch_start_ix = 0
            year_changed = False
            next_df = None
            index = 0
            while True:
                if tf == '15min':
                    print()
                if index >= len(price_df):
                    index = len(price_df) - 1
                    year_changed = True
                r = price_df.iloc[index]
                start_year = price_df.iloc[batch_start_ix].Time[0:4]
                end_year = r.Time[0:4]
                if int(start_year) < int(end_year):
                    year_changed = True
                if r.Time[5:10] in ['01-02', '01-03', '01-04', '01-05'] and tf in skip_sizes and not year_changed:
                    index += skip_sizes.get(tf)
                if year_changed:
                    start_date = parser.parse(price_df.iloc[batch_start_ix].Time)
                    end_date = parser.parse(price_df.iloc[index-1].Time)
                    upload_file = 'forex_trader_v2/prices/{ly}-{cy}/{sy}{sm}{sd}_{ey}{em}{ed}_{sym}_{tf}.csv'.format(
                        ly=start_date.year,
                        cy=start_date.year + 1,
                        sy=start_date.year,
                        sm=f'{"0" if start_date.month < 10 else ""}{start_date.month}',
                        sd=f'{"0" if start_date.day < 10 else ""}{start_date.day}',
                        ey=end_date.year,
                        em=f'{"0" if end_date.month < 10 else ""}{end_date.month}',
                        ed=f'{"0" if end_date.day < 10 else ""}{end_date.day}',
                        sym=''.join(symbol.split('_')),
                        tf=tf)
                    df_buffer = StringIO()
                    next_df = price_df[batch_start_ix:index]
                    next_df.to_csv(df_buffer)
                    s3.write_to_s3(upload_file, df_buffer.getvalue(), 'cointosis-backtest')
                    batch_start_ix = index
                    next_df = None
                    year_changed = False
                    if index == (len(price_df) - 1):
                        break
                index += 1
            if os.path.exists(filename.split('/')[-1]):
                os.remove(filename.split('/')[-1])


if __name__ == '__main__':
    divide_price_files()