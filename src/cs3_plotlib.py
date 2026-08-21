import datetime
import re

import hvplot.pandas
import pandas as pd
import numpy as np
import panel as pn
import holoviews as hv
from bokeh.models import CustomJSTickFormatter


def plot_values(scenario_list, var_list, unit_choice, df_all, c_default_units, ls_comparison, c_field_list, temp_unit_choice='F'):
    """
    Creates the timeseries plots

    Parameters
    ----------
    scenario_list: list
        Scenarios we want to plot
    var_list: list
        Fields we want to plot
    unit_choice: str
        Unit selection (CFS or TAF)
    df_all: DataFrame
        Data to be filtered and plotted
    c_default_units: dict
        Dictionary of default units for each field
    ls_comparison: list
        list of names of comparison scenarios
    c_field_list: dict
        Dictionary of fields and descriptions
    temp_unit_choice: str
        Temperature unit selection ('F' or 'C')

    Returns
    -------
    Panel Object
        Plot and table of data as a row (plot on the left, table on the right)
    """

    # if the data frame is empty, return a markdown frame. This will happen if only one scenario is selected and its the comparison one. the differences will be empty
    if df_all.empty:
        return pn.pane.Markdown("## No data to display")

    df_all_plot = df_all.groupby('Scenario').resample(rule='ME', on='Date').mean()
    df_all_plot.reset_index(inplace=True, drop=False)
    durations = [date.day for date in df_all_plot['Date']]

    b_diffs_flag = False

    # # ensure comparison scen is at the end of the list so the coloring is constant with the differences plot for all modules
    scenario_list = [scen for scen in scenario_list if scen not in ls_comparison] + \
                    [scen for scen in ls_comparison if scen in scenario_list]
    # check if none of the comparison scenarios are in the data frame
    # if none are, then we are creating the differences plot and don't want to include them
    if not any(comp in df_all_plot.Scenario.unique() for comp in ls_comparison):
        scenario_list = [scen for scen in scenario_list if scen not in ls_comparison]
        b_diffs_flag = True

    # check if no scenarios are selected
    if len(scenario_list) == 0:
        return pn.pane.Markdown("## No data to display")

    # check if no variables are selected
    if len(var_list) == 0:
        return pn.pane.Markdown('## Select variables above to display plot.')

    # to convert from cfs to taf or vice versa
    cfs_taf = np.multiply(durations, (24 * 3600 / 43560 / 1000))
    taf_cfs = np.divide((43560 * 1000 / 24 / 3600), durations)


    b_no_unit_flag = False
    s_no_unit_var = ''

    b_alt_unit = False
    ls_alt_vars = []
    s_alt_unit = ''

    # create copy of var list since lists are mutable
    var_list_final = var_list[:]
    # Unit conversion
    for var in var_list:
        try:
            original_unit = c_default_units[var].strip().upper()
        except:
            original_unit = None

        # check for variables that are not cfs/taf like EC, temperature, X2 position
        if original_unit not in ['NONE', 'CFS', 'TAF']:
            # if we havent already declared what the unit we will keep track of is, declare it
            if s_alt_unit == '':
                s_alt_unit = original_unit
            if original_unit == s_alt_unit:
                b_alt_unit = True
                ls_alt_vars.append(var)

        elif original_unit == 'NONE':
            # if we have more than one variable with no units selected we are not going to use it
            if b_no_unit_flag:
                if b_diffs_flag:
                    pn.state.notifications.position = 'center-center'
                    pn.state.notifications.warning('If more than one variable without units of TAF/CFS is selected, only the first will be displayed.', duration=7000)
                var_list_final.remove(var)
                continue
            b_no_unit_flag = True
            s_no_unit_var = var
            ls_alt_vars.append(var)
            pass
        elif original_unit == unit_choice:
            pass
        elif original_unit == 'CFS':
            df_all_plot[var] = \
                np.multiply(df_all_plot[var], cfs_taf)
        elif original_unit == 'TAF':
            df_all_plot[var] = \
                np.multiply(df_all_plot[var], taf_cfs)

    # If we found any non cfs/taf variables, we will only use those
    if b_alt_unit:
        var_list_final = ls_alt_vars
        if s_alt_unit == 'DEGF':
            if temp_unit_choice == 'C':
                df_all_plot[ls_alt_vars] = (df_all_plot[ls_alt_vars] - 32) * 5 / 9
                unit_choice = 'Degrees Celsius'
            else:
                unit_choice = 'Degrees Fahrenheit'
        else:
            unit_choice = s_alt_unit
    if len(var_list_final) == 0:
        return pn.pane.Markdown('## Select variables above to display plot.')

    # switch from variable name to description
    df_all_plot.rename(c_field_list, axis='columns', inplace=True)
    var_list_final = [c_field_list[var] for var in var_list_final]

    # Sortable, filter to target scenarios and vars
    df_wide = pd.DataFrame(df_all_plot['Date'].unique(), columns=['Date'])
    df_wide.reset_index(inplace=True, drop=True)

    keeplist = ['Date']

    for scenario in scenario_list:
        df_temp = df_all_plot.loc[df_all_plot['Scenario'] == scenario][var_list_final]
        #skip vars this scenarios module doesnt produce
        valid_vars = [v for v in var_list_final if not df_temp[v].isna().all()]
        if not valid_vars:
            continue
        df_temp = df_temp[valid_vars]
        df_temp.reset_index(inplace=True, drop=True)
        col_names = [f'{scenario}: {var}' for var in valid_vars]
        df_temp.columns = col_names
        df_wide[col_names] = df_temp[col_names]
        for name in col_names:
            keeplist.append(name)

    df_plot = df_wide.drop([var for var in df_wide if var not in keeplist])

    # round to one decimal place
    df_plot.loc[:, df_plot.columns != 'Date'] = df_plot.loc[:, df_plot.columns != 'Date'].round(1)

    keeplist.remove('Date')
    if b_no_unit_flag:
        no_unit_keeplist = [var for var in keeplist if s_no_unit_var in var]
        unit_keeplist = [var for var in keeplist if var not in no_unit_keeplist]
        c_no_unit_names = {
            'WYT_SAC_': {1: 'Wet', 2: 'Above Normal', 3: 'Below Normal', 4: 'Dry', 5: 'Critically Dry'},
            'WYT_SJR_': {1: 'Wet', 2: 'Above Normal', 3: 'Below Normal', 4: 'Dry', 5: 'Critically Dry'},
            'WYT_TRIN_': {1: 'Extremely Wet', 2: 'Wet', 3: 'Normal', 4: 'Dry', 5: 'Critically Dry'},
            'WYT_SHASTA_CVP_': {0: 'Non-Critical', 1: 'ShastaCritical'},
            'WYT_FEATHER_': {1: 'Non-Critical', 2: 'Critically Dry'},
            'WYT_SJRRP_DV': {1: 'Wet', 2: 'Normal-Wet', 3: 'Normal-Dry', 4: 'Dry', 5: 'Critical High', 6: 'Critical Low'},
            'WYT_AMERD983_CVP_': {1: 'Non-Critical', 2: 'Critically Dry'},
            'SHASTABIN_': {1: '1a', 2: '1b', 3: '2a', 4: '2b', 5: '3a', 6: '3b'}
        }
        if '/' in s_no_unit_var:
            s_var = s_no_unit_var.split('/')[1]
        else:
            s_var = s_no_unit_var
        if s_var not in c_no_unit_names.keys():
            yformatter = None
        else:
            yformatter = CustomJSTickFormatter(code="""
                                            var labels = %s;
                                            return labels[tick] || tick;
                                         """ % c_no_unit_names[s_var])
        # if we only have the no unit variable selected
        if len(var_list_final) == 1:
            return pn.Row(
                pn.Column(pn.pane.HoloViews(df_plot.hvplot.scatter(
                    x='Date',
                    y=no_unit_keeplist,
                    ylabel=c_default_units[s_no_unit_var] if c_default_units[s_no_unit_var] != 'NONE' else
                    c_field_list[s_no_unit_var],
                    xlabel='Date',
                    group_label='',
                    grid=True,
                    min_height=600,
                    yformatter=yformatter
                ).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False),
                          sizing_mode='stretch_width'),
                pn.Column(pn.pane.DataFrame(df_plot, index=False, max_height=500), sizing_mode='stretch_width'),
                sizing_mode='stretch_width'
            )
        # add horizontal line if we are doing the differences plot
        if b_diffs_flag:
            return pn.Row(
                pn.Column(
                    pn.pane.HoloViews((hv.HLine(0).opts(color='black', line_width=1) * df_plot.hvplot(
                        x='Date',
                        y=unit_keeplist,
                        ylabel=unit_choice,
                        group_label='',
                        xlabel='Date',
                        grid=True,
                        min_height=600
                    )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False),
                    pn.pane.HoloViews(df_plot.hvplot.scatter(
                        x='Date',
                        y=no_unit_keeplist,
                        ylabel=c_default_units[s_no_unit_var] if c_default_units[s_no_unit_var] != 'NONE' else
                        c_field_list[s_no_unit_var],
                        xlabel='Date',
                        group_label='',
                        grid=True,
                        min_height=400,
                        yformatter=yformatter
                    ).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False),
                    sizing_mode='stretch_width'
                ),
                pn.Column(pn.pane.DataFrame(df_plot, index=False, max_height=500), sizing_mode='stretch_width'),
                sizing_mode='stretch_width'
            )
        else:
            return pn.Row(
                pn.Column(
                    pn.pane.HoloViews((hv.HLine(0).opts(line_width=0) * df_plot.hvplot(
                        x='Date',
                        y=unit_keeplist,
                        ylabel=unit_choice,
                        xlabel='Date',
                        group_label='',
                        grid=True,
                        min_height=600,
                    )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width',linked_axes=False),
                    pn.pane.HoloViews(df_plot.hvplot.scatter(
                        x='Date',
                        y=no_unit_keeplist,
                        ylabel=c_default_units[s_no_unit_var] if c_default_units[s_no_unit_var] != 'NONE' else
                        c_field_list[s_no_unit_var],
                        xlabel='Date',
                        group_label='',
                        grid=True,
                        min_height=400,
                        yformatter=yformatter
                    ).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width',linked_axes=False),
                    sizing_mode='stretch_width'
                ),
                pn.Column(pn.pane.DataFrame(df_plot, index=False, max_height=500), sizing_mode='stretch_width'),
                sizing_mode='stretch_width'
            )
    # add horizontal line if we are doing the differences plot
    if b_diffs_flag:
        return pn.Row(pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(color='black', line_width=1) * df_plot.hvplot(
            x='Date',
            ylabel=unit_choice,
            xlabel='Date',
            grid=True,
            min_height=600
            )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False), sizing_mode='stretch_width'),
            pn.Column(pn.pane.DataFrame(df_plot, index=False, max_height=500), sizing_mode='stretch_width'),
            sizing_mode='stretch_width')

    else:
        return pn.Row(pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(line_width=0) * df_plot.hvplot(
            x='Date',
            ylabel=unit_choice,
            xlabel='Date',
            grid=True,
            min_height=600
        )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False), sizing_mode='stretch_width'),
        pn.Column(pn.pane.DataFrame(df_plot, index=False, max_height=500), sizing_mode='stretch_width'),
        sizing_mode='stretch_width')

