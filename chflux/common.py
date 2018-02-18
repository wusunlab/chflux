"""
Common functions used in flux calculation

(c) 2016-2017 Wu Sun <wu.sun@ucla.edu>

"""
from collections import namedtuple
import warnings

import numpy as np
from scipy import optimize
import scipy.constants.constants as sci_const
import pandas as pd


# Physical constants
# Do not modify unless you are in a different universe.
# - 'p_std': standard atmospheric pressure [Pa]
# - 'R_gas': the universal gas constant [J mol^-1 K^-1]
# - 'T_0': zero Celsius in Kelvin
# - 'air_conc_std': air concentration at STP condition [mol m^-3]
phys_const = {
    'T_0': sci_const.zero_Celsius,
    'p_std': sci_const.atm,
    'R_gas': sci_const.R,
    'air_conc_std': sci_const.atm / (sci_const.R * sci_const.zero_Celsius)}
T_0 = phys_const['T_0']


def chamber_lookup_table_func(doy, chamber_config):
    """
    (float) -> namedtuple

    Return a chamber meta information look-up table.
    """
    # define returned data template
    ChamberLookupTableResult = namedtuple(
        'ChamberLookupTableResult',
        ['schedule_start', 'schedule_end', 'n_ch', 'smpl_cycle_len',
         'n_cycle_per_day', 'unit_of_time', 'df'])

    for sch_id in chamber_config:
        if type(chamber_config[sch_id]['schedule_start']) is str:
            sch_start = pd.Timestamp(chamber_config[sch_id]['schedule_start'])
            sch_end = pd.Timestamp(chamber_config[sch_id]['schedule_end'])
            sch_start_doy = sch_start.dayofyear - 1. + \
                sch_start.hour / 24. + sch_start.minute / 1440. + \
                sch_start.second / 86400.
            sch_end_doy = sch_end.dayofyear - 1. + \
                sch_end.hour / 24. + sch_end.minute / 1440. + \
                sch_end.second / 86400.
        else:
            sch_start_doy = chamber_config[sch_id]['schedule_start']
            sch_end_doy = chamber_config[sch_id]['schedule_end']
        if (sch_start_doy <= doy < sch_end_doy):
            current_schedule = chamber_config[sch_id]
            break
    else:
        warnings.warn('No valid chamber schedule found on the day %s.' %
                      str(doy), RuntimeWarning)
        return None

    # initialize an empty dictionary and then convert it to a namedtuple
    chamber_lookup_table = {}
    for key in ['schedule_start', 'schedule_end', 'n_ch', 'smpl_cycle_len',
                'n_cycle_per_day', 'unit_of_time', ]:
        chamber_lookup_table[key] = current_schedule[key]

    df = pd.DataFrame()

    for key in ['ch_no', 'A_ch', 'A_ch_std', 'V_ch', 'ch_label',
                'is_leaf_chamber', 'flowmeter_no', 'TC_no', 'PAR_no',
                'ch_start', 'ch_o_b', 'ch_cls', 'ch_o_a',
                'ch_end', 'ch_atm_a', 'optimize_timelag', 'timelag_nominal',
                'timelag_upper_limit', 'timelag_lower_limit']:
        df[key] = current_schedule[key]

    if chamber_lookup_table['unit_of_time'] in ['second', 'sec', 's']:
        time_unit_conversion_factor = 60. * 60. * 24.
    elif chamber_lookup_table['unit_of_time'] in ['minute', 'min', 'm']:
        time_unit_conversion_factor = 60. * 24.
    elif chamber_lookup_table['unit_of_time'] in ['hour', 'hr', 'h']:
        time_unit_conversion_factor = 24.
    else:
        time_unit_conversion_factor = 1

    # convert the unit of all time variables specifying the schedule to day
    # this does not apply to `schedule_start` and `schedule end` since
    # they both are in day of year
    chamber_lookup_table['smpl_cycle_len'] /= time_unit_conversion_factor
    df[['ch_start', 'ch_o_b', 'ch_cls', 'ch_o_a', 'ch_end', 'ch_atm_a',
        'timelag_nominal', 'timelag_upper_limit', 'timelag_lower_limit']] /= \
        time_unit_conversion_factor

    chamber_lookup_table['df'] = df

    # convert to a namedtuple
    # `**` is the 'splat operator' for unpacking dictionaries
    chamber_lookup_table = ChamberLookupTableResult(**chamber_lookup_table)

    return chamber_lookup_table


