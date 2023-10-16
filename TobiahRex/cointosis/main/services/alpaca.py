from pprint import pprint

from alpaca_trade_api.rest import REST, APIError
import constants.alpaca as constants


class AlpacaService:
    def __init__(self, alpaca_client, is_fake=True):
        self.client = alpaca_client
        self.account_id = self._get_account_id()


    @staticmethod
    def get_base_url(is_fake):
        if not is_fake:
            return 'https://api.alpaca.markets'
        else:
            return 'https://paper-api.alpaca.markets'

    @staticmethod
    def build(env, is_fake=True):
        alpaca_client = REST(
            key_id=env.get('alpaca').get('key_id'),
            secret_key=env.get('alpaca').get('secret_key'),
            base_url=AlpacaService.get_base_url(is_fake),
            raw_data=True
        )
        return AlpacaService(alpaca_client, is_fake)

    def _check_symbol(self, symbol):
        if symbol is None or self.get_asset_info(symbol) is None:
            raise Exception(f'Symbol: {symbol} not recognized')

    def _local_reagg_prices_df(self, prices_df, timeframe):
        tf = constants.df_timeframe_mapping[timeframe]
        return prices_df.resample(tf).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'sum',
        })

    def _get_account_info(self):
        '''
        Returns the account information, "...including account status, funds available
        for trade, funds available for withdrawal, and various flags relevant to an
        account’s ability to trade."

        Account model: https://alpaca.markets/docs/api-references/trading-api/account/#account-model
        '''
        return self.client.get_account()

    def _get_account_id(self):
        return self.get_account_info()['id']

    def verify_client(self):
        return self.client is not None

    def _get_instruments(self, asset_type='crypto'):
        '''
        Returns the list of active & tradable assets. Refer to `get_asset_info()` for the Asset model.

        Parameters:
        - asset_type: One of {'crypto', 'us_equity', ...}
        '''
        all_assets = self.client.list_assets(asset_class=asset_type)
        return [asset for asset in all_assets if asset['status'] == 'active' and asset['tradable']]

    def get_asset_info(self, symbol):
        '''
        Returns information about a specific asset or None if it does not exist.

        Asset model:
        {
            'id': 'aaaaaaaa-bbbb-cccc-1234-1234567890ab',
            'class': 'crypto',
            'exchange': 'ABCD',
            'symbol': 'BTCUSD',
            'name': 'Bitcoin',
            'status': 'active',
            'tradable': True,
            'marginable': False,
            'shortable': False,
            'easy_to_borrow': False,
            'fractionable': True
        }
        '''
        try:
            return self.client.get_asset(symbol)
        except APIError as err:
            if str(err).startswith('asset not found'):
                return None
            else:
                raise err

    def _get_latest_prices(self, symbol, timeframe, start=None, size=100):
        '''
        For a given crypto pair, fetch an OHLCV DataFrame with the following columns:
        - timestamp (index), open, high, low, close, volume

        Parameters:
        - symbol: A crypto pair symbol. You can fetch the list of available crypto pairs with `get_available_assets(asset_type='crypto')`
        - start: A RFC-3339-formatted timestamp
            examples: '2020-06-15', '2019-10-12 08:00:00.00Z' (UTC), '2018-05-20 16:00:00.00Z-04:00' (UTC-4)
        - timeframe: One of the following: 1min, 5min, 15min, 30min, 1hr, 4hr, 1day
        '''
        if self.get_asset_info(symbol) is None:
            raise Exception(f'Symbol: {symbol} not recognized')
        prices_df = self.client.get_crypto_bars(
            symbol=symbol,
            timeframe=constants.api_timeframe_mapping[timeframe],
            start=start,
            limit=size,
        ).df
        # Filter by most common exchange
        most_common_exchange = prices_df['exchange'].value_counts().idxmax()
        prices_df = prices_df[prices_df['exchange'] == most_common_exchange]
        # Remove unneeded columns
        del prices_df['exchange']
        del prices_df['trade_count']
        del prices_df['vwap']
        # Reformat DataFrame index
        prices_df.index = prices_df.index \
            .rename('time') \
            .tz_convert('US/Pacific') \
            .strftime('%Y-%m-%d %H:%M:%S')
        return prices_df

    def _get_prices_by_aggs(self, symbol, timeframes, start=None):
        '''
        Fetches a dictionary mapping of timeframes to OHLCV timeframes. Refer to `get_prices()`
        for return value for each timeframe's OHLCV DataFrame.
        '''
        self._check_symbol(symbol)
        latest_prices = {}
        for tf in timeframes:
            latest_prices[tf] = self.get_prices(symbol, tf, start)
        return latest_prices

    def _get_open_positions(self, symbol=None):
        '''
        Fetches a list of open positions on the current account for either all symbols or a specific symbol.

        Parameters:
        - symbol (optional): An asset pair symbol.

        # Position model: https://alpaca.markets/docs/api-references/trading-api/positions/#position-entity
        '''
        if symbol is None:
            return self.client.list_positions()
        else:
            self._check_symbol(symbol)
            return self.client.get_position(symbol)

    def _close_trade(self, context):
        '''
        Closes (liquidates) the open position for the given symbol. Works for both long and short positions.

        Parameters:
        - symbol: An asset pair symbol.
        - quantity (optional): The amount of the asset to liquidate. If not specified, liquidate all of the asset.

        # Position model: https://alpaca.markets/docs/api-references/trading-api/positions/#position-entity
        '''
        symbol = context.get('symbol')
        size = None
        return self.client.close_position(
            symbol=symbol,
            qty=size)

    def _get_open_trades(self, symbol=None):
        '''
        Fetches a list of the open trades on the current account, for either all symbols or a specific one.

        NOTE: Unused for now since we're working with market orders only.

        Parameters:
        - symbol (optional): An asset pair symbol.

        # Order/Trade model: https://alpaca.markets/docs/api-references/trading-api/orders/#order-entity
        '''
        if symbol is None:
            symbols = []
        else:
            self._check_symbol(symbol)
            symbols = [symbol]
        return self.client.list_orders(
            status='open',
            limit=500,
            symbols=symbols,
        )

    def _get_closed_trades(self, symbol=None):
        '''
        Fetches a list of the closed buy & sell trades on the current account, for either all
        symbols or a specific one.

        Parameters:
        - symbol (optional): An asset pair symbol.

        # Order/Trade model: https://alpaca.markets/docs/api-references/trading-api/orders/#order-entity
        '''
        if symbol is None:
            symbols = []
        else:
            self._check_symbol(symbol)
            symbols = [symbol]
        return self.client.list_orders(
            status='closed',
            limit=500,
            symbols=symbols,
        )

    def _get_trade_by_id(self, trade_id):
        '''
        Fetches a trade by ID.

        Parameters:
        - trade_id (optional): The ID of the trade.

        # Order/Trade model: https://alpaca.markets/docs/api-references/trading-api/orders/#order-entity
        '''
        return self.client.get_order(
            order_id=trade_id,
        )

    def _open_trade(self, symbol, size, trade_type, order_type='market'):
        """Submit either a buy or sell market order for a given symbol and quantity.

        Args:
            symbol (str): An asset pair symbol.
            size (int): The amount of the asset to buy/sell.
            trade_type (str): Is it a buy or sell order?
            order_type (str): The order type (market, limit, stop, stop_limit, or trailing_stop)

        Returns:
            dict: API response

        NOTE:
            Order/Trade model: https://alpaca.markets/docs/api-references/trading-api/orders/#order-entity
        """
        if not trade_type:
            raise Exception('Did not provide required Trade Type')
        self._check_symbol(symbol)
        return self.client.submit_order(
            symbol=symbol,
            qty=size,
            side=trade_type,
            type=order_type,
            time_in_force='gtc',
        )

    def get_price_api(self):
        price_api = {
            'get_prices_by_aggs': self._get_prices_by_aggs,
            'get_latest_prices': self._get_latest_prices
        }
        return price_api

    def get_trader_api(self):
        trader_api = {
            'close_trade': self._close_trade,
            'open_trade': self._open_trade,
            'get_open_positions': self._get_open_positions,
            'get_open_trades': self._get_open_trades,
            'get_closed_trades': self._get_closed_trades,
            'get_trade_by_id': self._get_trade_by_id,
            'get_spread': lambda _: None,
        }
        return trader_api

    def get_account_api(self):
        account_api = {
            'get_account_info': self._get_account_info,
            'get_instruments': self._get_instruments,
            'get_account_id': self._get_account_id,
        }
        return account_api


if __name__ == '__main__':
    afs = AlpacaService.build()

    TRADE_SYMBOL = 'BTCUSD'
    make_buy_trade_action   = False
    make_sell_trade_action  = False

    if make_buy_trade_action:
        # Make a buy action if requested
        print('Buy trade action')
        pprint(
            afs.open_trade(
                symbol=TRADE_SYMBOL,
                quantity=1,
                side='buy',
                order_type='market',
            )
        )
        print()

    if make_sell_trade_action:
        # Make a sell action if requested
        print('Sell trade action')
        pprint(
            afs.close_trade(
                symbol=TRADE_SYMBOL,
                # quantity=1,
            )
        )
        print()

    # Print current open positions and history of trades
    print('Open positions')
    pprint(afs.get_open_positions())
    print()

    print('Closed trades')
    pprint(afs.get_closed_trades())
    print()