def plot_time_group(scenario_list, var_list, unit_choice, df_all,
                    c_default_units, period_choice, ls_comparison,
                    c_field_list, li_wyt_selected, b_wyt_period_year, li_wyt_period_months, temp_unit_choice='F'):
    """
    Creates time aggregated plot

    Parameters
    ----------
    scenario_list: list
        Scenarios we want to plot
    var_list: list
        Fields we want to plot
    unit_choice: str
        Unit selection (CFS or TAF)
    df_all: DataFrame
        Data to be filtered and plotted
    c_default_units: dict
        Dictionary of default units for each field
    period_choice: int or str
        Time period selected
    ls_comparison: list
        list of names of comparison scenarios
    c_field_list: dict
        Dictionary of fields and descriptions
    li_wyt_selected: list
        Water year types selected for WYT time period
    b_wyt_period_year: bool
        If water year totals have been selected for WYT time period
    li_wyt_period_months: list
        Months selected for WYT time period
    temp_unit_choice: str
        Temperature unit selection ('F' or 'C')
    Returns
    -------
    Panel Object
        Plot and table side-by-side as a row. If grouping by water year type the row
        is preceded by a title describing the selected WYTs.
    """

    # if the data frame is empty, return a markdown frame. This will happen if only one scenario is selected and its the comparison one. the differences will be empty
    if df_all.empty:
        return pn.pane.Markdown("## No data to display")

    df_all_plot = df_all.groupby('Scenario').resample(rule='ME', on='Date').mean()
    df_all_plot.reset_index(inplace=True, drop=False)
    durations = [date.day for date in df_all_plot['Date']]

    b_diffs_flag = False

    # # ensure comparison scen is at the end of the list so the coloring is constant with the differences plot for all modules
    scenario_list = [scen for scen in scenario_list if scen not in ls_comparison] + \
                    [scen for scen in ls_comparison if scen in scenario_list]
    # check if none of the comparison scenarios are in the data frame
    # if none are, then we are creating the differences plot and don't want to include them
    if not any(comp in df_all_plot.Scenario.unique() for comp in ls_comparison):
        scenario_list = [scen for scen in scenario_list if scen not in ls_comparison]
        b_diffs_flag = True

    # check if any scenarios are selected
    if len(scenario_list) == 0:
        return pn.pane.Markdown("## No data to display")

    # check if any variables are selected
    if len(var_list) == 0:
        return pn.pane.Markdown('## Select variables above to display plot.')

    # to convert from cfs to taf or vice versa
    cfs_taf = np.multiply(durations, (24 * 3600 / 43560 / 1000))
    taf_cfs = np.divide((43560 * 1000 / 24 / 3600), durations)

    b_alt_unit = False
    ls_alt_vars = []
    s_alt_unit = ''

    # create copy of var list since lists are mutable
    var_list_final = var_list[:]
    # Unit conversion
    for var in var_list:
        try:
            original_unit = c_default_units[var].strip().upper()
        except:
            original_unit = 'NONE'
        # check for variables that are not cfs/taf like EC, temperature, X2 position
        if original_unit not in ['NONE', 'CFS', 'TAF']:
            # if we havent already declared what the unit we will keep track of is, declare it
            if s_alt_unit == '':
                s_alt_unit = original_unit
            if original_unit == s_alt_unit:
                b_alt_unit = True
                ls_alt_vars.append(var)
        elif original_unit not in ['CFS', 'TAF']:
            var_list_final.remove(var)
            pass
        elif original_unit == unit_choice:
            pass
        elif original_unit == 'CFS':
            df_all_plot[var] = \
                np.multiply(df_all_plot[var], cfs_taf)
        elif original_unit == 'TAF':
            df_all_plot[var] = \
                np.multiply(df_all_plot[var], taf_cfs)
    agg_func = 'sum' if unit_choice == 'TAF' else 'mean'

    # If we found any non cfs/taf variables, we will only use those
    if b_alt_unit:
        var_list_final = ls_alt_vars
        if s_alt_unit == 'DEGF':
            if temp_unit_choice == 'C':
                df_all_plot[ls_alt_vars] = (df_all_plot[ls_alt_vars] - 32) * 5 / 9
                unit_choice = 'Degrees Celsius'
            else:
                unit_choice = 'Degrees Fahrenheit'
        else:
            unit_choice = s_alt_unit
        agg_func = 'mean'

    if len(var_list_final) == 0:
        return pn.pane.Markdown('## Select variables above to display plot.')

    # switch from variable name to description
    df_all_plot.rename(c_field_list, axis='columns', inplace=True)
    var_list_final = [c_field_list[var] for var in var_list_final]

    # if we are sorting by WYT we need to do some work before switching to wide frame
    if isinstance(period_choice, str) and ('WYT' in period_choice or 'SHASTABIN_' in period_choice):
        # sort for the years we want
        # see if any years are selected
        if not li_wyt_selected:
            return pn.pane.Markdown("## No data to display")

        # we do have some selected
        # what the column with the wyt is called
        s_wyt_col = c_field_list[period_choice]

        # select just september since that will have the correct wyt
        df_septembers = df_all_plot[df_all_plot['Month'] == 9]

        # pull the years and scenarios that match the selected wyts
        df_wy_to_use = df_septembers[df_septembers[s_wyt_col].isin(li_wyt_selected)][['Scenario', 'OctSeptYear', s_wyt_col]]
        # dictionary to hold {(scenario, WY): WYT}
        c_wy_to_wyt = {}
        for index, row in df_wy_to_use.iterrows():
            c_wy_to_wyt[(row['Scenario'], row['OctSeptYear'])] = row[s_wyt_col]

        # Assign wyt column to be the final wyt
        def wy_to_wyt(wyt_dict, scen, year):
            try:
                return wyt_dict[(scen, year)]
            except:
                return np.nan

        df_all_plot[s_wyt_col] = df_all_plot.apply(lambda row: wy_to_wyt(c_wy_to_wyt, row['Scenario'], row['OctSeptYear']), axis=1)

    # Sortable, filter to target scenarios and vars
    df_wide = pd.DataFrame(df_all_plot['Date'].unique(), columns=['Date'])
    df_wide[['OctSeptYear', 'JanDecYear', 'MarFebYear', 'Month']] = df_all_plot.loc[df_all_plot['Scenario'] == scenario_list[0]][['OctSeptYear', 'JanDecYear', 'MarFebYear', 'Month']].reset_index(drop=True)
    df_wide.reset_index(inplace=True, drop=True)

    #keeplist = ['Date']
    keeplist = []

    # if grouping by wyt we need to include that variable
    if isinstance(period_choice, str) and ('WYT' in period_choice or 'SHASTABIN_' in period_choice):
        for scenario in scenario_list:
            df_temp = df_all_plot.loc[df_all_plot['Scenario'] == scenario][[s_wyt_col]]
            df_temp.reset_index(inplace=True, drop=True)
            col_names = [f'{scenario}: {s_wyt_col}']
            df_temp.columns = col_names
            df_wide[col_names] = df_temp[col_names]  # WHAT THE HECK
            for name in col_names:
                keeplist.append(name)

    for scenario in scenario_list:
        df_temp = df_all_plot.loc[df_all_plot['Scenario'] == scenario][var_list_final]
        # skip vars this scenario's module doesn't produce (all-NaN for this scenario)
        valid_vars = [v for v in var_list_final if not df_temp[v].isna().all()]
        if not valid_vars:
            continue
        df_temp = df_temp[valid_vars]
        df_temp.reset_index(inplace=True, drop=True)
        col_names = [f'{scenario}: {var}' for var in valid_vars]
        df_temp.columns = col_names
        df_wide[col_names] = df_temp[col_names]       # WHAT THE HECK
        for name in col_names:
            keeplist.append(name)
        debug = True

    # ------- Agg ops below -------------

    # Remove incomplete years (default CS3 runs typically based on WY)
    # Grouping by calendar year or contract year (Mar-Feb) leaves partial
    # years @ start/end of run

    # grouping by period choice
    # if we chose a year option
    if period_choice in ["OctSeptYear", "JanDecYear", "MarFebYear"]:
        df_timecounts = df_wide.groupby(by=[period_choice]).count()
        droplist = df_timecounts[df_timecounts['Date'] < 12].index
        df_wide = df_wide[df_wide[period_choice].isin(droplist) == False]
        # Can't sum dates: drop
        df_wide = df_wide.drop('Date', axis=1)
        df_grouped = df_wide.groupby(by=[period_choice]).agg(agg_func)
        df_plot = df_grouped[keeplist]

        # round to one decimal place
        df_plot.loc[:, df_plot.columns != 'Date'] = df_plot.loc[:, df_plot.columns != 'Date'].round(1)

        # add horizontal line if we are doing the differences plot
        if b_diffs_flag:
            return pn.Row(
                pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(color='black', line_width=1) * df_plot.hvplot(
                    min_height=600,
                    grid=True,
                    ylabel=('Total ' if unit_choice == 'TAF' else 'Average ') + unit_choice,
                    xlabel='Year',
                )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False),
                          sizing_mode='stretch_width'),
                pn.Column(pn.pane.DataFrame(df_plot, max_height=500), sizing_mode='stretch_width'),
                sizing_mode='stretch_width')
        else:
            return pn.Row(
                pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(line_width=0) * df_plot.hvplot(
                    min_height=600,
                    grid=True,
                    ylabel=('Total ' if unit_choice == 'TAF' else 'Average ') + unit_choice,
                    xlabel='Year',
                )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False),
                          sizing_mode='stretch_width'),
                pn.Column(pn.pane.DataFrame(df_plot, max_height=500), sizing_mode='stretch_width'),
                sizing_mode='stretch_width')

    # if water year type is selected as period
    elif isinstance(period_choice, str) and ('WYT' in period_choice or 'SHASTABIN_' in period_choice):
        # filter for selected WYTs
        # get rif of anywhere all wyt columns are empty
        df_wide = df_wide.dropna(subset=keeplist[:len(scenario_list)], how='all')

        # check if we ended up with no matching years
        if df_wide.empty:
            return pn.pane.Markdown("## No data to display")

        # if we want to look at water year totals
        if b_wyt_period_year:
            # drop incomplete years
            df_timecounts = df_wide.groupby(by=['OctSeptYear']).count()
            droplist = df_timecounts[df_timecounts['Date'] < 12].index
            df_wide = df_wide[df_wide['OctSeptYear'].isin(droplist) == False]

            # Can't sum dates: drop
            df_wide = df_wide.drop('Date', axis=1)

            # get the year totals/averages
            df_grouped = df_wide.groupby(by=['OctSeptYear']).agg(agg_func)

            # assign the WYt to be the correct one
            df_grouped[keeplist[:len(scenario_list)]] = df_grouped[keeplist[:len(scenario_list)]]/12

            # get rid of other columns we dont need
            df_plot = df_grouped[keeplist]
        else:
            if len(li_wyt_period_months) == 0:
                return pn.pane.Markdown("## No data to display")
            # first get rid of the years we dont need
            df_wide = df_wide.dropna(subset=keeplist[:len(scenario_list)], how='all')

            # pull out only those months
            df_wide = df_wide[df_wide['Month'].isin(li_wyt_period_months)]

            # drop incomplete years
            df_timecounts = df_wide.groupby(by=['OctSeptYear']).count()
            droplist = df_timecounts[df_timecounts['Date'] < len(li_wyt_period_months)].index
            df_wide = df_wide[df_wide['OctSeptYear'].isin(droplist) == False]

            # Can't sum dates: drop
            df_wide = df_wide.drop('Date', axis=1)

            # get the year totals/avgs
            df_grouped = df_wide.groupby(by=['OctSeptYear']).agg(agg_func)

            # assign the WYt to be the correct one
            df_grouped[keeplist[:len(scenario_list)]] = df_grouped[keeplist[:len(scenario_list)]] / len(li_wyt_period_months)

            # get rid of other columns we dont need
            df_plot = df_grouped[keeplist]

        # round to one decimal place
        df_plot.loc[:, df_plot.columns != 'Date'] = df_plot.loc[:, df_plot.columns != 'Date'].round(1)

        s_title = "## " + s_wyt_col + " "

        c_no_unit_names = {
            'WYT_SAC_': {1: 'Wet', 2: 'Above Normal', 3: 'Below Normal', 4: 'Dry', 5: 'Critically Dry'},
            'WYT_SJR_': {1: 'Wet', 2: 'Above Normal', 3: 'Below Normal', 4: 'Dry', 5: 'Critically Dry'},
            'WYT_TRIN_': {1: 'Extremely Wet', 2: 'Wet', 3: 'Normal', 4: 'Dry', 5: 'Critically Dry'},
            'WYT_SHASTA_CVP_': {0: 'Non-Critical', 1: 'ShastaCritical'},
            'WYT_FEATHER_': {1: 'Non-Critical', 2: 'Critically Dry'},
            'WYT_SJRRP_DV': {1: 'Wet', 2: 'Normal-Wet', 3: 'Normal-Dry', 4: 'Dry', 5: 'Critical High', 6: 'Critical Low'},
            'WYT_AMERD983_CVP_': {1: 'Non-Critical', 2: 'Critically Dry'},
            'SHASTABIN_': {1: '1a', 2: '1b', 3: '2a', 4: '2b', 5: '3a', 6: '3b'}
        }
        try:
            if '/' in period_choice:
                period_choice_stripped = period_choice.split('/')[1]
            else:
                period_choice_stripped = period_choice
            if period_choice_stripped[:3] == 'WYT':
                s_all_sel_wyt = 'All Water Year Types' if len(li_wyt_selected) == len(list(c_no_unit_names[period_choice_stripped].keys())) else ', '.join([c_no_unit_names[period_choice_stripped][wyt] for wyt in li_wyt_selected])
            else:
                s_all_sel_wyt = ', '.join([c_no_unit_names[period_choice_stripped][wyt] for wyt in li_wyt_selected])
        except:
            s_all_sel_wyt = ', '.join([str(wyt) for wyt in li_wyt_selected])

        s_title += s_all_sel_wyt + ' Years \n'
        if b_wyt_period_year:
            s_title += "## Water Year Total"
        else:
            li_wyt_period_months.sort()
            ls_months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            s_title += "## " + ', '.join([ls_months[i-1] for i in li_wyt_period_months])
        # add horizontal line if we are doing the differences plot
        if b_diffs_flag:
            return pn.Column(
                s_title,
                pn.Row(
                    pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(color='black', line_width=1) * df_plot.hvplot.scatter(
                        y=keeplist[len(scenario_list):],  # to avoid plotting the wyt
                        min_height=600,
                        grid=True,
                        xlabel='Water Year',
                        ylabel=('Total ' if unit_choice == 'TAF' else 'Average ') + unit_choice,
                    )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False),sizing_mode='stretch_width'),
                    pn.Column(pn.pane.DataFrame(df_plot, max_height=500), sizing_mode='stretch_width'),
                    sizing_mode='stretch_width'
                )
            )
        else:
            return pn.Column(
                s_title,
                pn.Row(
                    pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(line_width=0) * df_plot.hvplot.scatter(
                        y=keeplist[len(scenario_list):],  # to avoid plotting the wyt
                        min_height=600,
                        grid=True,
                        xlabel='Water Year',
                        ylabel=('Total ' if unit_choice == 'TAF' else 'Average ') + unit_choice,
                    )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False),
                              sizing_mode='stretch_width'),
                    pn.Column(pn.pane.DataFrame(df_plot, max_height=500), sizing_mode='stretch_width'),sizing_mode='stretch_width'
                )
            )
    # selected a month
    elif isinstance(period_choice, int):
        df_wide = df_wide[df_wide.Month == period_choice]

        # Can't sum dates: drop
        df_wide = df_wide.drop('Date', axis=1)
        # this shouldn't make a difference since it will be one per month but it makes it match the rest
        df_grouped = df_wide.groupby(by=['JanDecYear']).agg(agg_func)
        df_plot = df_grouped[keeplist]

        # round to one decimal place
        df_plot.loc[:, df_plot.columns != 'Date'] = df_plot.loc[:, df_plot.columns != 'Date'].round(1)

        c_num_to_month = {1: "January", 2: "February", 3: "March", 4: "April",
                          5: "May", 6: "June", 7: "July", 8: "August",
                          9: "September", 10: "October", 11: "November", 12: "December"}
        # add horizontal line if we are doing the differences plot
        if b_diffs_flag:
            return pn.Row(
                pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(color='black', line_width=1) * df_plot.hvplot(
                    min_height=600,
                    ylabel=c_num_to_month[period_choice] + ' ' + unit_choice,
                    xlabel='Year',
                    grid=True
                )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False),
                          sizing_mode='stretch_width'),
                pn.Column(pn.pane.DataFrame(df_plot, max_height=500), sizing_mode='stretch_width'),
                sizing_mode='stretch_width'
            )

        else:
            return pn.Row(
                pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(line_width=0) * df_plot.hvplot(
                    min_height=600,
                    ylabel=c_num_to_month[period_choice] + ' ' + unit_choice,
                    xlabel='Year',
                    grid=True
                )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False),
                          sizing_mode='stretch_width'),
                pn.Column(pn.pane.DataFrame(df_plot, max_height=500), sizing_mode='stretch_width'),
                sizing_mode='stretch_width'
            )
    # if they picked a partial month
    else:
        # pull out start and stop months and then create a list of all the months in between
        i_start_month, i_end_month = int(period_choice.split('-')[0]), int(period_choice.split('-')[1])
        if i_end_month > i_start_month:
            li_months = list(range(i_start_month, i_end_month+1))
        else:
            li_months = list(range(i_start_month, 13)) + list(range(1, i_end_month+1))

        # filter for those months
        df_wide = df_wide[df_wide['Month'].isin(li_months)]

        # Can't sum dates: drop
        df_wide = df_wide.drop('Date', axis=1)

        # if we cross a cal year change, group by WY
        if period_choice in ['11-3', '10-1', '12-2', '10-4']:
            df_grouped = df_wide.groupby(by=['OctSeptYear']).agg(agg_func)
        else:
            df_grouped = df_wide.groupby(by=['JanDecYear']).agg(agg_func)
        df_plot = df_grouped[keeplist]

        # round to one decimal place
        df_plot.loc[:, df_plot.columns != 'Date'] = df_plot.loc[:, df_plot.columns != 'Date'].round(1)

        # add horizontal line if we are doing the differences plot
        if b_diffs_flag:
            return pn.Row(
                pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(color='black', line_width=1) * df_plot.hvplot(
                    min_height=600,
                    ylabel=('Total ' if unit_choice == 'TAF' else 'Average ') + unit_choice,
                    xlabel='Year',
                    grid=True
                )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False),
                          sizing_mode='stretch_width'),
                pn.Column(pn.pane.DataFrame(df_plot, max_height=500), sizing_mode='stretch_width'),
                sizing_mode='stretch_width'
            )

        else:
            return pn.Row(
                pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(line_width=0) * df_plot.hvplot(
                    min_height=600,
                    ylabel=('Total ' if unit_choice == 'TAF' else 'Average ') + unit_choice,
                    xlabel='Year',
                    grid=True
                )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False),
                          sizing_mode='stretch_width'),
                pn.Column(pn.pane.DataFrame(df_plot, max_height=500), sizing_mode='stretch_width'),
                sizing_mode='stretch_width'
            )