def optimize_timelag(time, conc, t_turnover,
                     dt_open_before, dt_close, dt_open_after,
                     dt_left_margin=0., dt_right_margin=0.,
                     closure_period_only=False, bounds=None, guess=None):
    """
    The time lag optimization function.

    Parameters
    ----------
    time : array_like
        Time since switching to the current chamber line, in seconds.
    conc : array_like
        Concentrations
    t_turnover : float
        The turnover time, `V_ch_mol` [mol] divided by `f_ch` [mol s^-1].
    dt_open_before : float
        Chamber opening period before closure measurement, in seconds.
    dt_open_after : float
        Chamber opening period after closure measurement, in seconds.
    dt_left_margin : optional, float
        Left margin on the closure period series to exclude, in seconds.
    dt_right_margin : optional, float
        Right margin on the closure period series to exclude, in seconds.
    closure_period_only : optional, bool
        If True (default), use the closure period only in evaluating the cost
        function for time lag optimization. If False, use the closure period
        and the opening period before it to evaluate the cost function.
    bounds : optional, tuple
        Lower and upper bounds of the time lag, in seconds. Only when both
        values are given does it call a bounded optimization.
    guess: optional, float
        The initial guess value for the time lag, in seconds. If not given, the
        default value will be 0.

    Returns
    -------
    timelag : float
        The optimized time lag value in seconds.
    status_timelag : int
        Status code for the time lag optimization procedure.
        * 0 -- Convergence
        * 1 -- Failure to converge.

    """

    def _timelag_resid_func(t_lag, time, conc, t_turnover,
                            dt_open_before, dt_close, dt_open_after,
                            dt_left_margin, dt_right_margin,
                            closure_period_only=False):
        """
        The timelag optimization function to minimize.

        Parameters
        ----------
        t_lag : float
            Time lag, in sec
        time : array_like
            Time since switching to the current chamber line, in seconds.
        conc : array_like
            Concentrations.
        t_turnover : float
            The turnover time, `V_ch_mol` [mol] divided by `f_ch` [mol s^-1].

        Returns
        -------
        MSR : float
            Mean squared difference.

        """
        # all index arrays should only contain the indices of finite values
        _ind_chb = np.where(
            (time >= t_lag + dt_left_margin) &
            (time < t_lag + dt_open_before - dt_right_margin) &
            np.isfinite(time) & np.isfinite(conc))
        _ind_chc = np.where(
            (time >= t_lag + dt_open_before + dt_left_margin) &
            (time < t_lag + dt_open_before + dt_close - dt_right_margin) &
            np.isfinite(time) & np.isfinite(conc))
        _ind_cha = np.where(
            (time >= t_lag + dt_open_before + dt_close + dt_left_margin) &
            (time < t_lag + dt_open_before + dt_close + dt_open_after -
                dt_right_margin) &
            np.isfinite(time) & np.isfinite(conc))

        _median_chb = np.nanmedian(conc[_ind_chb])
        _median_cha = np.nanmedian(conc[_ind_cha])
        _t_mid_chb = np.nanmedian(time[_ind_chb])
        _t_mid_cha = np.nanmedian(time[_ind_cha])

        # baseline
        _k_bl = (_median_cha - _median_chb) / (_t_mid_cha - _t_mid_chb)
        _b_bl = _median_chb - _k_bl * _t_mid_chb
        _conc_bl = _k_bl * time + _b_bl

        _x_obs = 1. - np.exp(- (time[_ind_chc] - t_lag - dt_open_before) /
                             t_turnover)
        _y_obs = conc[_ind_chc] - _conc_bl[_ind_chc]

        if _x_obs.size == 0:
            return(np.nan)
        # if no valid observations in chamber closure period, return NaN value
        # this will terminate the optimization procedure, and returns a
        # 'status code' of 1 in `optimize.minimize`

        # _slope, _intercept, _r_value, _p_value, _sd_slope = \
        #     stats.linregress(_x_obs, _y_obs)
        # _slope, _intercept, _, _, _ = stats.linregress(_x_obs, _y_obs)
        _slope = np.sum(_y_obs * _x_obs) / np.sum(_x_obs * _x_obs)
        _intercept = 0.
        _y_fitted = _slope * _x_obs + _intercept

        if closure_period_only:
            MSR = np.nansum((_y_fitted - _y_obs) ** 2) / \
                (_ind_chc[0].size - 2)  # mean squared residual
        else:
            _conc_fitted = _slope * \
                (1. - np.exp(- (time - t_lag - dt_open_before) /
                             t_turnover)) + _intercept + _conc_bl
            _conc_fitted[(time < t_lag + dt_open_before) |
                         (time > t_lag + dt_open_before + dt_close)] = \
                _conc_bl[(time < t_lag + dt_open_before) |
                         (time > t_lag + dt_open_before + dt_close)]
            resid = conc - _conc_fitted
            # do not include the chamber open period after closure
            resid_trunc = resid[time <= t_lag + dt_open_before + dt_close]
            # degree of freedom = 3
            MSR = np.nansum(resid_trunc * resid_trunc) / \
                (np.sum(np.isfinite(resid_trunc)) - 3.)
        return(MSR)

    # warning messages
    msg_warn_bounds = 'Illegal bounds given to timelag optimization! ' + \
        'Default to unbounded optimization method.'
    msg_warn_guess = 'Illegal timelag guess! Default to 0.'

    # do time lag optimization
    # get the bounds
    # legal input of bounds: 1. must be finite numbers; 2. the lower bound
    # must be less than the upper bound
    if bounds is None:
        flag_bounded_optimization = False
    else:
        try:
            timelag_lolim, timelag_uplim = bounds
        except TypeError:
            flag_bounded_optimization = False
            warnings.warn(msg_warn_bounds, RuntimeWarning)
        else:
            if np.isfinite(timelag_lolim) and np.isfinite(timelag_uplim):
                flag_bounded_optimization = timelag_lolim < timelag_uplim
            else:
                flag_bounded_optimization = False
                warnings.warn(msg_warn_bounds, RuntimeWarning)

    # get initial guess value
    if guess is None:
        timelag_guess = 0.
    else:
        try:
            timelag_guess = float(guess)
        except ValueError:
            warnings.warn(msg_warn_guess, RuntimeWarning)
            timelag_guess = 0.
        except TypeError:
            warnings.warn(msg_warn_guess, RuntimeWarning)
            timelag_guess = 0.
        if not np.isfinite(timelag_guess):
            warnings.warn(msg_warn_guess, RuntimeWarning)
            timelag_guess = 0.

    if flag_bounded_optimization:
        # bounded optimization uses `scipy.optimize.minimize_scalar`
        timelag_results = optimize.minimize_scalar(
            _timelag_resid_func,
            bounds=(timelag_lolim, timelag_uplim),
            args=(time, conc, t_turnover,
                  dt_open_before, dt_close, dt_open_after,
                  dt_left_margin, dt_right_margin,
                  closure_period_only),
            method='bounded', options={'xatol': 1e-6})
        timelag = timelag_results.x
        status_timelag = 0 if timelag_results.success else 1
    else:
        # unbounded optimization uses `scipy.optimize.minimize`
        timelag_results = optimize.minimize(
            _timelag_resid_func, x0=timelag_guess,
            args=(time, conc, t_turnover,
                  dt_open_before, dt_close, dt_open_after,
                  dt_left_margin, dt_right_margin,
                  closure_period_only),
            method='Nelder-Mead',
            options={'xatol': 1e-6, 'fatol': 1e-6, 'disp': False})
        timelag = timelag_results.x[0]
        status_timelag = timelag_results.status

    return timelag, status_timelag


