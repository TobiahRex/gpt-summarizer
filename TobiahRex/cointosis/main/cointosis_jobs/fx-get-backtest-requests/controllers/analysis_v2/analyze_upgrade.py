import constants
from services.log import LogService
from services.utilis import UtilityService


class AnalyzeUpgrade:
    def __init__(self, *args, **kwargs):
        self.env = kwargs.get('env')
        self.backtest_env = kwargs.get('backtest_env')
        self.log = kwargs.get('log_service')
        self.utils = kwargs.get('utils')

    @staticmethod
    def build(env, backtest_env):
        return AnalyzeUpgrade(
            env=env,
            backtest_env=backtest_env,
            log_service=LogService.build(name_prefix='AnalyzeUpgrade'),
            utils=UtilityService.build())

    def analyze_tf_upgrade(self, context):
        error_msg = ''
        if context.get('action') != 'wait':
            return
        if not self._analyze_htf_action(self.env, self.backtest_env, context):
            error_msg = 'Could not calc HTF action'
        if context['htf_action'] == 'upgrade':
            if not self._analyze_upgrade_tfs(context):
                error_msg = 'Could not upgrade TFs'
        if error_msg:
            self.log.handle(-1, error_msg, '@analyze_tf_upgrade')

    @staticmethod
    def _analyze_htf_action(env, backtest_env, context):
        """Analyize HTF volatility; if volatility achieves threshold, then upgrade all time frames by 1 aggregation.
        Intuitively; we're trying to capture a stronger trend without getting faked out by short term
        retracements/opposite trends.
        """
        htf_agg = context.get('tfs')[0]
        context['htf_action'] = ''
        curr_size = context.get('position').get('total_size')
        if not curr_size:
            return True
        if any([
            htf_agg in ['4hr', '1day'],
            context.get('position').get('behaviors')[-1] == 'upgrade_on_htf_force',
            env.get('backtest_active') and (int(backtest_env.get('run_info').get('entry_bar', '1')) < 2000)
        ]):
            return True
        htf_price_df = context.get('latest_prices').get(htf_agg)
        last_htf_force = htf_price_df.iloc[-1].force
        htf_upgrade_force = env.get('indicators').get(
            'force').get('htf_upgrade')
        if abs(last_htf_force) > htf_upgrade_force:
            context['position']['behaviors'].append('upgrade_on_htf_force')
            context['htf_action'] = 'upgrade'
        return True

    @staticmethod
    def _analyze_upgrade_tfs(context):
        mtf_agg = context.get('tfs')[1]
        for grp_list in constants.tfs_3_map.values():
            if mtf_agg == grp_list[-1]:
                context['position']['upgrade_tfs'] = grp_list
                break
        context['htf_action'] = ''
        return True