def plot_time_exceedance(scenario_list, var_list, unit_choice, df_all,
                         c_default_units, period_choice, s_comparison, c_field_list,
                         li_wyt_selected, b_wyt_period_year, li_wyt_period_months,
                         b_show_year, s_module, temp_unit_choice = 'F'):
    """
    Creates exceedance plots

    Parameters
    ----------
    scenario_list: list
        Scenarios we want to plot
    var_list: list
        Fields we want to plot
    unit_choice: str
        Unit selection (CFS or TAF)
    df_all: DataFrame
        Data to be filtered and plotted
    c_default_units: dict
        Dictionary of default units for each field
    period_choice: int or str
        Time period selected
    s_comparison: str
        Name of comparison scenario
    c_field_list: dict
        Dictionary of fields and descriptions
    li_wyt_selected: list
        Water year types selected for WYT time period
    b_wyt_period_year: bool
        If water year totals have been selected for WYT time period
    li_wyt_period_months: list
        Months selected for WYT time period
    b_show_year: bool
        Whether to show the year in the table
    s_module: str
        Module from c_flag
    temp_unit_choice: str
        Temperature unit selection ('F' or 'C')
    Returns
    -------
    Panel Object
            Plot and table of data as a column
    """

    #key for temp version
    b_not_temperature = 'temperature' not in s_module

    # if the data frame is empty, return a markdown frame. This will happen if only one scenario is selected and its the comparison one. the differences will be empty
    if df_all.empty:
        return pn.pane.Markdown("## No data to display")

    df_all_plot = df_all.groupby('Scenario').resample(rule='ME', on='Date').mean()
    df_all_plot.reset_index(inplace=True, drop=False)
    durations = [date.day for date in df_all_plot['Date']]

    b_diffs_flag = False

    # ensure comparison scen is at the end of the list so the coloring is constant with the differences plot
    if s_comparison in scenario_list:
        scenario_list.remove(s_comparison)
        scenario_list.append(s_comparison)

    # check if comparison scen is in the data frame
    # if it's not, then we are creating the differences plot and don't want to include comparison scen
    if s_comparison not in df_all_plot.Scenario.unique():
        scenario_list = [scen for scen in scenario_list if scen != s_comparison]
        b_diffs_flag = True

    # check if any scenarios are selected
    if len(scenario_list) == 0:
        return pn.pane.Markdown("## No data to display")

    # check if any variables are selected
    if len(var_list) == 0:
        return pn.pane.Markdown('## Select variables above to display plot.')

    # to convert from cfs to taf or vice versa
    cfs_taf = np.multiply(durations, (24 * 3600 / 43560 / 1000))
    taf_cfs = np.divide((43560 * 1000 / 24 / 3600), durations)

    # create copy of var list since lists are mutable
    var_list_final = var_list[:]

    b_alt_unit = False
    ls_alt_vars = []
    s_alt_unit = ''

    # Unit conversion
    for var in var_list:
        try:
            original_unit = c_default_units[var].strip().upper()
        except:
            original_unit = None
        # check for variables that are not cfs/taf like EC, temperature, X2 position
        if original_unit not in ['NONE', 'CFS', 'TAF']:
            # if we havent already declared what the unit we will keep track of is, declare it
            if s_alt_unit == '':
                s_alt_unit = original_unit
            if original_unit == s_alt_unit:
                b_alt_unit = True
                ls_alt_vars.append(var)
        elif original_unit not in ['CFS', 'TAF']:
            var_list_final.remove(var)
            pass
        elif original_unit == unit_choice:
            pass
        elif original_unit == 'CFS':
            df_all_plot[var] = \
                np.multiply(df_all_plot[var], cfs_taf)
        elif original_unit == 'TAF':
            df_all_plot[var] = \
                np.multiply(df_all_plot[var], taf_cfs)
    agg_func = 'sum' if unit_choice == 'TAF' else 'mean'

    # If we found any non cfs/taf variables, we will only use those
    if b_alt_unit:
        var_list_final = ls_alt_vars
        if s_alt_unit == 'DEGF':
            if temp_unit_choice == 'C':
                df_all_plot[ls_alt_vars] = (df_all_plot[ls_alt_vars] - 32) * 5 / 9
                unit_choice = 'Degrees Celsius'
            else:
                unit_choice = 'Degrees Fahrenheit'
        else:
            unit_choice = s_alt_unit
        agg_func = 'mean'

    if len(var_list_final) == 0:
        return pn.pane.Markdown('## Select variables above to display plot.')

    # switch from variable name to description
    df_all_plot.rename(c_field_list, axis='columns', inplace=True)
    var_list_final = [c_field_list[var] for var in var_list_final]

    # if we are sorting by WYT we need to do some work before switching to wide frame
    if isinstance(period_choice, str) and ('WYT' in period_choice or 'SHASTABIN_' in period_choice):
        # sort for the years we want
        # see if any years are selected
        if not li_wyt_selected:
            return pn.pane.Markdown("## No data to display")

        # we do have some selected
        # what the column with the wyt is called
        s_wyt_col = c_field_list[period_choice]

        # select just september since that will have the correct wyt
        df_septembers = df_all_plot[df_all_plot['Month'] == 9]

        # pull the years and scenarios that match the selected wyts
        df_wy_to_use = df_septembers[df_septembers[s_wyt_col].isin(li_wyt_selected)][['Scenario', 'OctSeptYear', s_wyt_col]]
        # dictionary to hold {(scenario, WY): WYT}
        c_wy_to_wyt = {}
        for index, row in df_wy_to_use.iterrows():
            c_wy_to_wyt[(row['Scenario'], row['OctSeptYear'])] = row[s_wyt_col]

        # Assign wyt column to be the final wyt
        def wy_to_wyt(wyt_dict, scen, year):
            try:
                return wyt_dict[(scen, year)]
            except:
                return np.nan

        df_all_plot[s_wyt_col] = df_all_plot.apply(lambda row: wy_to_wyt(c_wy_to_wyt, row['Scenario'], row['OctSeptYear']), axis=1)

    # Sortable, filter to target scenarios and vars
    df_wide = pd.DataFrame(df_all_plot['Date'].unique(), columns=['Date'])
    df_wide[['OctSeptYear', 'JanDecYear', 'MarFebYear', 'Month']] = df_all_plot.loc[df_all_plot['Scenario'] == scenario_list[0]][['OctSeptYear', 'JanDecYear', 'MarFebYear', 'Month']].reset_index(drop=True)
    df_wide.reset_index(inplace=True, drop=True)

    # This will allow us to drop the columns used for sorting / aggregating once the
    # final df_plot has been constructed. Eventually we might write some more streamlined
    # code to calculate WY/DY/etc on the fly
    keeplist = []

    # if grouping by wyt we need to include that variable
    if isinstance(period_choice, str) and ('WYT' in period_choice or 'SHASTABIN_' in period_choice):
        for scenario in scenario_list:
            df_temp = df_all_plot.loc[df_all_plot['Scenario'] == scenario][[s_wyt_col]]
            df_temp.reset_index(inplace=True, drop=True)
            col_names = [f'{scenario}: {s_wyt_col}']
            df_temp.columns = col_names
            df_wide[col_names] = df_temp[col_names]  # WHAT THE HECK
            for name in col_names:
                keeplist.append(name)

    for scenario in scenario_list:
        df_temp = df_all_plot.loc[df_all_plot['Scenario'] == scenario][var_list_final]
        valid_vars = [v for v in var_list_final if not df_temp[v].isna().all()]
        if not valid_vars:
            continue
        df_temp = df_temp[valid_vars]
        df_temp.reset_index(inplace=True, drop=True)
        col_names = [f'{scenario}: {var}' for var in valid_vars]
        df_temp.columns = col_names
        df_wide[col_names] = df_temp[col_names]       # WHAT THE HECK
        for name in col_names:
            keeplist.append(name)
        debug = True

    # ------- Agg ops below -------------

    # Remove incomplete years (default CS3 runs typically based on WY)
    # Grouping by calendar year or contract year (Mar-Feb) leaves partial
    # years @ start/end of run
    # period_choice = 'JanDecYear' #dbg only
    if period_choice in ['OctSeptYear', 'JanDecYear', 'MarFebYear']:
        df_timecounts = df_wide.groupby(by=[period_choice]).count()
        droplist = df_timecounts[df_timecounts['Date'] < 12].index
        df_wide = df_wide[df_wide[period_choice].isin(droplist) == False]

        # Exceedance

        # Can't sum dates: drop
        df_wide = df_wide.drop('Date', axis=1)
        df_grouped = df_wide.groupby(by=[period_choice]).agg(agg_func)

        df_exceed = pd.DataFrame(index=list(range(df_grouped.shape[0])))

        # add exceedance probabilities
        i_n = df_grouped.shape[0]
        ld_probabilities = [m/(i_n+1) * 100 for m in range(i_n, 0, -1)]
        df_exceed['exceedance_probability'] = ld_probabilities

        for var in keeplist:
            if var != 'Date':
                if b_show_year:
                    l_years_sorted = df_grouped[var].sort_values().index
                    df_exceed[var+' (Year)'] = l_years_sorted
                l_sorted = df_grouped[var].sort_values().reset_index(drop=True)
                df_exceed[var] = l_sorted

        # round to one decimal place
        df_exceed = df_exceed.round(1)

        # add horizontal line if we are doing the differences plot
        if b_diffs_flag:
            return pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(color='black', line_width=1) * df_exceed.hvplot(
                x='exceedance_probability',
                y=keeplist,
                min_height=600,
                ylabel=('Total ' if unit_choice == 'TAF' else 'Average ') + unit_choice,
                xlabel='Probability of Exceedance',
                flip_xaxis=(b_not_temperature),
                xformatter='%f%%',
                grid=True,
            )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False), pn.pane.DataFrame(df_exceed, index=False, max_height=500))

        else:
            return pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(line_width=0) * df_exceed.hvplot(
                x='exceedance_probability',
                y=keeplist,
                min_height=600,
                ylabel=('Total ' if unit_choice == 'TAF' else 'Average ') + unit_choice,
                xlabel='Probability of Exceedance',
                flip_xaxis=(b_not_temperature),
                xformatter='%f%%',
                grid=True
            )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False), pn.pane.DataFrame(df_exceed, index=False, max_height=500))

    # if water year type is selected as period
    elif isinstance(period_choice, str) and ('WYT' in period_choice or 'SHASTABIN_' in period_choice):
        # filter for selected WYTs
        # get rif of anywhere all wyt columns are empty
        df_wide = df_wide.dropna(subset=keeplist[:len(scenario_list)], how='all')

        # check if we ended up with no matching years
        if df_wide.empty:
            return pn.pane.Markdown("## No data to display")

            # if we want to look at water year totals
        if b_wyt_period_year:
            # drop incomplete years
            df_timecounts = df_wide.groupby(by=['OctSeptYear']).count()
            droplist = df_timecounts[df_timecounts['Date'] < 12].index
            df_wide = df_wide[df_wide['OctSeptYear'].isin(droplist) == False]

            # Can't sum dates: drop
            df_wide = df_wide.drop('Date', axis=1)

            # get the year totals/avgs
            df_grouped = df_wide.groupby(by=['OctSeptYear']).agg(agg_func)

            df_exceed = pd.DataFrame(index=list(range(df_grouped.shape[0])))

            # add exceedance probabilities
            i_n = df_grouped.shape[0]
            ld_probabilities = [m / (i_n + 1) * 100 for m in range(i_n, 0, -1)]
            df_exceed['exceedance_probability'] = ld_probabilities

            for var in keeplist[len(scenario_list):]:
                if var != 'Date':
                    if b_show_year:
                        l_years_sorted = df_grouped[var].sort_values().index
                        df_exceed[var + ' (Year)'] = l_years_sorted
                    l_sorted = df_grouped[var].sort_values().reset_index(drop=True)
                    df_exceed[var] = l_sorted

        else:
            if len(li_wyt_period_months) == 0:
                return pn.pane.Markdown("## No data to display")

            # first get rid of the years we dont need
            df_wide = df_wide.dropna(subset=keeplist[:len(scenario_list)], how='all')

            # pull out only those months
            df_wide = df_wide[df_wide['Month'].isin(li_wyt_period_months)]

            # drop incomplete years
            df_timecounts = df_wide.groupby(by=['OctSeptYear']).count()
            droplist = df_timecounts[df_timecounts['Date'] < len(li_wyt_period_months)].index
            df_wide = df_wide[df_wide['OctSeptYear'].isin(droplist) == False]

            # Can't sum dates: drop
            df_wide = df_wide.drop('Date', axis=1)

            # get the year totals/avgs
            df_grouped = df_wide.groupby(by=['OctSeptYear']).agg(agg_func)

            df_exceed = pd.DataFrame(index=list(range(df_grouped.shape[0])))

            # add exceedance probabilities
            i_n = df_grouped.shape[0]
            ld_probabilities = [m / (i_n + 1) * 100 for m in range(i_n, 0, -1)]
            df_exceed['exceedance_probability'] = ld_probabilities

            for var in keeplist[len(scenario_list):]:
                if b_show_year:
                    l_years_sorted = df_grouped[var].sort_values().index
                    df_exceed[var + ' (Year)'] = l_years_sorted
                l_sorted = df_grouped[var].sort_values().reset_index(drop=True)
                df_exceed[var] = l_sorted

        # round to one decimal place
        df_exceed = df_exceed.round(1)

        s_title = "## " + s_wyt_col + " "

        c_no_unit_names = {
            'WYT_SAC_': {1: 'Wet', 2: 'Above Normal', 3: 'Below Normal', 4: 'Dry', 5: 'Critically Dry'},
            'WYT_SJR_': {1: 'Wet', 2: 'Above Normal', 3: 'Below Normal', 4: 'Dry', 5: 'Critically Dry'},
            'WYT_TRIN_': {1: 'Extremely Wet', 2: 'Wet', 3: 'Normal', 4: 'Dry', 5: 'Critically Dry'},
            'WYT_SHASTA_CVP_': {0: 'Non-Critical', 1: 'ShastaCritical'},
            'WYT_FEATHER_': {1: 'Non-Critical', 2: 'Critically Dry'},
            'WYT_SJRRP_DV': {1: 'Wet', 2: 'Normal-Wet', 3: 'Normal-Dry', 4: 'Dry', 5: 'Critical High', 6: 'Critical Low'},
            'WYT_AMERD983_CVP_': {1: 'Non-Critical', 2: 'Critically Dry'},
            'SHASTABIN_': {1: '1a', 2: '1b', 3: '2a', 4: '2b', 5: '3a', 6: '3b'}
        }
        try:
            if '/' in period_choice:
                period_choice_stripped = period_choice.split('/')[1]
            else:
                period_choice_stripped = period_choice
            if period_choice_stripped[:3] == 'WYT':
                s_all_sel_wyt = 'All Water Year Types' if len(li_wyt_selected) == len(list(c_no_unit_names[period_choice_stripped].keys())) else ', '.join(
                    [c_no_unit_names[period_choice_stripped][wyt] for wyt in li_wyt_selected])
            else:
                s_all_sel_wyt = ', '.join([c_no_unit_names[period_choice_stripped][wyt] for wyt in li_wyt_selected])
        except:
            s_all_sel_wyt = ', '.join([str(wyt) for wyt in li_wyt_selected])

        s_title += s_all_sel_wyt + ' Years \n'
        if b_wyt_period_year:
            s_title += "## Water Year Total"
        else:
            li_wyt_period_months.sort()
            ls_months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            s_title += "## " + ', '.join([ls_months[i-1] for i in li_wyt_period_months])

        # add horizontal line if we are doing the differences plot
        if b_diffs_flag:
            return pn.Column(s_title, pn.pane.HoloViews((hv.HLine(0).opts(color='black', line_width=1) * df_exceed.hvplot(
                x='exceedance_probability',
                y=[var for var in df_exceed.columns if '(Year)' not in var and 'exceedance_probability' != var],
                min_height=600,
                ylabel=('Total ' if unit_choice == 'TAF' else 'Average ') + unit_choice,
                xlabel='Probability of Exceedance',
                flip_xaxis=(b_not_temperature),
                xformatter='%f%%',
                grid=True
            )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False), pn.pane.DataFrame(df_exceed, index=False, max_height=500))

        else:
            return pn.Column(s_title, pn.pane.HoloViews((hv.HLine(0).opts(line_width=0) * df_exceed.hvplot(
                x='exceedance_probability',
                y=[var for var in df_exceed.columns if '(Year)' not in var and 'exceedance_probability' != var],
                min_height=600,
                ylabel=('Total ' if unit_choice == 'TAF' else 'Average ') + unit_choice,
                xlabel='Probability of Exceedance',
                flip_xaxis=(b_not_temperature),
                xformatter='%f%%',
                grid=True
            )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False), pn.pane.DataFrame(df_exceed, index=False, max_height=500))


    # month choice
    elif isinstance(period_choice, int):
        df_wide = df_wide[df_wide.Month == period_choice]

        # Exceedance

        # Can't sum dates: drop
        df_wide = df_wide.drop('Date', axis=1)
        df_grouped = df_wide.groupby(by=['JanDecYear']).agg(agg_func)

        df_exceed = pd.DataFrame(index=list(range(df_grouped.shape[0])))

        # add exceedance probabilities
        i_n = df_grouped.shape[0]
        ld_probabilities = [m / (i_n + 1) * 100 for m in range(i_n, 0, -1)]
        df_exceed['exceedance_probability'] = ld_probabilities

        for var in keeplist:
            if b_show_year:
                l_years_sorted = df_grouped[var].sort_values().index
                df_exceed[var+' (Year)'] = l_years_sorted
            l_sorted = df_grouped[var].sort_values().reset_index(drop=True)
            df_exceed[var] = l_sorted

        # round to one decimal place
        df_exceed = df_exceed.round(1)

        c_num_to_month = {1: "January", 2: "February", 3: "March", 4: "April",
                          5: "May", 6: "June", 7: "July", 8: "August",
                          9: "September", 10: "October", 11: "November", 12: "December"}

        # add horizontal line if we are doing the differences plot
        if b_diffs_flag:
            return pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(color='black', line_width=1) * df_exceed.hvplot(
                x='exceedance_probability',
                y=keeplist,
                min_height=600,
                ylabel=c_num_to_month[period_choice] + ' ' + unit_choice,
                xlabel='Probability of Exceedance',
                flip_xaxis=(b_not_temperature),
                xformatter='%f%%',
                grid=True
            )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False), pn.pane.DataFrame(df_exceed, index=False, max_height=500))

        else:
            return pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(line_width=0) * df_exceed.hvplot(
                x='exceedance_probability',
                y=keeplist,
                min_height=600,
                ylabel=c_num_to_month[period_choice] + ' ' + unit_choice,
                xlabel='Probability of Exceedance',
                flip_xaxis=(b_not_temperature),
                xformatter='%f%%',
                grid=True
            )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False), pn.pane.DataFrame(df_exceed, index=False, max_height=500))

    else:
        # pull out start and stop months and then create a list of all the months in between
        i_start_month, i_end_month = int(period_choice.split('-')[0]), int(period_choice.split('-')[1])
        if i_end_month > i_start_month:
            li_months = list(range(i_start_month, i_end_month+1))
        else:
            li_months = list(range(i_start_month, 13)) + list(range(1, i_end_month+1))

        # filter for those months
        df_wide = df_wide[df_wide['Month'].isin(li_months)]

        # Exceedance

        # Can't sum dates: drop
        df_wide = df_wide.drop('Date', axis=1)

        # if we cross a cal year change, group by WY
        if period_choice in ['11-3', '10-1', '12-2', '10-4']:
            df_grouped = df_wide.groupby(by=['OctSeptYear']).agg(agg_func)
        else:
            df_grouped = df_wide.groupby(by=['JanDecYear']).agg(agg_func)

        df_exceed = pd.DataFrame(index=list(range(df_grouped.shape[0])))

        # add exceedance probabilities
        i_n = df_grouped.shape[0]
        ld_probabilities = [m / (i_n + 1) * 100 for m in range(i_n, 0, -1)]
        df_exceed['exceedance_probability'] = ld_probabilities

        for var in keeplist:
            if b_show_year:
                l_years_sorted = df_grouped[var].sort_values().index
                df_exceed[var + ' (Year)'] = l_years_sorted
            l_sorted = df_grouped[var].sort_values().reset_index(drop=True)
            df_exceed[var] = l_sorted

        # round to one decimal place
        df_exceed = df_exceed.round(1)

        # add horizontal line if we are doing the differences plot
        if b_diffs_flag:
            return pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(color='black', line_width=1) * df_exceed.hvplot(
                x='exceedance_probability',
                y=keeplist,
                min_height=600,
                ylabel=('Total ' if unit_choice == 'TAF' else 'Average ') + unit_choice,
                xlabel='Probability of Exceedance',
                flip_xaxis=(b_not_temperature),
                xformatter='%f%%',
                grid=True
            )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False), pn.pane.DataFrame(df_exceed, index=False, max_height=500))

        else:
            return pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(line_width=0) * df_exceed.hvplot(
                x='exceedance_probability',
                y=keeplist,
                min_height=600,
                ylabel=('Total ' if unit_choice == 'TAF' else 'Average ') + unit_choice,
                xlabel='Probability of Exceedance',
                flip_xaxis=(b_not_temperature),
                xformatter='%f%%',
                grid=True
            )).opts(legend_position='bottom', legend_cols=1), sizing_mode='stretch_width', linked_axes=False), pn.pane.DataFrame(df_exceed, index=False, max_height=500))