def dixon_test(x, left=True, right=True, q_conf='q95'):
    """
    Use Dixon's Q test to identify one or two outliers. The test is based upon
    two assumptions: (1) data must be normally distributed; (2) the test may
    only be used once to a dataset and not repeated.

    Adapted from: <http://sebastianraschka.com/Articles/2014_dixon_test.html>
    (Retrieved 23 Apr 2017).

    Parameters
    ----------
    x : array_like
        Data points. Must be a list or a one dimensional array.
    left : bool, optional
        If True, test the minimum value.
    right : bool, optional
        If True, test the maximum value.
        (At least one of the two, `left` or `right`, must be True.)
    q_conf : str, optional
        Confidence level: 'q95' -- 95% confidence (default). Others supported
        are 'q90' (90% C.I.) and 'q99' (99% C.I.).

    Returns
    -------
    outliers : list
        A list of two values containing the outliers or None. The first element
        corresponds to the minimum value, and the second element corresponds
        to the maximum value. If the tested value is not an outlier, return
        None at its position.

    References
    ----------
    .. [1] Dean, R. B. and Dixon, W. J. (1951). Simplified Statistics for Small
       Numbers of Observations. Anal. Chem., 23(4), 636—638.
    .. [2] Dixon, W. J. (1953). Processing data for outliers Reference.
       J. Biometrics, 9, 74–89.
    .. [3] Rorabacher, D. B. (1991). Statistical Treatment for Rejection of
       Deviant Values: Critical Values of Dixon Q Parameter and Related
       Subrange Ratios at the 95 percent Confidence Level. Anal. Chem., 63(2),
       139–146.

    """
    # critical Q value table
    q_dicts = {'q90': [0.941, 0.765, 0.642, 0.560, 0.507, 0.468, 0.437,
                       0.412, 0.392, 0.376, 0.361, 0.349, 0.338, 0.329,
                       0.320, 0.313, 0.306, 0.300, 0.295, 0.290, 0.285,
                       0.281, 0.277, 0.273, 0.269, 0.266, 0.263, 0.260],
               'q95': [0.970, 0.829, 0.710, 0.625, 0.568, 0.526, 0.493,
                       0.466, 0.444, 0.426, 0.410, 0.396, 0.384, 0.374,
                       0.365, 0.356, 0.349, 0.342, 0.337, 0.331, 0.326,
                       0.321, 0.317, 0.312, 0.308, 0.305, 0.301, 0.290],
               'q99': [0.994, 0.926, 0.821, 0.740, 0.680, 0.634, 0.598,
                       0.568, 0.542, 0.522, 0.503, 0.488, 0.475, 0.463,
                       0.452, 0.442, 0.433, 0.425, 0.418, 0.411, 0.404,
                       0.399, 0.393, 0.388, 0.384, 0.38, 0.376, 0.372]}
    # cast to numpy array and remove NaNs
    x_arr = np.array(x)
    x_arr = x_arr[np.isfinite(x_arr)]
    # minimum and maximum data sizes allowed
    min_size = 3
    max_size = len(q_dicts[q_conf]) + min_size - 1
    if len(x_arr) < min_size:
        raise ValueError('Sample size too small: ' +
                         'at least %d data points are required' % min_size)
    elif len(x_arr) > max_size:
        raise ValueError('Sample size too large')

    if not (left or right):
        raise ValueError('At least one of the two options, ' +
                         '`left` or `right`, must be True.')

    q_crit = q_dicts[q_conf][len(x_arr) - 3]

    # for small dataset, the built-in `sorted()` is faster than `np.sort()`
    x_sorted = sorted(x_arr)

    x_range = x_sorted[-1] - x_sorted[0]
    if x_range == 0:
        outliers = [None, None]
    else:
        Q_min = abs((x_sorted[1] - x_sorted[0]) / x_range)
        Q_max = abs((x_sorted[-1] - x_sorted[-2]) / x_range)
        outliers = [
            x_sorted[0] if (Q_min > q_crit) and (Q_min >= Q_max) else None,
            x_sorted[-1] if (Q_max > q_crit) and (Q_max >= Q_min) else None]

    return outliers