def plot_bars(df_all, period_choice, var_list, scenario_list,
              unit_choice, stat_choice, c_default_units, ls_comparison, c_field_list,
              li_wyt_selected, b_wyt_period_year, li_wyt_period_months, temp_unit_choice = 'F'):
    """
    Creates bar plot

    Parameters
    ----------
    df_all: DataFrame
        Data to be filtered and plotted
    period_choice: int or str
        Time period selected
    var_list: list
        Fields we want to plot
    scenario_list: list
        Scenarios we want to plot
    unit_choice: str
        Unit selection (CFS or TAF)
    stat_choice: str
        Statistic to calculate
    c_default_units: dict
        Dictionary of default units for each field
    ls_comparison: list
        list of names of comparison scenarios
    c_field_list: dict
        Dictionary of fields and descriptions
    li_wyt_selected: list
        Water year types selected for WYT time period
    b_wyt_period_year: bool
        If water year totals have been selected for WYT time period
    li_wyt_period_months: list
        Months selected for WYT time period
    temp_unit_choice: str
        Temperature unit selection ('F' or 'C')
    Returns
    -------
    Panel Object
        Plot and table side-by-side as a row. If grouping by water year type the row
        is preceded by a title describing the selected WYTs.
    """

    # if the data frame is empty, return a markdown frame. This will happen if only one scenario is selected and its the comparison one. the differences will be empty
    if df_all.empty:
        return pn.pane.Markdown("## No data to display")

    df_all_plot = df_all.groupby('Scenario').resample(rule='ME', on='Date').mean()
    df_all_plot.reset_index(inplace=True, drop=False)
    durations = [date.day for date in df_all_plot['Date']]

    b_diffs_flag = False

    # # ensure comparison scen is at the end of the list so the coloring is constant with the differences plot for all modules
    scenario_list = [scen for scen in ls_comparison if scen in scenario_list] + \
                    [scen for scen in scenario_list if scen not in ls_comparison]
    # check if none of the comparison scenarios are in the data frame
    # if none are, then we are creating the differences plot and don't want to include them
    if not any(comp in df_all_plot.Scenario.unique() for comp in ls_comparison):
        scenario_list = [scen for scen in scenario_list if scen not in ls_comparison]
        b_diffs_flag = True

    # check if no scenarios are selected
    if len(scenario_list) == 0:
        return pn.pane.Markdown("## No data to display")

    # check if no variables are selected
    if len(var_list) == 0:
        return pn.pane.Markdown('## Select variables above to display plot.')

    # to convert from cfs to taf or vice versa
    cfs_taf = np.multiply(durations, (24 * 3600 / 43560 / 1000))
    taf_cfs = np.divide((43560 * 1000 / 24 / 3600), durations)

    # create copy of var list since lists are mutable
    var_list_final = var_list[:]

    b_alt_unit = False
    ls_alt_vars = []
    s_alt_unit = ''

    # Unit conversion
    for var in var_list:
        try:
            original_unit = c_default_units[var].strip().upper()
        except:
            original_unit = None
        # check for variables that are not cfs/taf like EC, temperature, X2 position
        if original_unit not in ['NONE', 'CFS', 'TAF']:
            # if we havent already declared what the unit we will keep track of is, declare it
            if s_alt_unit == '':
                s_alt_unit = original_unit
            if original_unit == s_alt_unit:
                b_alt_unit = True
                ls_alt_vars.append(var)
        elif original_unit not in ['CFS', 'TAF']:
            var_list_final.remove(var)
            pass
        elif original_unit == unit_choice:
            pass
        elif original_unit == 'CFS':
            df_all_plot[var] = \
                np.multiply(df_all_plot[var], cfs_taf)
        elif original_unit == 'TAF':
            df_all_plot[var] = \
                np.multiply(df_all_plot[var], taf_cfs)
    agg_func = 'sum' if unit_choice == 'TAF' else 'mean'

    # If we found any non cfs/taf variables, we will only use those
    if b_alt_unit:
        var_list_final = ls_alt_vars
        if s_alt_unit == 'DEGF':
            if temp_unit_choice == 'C':
                df_all_plot[ls_alt_vars] = (df_all_plot[ls_alt_vars] - 32) * 5 / 9
                unit_choice = 'Degrees Celsius'
            else:
                unit_choice = 'Degrees Fahrenheit'
        else:
            unit_choice = s_alt_unit
        agg_func = 'mean'

    if len(var_list_final) == 0:
        return pn.pane.Markdown('## Select variables above to display plot.')

    # switch from variable name to description
    df_all_plot.rename(c_field_list, axis='columns', inplace=True)
    var_list_final = [c_field_list[var] for var in var_list_final]

    # if we are sorting by WYT we need to do some work before switching to wide frame
    if isinstance(period_choice, str) and ('WYT' in period_choice or 'SHASTABIN_' in period_choice):
        # sort for the years we want
        # see if any years are selected
        if not li_wyt_selected:
            return pn.pane.Markdown("## No data to display")

        # we do have some selected
        # what the column with the wyt is called
        s_wyt_col = c_field_list[period_choice]

        # select just september since that will have the correct wyt
        df_septembers = df_all_plot[df_all_plot['Month'] == 9]

        # pull the years and scenarios that match the selected wyts
        df_wy_to_use = df_septembers[df_septembers[s_wyt_col].isin(li_wyt_selected)][['Scenario', 'OctSeptYear', s_wyt_col]]
        # dictionary to hold {(scenario, WY): WYT}
        c_wy_to_wyt = {}
        for index, row in df_wy_to_use.iterrows():
            c_wy_to_wyt[(row['Scenario'], row['OctSeptYear'])] = row[s_wyt_col]

        # Assign wyt column to be the final wyt
        def wy_to_wyt(wyt_dict, scen, year):
            try:
                return wyt_dict[(scen, year)]
            except:
                return np.nan

        df_all_plot[s_wyt_col] = df_all_plot.apply(lambda row: wy_to_wyt(c_wy_to_wyt, row['Scenario'], row['OctSeptYear']), axis=1)

    # Sortable, filter to target scenarios and vars
    df_wide = pd.DataFrame(df_all_plot['Date'].unique(), columns=['Date'])
    df_wide[['OctSeptYear', 'JanDecYear', 'MarFebYear', 'Month']] = df_all_plot.loc[df_all_plot['Scenario'] == scenario_list[0]][['OctSeptYear', 'JanDecYear', 'MarFebYear', 'Month']].reset_index(drop=True)
    df_wide.reset_index(inplace=True, drop=True)

    keeplist = []

    # if grouping by wyt we need to include that variable
    if isinstance(period_choice, str) and ('WYT' in period_choice or 'SHASTABIN_' in period_choice):
        for scenario in scenario_list:
            df_temp = df_all_plot.loc[df_all_plot['Scenario'] == scenario][[s_wyt_col]]
            df_temp.reset_index(inplace=True, drop=True)
            col_names = [f'{scenario}: {s_wyt_col}']
            df_temp.columns = col_names
            df_wide[col_names] = df_temp[col_names]
            for name in col_names:
                keeplist.append(name)
    for var in var_list_final:
        for index, scenario in enumerate(scenario_list):
            df_temp = df_all_plot.loc[df_all_plot['Scenario'] == scenario][[var]]
            # skip if this scenario's module doesn't produce this var (all-NaN)
            if df_temp[var].isna().all():
                continue
            df_temp.reset_index(inplace=True, drop=True)
            col_names = [f'{scenario}: {var}']
            df_temp.columns = col_names
            df_wide[col_names] = df_temp[col_names]
            keeplist.append(col_names[0])

    # ------- Agg ops below -------------
    if period_choice in ['OctSeptYear', 'JanDecYear', 'MarFebYear']:
        df_timecounts = df_wide.groupby(by=[period_choice]).count()
        droplist = df_timecounts[df_timecounts['Date'] < 12].index
        df_wide = df_wide[df_wide[period_choice].isin(droplist) == False]

        # Can't sum dates: drop
        df_wide = df_wide.drop('Date', axis=1)
        df_grouped = df_wide.groupby(by=[period_choice]).agg(agg_func)
        df_plot = df_grouped[keeplist]

        # calculate chosen stat
        if stat_choice == 'Average':
            df_stats = df_plot.mean().to_frame()
        elif stat_choice == 'Minimum':
            df_stats = df_plot.min().to_frame()
        elif stat_choice == 'Maximum':
            df_stats = df_plot.max().to_frame()
        # want an exceedance probability
        else:
            i_exceedance_prob = int(stat_choice.split('%')[0])

            df_exceed = pd.DataFrame(index=df_plot.reset_index().index)
            # add exceedance probabilities
            i_n = df_plot.shape[0]
            ld_probabilities = [m / (i_n + 1) * 100 for m in range(i_n, 0, -1)]
            df_exceed['exceedance_probability'] = ld_probabilities

            for var in keeplist:
                if var != 'Date':
                    l_sorted = df_plot[var].sort_values().reset_index(drop=True)
                    df_exceed[var] = l_sorted

            # if hte probability has already been calculated
            df_exceed = df_exceed.set_index('exceedance_probability')
            if i_exceedance_prob in df_exceed.index:
                df_stats = df_exceed.loc[i_exceedance_prob].to_frame()

            # need to interpolate
            else:
                df_exceed.loc[i_exceedance_prob] = pd.Series(dtype='float32')
                df_exceed.interpolate(method='index', inplace=True)
                df_stats = df_exceed.loc[i_exceedance_prob].to_frame()

    # if water year type is selected as period
    elif isinstance(period_choice, str) and ('WYT' in period_choice or 'SHASTABIN_' in period_choice):
        # filter for selected WYTs
        # get rif of anywhere all wyt columns are empty
        df_wide = df_wide.dropna(subset=keeplist[:len(scenario_list)], how='all')

        # check if we ended up with no matching years
        if df_wide.empty:
            return pn.pane.Markdown("## No data to display")

        # if we want to look at water year totals
        if b_wyt_period_year:
            # drop incomplete years
            df_timecounts = df_wide.groupby(by=['OctSeptYear']).count()
            droplist = df_timecounts[df_timecounts['Date'] < 12].index
            df_wide = df_wide[df_wide['OctSeptYear'].isin(droplist) == False]

            # Can't sum dates: drop
            df_wide = df_wide.drop('Date', axis=1)

            # get the year totals/avgs
            df_grouped = df_wide.groupby(by=['OctSeptYear']).agg(agg_func)

            # assign the WYt to be the correct one
            df_grouped[keeplist[:len(scenario_list)]] = df_grouped[keeplist[:len(scenario_list)]] / 12

            # get rid of other columns we dont need
            df_plot = df_grouped[keeplist]
        else:
            if len(li_wyt_period_months) == 0:
                return pn.pane.Markdown("## No data to display")
            # first get rid of the years we dont need
            df_wide = df_wide.dropna(subset=keeplist[:len(scenario_list)], how='all')

            # pull out only those months
            df_wide = df_wide[df_wide['Month'].isin(li_wyt_period_months)]

            # drop incomplete years
            df_timecounts = df_wide.groupby(by=['OctSeptYear']).count()
            droplist = df_timecounts[df_timecounts['Date'] < len(li_wyt_period_months)].index
            df_wide = df_wide[df_wide['OctSeptYear'].isin(droplist) == False]

            # Can't sum dates: drop
            df_wide = df_wide.drop('Date', axis=1)

            # get the year totals/avgs
            df_grouped = df_wide.groupby(by=['OctSeptYear']).agg(agg_func)

            # assign the WYt to be the correct one
            df_grouped[keeplist[:len(scenario_list)]] = df_grouped[keeplist[:len(scenario_list)]] / len(li_wyt_period_months)

            # get rid of other columns we don't need
            df_plot = df_grouped[keeplist]

        df_final = pd.DataFrame(index=pd.MultiIndex.from_product([li_wyt_selected, scenario_list], names=[s_wyt_col, 'Scenario']))
        for i_wyt in li_wyt_selected:
            for s_scen in scenario_list:
                s_scen_wyt_col = f'{s_scen}: {s_wyt_col}'
                col_names = [f'{s_scen}: {var_list_final[0]}']
                if col_names[0] not in df_plot.columns:
                    continue
                df_temp = df_plot[df_plot[s_scen_wyt_col] == i_wyt]
                if stat_choice == 'Average':
                    df_temp = df_temp[col_names].mean()
                elif stat_choice == 'Minimum':
                    df_temp = df_temp[col_names].min()
                elif stat_choice == 'Maximum':
                    df_temp = df_temp[col_names].max()
                # want an exceedance probability
                else:
                    i_exceedance_prob = int(stat_choice.split('%')[0])

                    df_exceed = pd.DataFrame(index=df_temp.reset_index().index)
                    # add exceedance probabilities
                    i_n = df_temp.shape[0]
                    ld_probabilities = [m / (i_n + 1) * 100 for m in range(i_n, 0, -1)]
                    df_exceed['exceedance_probability'] = ld_probabilities

                    l_sorted = df_temp[col_names[0]].sort_values().reset_index(drop=True)
                    df_exceed[col_names[0]] = l_sorted

                    # if hte probability has already been calculated
                    df_exceed = df_exceed.set_index('exceedance_probability')
                    if i_exceedance_prob in df_exceed.index:
                        df_temp = df_exceed.loc[i_exceedance_prob]

                    # need to interpolate
                    else:
                        df_exceed.loc[i_exceedance_prob] = pd.Series(dtype='float32')
                        df_exceed.interpolate(method='index', inplace=True)
                        df_temp = df_exceed.loc[i_exceedance_prob]

                df_final.loc[(i_wyt, s_scen), var_list_final[0]] = df_temp.values
        for s_scen in scenario_list:
            s_scen_wyt_col = f'{s_scen}: {s_wyt_col}'
            col_names = [f'{s_scen}: {var_list_final[0]}']
            if col_names[0] not in df_plot.columns:
                continue
            df_temp = df_plot[df_plot[s_scen_wyt_col] == i_wyt]
            if stat_choice == 'Average':
                df_temp = df_temp[col_names].mean()
            elif stat_choice == 'Minimum':
                df_temp = df_temp[col_names].min()
            elif stat_choice == 'Maximum':
                df_temp = df_temp[col_names].max()
            # want an exceedance probability
            else:
                i_exceedance_prob = int(stat_choice.split('%')[0])

                df_exceed = pd.DataFrame(index=df_temp.reset_index().index)
                # add exceedance probabilities
                i_n = df_temp.shape[0]
                ld_probabilities = [m / (i_n + 1) * 100 for m in range(i_n, 0, -1)]
                df_exceed['exceedance_probability'] = ld_probabilities

                l_sorted = df_temp[col_names[0]].sort_values().reset_index(drop=True)
                df_exceed[col_names[0]] = l_sorted

                # if hte probability has already been calculated
                df_exceed = df_exceed.set_index('exceedance_probability')
                if i_exceedance_prob in df_exceed.index:
                    df_temp = df_exceed.loc[i_exceedance_prob]

                # need to interpolate
                else:
                    df_exceed.loc[i_exceedance_prob] = pd.Series(dtype='float32')
                    df_exceed.interpolate(method='index', inplace=True)
                    df_temp = df_exceed.loc[i_exceedance_prob]
            df_final.loc[(99, s_scen), var_list_final[0]] = df_temp.values

        # round to one decimal place
        df_final.loc[:, df_final.columns != 'Date'] = df_final.loc[:, df_final.columns != 'Date'].round(1)
        df_plot = df_plot.round(1)

        s_title = "## " + s_wyt_col + " "

        c_no_unit_names = {
            'WYT_SAC_': {1: 'Wet', 2: 'Above Normal', 3: 'Below Normal', 4: 'Dry', 5: 'Critically Dry'},
            'WYT_SJR_': {1: 'Wet', 2: 'Above Normal', 3: 'Below Normal', 4: 'Dry', 5: 'Critically Dry'},
            'WYT_TRIN_': {1: 'Extremely Wet', 2: 'Wet', 3: 'Normal', 4: 'Dry', 5: 'Critically Dry'},
            'WYT_SHASTA_CVP_': {0: 'Non-Critical', 1: 'ShastaCritical'},
            'WYT_FEATHER_': {1: 'Non-Critical', 2: 'Critically Dry'},
            'WYT_SJRRP_DV': {1: 'Wet', 2: 'Normal-Wet', 3: 'Normal-Dry', 4: 'Dry', 5: 'Critical High', 6: 'Critical Low'},
            'WYT_AMERD983_CVP_': {1: 'Non-Critical', 2: 'Critically Dry'},
            'SHASTABIN_': {1: '1a', 2: '1b', 3: '2a', 4: '2b', 5: '3a', 6: '3b'}
        }
        try:
            if '/' in period_choice:
                period_choice_stripped = period_choice.split('/')[1]
            else:
                period_choice_stripped = period_choice
            if period_choice_stripped[:3] == 'WYT':
                s_all_sel_wyt = 'All Water Year Types' if len(li_wyt_selected) == len(list(c_no_unit_names[period_choice_stripped].keys())) else ', '.join(
                    [c_no_unit_names[period_choice_stripped][wyt] for wyt in li_wyt_selected])
            else:
                s_all_sel_wyt = ', '.join([c_no_unit_names[period_choice_stripped][wyt] for wyt in li_wyt_selected])
        except:
            c_no_unit_names[period_choice_stripped] = {wyt: wyt for wyt in li_wyt_selected}
            s_all_sel_wyt = 'All Water Year Types' if len(li_wyt_selected) == len(list(c_no_unit_names[period_choice_stripped].keys())) else ', '.join(
                [c_no_unit_names[period_choice][wyt] for wyt in li_wyt_selected])

        try:
            for wyt in list(c_no_unit_names.keys()):
                c_no_unit_names[wyt][99] = s_all_sel_wyt
            df_final.rename(index=c_no_unit_names[period_choice_stripped], inplace=True)
        except:
            for wyt in list(c_no_unit_names.keys()):
                c_no_unit_names[wyt][99] = s_all_sel_wyt
            df_final.rename(index=c_no_unit_names[period_choice_stripped], inplace=True)

        s_title += s_all_sel_wyt + ' Years \n'
        if b_wyt_period_year:
            s_title += "## Water Year Total"
        else:
            ls_months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
            li_wyt_period_months.sort()
            s_title += "## " + ', '.join([ls_months[i - 1] for i in li_wyt_period_months])

        # if they have more than one variable selected, display a warning that only the first will display
        # b_diffs_flag is so that we only get one
        if len(var_list_final) > 1 and b_diffs_flag:
            pn.state.notifications.position = 'center-center'
            pn.state.notifications.warning('If more than one variable is selected while filtering by water year type, the bar chart will only display the first variable.', duration=7000)
        if b_diffs_flag:
            return pn.Column(
                s_title,
                pn.Row(
                    pn.Column(pn.pane.HoloViews(hv.HLine(0).opts(color='black', line_width=1) * df_final.hvplot.bar(
                        title='', grid=True,
                        xlabel=s_wyt_col + ', Scenario',
                        ylabel=stat_choice + ' ' + var_list_final[0] + ' (' + unit_choice + ')',
                        rot=90,
                        min_height=600, legend=False), sizing_mode='stretch_width', linked_axes=False),
                              sizing_mode='stretch_width'),
                    pn.Column(pn.pane.DataFrame(df_plot, max_height=500), sizing_mode='stretch_width'),
                    sizing_mode='stretch_width'
                )
            )

        else:
            return pn.Column(
                s_title,
                pn.Row(
                    pn.Column(pn.pane.HoloViews(df_final.hvplot.bar(
                        title='', grid=True,
                        xlabel=s_wyt_col + ', Scenario',
                        ylabel=stat_choice + ' ' + var_list_final[0] + ' (' + unit_choice + ')',
                        rot=90,
                        min_height=600), sizing_mode='stretch_width', linked_axes=False), sizing_mode='stretch_width'),
                    pn.Column(pn.pane.DataFrame(df_plot, max_height=500), sizing_mode='stretch_width'),
                    sizing_mode='stretch_width'
                )
            )
    # Month chosen
    elif isinstance(period_choice, int):
        df_wide = df_wide[df_wide.Month == period_choice]

        # Can't sum dates: drop
        df_wide = df_wide.drop('Date', axis=1)

        # this will group by year so there will only be one value
        df_grouped = df_wide.groupby(by=['JanDecYear']).agg(agg_func)
        df_plot = df_grouped[keeplist]

        # calculate chosen stat
        if stat_choice == 'Average':
            df_stats = df_plot.mean().to_frame()
        elif stat_choice == 'Minimum':
            df_stats = df_plot.min().to_frame()
        elif stat_choice == 'Maximum':
            df_stats = df_plot.max().to_frame()
        # want an exceedance probability
        else:
            i_exceedance_prob = int(stat_choice.split('%')[0])

            df_exceed = pd.DataFrame(index=df_plot.reset_index().index)
            # add exceedance probabilities
            i_n = df_plot.shape[0]
            ld_probabilities = [m / (i_n + 1) * 100 for m in range(i_n, 0, -1)]
            df_exceed['exceedance_probability'] = ld_probabilities

            for var in keeplist:
                if var != 'Date':
                    l_sorted = df_plot[var].sort_values().reset_index(drop=True)
                    df_exceed[var] = l_sorted

            # if hte probability has already been calculated
            df_exceed = df_exceed.set_index('exceedance_probability')
            if i_exceedance_prob in df_exceed.index:
                df_stats = df_exceed.loc[i_exceedance_prob].to_frame()

            # need to interpolate
            else:
                df_exceed.loc[i_exceedance_prob] = pd.Series(dtype='float32')
                df_exceed.interpolate(method='index', inplace=True)
                df_stats = df_exceed.loc[i_exceedance_prob].to_frame()
    # chose a partial year
    else:
        # pull out start and stop months and then create a list of all the months in between
        i_start_month, i_end_month = int(period_choice.split('-')[0]), int(period_choice.split('-')[1])
        if i_end_month > i_start_month:
            li_months = list(range(i_start_month, i_end_month+1))
        else:
            li_months = list(range(i_start_month, 13)) + list(range(1, i_end_month+1))

        # filter for those months
        df_wide = df_wide[df_wide['Month'].isin(li_months)]

        # Can't sum dates: drop
        df_wide = df_wide.drop('Date', axis=1)

        # if we cross a cal year change, group by WY
        if period_choice in ['11-3', '10-1', '12-2', '10-4']:
            df_grouped = df_wide.groupby(by=['OctSeptYear']).agg(agg_func)
        else:
            df_grouped = df_wide.groupby(by=['JanDecYear']).agg(agg_func)
            
        df_plot = df_grouped[keeplist]

        # calculate chosen stat
        if stat_choice == 'Average':
            df_stats = df_plot.mean().to_frame()
        elif stat_choice == 'Minimum':
            df_stats = df_plot.min().to_frame()
        elif stat_choice == 'Maximum':
            df_stats = df_plot.max().to_frame()
        # want an exceedance probability
        else:
            i_exceedance_prob = int(stat_choice.split('%')[0])

            df_exceed = pd.DataFrame(index=df_plot.reset_index().index)
            # add exceedance probabilities
            i_n = df_plot.shape[0]
            ld_probabilities = [m / (i_n + 1) * 100 for m in range(i_n, 0, -1)]
            df_exceed['exceedance_probability'] = ld_probabilities

            for var in keeplist:
                if var != 'Date':
                    l_sorted = df_plot[var].sort_values().reset_index(drop=True)
                    df_exceed[var] = l_sorted

            # if hte probability has already been calculated
            df_exceed = df_exceed.set_index('exceedance_probability')
            if i_exceedance_prob in df_exceed.index:
                df_stats = df_exceed.loc[i_exceedance_prob].to_frame()

            # need to interpolate
            else:
                df_exceed.loc[i_exceedance_prob] = pd.Series(dtype='float32')
                df_exceed.interpolate(method='index', inplace=True)
                df_stats = df_exceed.loc[i_exceedance_prob].to_frame()

    # round to one decimal place
    df_stats.loc[:, df_stats.columns != 'Date'] = df_stats.loc[:, df_stats.columns != 'Date'].round(1)
    df_plot = df_plot.round(1)

    # calculate bound, pick colors, and plot for all data above
    # Set upper and lower bounds
    if np.min(df_stats) > 0:
        y_lower = 0
    else:
        y_lower = np.min(df_stats) * 1.05
    if np.max(df_stats) > 0:
        y_upper = np.max(df_stats) * 1.05
    else:
        y_upper = 0

    # full list of color options
    ls_colors = ['#003E51', '#007396', '#C69214', '#FF671F', '#215732', '#4C12A1', '#9A3324'] + hv.Cycle.default_cycles["default_colors"]

    # the colors we need, one for each scenario
    if len(scenario_list) >= len(ls_colors):
        # in case we have more scenarios than colors
        ls_colors_to_use = ls_colors
    else:
        ls_colors_to_use = ls_colors[:(len(scenario_list) % len(ls_colors))]

    # pull out how many times we will need to duplicate this list
    i_full_list, i_remainder_list = divmod(df_stats.shape[0], len(ls_colors_to_use))
    ls_colors_to_use = ls_colors_to_use * i_full_list + ls_colors_to_use[:i_remainder_list]
    df_stats['Color'] = ls_colors_to_use[::-1]

    # add horizontal line if we are doing the differences plot
    if b_diffs_flag:
        return pn.Row(
            pn.Column(pn.pane.HoloViews(hv.HLine(0).opts(color='black', line_width=1) * df_stats.hvplot.bar(
                title='', color='Color', grid=True,
                ylabel=stat_choice + ' ' + unit_choice,
                ylim=(y_lower, y_upper), rot=20,
                min_height=600, legend=False), sizing_mode='stretch_width', linked_axes=False),
                      sizing_mode='stretch_width'),
            pn.Column(pn.pane.DataFrame(df_plot, max_height=500), sizing_mode='stretch_width'),
            sizing_mode='stretch_width'
        )

    else:
        return pn.Row(
            pn.Column(pn.pane.HoloViews(df_stats.hvplot.bar(
                title='', color='Color', grid=True,
                ylabel=stat_choice + ' ' + unit_choice,
                ylim=(y_lower, y_upper), rot=20,
                min_height=600), sizing_mode='stretch_width', linked_axes=False), sizing_mode='stretch_width'),
            pn.Column(pn.pane.DataFrame(df_plot, max_height=500), sizing_mode='stretch_width'),
            sizing_mode='stretch_width'
        )


def monthly_pattern(df_all, var_list, scenario_list, unit_choice,
                    stat_choice, c_default_units, ls_comparison,
                    c_field_list, period_choice, li_wyt_selected, temp_unit_choice = 'F'):
    """
    Creates monthly pattern plot

    Parameters
    ----------
    df_all: DataFrame
        Data to be filtered and plotted
    var_list: list
        Fields we want to plot
    scenario_list: list
        Scenarios we want to plot
    unit_choice: str
        Unit selection (CFS or TAF)
    stat_choice: str
        Statistic to calculate
    c_default_units: dict
        Dictionary of default units for each field
    ls_comparison: list
        list of names of comparison scenarios
    c_field_list: dict
        Dictionary of fields and descriptions
    li_wyt_selected: list
        Water year types selected for WYT time period
    period_choice: int or str
        Time period selected
    li_wyt_selected
    temp_unit_choice: str
        Temperature unit selection ('F' or 'C')

    Returns
    -------
    Panel Object
        A column containing the WYT title (if applicable) followed by a row with the
        plot on the left and the full data table on the right
    """

    # if the data frame is empty, return a markdown frame. This will happen if only one scenario is selected and its the comparison one. the differences will be empty
    if df_all.empty:
        return pn.pane.Markdown("## No data to display")

    df_all_plot = df_all.groupby('Scenario').resample(rule='ME', on='Date').mean()
    df_all_plot.reset_index(inplace=True, drop=False)
    durations = [date.day for date in df_all_plot['Date']]

    b_diffs_flag = False

    # # ensure comparison scen is at the end of the list so the coloring is constant with the differences plot for all modules
    scenario_list = [scen for scen in scenario_list if scen not in ls_comparison] + \
                    [scen for scen in ls_comparison if scen in scenario_list]
    # check if none of the comparison scenarios are in the data frame
    # if none are, then we are creating the differences plot and don't want to include them
    if not any(comp in df_all_plot.Scenario.unique() for comp in ls_comparison):
        scenario_list = [scen for scen in scenario_list if scen not in ls_comparison]
        b_diffs_flag = True

    # check if no scenarios are selected
    if len(scenario_list) == 0:
        return pn.pane.Markdown("## No data to display")

    # check if no variables are selected
    if len(var_list) == 0:
        return pn.pane.Markdown('## Select variables above to display plot.')

    # to convert from cfs to taf or vice versa
    cfs_taf = np.multiply(durations, (24 * 3600 / 43560 / 1000))
    taf_cfs = np.divide((43560 * 1000 / 24 / 3600), durations)

    # create copy of var list since lists are mutable
    var_list_final = var_list[:]

    b_alt_unit = False
    ls_alt_vars = []
    s_alt_unit = ''

    # Unit conversion
    for var in var_list:
        try:
            original_unit = c_default_units[var].strip().upper()
        except:
            original_unit = None

        # check for variables that are not cfs/taf like EC, temperature, X2 position
        if original_unit not in ['NONE', 'CFS', 'TAF']:
            # if we havent already declared what the unit we will keep track of is, declare it
            if s_alt_unit == '':
                s_alt_unit = original_unit
            if original_unit == s_alt_unit:
                b_alt_unit = True
                ls_alt_vars.append(var)
        elif original_unit not in ['CFS', 'TAF']:
            var_list_final.remove(var)
            pass
        elif original_unit == unit_choice:
            pass
        elif original_unit == 'CFS':
            df_all_plot[var] = \
                np.multiply(df_all_plot[var], cfs_taf)
        elif original_unit == 'TAF':
            df_all_plot[var] = \
                np.multiply(df_all_plot[var], taf_cfs)

    # If we found any non cfs/taf variables, we will only use those
    if b_alt_unit:
        var_list_final = ls_alt_vars
        if s_alt_unit == 'DEGF':
            if temp_unit_choice == 'C':
                df_all_plot[ls_alt_vars] = (df_all_plot[ls_alt_vars] - 32) * 5 / 9
                unit_choice = 'Degrees Celsius'
            else:
                unit_choice = 'Degrees Fahrenheit'
        else:
            unit_choice = s_alt_unit

    if len(var_list_final) == 0:
        return pn.pane.Markdown('## Select variables above to display plot.')

    # switch from variable name to description
    df_all_plot.rename(c_field_list, axis='columns', inplace=True)
    var_list_final = [c_field_list[var] for var in var_list_final]

    # if we are sorting by WYT we need to do some work before switching to wide frame
    if isinstance(period_choice, str) and ('WYT' in period_choice or 'SHASTABIN_' in period_choice):
        # sort for the years we want
        # see if any years are selected
        if not li_wyt_selected:
            return pn.pane.Markdown("## No data to display")

        # we do have some selected
        # what the column with the wyt is called
        s_wyt_col = c_field_list[period_choice]

        # select just september since that will have the correct wyt
        df_septembers = df_all_plot[df_all_plot['Month'] == 9]

        # pull the years and scenarios that match the selected wyts
        df_wy_to_use = df_septembers[df_septembers[s_wyt_col].isin(li_wyt_selected)][['Scenario', 'OctSeptYear', s_wyt_col]]
        # dictionary to hold {(scenario, WY): WYT}
        c_wy_to_wyt = {}
        for index, row in df_wy_to_use.iterrows():
            c_wy_to_wyt[(row['Scenario'], row['OctSeptYear'])] = row[s_wyt_col]

        # Assign wyt column to be the final wyt
        def wy_to_wyt(wyt_dict, scen, year):
            try:
                return wyt_dict[(scen, year)]
            except:
                return np.nan

        df_all_plot[s_wyt_col] = df_all_plot.apply(lambda row: wy_to_wyt(c_wy_to_wyt, row['Scenario'], row['OctSeptYear']), axis=1)

    # Sortable, filter to target scenarios and vars
    df_wide = pd.DataFrame(df_all_plot['Date'].unique(), columns=['Date'])
    df_wide[['Month']] = df_all_plot.loc[df_all_plot['Scenario'] == scenario_list[0]][['Month']].reset_index(drop=True)
    df_wide.reset_index(inplace=True, drop=True)

    keeplist = ['Month']

    # this will stay empty unless we have a wyt selected
    s_title = ''

    # if grouping by wyt we need to include that variable
    if isinstance(period_choice, str) and ('WYT' in period_choice or 'SHASTABIN_' in period_choice):
        # to hold the wyt columns so we can filter with them but they dont end up in keeplist
        ls_wyt_cols = []
        for scenario in scenario_list:
            df_temp = df_all_plot.loc[df_all_plot['Scenario'] == scenario][[s_wyt_col]]
            df_temp.reset_index(inplace=True, drop=True)
            col_names = [f'{scenario}: {s_wyt_col}']
            df_temp.columns = col_names
            df_wide[col_names] = df_temp[col_names]
            for name in col_names:
                ls_wyt_cols.append(name)
        df_wide = df_wide.dropna(subset=ls_wyt_cols, how='all')
        # create a title that displays the WYTs
        c_no_unit_names = {
            'WYT_SAC_': {1: 'Wet', 2: 'Above Normal', 3: 'Below Normal', 4: 'Dry', 5: 'Critically Dry'},
            'WYT_SJR_': {1: 'Wet', 2: 'Above Normal', 3: 'Below Normal', 4: 'Dry', 5: 'Critically Dry'},
            'WYT_TRIN_': {1: 'Extremely Wet', 2: 'Wet', 3: 'Normal', 4: 'Dry', 5: 'Critically Dry'},
            'WYT_SHASTA_CVP_': {0: 'Non-Critical', 1: 'ShastaCritical'},
            'WYT_FEATHER_': {1: 'Non-Critical', 2: 'Critically Dry'},
            'WYT_SJRRP_DV': {1: 'Wet', 2: 'Normal-Wet', 3: 'Normal-Dry', 4: 'Dry', 5: 'Critical High', 6: 'Critical Low'},
            'WYT_AMERD983_CVP_': {1: 'Non-Critical', 2: 'Critically Dry'},
            'SHASTABIN_': {1: '1a', 2: '1b', 3: '2a', 4: '2b', 5: '3a', 6: '3b'}
        }
        try:
            if '/' in period_choice:
                period_choice_stripped = period_choice.split('/')[1]
            else:
                period_choice_stripped = period_choice
            if period_choice_stripped[:3] == 'WYT':
                s_all_sel_wyt = 'All' if len(li_wyt_selected) == len(list(c_no_unit_names[period_choice_stripped].keys())) else ', '.join(
                    [c_no_unit_names[period_choice_stripped][wyt] for wyt in li_wyt_selected])
            else:
                s_all_sel_wyt = ', '.join([c_no_unit_names[period_choice_stripped][wyt] for wyt in li_wyt_selected])
        except:
            c_no_unit_names[period_choice_stripped] = {wyt: wyt for wyt in li_wyt_selected}
            s_all_sel_wyt = 'All' if len(li_wyt_selected) == len(list(c_no_unit_names[period_choice_stripped].keys())) else ', '.join(
                [c_no_unit_names[period_choice_stripped][wyt] for wyt in li_wyt_selected])
        s_title = '## ' + s_wyt_col + ': ' + s_all_sel_wyt + ' Years'

    for scenario in scenario_list:
        df_temp = df_all_plot.loc[df_all_plot['Scenario'] == scenario][var_list_final]
        # skip vars this scenario's module doesn't produce (all-NaN for this scenario)
        valid_vars = [v for v in var_list_final if not df_temp[v].isna().all()]
        if not valid_vars:
            continue
        df_temp = df_temp[valid_vars]
        df_temp.reset_index(inplace=True, drop=True)
        col_names = [f'{scenario}: {var}' for var in valid_vars]
        df_temp.columns = col_names
        df_wide[col_names] = df_temp[col_names]
        for name in col_names:
            keeplist.append(name)
    df_grouped = df_wide[keeplist].groupby('Month')

    if stat_choice == 'Average':
        df_plot = df_grouped.mean()
    elif stat_choice == 'Minimum':
        df_plot = df_grouped.min()
    elif stat_choice == 'Maximum':
        df_plot = df_grouped.max()
    # want an exceedance probability
    else:
        i_exceedance_prob = int(stat_choice.split('%')[0])
        # data frame to hold the values to plot
        df_plot = pd.DataFrame(index=list(range(1,13)))
        df_plot.index.name = 'Month'
        for month, df_month in df_grouped:
            df_exceed = pd.DataFrame(index=df_month.reset_index().index)
            # add exceedance probabilities
            i_n = df_month.shape[0]
            ld_probabilities = [m / (i_n + 1) * 100 for m in range(i_n, 0, -1)]
            df_exceed['exceedance_probability'] = ld_probabilities

            for var in keeplist:
                if var != 'Month':
                    l_sorted = df_month[var].sort_values().reset_index(drop=True)
                    df_exceed[var] = l_sorted

            # if hte probability has already been calculated
            df_exceed = df_exceed.set_index('exceedance_probability')
            if i_exceedance_prob in df_exceed.index:
                df_plot.loc[month, df_exceed.columns] = df_exceed.loc[i_exceedance_prob]

            # need to interpolate
            else:
                df_exceed.loc[i_exceedance_prob] = pd.Series(dtype='float32')
                df_exceed.interpolate(method='index', inplace=True)
                df_plot.loc[month, df_exceed.columns] = df_exceed.loc[i_exceedance_prob]
    # round to one decimal
    df_plot = df_plot.round(1)
    df_wide.loc[:, df_wide.columns != 'Date'] = df_wide.loc[:, df_wide.columns != 'Date'].round(1)

    # reorder to be in water year
    df_plot = df_plot.reindex(index=[10, 11, 12, 1, 2, 3, 4, 5, 6, 7, 8, 9])

    # switch from numbers to month abbreviations
    c_num_to_month = {1: 'Jan', 2: 'Feb', 3: 'Mar', 4: 'Apr', 5: 'May', 6: 'Jun', 7: 'Jul', 8: 'Aug', 9: 'Sep', 10: 'Oct', 11: 'Nov', 12: 'Dec'}
    df_plot.index = df_plot.index.map(c_num_to_month)

    # if doing difference plot, add horizontal line
    if b_diffs_flag:
        return pn.Column(
            s_title,
            pn.Row(
                pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(color='black', line_width=1) * df_plot.hvplot(
                    x='Month',
                    min_height=600,
                    xlabel='Month',
                    ylabel=stat_choice + ' ' + unit_choice,
                    grid=True
                )).opts(legend_position='bottom', legend_cols=1),
                                            sizing_mode='stretch_width', linked_axes=False),
                          sizing_mode='stretch_width'),
                pn.Column(pn.pane.DataFrame(df_wide, index=False, max_height=500), sizing_mode='stretch_width'),
                sizing_mode='stretch_width'))
    else:
        return pn.Column(
            s_title,
            pn.Row(
                pn.Column(pn.pane.HoloViews((hv.HLine(0).opts(line_width=0) * df_plot.hvplot(
                    x='Month',
                    min_height=600,
                    xlabel='Month',
                    ylabel=stat_choice + ' ' + unit_choice,
                    grid=True
                )).opts(legend_position='bottom', legend_cols=1),
                                            sizing_mode='stretch_width', linked_axes=False),
                          sizing_mode='stretch_width'),
                pn.Column(pn.pane.DataFrame(df_wide, index=False, max_height=500), sizing_mode='stretch_width'),
                sizing_mode='stretch_width'))

def plot_single_year(scenario_list, df_all, c_field_list, s_reservoir, i_year, temp_unit_choice='F'):
    """
    Creates the single-year operations, cold water profile, and temperature plots for
    Shasta or Folsom

    Parameters
    ----------
    scenario_list: list
        Scenarios we want to plot
    df_all: DataFrame
        Data to be filtered and plotted
    c_field_list: dict
        Dictionary of fields and descriptions
    s_reservoir: str
        Which reservoir to plot ('Shasta' or 'Folsom')
    i_year: int
        Year to plot
    temp_unit_choice: str
        Temperature unit selection ('F' or 'C')

    Returns
    -------
    Panel Object
        A column containing, for each scenario: the operations plot (storage + flow
        curves) and cold water profile plot side by side, the temperature
        plots (one per temperature field, all scenarios overlaid), the full
        data tables for each scenario
    """
    # check if no scenarios are selected
    if len(scenario_list) == 0:
        return pn.pane.Markdown("## No data to display")

    # Loop through each scenario and create a plot

    # trim to time period for operations
    o_operations_dates = pd.date_range(start=datetime.datetime(year=i_year, month=1, day=31), end=datetime.datetime(year=i_year, month=12, day=31), freq='ME').to_pydatetime()
    df_operations = df_all[df_all['Date'].isin(o_operations_dates)].reset_index(drop=True)

    # trim to dates for cold water
    o_first_of_months = pd.date_range(start=datetime.datetime(year=i_year, month=1, day=1), end=datetime.datetime(year=i_year, month=12, day=1), freq='MS')
    o_end_of_months = pd.date_range(start=datetime.datetime(year=i_year, month=1, day=31), end=datetime.datetime(year=i_year, month=12, day=31), freq='ME')
    o_cold_water_dates = o_end_of_months.append(o_first_of_months + datetime.timedelta(days=9))
    o_cold_water_dates = o_cold_water_dates.append(o_first_of_months + datetime.timedelta(days=19))
    o_cold_water_dates = np.sort(o_cold_water_dates.to_pydatetime())
    df_cold_water = df_all[df_all['Date'].isin(o_cold_water_dates)].reset_index(drop=True)

    # Trim to year for temperature
    o_temperature_dates = pd.date_range(start=datetime.datetime(year=i_year, month=1, day=1), end=datetime.datetime(year=i_year, month=12, day=31), freq='d').to_pydatetime()
    df_temperature = df_all[df_all['Date'].isin(o_temperature_dates)].reset_index(drop=True)
    df_temperature = df_temperature[df_temperature['Scenario'].isin(scenario_list)]

    if s_reservoir == 'Shasta':
        # variables we need for shasta
        ls_cfs_vars = ['CALSIM/C_KSWCK/CHANNEL', 'CALSIM/C_SHSTA/CHANNEL', 'CALSIM/I_SHSTA/INFLOW', 'ShaSpill']
        ls_taf_vars = ['CALSIM/S_SHSTA/STORAGE']
        ls_cold_water_vars = ['<45 (Shasta)', '45-50 (Shasta)', '50-55 (Shasta)', '55-60 (Shasta)', '60-65 (Shasta)', '65-70 (Shasta)', '70+ (Shasta)']
        ls_temp_fields = ['SACRAMENTO/HWY44/TEMP_F', 'SACRAMENTO/BLW CLEAR CREEK/TEMP_F', 'SACRAMENTO/AIRPORT/TEMP_F']

        # Convert I_SHSTA to CFS from TAF
        df_operations['CALSIM/I_SHSTA/INFLOW'] = df_operations['CALSIM/I_SHSTA/INFLOW'] / (df_operations['Date'].dt.day * (3600 * 24 / 43560 / 1000))
    else:
        # Folsom
        # variables we need for folsom
        ls_cfs_vars = ['CALSIM/C_NTOMA/CHANNEL', 'CALSIM/C_FOLSM/CHANNEL', 'CALSIM/I_FOLSM/INFLOW', 'FolSpill']
        ls_taf_vars = ['CALSIM/S_FOLSM/STORAGE']
        ls_cold_water_vars = ['<45 (Folsom)', '45-50 (Folsom)', '50-55 (Folsom)', '55-60 (Folsom)', '60-65 (Folsom)', '65-70 (Folsom)', '70+ (Folsom)']
        ls_temp_fields = ['AMERICAN/BLW NIMBUS(HAZEL AVE)/TEMP_F', 'AMERICAN/WILLIAM POND PARK/TEMP_F']

        # Convert I_SHSTA to CFS from TAF
        df_operations['CALSIM/I_FOLSM/INFLOW'] = df_operations['CALSIM/I_FOLSM/INFLOW'] / (df_operations['Date'].dt.day * (3600 * 24 / 43560 / 1000))

    # switch from variable name to description
    df_operations.rename(c_field_list, axis='columns', inplace=True)
    ls_cfs_vars = [c_field_list[var] for var in ls_cfs_vars]
    ls_taf_vars = [c_field_list[var] for var in ls_taf_vars]

    df_temperature.rename(c_field_list, axis='columns', inplace=True)
    ls_temp_fields = [c_field_list[var] for var in ls_temp_fields]

    if temp_unit_choice == 'C':
        df_temperature[ls_temp_fields] = (df_temperature[ls_temp_fields] - 32) * 5 / 9

    # these will hold the plots and dataframes
    o_final_plots = pn.FlexBox()
    o_final_temp_plots = pn.FlexBox()
    o_final_data = pn.FlexBox()

    for scenario in scenario_list:
        # create operations plot
        df_plot_ops = df_operations.loc[df_operations['Scenario'] == scenario][['Date'] + ls_taf_vars + ls_cfs_vars]
        df_plot_ops.reset_index(inplace=True, drop=True)
        df_plot_ops.loc[:, df_plot_ops.columns != 'Date'] = df_plot_ops.loc[:, df_plot_ops.columns != 'Date'].round(1)

        f_cfs_min = df_plot_ops[ls_cfs_vars].min().min()
        f_cfs_max = df_plot_ops[ls_cfs_vars].max().max() + 500
        o_plot_opps = hv.Bars(
            df_plot_ops, 'Date', (ls_taf_vars[0], 'TAF'), label=ls_taf_vars[0]
        ).opts(yaxis='left', color='#007396', line_color=None) * hv.Labels(
            df_plot_ops, ['Date', ls_taf_vars[0]], ls_taf_vars[0]
        ).opts(text_baseline='bottom', text_color='black', text_font_size='9pt')

        # Plot all the CFS variables
        o_plot_opps = o_plot_opps * hv.Curve(df_plot_ops, 'Date', (ls_cfs_vars[0], 'CFS'), label=ls_cfs_vars[0]).opts(yaxis='right', tools=['hover'], ylim=(f_cfs_min, f_cfs_max), color='#9A3324', line_dash='dashed')
        o_plot_opps = o_plot_opps * hv.Curve(df_plot_ops, 'Date', (ls_cfs_vars[1], 'CFS'), label=ls_cfs_vars[1]).opts(tools=['hover'], ylim=(f_cfs_min, f_cfs_max), yaxis=None, color='#003E51')
        o_plot_opps = o_plot_opps * hv.Curve(df_plot_ops, 'Date', (ls_cfs_vars[2], 'CFS'), label=ls_cfs_vars[2]).opts(tools=['hover'], ylim=(f_cfs_min, f_cfs_max), yaxis=None, color='#C69214')
        o_plot_opps = o_plot_opps * hv.Curve(df_plot_ops, 'Date', (ls_cfs_vars[3], 'CFS'), label=ls_cfs_vars[3]).opts(tools=['hover'], ylim=(f_cfs_min, f_cfs_max), yaxis=None, color='#FF671F')

        o_plot_opps = o_plot_opps.opts(title=scenario + ' Operations', multi_y=True, min_width=1200, min_height=600, tools=['hover'], legend_position='bottom', legend_cols=3, show_grid=True, xticks=o_operations_dates)

        # create the cold water plot
        df_plot_cold_water = df_cold_water.loc[df_cold_water['Scenario'] == scenario][['Date'] + ls_cold_water_vars]
        df_plot_cold_water.reset_index(inplace=True, drop=True)
        df_plot_cold_water[ls_cold_water_vars] = df_plot_cold_water[ls_cold_water_vars].round()

        o_plot_cold_water = df_plot_cold_water.hvplot.bar(x='Date', line_color=None, stacked=True, color=['#4C12A1', '#003E51', '#007396', '#215732', '#C69214', '#FF671F', '#9A3324'], grid=True).opts(
            title=scenario + ' Cold Water Profile', ylabel=s_reservoir+' Storage (TAF)', min_width=1200, min_height=600, legend_position='bottom', yformatter='%.0f', xticks=o_cold_water_dates[::2])

        o_final_plots.append(hv.Layout(o_plot_opps + o_plot_cold_water).opts(shared_axes=False).cols(1))
        o_final_data.append(pn.Column("## " + scenario, pn.pane.DataFrame(df_plot_ops, index=False, max_height=500),
                                      pn.pane.DataFrame(df_plot_cold_water, index=False, max_height=500),
                                      pn.pane.DataFrame(df_temperature[df_temperature['Scenario'] == scenario][['Date']+ls_temp_fields], index=False, max_height=500)))

    for temp_field in ls_temp_fields:
        df_plot_temp = df_temperature[['Date', 'Scenario', temp_field]]
        o_temp_plot = df_plot_temp.hvplot(x='Date',
                                          by='Scenario',
                                          ylabel='Degrees Celsius' if temp_unit_choice == 'C' else 'Degrees Fahrenheit',
                                          grid=True,
                                          title=temp_field).opts(min_width=1200, min_height=600, legend_position='bottom', shared_axes=False)
        o_final_temp_plots.append(o_temp_plot)

    return pn.Column(o_final_plots, o_final_temp_plots,o_final_data)


def get_spatial_group(field, s_module):
    """
    Returns the group a field belongs to for spatial plotting purposes.
    For hydro_out fields ending in _EXT or _INT get their own group (e.g. 'DP_EXT'),
    all other fields group under their first prefix segment (e.g. 'AWO', 'DP').

    Parameters
    ----------
    field: str
        Field name
    s_module: str
        Module name
    Returns
    -------
    str
        Spatial group name
    """
    if s_module == 'hydro_in':
        parts = field.split('_')
        if len(parts) == 1:
            return 'RefETO' #bare field looks like WBA02 from RefETO file
        return f'{parts[1]} ET' #returns AL ET for WBA02_AL_ET for example
    if s_module == 'hydro_out':
        if field.endswith(('_EXT', '_INT')):
            prefix = field.split('_')[0]
            suffix = field.split('_')[-1]
            return f'{prefix}_{suffix}'
        return field.split('_')[0]

def plot_spatial(scenario_list, unit_choice, df_all, df_diffs,
                 c_default_units_all, period_choice, s_comparison, spatial_var_choice, c_gdf,
                 c_field_list=None, li_wyt_selected=None, b_wyt_period_year=False, li_wyt_period_months=None, s_module=None):
    """
    Creates spatial plot of annual average values by Area, one tab per scenario

    Parameters
    ----------
    scenario_list: list
        Scenarios we want to plot
    unit_choice: str
        CFS/TAF. currently assumed to be stored in TAF natively
    df_all: DataFrame
        Data to be filtered and plotted
    df_diffs: DataFrame
        Data to be filtered and plotted (differences from comparison scenario)
    c_default_units_all: dict
        Unused - kept for interface consistency
    period_choice: object
        Time period selected
    s_comparison: str
        Name of comparison scenario
    spatial_var_choice: str
        Substring identifying which variable group to plot
    c_gdf: dict
       Dict mapping spatial prefix -> GeoDataFrame with 'ID' and 'geometry' columns
    c_field_list: dict, optional
        Dictionary of fields and descriptions - required to resolve the WYT column name
        when period_choice is a WYT/SHASTABIN field
    li_wyt_selected: list, optional
        Water year types selected for WYT time period
    b_wyt_period_year: bool, optional
        If water year totals have been selected for WYT time period
    li_wyt_period_months: list, optional
        Months selected for WYT time period

    Returns
    -------
    Panel Object
        Tabs (one per scenario), each containing an absolute map + diff map
    """
    c_field_list = c_field_list or {}
    li_wyt_selected = li_wyt_selected or []
    li_wyt_period_months = li_wyt_period_months or []

    # look up correct GeoDataFrame for the selected variable
    o_gdf = c_gdf.get(spatial_var_choice)
    if o_gdf is None:
        return pn.pane.Markdown(f"No shapefile available for '{spatial_var_choice}'")
    o_gdf = o_gdf.copy()

    #determine ID column name based on variable
    s_id_col = [s_col for s_col in o_gdf.columns if s_col != 'geometry'][0]

    ls_all_var = [s_col for s_col in df_all if s_col not in ['Date', 'Scenario', 'Year', 'Month', 'JanDecYear', 'OctSeptYear', 'MarFebYear']]
    ls_matched_var = [s_var for s_var in ls_all_var if get_spatial_group(s_var, s_module) == spatial_var_choice]

    if not ls_matched_var:
        return pn.pane.Markdown(f"No matching data fields found for '{spatial_var_choice}'")

    df_all_plot = df_all.copy(deep=True)
    df_all_plot.reset_index(inplace=True, drop=True)

    #compute conversion factor
    durations = [date.day for date in df_all_plot['Date']]
    taf_cfs = np.divide((43560 * 1000 / 24 / 3600), durations)
    agg_func = 'sum' if unit_choice == 'TAF' else 'mean'
    s_val_col = f'AnnualAverage ({unit_choice})'

    if unit_choice == 'CFS':
        df_all_plot[ls_matched_var] = df_all_plot[ls_matched_var].multiply(taf_cfs, axis=0)

    df_diffs_plot = df_diffs.copy(deep=True)
    df_diffs_plot.reset_index(inplace=True, drop=True)
    if unit_choice == 'CFS' and not df_diffs_plot.empty:
        durations_diff = [date.day for date in df_diffs_plot['Date']]
        taf_cfs_diff = np.divide((43560 * 1000 / 24 / 3600), durations_diff)
        df_diffs_plot[ls_matched_var] = df_diffs_plot[ls_matched_var].multiply(taf_cfs_diff, axis=0)

    # check if comparison scen is in the data frame
    # if it's not, then we are creating the differences plot and don't want to include comparison scen
    if s_comparison not in df_all_plot.Scenario.unique():
        scenario_list = [s_scen for s_scen in scenario_list if s_scen != s_comparison]

    if len(scenario_list) == 0:
        return

    # pick a scenario that actually has the spatial fields
    df_scen_has_data = (
        df_all_plot[df_all_plot['Scenario'].isin(scenario_list)]
        .groupby('Scenario')[ls_matched_var]
        .apply(lambda g: g.notna().any().any())
    )
    ls_valid_scens = [s_scen for s_scen in scenario_list if df_scen_has_data.get(s_scen, False)]
    if not ls_valid_scens:
        return pn.pane.Markdown("## No spatial data for the selected scenarios")

    # derive the merge ID from the variable name (strip the leading prefix segment)
    b_strip_suffix = spatial_var_choice.endswith(('_EXT', '_INT'))

    # if grouping by WYT, resolve the column name up front and merge it onto both df_all_plot and df_diffs
    b_is_wyt_period = isinstance(period_choice, str) and ('WYT' in period_choice or 'SHASTABIN_' in period_choice)
    s_wyt_col = None
    if b_is_wyt_period:
        if period_choice not in c_field_list:
            return pn.pane.Markdown("## No data to display")
        s_wyt_col = c_field_list[period_choice]
        if s_wyt_col not in df_all_plot.columns:
            return pn.pane.Markdown("## No data to display")

    #loop over every valid scenario
    scenario_tabs = pn.Tabs(tabs_location='left')

    for s_scen_to_use in ls_valid_scens:
        # absolute map for this scenario
        ls_cols = ['Date', 'OctSeptYear', 'JanDecYear', 'MarFebYear', 'Month'] + ls_matched_var
        if b_is_wyt_period:
            ls_cols = ls_cols + [s_wyt_col]
        df_wide = df_all_plot[df_all_plot.Scenario == s_scen_to_use][ls_cols]

        # filter df_wide according to period choice then reduce
        df_ann_avg = None

        #year type
        if period_choice in ['OctSeptYear', 'JanDecYear', 'MarFebYear']:
            df_ann_avg_ts = df_wide.groupby(period_choice)[ls_matched_var].agg(agg_func)
            if not df_ann_avg_ts.empty:
                df_ann_avg = pd.DataFrame(df_ann_avg_ts[ls_matched_var].mean()).reset_index()
                df_ann_avg.columns = ['Variable', s_val_col]

        # water year type / shastabin grouping
        elif b_is_wyt_period:
            if li_wyt_selected and s_wyt_col in df_wide.columns:
                df_wide_wyt = df_wide.dropna(subset=[s_wyt_col], how='all')
                df_wide_wyt = df_wide_wyt[df_wide_wyt[s_wyt_col].isin(li_wyt_selected)]

                if not df_wide_wyt.empty:
                    if b_wyt_period_year:
                        pass #use full water year, no filtering needed
                    else:
                        if len(li_wyt_period_months) > 0:
                            df_wide_wyt = df_wide_wyt[df_wide_wyt['Month'].isin(li_wyt_period_months)]
                        else:
                            df_wide_wyt = df_wide_wyt.iloc[0:0]
                if not df_wide_wyt.empty:
                    df_ann_avg_ts = df_wide_wyt.groupby('OctSeptYear')[ls_matched_var].agg(agg_func)
                    df_ann_avg = pd.DataFrame(df_ann_avg_ts[ls_matched_var].mean()).reset_index()
                    df_ann_avg.columns = ['Variable', s_val_col]

        # single month chosen
        elif isinstance(period_choice, int):
            df_wide_month = df_wide[df_wide.Month == period_choice]
            if not df_wide_month.empty:
                df_ann_avg_ts = df_wide_month.groupby('JanDecYear')[ls_matched_var].agg(agg_func)
                df_ann_avg = pd.DataFrame(df_ann_avg_ts[ls_matched_var].mean()).reset_index()
                df_ann_avg.columns = ['Variable', s_val_col]

        # partial year / month range chosen (e.g. '10-4')
        else:
            i_start_month, i_end_month = int(period_choice.split('-')[0]), int(period_choice.split('-')[1])
            if i_end_month > i_start_month:
                li_months = list(range(i_start_month, i_end_month + 1))
            else:
                li_months = list(range(i_start_month, 13)) + list(range(1, i_end_month + 1))

            df_wide_range = df_wide[df_wide['Month'].isin(li_months)]
            if not df_wide_range.empty:
                # if we cross a cal year change, group by WY, same as plot_time_group/plot_bars
                if period_choice in ['11-3', '10-1', '12-2', '10-4']:
                    df_ann_avg_ts = df_wide_range.groupby('OctSeptYear')[ls_matched_var].agg(agg_func)
                else:
                    df_ann_avg_ts = df_wide_range.groupby('JanDecYear')[ls_matched_var].agg(agg_func)

                df_ann_avg = pd.DataFrame(df_ann_avg_ts[ls_matched_var].mean()).reset_index()
                df_ann_avg.columns = ['Variable', s_val_col]

        if df_ann_avg is None:
            abs_panel = pn.Column(
                pn.pane.Markdown(f"### {s_scen_to_use}"),
                pn.pane.Markdown("## No data to display", height=400)
            )
        else:
            if s_module == 'hydro_in':
                df_ann_avg[s_id_col] = [
                    re.match(r'^WBA(\d+[A-Z]?)$', s_var.split('_')[0]).group(1) for s_var in df_ann_avg.Variable
                ]
            else:
                df_ann_avg[s_id_col] = ['_'.join(s_var.split("_")[1:]) for s_var in df_ann_avg.Variable]
                if b_strip_suffix:
                    df_ann_avg[s_id_col] = df_ann_avg[s_id_col].str.rsplit('_', n=1).str[0]

            o_gdf_abs = o_gdf.merge(df_ann_avg, left_on=s_id_col, right_on=s_id_col, how='inner')
            o_gdf_plot = o_gdf_abs[['geometry', s_val_col]]
            o_gdf_plot = o_gdf_plot.dropna(subset=['geometry'])

            abs_panel = pn.Column(
                pn.pane.Markdown(f"### {s_scen_to_use}"),
                pn.pane.HoloViews(o_gdf_plot.hvplot(c=s_val_col, geo=True, frame_height=800), center=True),
                pn.pane.DataFrame(df_ann_avg, max_height=700)
            )

        # diff map for this scenario
        if s_scen_to_use == s_comparison:
            diff_panel = pn.Column(
                pn.pane.Markdown(f"### {s_scen_to_use} (Difference from {s_comparison})"),
                pn.pane.Markdown("*This is the comparison scenario — no difference to display.*",
                                 height=800)
            )
        else:
            # same merge logic as the absolute map above, run against df_diffs instead of df_all_plot
            ls_diff_cols = ['Date', 'OctSeptYear', 'JanDecYear', 'MarFebYear', 'Month'] + ls_matched_var
            if b_is_wyt_period:
                # df_diffs doesn't carry the WYT column, so pull it in from df_all_plot by OctSeptYear
                df_wyt_lookup = df_all_plot[df_all_plot.Scenario == s_scen_to_use][
                    ['OctSeptYear', s_wyt_col]].drop_duplicates()
                df_wide_diff = df_diffs_plot[df_diffs_plot.Scenario == s_scen_to_use][ls_diff_cols]
                df_wide_diff = df_wide_diff.merge(df_wyt_lookup, on='OctSeptYear', how='left')
            else:
                df_wide_diff = df_diffs_plot[df_diffs_plot.Scenario == s_scen_to_use][ls_diff_cols]

            if df_wide_diff.empty or df_wide_diff[ls_matched_var].isna().all().all():
                # NEW: guard for scenarios with no diff data - original didn't need this
                # since it was only ever called with a scenario known to have data
                diff_panel = pn.Column(
                    pn.pane.Markdown(f"### {s_scen_to_use} (Difference from {s_comparison})"),
                    pn.pane.Markdown("## No data to display", height=800)
                )
            else:
                # same period_choice filtering/reduction as the absolute map, run against df_wide_diff instead of df_wide
                df_ann_avg_diff = None

                if period_choice in ['OctSeptYear', 'JanDecYear', 'MarFebYear']:
                    df_ann_avg_ts_diff = df_wide_diff.groupby(period_choice)[ls_matched_var].agg(agg_func)
                    if not df_ann_avg_ts_diff.empty:
                        df_ann_avg_diff = pd.DataFrame(df_ann_avg_ts_diff[ls_matched_var].mean()).reset_index()
                        df_ann_avg_diff.columns = ['Variable', s_val_col]

                elif b_is_wyt_period:
                    if li_wyt_selected and s_wyt_col in df_wide_diff.columns:
                        df_wide_diff_wyt = df_wide_diff.dropna(subset=[s_wyt_col], how='all')
                        df_wide_diff_wyt = df_wide_diff_wyt[df_wide_diff_wyt[s_wyt_col].isin(li_wyt_selected)]

                        if not df_wide_diff_wyt.empty:
                            if not b_wyt_period_year:
                                if len(li_wyt_period_months) > 0:
                                    df_wide_diff_wyt = df_wide_diff_wyt[
                                        df_wide_diff_wyt['Month'].isin(li_wyt_period_months)]
                                else:
                                    df_wide_diff_wyt = df_wide_diff_wyt.iloc[0:0]

                        if not df_wide_diff_wyt.empty:
                            df_ann_avg_ts_diff = df_wide_diff_wyt.groupby('OctSeptYear')[ls_matched_var].agg(agg_func)
                            df_ann_avg_diff = pd.DataFrame(df_ann_avg_ts_diff[ls_matched_var].mean()).reset_index()
                            df_ann_avg_diff.columns = ['Variable', s_val_col]

                elif isinstance(period_choice, int):
                    df_wide_diff_month = df_wide_diff[df_wide_diff.Month == period_choice]
                    if not df_wide_diff_month.empty:
                        df_ann_avg_ts_diff = df_wide_diff_month.groupby('JanDecYear')[ls_matched_var].agg(agg_func)
                        df_ann_avg_diff = pd.DataFrame(df_ann_avg_ts_diff[ls_matched_var].mean()).reset_index()
                        df_ann_avg_diff.columns = ['Variable', s_val_col]

                else:
                    i_start_month, i_end_month = int(period_choice.split('-')[0]), int(period_choice.split('-')[1])
                    if i_end_month > i_start_month:
                        li_months = list(range(i_start_month, i_end_month + 1))
                    else:
                        li_months = list(range(i_start_month, 13)) + list(range(1, i_end_month + 1))

                    df_wide_diff_range = df_wide_diff[df_wide_diff['Month'].isin(li_months)]
                    if not df_wide_diff_range.empty:
                        if period_choice in ['11-3', '10-1', '12-2', '10-4']:
                            df_ann_avg_ts_diff = df_wide_diff_range.groupby('OctSeptYear')[ls_matched_var].agg(agg_func)
                        else:
                            df_ann_avg_ts_diff = df_wide_diff_range.groupby('JanDecYear')[ls_matched_var].agg(agg_func)

                        df_ann_avg_diff = pd.DataFrame(df_ann_avg_ts_diff[ls_matched_var].mean()).reset_index()
                        df_ann_avg_diff.columns = ['Variable', s_val_col]

                if df_ann_avg_diff is None:
                    diff_panel = pn.Column(
                        pn.pane.Markdown(f"### {s_scen_to_use} (Difference from {s_comparison})"),
                        pn.pane.Markdown("## No data to display", height=800)
                    )
                else:
                    if s_module == 'hydro_in':
                        #capture wba number
                        df_ann_avg_diff[s_id_col] = [
                            re.match(r'^WBA(\d+[A-Z]?)$', s_var.split('_')[0]).group(1) for s_var in
                            df_ann_avg_diff.Variable
                        ]
                    else:
                        df_ann_avg_diff[s_id_col] = ['_'.join(s_var.split("_")[1:]) for s_var in
                                                     df_ann_avg_diff.Variable]
                        if b_strip_suffix:
                            df_ann_avg_diff[s_id_col] = df_ann_avg_diff[s_id_col].str.rsplit('_', n=1).str[0]

                    o_gdf_diff = o_gdf.merge(df_ann_avg_diff, left_on=s_id_col, right_on=s_id_col, how='inner')
                    o_gdf_plot_diff = o_gdf_diff[['geometry', s_val_col]]
                    o_gdf_plot_diff = o_gdf_plot_diff.dropna(subset=['geometry'])

                    diff_panel = pn.Column(
                        pn.pane.Markdown(f"### {s_scen_to_use} (Difference from {s_comparison})"),
                        pn.pane.HoloViews(o_gdf_plot_diff.hvplot(
                            c=s_val_col, geo=True, frame_height=800), center=True),
                        pn.pane.DataFrame(df_ann_avg_diff, max_height=700)
                    )

        scenario_tabs.append((s_scen_to_use, pn.Row(abs_panel, diff_panel)))

    return pn.Column(pn.pane.Markdown("### Scenarios"), scenario_tabs)