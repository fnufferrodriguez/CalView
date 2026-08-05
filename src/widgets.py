import warnings

import panel as pn
import os
import pandas as pd
from src.cs3_plotlib import *
from functools import partial
from src.csdss_readlib_fullfile import *
import geopandas as gpd


## Functions that should work for any version of the visualizer
def create_plot_title(s_title, s_comparison='', s_period='', s_stat=''):
    """
    To create the titles for the plots that change when values are updated

    Parameters
    ----------
    s_title: str
        Plot title
    s_comparison: str
        Comparison scenario, if a difference plots
    s_stat: str
        Statistic, if applicaple

    Returns
    -------
        Title markdown pane
    """
    c_period_code_to_name = {"JanDecYear": "January-December", "OctSeptYear": "October-September", "MarFebYear": "March-February",
                             1: "January", 2: "February", 3: "March", 4: "April",
                             5: "May", 6: "June", 7: "July", 8: "August",
                             9: "September", 10: "October", 11: "November", 12: "December",
                             '11-3': 'November-March', '8-10': 'August-October', '10-1': 'October-January',
                             '12-2': 'December-February', '3-5': 'March-May', '3-6': 'March-June',
                             '6-9': 'June-September', '9-11': 'September-November', '10-4': 'October-April'
                             }
    s_final_title = "# "
    if s_stat:
        s_final_title += s_stat + ' Value ' + s_title
    else:
        s_final_title += s_title
    if s_comparison:
        s_final_title += " (Difference from " + s_comparison + ")"
    if s_period:
        if s_period in c_period_code_to_name.keys():
            s_final_title += " (" + c_period_code_to_name[s_period] + ")"
        # this is when we are grouping by wyt
        else:
            s_final_title += " (Water Year Type)"
    return pn.pane.Markdown(s_final_title)


def update_wyt_names(target, event):
    """
    Get the names for the water year types

    Parameters
    ----------
    target: obj
        water year type selector widget
    event: obj
        Period selector widget

    Returns
    -------
        none
    """
    if event.new != event.old:
        if isinstance(event.new, str) and ('WYT' in event.new or 'SHASTABIN_' in event.new):

            # Dictionary with all the names for each number code for each WYT field
            c_wyt_names = {
                'WYT_SAC_': {'Wet': 1, 'Above Normal': 2, 'Below Normal': 3, 'Dry': 4, 'Critically Dry': 5},
                'WYT_SJR_': {'Wet': 1, 'Above Normal': 2, 'Below Normal': 3, 'Dry': 4, 'Critically Dry': 5},
                'WYT_TRIN_': {'Extremely Wet': 1, 'Wet': 2, 'Normal': 3, 'Dry': 4, 'Critically Dry': 5},
                'WYT_SHASTA_CVP_': {'Non-Critical': 0, 'ShastaCritical': 1},
                'WYT_FEATHER_': {'Non-Critical': 1, 'Critically Dry': 2},
                'WYT_SJRRP_DV': {'Wet': 1, 'Normal-Wet': 2, 'Normal-Dry': 3, 'Dry': 4, 'Critical High': 5, 'Critical Low': 6},
                'WYT_AMERD983_CVP_': {'Non-Critical': 1, 'Critically Dry': 2},
                'SHASTABIN_': {'1a': 1, '1b': 2, '2a': 3, '2b': 4, '3a': 5, '3b': 6},
                'Default': [1, 2, 3, 4, 5]
            }
            try:
                if '/' in event.new:
                    wyt = event.new.split('/')[1]
                else:
                    wyt = event.new
                target.options = c_wyt_names[wyt]
                target.value = list(c_wyt_names[wyt].values())
            except:
                target.options = c_wyt_names['Default']
                target.value = c_wyt_names['Default']
    return
def module_selector(c_flag):
    """
    Widget that allows user selection for module type (ex. calsim hydro inputs and outputs)

    Parameters
    ----------
    c_flag: dict
        Dictionary of module options (keys are module names, values are booleans)

    Returns
    -------
    mod_selector: object
        widget
    """
    # Select the variables
    mod_selector = pn.widgets.MultiChoice(
        name='Module Selector',
        options=list(c_flag.keys()),
        value=[k for k, v in c_flag.items() if v],
        option_limit=len(list(c_flag.keys())),
        search_option_limit=len(list(c_flag.keys())),
        width=400
    )

    mod_selector.param.watch(partial(update_c_flag, c_flag=c_flag), 'value')

    return mod_selector

def update_c_flag(event, c_flag):
    """
    Updates c_flag dict in place based on module selector's current selections

    Parameters
    ----------
    event: obj
        Event from the module selector widget
    c_flag: dict
        Dictionary of module options to update

    Returns
    -------
        none
    """
    for key in c_flag:
        c_flag[key] = key in event.new

def wyt_period_toggle(target, event):
    """
    Disables the month selector if full year button is selected

    Parameters
    ----------
    target: obj
        Month selector widget
    event: obj
        Full year button

    Returns
    -------
        none
    """
    # disable months if the button is toggled
    target.disabled = event.new


def update_dss_file_widget(event, s_module, file_picker_column, file_picker_col_tracker):
    """
    Switches between DSS selector and pickle file selector

    Parameters
    ----------
    event: obj
        Toggle for new runs or old runs widget
    s_module: str
        Which module this picker belongs to (e.g. 'calsim', 'hydro_out')
    file_picker_column: obj
        Column holding file picker
    file_picker_col_tracker: list
        Tracker for what is in the column

    Returns
    -------
        none
    """
    # global file_picker_column  # Access the global variable
    # global file_picker_col_tracker
    if event.name == "value":
        file_picker_column.pop(file_picker_col_tracker.index("dss_file"))  # Remove the dss_file widget
        file_picker_col_tracker.remove("dss_file")
        file_picker_column.pop(file_picker_col_tracker.index("instructions"))
        file_picker_col_tracker.remove("instructions")

        # Add back dss_file widget with updated file pattern
        if event.new == "New outputs":
            # new calsim
            if s_module == 'calsim':
                o_instructions = pn.pane.Markdown("### Select the DSS files to be read in.")
                o_instructions_tooltip = pn.widgets.TooltipIcon(value="Move all DSS files from 'File Browser' section to 'Selected files' section then click 'Continue'")
                dss_file = pn.widgets.FileSelector(
                    name='Select CalSim output DSS file for new run or pickle file for previous run',
                    file_pattern="*.dss",
                    only_files=True,
                    max_width=1000,
                    root_directory=os.path.abspath(os.sep)
                )
            # new temperature
            elif s_module in ('temperature', 'salinity', 'hydro_in'):
                o_instructions = pn.pane.Markdown("### Select the folders to be read in.")
                o_instructions_tooltip = pn.widgets.TooltipIcon(value="Move all folders from 'File Browser' section to 'Selected files' section then click 'Continue'")
                dss_file = pn.widgets.FileSelector(
                    name='',
                    only_files=False,
                    max_width=1000,
                    root_directory=os.path.abspath(os.sep)
                )
            #new hydro
            elif s_module == 'hydro_out':
                o_instructions = pn.pane.Markdown("### Select the DSS files to be read in.")
                o_instructions_tooltip = pn.widgets.TooltipIcon(value="Move all DSS files from 'File Browser' section to 'Selected files' section then click 'Continue'")
                dss_file = pn.widgets.FileSelector(
                    name='Select CalSim Hydro output DSS file for new run or pickle file for previous run',
                    file_pattern="*.dss",
                    only_files=True,
                    max_width=1000,
                    root_directory=os.path.abspath(os.sep)
                )
        # Pickle files
        else:
            o_instructions = pn.pane.Markdown('### <span style="color:red">Select the pickle files previously created (diffs.pkl, units.pkl, values.pkl, and fields.pkl)</span>')
            o_instructions_tooltip = pn.widgets.TooltipIcon(value="Move the four pkl files from 'File Browser' section to 'Selected files' section then click 'Continue'")
            dss_file = pn.widgets.FileSelector(
                name='Select CalSim output DSS file for new run or pickle file for previous run',
                file_pattern="*.pkl",
                only_files=True,
                max_width=1000,
                root_directory=os.path.abspath(os.sep)
            )

        # replace widget and instructions
        file_picker_column.insert(2, pn.Row(o_instructions, o_instructions_tooltip))
        file_picker_col_tracker.insert(2, "instructions")
        file_picker_column.insert(3, dss_file)
        file_picker_col_tracker.insert(3, "dss_file")

    file_picker_column.param.trigger("objects")  # Trigger UI update


def hide_show_wyt(event, header):
    """
    Hides or shows the water year type selector

    Parameters
    ----------
    event: obj
        Period selector widget
    header: obj
        Row holding the water year type widgets

    Returns
    -------
        none
    """
    # make sure that the header has been populated
    if len(header) > 2:
        # check if a WYT is selected
        if isinstance(event.new, str) and ('WYT' in event.new or 'SHASTABIN_' in event.new):
            # turn on the visibility
            header[2][1].visible = True
        else:
            # turn it off
            header[2][1].visible = False
    return


def create_widgets(scenario_names, c_field_list):
    """
    Creates the widgets

    Parameters
    ----------
    scenario_names: list
        List of scenario names
    c_field_list: dict
        Dictionary of fields and names

    Returns
    -------
    scen_selector: obj
        Scenario selection widget
    unit_selector: obj
        Unit toggle widget
    period_selector: obj
        Time period selecting widget
    wyt_selector: obj
        Water year type selector widget
    wyt_period_selector: obj
        Water year type month selector widget
    wyt_period_selector_year: obj
        Water year type full year button widget
    var_selector: obj
        Field selector widget
    bar_stat_sel: obj
        Statistic selector for bar plots widget
    monthly_stat_sel: obj
        Statistic selector for monthly plots widget
    exceedance_show_year_check: obj
        Checkbox for showing year in exceedence table
    exceedance_show_year_check_diffs: obj
        Checkbox for showing year in differences exceedence table
    """

    # Select which alts to examine
    scen_selector = pn.widgets.MultiChoice(
        name='Scenario Selector',
        options=scenario_names,
        value=scenario_names,
        option_limit=len(scenario_names),
        search_option_limit=len(scenario_names),
        width=400
    )

    # Toggle for units
    unit_selector = pn.widgets.RadioButtonGroup(
        name='Units selector',
        options=['TAF', 'CFS'],
        button_style='outline',
        button_type='primary',
        width=200,
        margin=32
    )

    # Selector for time period
    period_selector = pn.widgets.Select(
        name='Period Selector',
        groups={'Year': {"January-December": "JanDecYear", "October-September": "OctSeptYear", "March-February": "MarFebYear"},
                'Month': {"January": 1, "February": 2, "March": 3, "April": 4,
                          "May": 5, "June": 6, "July": 7, "August": 8,
                          "September": 9, "October": 10, "November": 11, "December": 12},
                "Partial Year": {'March-May': '3-5', 'March-June': '3-6', 'June-September': '6-9',
                                 'August-October': '8-10', 'September-November': '9-11', 'October-January': '10-1',
                                 'October-April': '10-4', 'November-March': '11-3', 'December-February': '12-2'},
                'Water Year Type': {description: wyt for wyt, description in c_field_list.items() if 'WYT' in wyt},
                '': {description: var for var, description in c_field_list.items() if 'SHASTABIN_' in var}
                },
        width=300
    )

    # Selector for water year types
    wyt_selector = pn.widgets.CheckButtonGroup(
        name='Water Year Type',
        options={'Wet': 1, 'Above Normal': 2, 'Below Normal': 3, 'Dry': 4, 'Critically Dry': 5},
        button_type='primary',
        button_style='outline'
    )

    # Month selector for WYT periods
    wyt_period_selector = pn.widgets.CheckButtonGroup(
        name='WYT Period Selector',
        options={"January": 1, "February": 2, "March": 3, "April": 4,
                 "May": 5, "June": 6, "July": 7, "August": 8,
                 "September": 9, "October": 10, "November": 11, "December": 12
                 },
        button_type='primary',
        button_style='outline'
    )

    # Water year total toggle
    wyt_period_selector_year = pn.widgets.Toggle(
        name='Water Year Total',
        button_type='primary',
        button_style='outline')

    # to update the names when the period is changed
    wyt_names_linked = period_selector.link(wyt_selector, callbacks={'value': update_wyt_names})

    # toggle to turn off the months when wy total is selected
    wyt_period_linked = wyt_period_selector_year.link(wyt_period_selector, callbacks={'value': wyt_period_toggle})

    # Trigger update
    period_selector.param.trigger('value')

    # for the field names we need a diction of {description: field}
    c_description_to_field = {description: field for field, description in c_field_list.items()}

    # Select the variables todo move into the tabs
    var_selector = pn.widgets.MultiChoice(
        name='Variable Selector',
        options=c_description_to_field,
        value=[list(c_description_to_field.values())[0]],
        option_limit=len(list(c_description_to_field.keys())),
        search_option_limit=len(list(c_description_to_field.keys())),
        width=400
    )

    # Stat selector for bar plots
    bar_stat_sel = pn.widgets.Select(
        name='Statistic Selector',
        options=['Average', 'Minimum', 'Maximum',
                 '90% Exceedence Probability', '75% Exceedence Probability', '50% Exceedence Probability',
                 '25% Exceedence Probability', '10% Exceedence Probability'],
        width=400
    )

    # Stat selector for monthly plots
    monthly_stat_sel = pn.widgets.Select(
        name='Statistic Selector',
        options=['Average', 'Minimum', 'Maximum',
                 '90% Exceedence Probability', '75% Exceedence Probability', '50% Exceedence Probability',
                 '25% Exceedence Probability', '10% Exceedence Probability'],
        width=400
    )

    # Create checkbox widget to specify CalSimHydro Files w/  Spatial Data
    wba_spatial_sel = pn.widgets.Checkbox(
        name='Create Spatial Plot (only select if data has WBA specific values, i.e. CalSimHydro Files)'
    )

    # Check boxed for showing years in exceedance tables
    exceedance_show_year_check = pn.widgets.Checkbox(name='Show year in table')
    exceedance_show_year_check_diffs = pn.widgets.Checkbox(name='Show year in table')

    # Return all these widgets
    return scen_selector, unit_selector, period_selector, wyt_selector, wyt_period_selector, wyt_period_selector_year, var_selector, bar_stat_sel, monthly_stat_sel, exceedance_show_year_check, exceedance_show_year_check_diffs, wba_spatial_sel


def create_metadata(scenario_names, c_field_list, c_default_units, s_module):
    """
    Create the metadata section

    Parameters
    ----------
    scenario_names: list
        List of scenarios
    c_field_list: dict
        Dictionary of fields and names
    c_default_units: dict
        Dictionary of default units
    s_module: str
        Flag for module from c_flag

    Returns
    -------
    o_metadata: obj
        Panel object holding all the metadata
    """
    if s_module == 'calsim':
        # File names for each run
        run_names = {scen: c_default_units[scen] for scen in scenario_names}
        df_run_names = pd.DataFrame.from_dict(run_names, orient='index', columns=['File Name'])
        df_run_names.index.name = 'Scenario Name'
    elif s_module=='temperature':
        # dictionary of files for each run
        run_names = {scen: c_default_units[scen] for scen in scenario_names}
        df_run_names = pd.DataFrame.from_dict(run_names, orient='index')
        df_run_names.index.name = 'Scenario Name'
        df_run_names.rename(columns={'calsim_DV': 'CalSim DV File','calsim_SV': 'CalSim SV File', 'AR_WQ_Report': 'American River Output',
                                     'a_CALSIMII_HEC5Q': 'American River Input', 'SR_WQ_Report': 'Sacramento River Output', 's_CALSIMII_HEC5Q': 'Sacramento River Input'}, inplace=True)
    elif s_module=='salinity':
        # dictionary of files for each run
        run_names = {scen: c_default_units[scen] for scen in scenario_names}
        df_run_names = pd.DataFrame.from_dict(run_names, orient='index')
        df_run_names.index.name = 'Scenario Name'
        df_run_names.rename(columns={'flow': 'Flow File', 'ec': 'EC File'}, inplace=True)

    elif s_module=='hydro_out':
        # dictionary of files for each run
        run_names = {scen: c_default_units[scen] for scen in scenario_names}
        df_run_names = pd.DataFrame.from_dict(run_names, orient='index')
        df_run_names.index.name = 'Scenario Name'
    # Title for file names
    o_scen_names_title = pn.pane.Markdown("# Files and names")

    # Field names and field descriptions
    df_field_names = pd.DataFrame.from_dict(c_field_list, orient='index', columns=['Description'])
    df_field_names.index.name = 'Field'

    # Add in units for each field
    df_field_names['Default Units'] = df_field_names.index.map(c_default_units)

    # Title for fields and descriptions
    o_field_names_title = pn.pane.Markdown("# Fields and descriptions")

    # Dictionary with formulas for calculated fields TODO specify which of these are for which calview
    c_calcs_for_calculated = {
        'Total System Storage SWP and CVP': 'S_TRNTY + S_SHSTA + S_OROVL + S_FOLSM + S_SLUIS_CVP + S_SLUIS_SWP',
        'Total Exports SWP and CVP': 'C_CAA003_SWP + C_DMC003 + C_CAA003_CVP',
        'Total San Luis Storage SWP and CVP': 'S_SLUIS_CVP + S_SLUIS_SWP',
        'Flow Shortage on Sac Reg for Salinity': 'MAX(MAX(RSREQSACDV, JPREQSACDV, EMREQSACDV, COREQSACDV) - (C_SAC041 + SP_SAC083_YBP037), 0)',
        'Flow Shortage on X2 Delta Req Outflow': 'MAX(MRDO_FINALDV - NDOI, 0)',
        'MRDO_SHORT': 'MRDO_FINALDV - NDOI_MIN',
        'Combined Madera and Friant-Kern Canals Diversion': 'D_MLRTN_FRK000 + D_MLRTN_MDC006',
        'Stanislaus River Delivery - Oakdale North / SSJID 1+2': 'D_STS059_OAK001 + D_SSJ004_61_PA1 + D_WDWRD_61_PA3 + D_WTPDGT_61_NU2',
        'CVP Delivery Total': 'DEL_CVP_TOTAL_N + DEL_CVP_TOTAL_S',
        'CVP Delivery PMI N (w CCWD)': 'DEL_CVP_PMI_N + D420',
        'CVP Delivery North (w CCWD)': 'DEL_CVP_TOTAL_N - DEL_CVP_PMI_N + DEL_CVP_PMI_N_WAMR + D420',
        'ShaSpill': 'np.where(TrueSpill > 0, SacExc * TrueSpill / (SacExc + AmerExc)), 0)',
        'FolSpill': 'np.where(TrueSpill > 0, AmerExc * TrueSpill / (SacExc + AmerExc)), 0)',
        'CVPSpill': 'SpaSpill + FolSpill',
        '<45 (Shasta)': 'Storage.lt.45.00F (Sacramento River)',
        '45-50 (Shasta)': 'Storage.lt.50.00F (Sacramento River) - Storage.lt.45.00F (Sacramento River)',
        '50-55 (Shasta)': 'Storage.lt.55.00F (Sacramento River) - Storage.lt.50.00F (Sacramento River)',
        '55-60 (Shasta)': 'Storage.lt.60.00F (Sacramento River) - Storage.lt.55.00F (Sacramento River)',
        '60-65 (Shasta)': 'Storage.lt.65.00F (Sacramento River) - Storage.lt.60.00F (Sacramento River)',
        '65-70 (Shasta)': 'Storage.lt.70.00F (Sacramento River) - Storage.lt.65.00F (Sacramento River)',
        '70+ (Shasta)': 'Storage.lt.99.00F (Sacramento River) - Storage.lt.70.00F (Sacramento River)',
        '<45 (Folsom)': 'Storage.lt.45.00F (American River)',
        '45-50 (Folsom)': 'Storage.lt.50.00F (American River) - Storage.lt.45.00F (American River)',
        '50-55 (Folsom)': 'Storage.lt.55.00F (American River) - Storage.lt.50.00F (American River)',
        '55-60 (Folsom)': 'Storage.lt.60.00F (American River) - Storage.lt.55.00F (American River)',
        '60-65 (Folsom)': 'Storage.lt.65.00F (American River) - Storage.lt.60.00F (American River)',
        '65-70 (Folsom)': 'Storage.lt.70.00F (American River) - Storage.lt.65.00F (American River)',
        '70+ (Folsom)': 'Storage.lt.99.00F (American River) - Storage.lt.70.00F (American River)',
        'SWP/CVP South Delta Pumping Flow (Total Export)': 'HYDROV8.2.2/CLIFTON_COURT/FLOW-MEAN - HYDROV8.2.2/CHDMC006/FLOW-MEAN',
        'Combined Old and Middle River (OMR) Flow': 'HYDROV8.2.2/RMID015_144/FLOW-MEAN - HYDROV8.2.2/RMID015_145/FLOW-MEAN + HYDROV8.2.2/ROLD024/FLOW-MEAN',
        'Old River at Rock Slough Chloride': 'MAX(0.285 * QUALV8.2.2/ROLD024/EC-MEAN - 50, 0.15 * QUALV8.2.2/ROLD024/EC-MEAN - 12)'
    }

    # Calculated field formulas
    c_used_calc_fields = {field: c_calcs_for_calculated[field] for field in c_calcs_for_calculated if field in c_field_list.keys()}
    df_calc_fields = pd.DataFrame.from_dict(c_used_calc_fields, orient='index', columns=['Formula'])
    df_calc_fields.index.name = 'Calculated Field'

    # Title for calculated fields section
    o_calc_field_title = pn.pane.Markdown("# Calculated Fields")

    # Arrange the data
    o_metadata = pn.Column(
        o_scen_names_title,
        pn.pane.DataFrame(df_run_names),
        pn.Row(
            pn.Column(
                o_field_names_title,
                pn.pane.DataFrame(df_field_names)
            ),
            pn.Column(
                o_calc_field_title,
                pn.pane.DataFrame(df_calc_fields)
            )
        )
    )

    return o_metadata


def create_plots(scenario_names, c_field_list, df_all_data, c_default_units, df_diffs, s_comparison,
                 header, tabs_row, s_module):
    """
    Creates plot objects and lays them out

    Parameters
    ----------
    scenario_names: list
        List of possible scenarios to select from
    c_field_list: dict
        Dictionary of field name and descriptions
    df_all_data: DataFrame
        DataFrame with all of the data that can be plotted
    c_default_units: dict
        Diction of default units for all fields
    df_diffs: DataFrame
        Dataframe of difference from comparison scenario data
    s_comparison: str
        Name of comparison scenario
    header: object
        Panel Row for widget to go in
    tabs_row: object
        Panel Row for tabs to go in
    s_module: str
        Module from c_flag

    Returns
    -------
        none
    """

    # Create the widgets
    (scen_selector, unit_selector, period_selector, wyt_selector, wyt_period_selector, wyt_period_selector_year,
     var_selector, bar_stat_sel, monthly_stat_sel, exceedance_show_year_check, exceedance_show_year_check_diffs, wba_spatial_sel) = create_widgets(scenario_names, c_field_list)
    #spatial plotting is always on for hydro (intentially not using wba_spatial_sel
    # to update the visibility when period is changed
    wyt_watcher = period_selector.param.watch(partial(hide_show_wyt, header=header), 'value')

    # remove comparison scen from the differences dataframe as all values are zero
    df_diffs = df_diffs[df_diffs.Scenario != s_comparison]


    # Create other plots

    # Timeseries plot
    bound_plot_ts = pn.bind(
        plot_values,
        scenario_list=scen_selector,
        var_list=var_selector,
        unit_choice=unit_selector,
        df_all=df_all_data,
        c_default_units=c_default_units,
        s_comparison=s_comparison,
        c_field_list=c_field_list
    )

    # Differences timeseries plot
    bound_plot_diffs_ts = pn.bind(
        plot_values,
        scenario_list=scen_selector,
        var_list=var_selector,
        unit_choice=unit_selector,
        df_all=df_diffs,
        c_default_units=c_default_units,
        s_comparison=s_comparison,
        c_field_list=c_field_list
    )

    # Time aggregated plot
    bound_plot_grouped = pn.bind(
        plot_time_group,
        scenario_list=scen_selector,
        var_list=var_selector,
        unit_choice=unit_selector,
        df_all=df_all_data,
        c_default_units=c_default_units,
        period_choice=period_selector,
        s_comparison=s_comparison,
        c_field_list=c_field_list,
        li_wyt_selected=wyt_selector,
        b_wyt_period_year=wyt_period_selector_year,
        li_wyt_period_months=wyt_period_selector
    )

    # Time aggregated differences plot
    bound_plot_grouped_diff = pn.bind(
        plot_time_group,
        scenario_list=scen_selector,
        var_list=var_selector,
        unit_choice=unit_selector,
        df_all=df_diffs,
        c_default_units=c_default_units,
        period_choice=period_selector,
        s_comparison=s_comparison,
        c_field_list=c_field_list,
        li_wyt_selected=wyt_selector,
        b_wyt_period_year=wyt_period_selector_year,
        li_wyt_period_months=wyt_period_selector
    )

    # Exceedance plot
    bound_plot_exceedance = pn.bind(
        plot_time_exceedance,
        scenario_list=scen_selector,
        var_list=var_selector,
        unit_choice=unit_selector,
        df_all=df_all_data,
        c_default_units=c_default_units,
        period_choice=period_selector,
        s_comparison=s_comparison,
        c_field_list=c_field_list,
        li_wyt_selected=wyt_selector,
        b_wyt_period_year=wyt_period_selector_year,
        li_wyt_period_months=wyt_period_selector,
        b_show_year=exceedance_show_year_check,
        s_module = s_module
    )

    # Exceedance differences plot
    bound_plot_diffs_exceedance = pn.bind(
        plot_time_exceedance,
        scenario_list=scen_selector,
        var_list=var_selector,
        unit_choice=unit_selector,
        df_all=df_diffs,
        c_default_units=c_default_units,
        period_choice=period_selector,
        s_comparison=s_comparison,
        c_field_list=c_field_list,
        li_wyt_selected=wyt_selector,
        b_wyt_period_year=wyt_period_selector_year,
        li_wyt_period_months=wyt_period_selector,
        b_show_year=exceedance_show_year_check_diffs,
        s_module = s_module
    )

    # Bar plot
    bound_single_var_plot = pn.bind(
        plot_bars,
        df_all=df_all_data,
        period_choice=period_selector,
        var_list=var_selector,
        scenario_list=scen_selector,
        unit_choice=unit_selector,
        stat_choice=bar_stat_sel,
        c_default_units=c_default_units,
        s_comparison=s_comparison,
        c_field_list=c_field_list,
        li_wyt_selected=wyt_selector,
        b_wyt_period_year=wyt_period_selector_year,
        li_wyt_period_months=wyt_period_selector
    )

    # Difference bar plot
    bound_single_var_diff_plot = pn.bind(
        plot_bars,
        df_all=df_diffs,
        period_choice=period_selector,
        var_list=var_selector,
        scenario_list=scen_selector,
        unit_choice=unit_selector,
        stat_choice=bar_stat_sel,
        c_default_units=c_default_units,
        s_comparison=s_comparison,
        c_field_list=c_field_list,
        li_wyt_selected=wyt_selector,
        b_wyt_period_year=wyt_period_selector_year,
        li_wyt_period_months=wyt_period_selector
    )

    # Monthly pattern plot
    bound_monthly_plot = pn.bind(
        monthly_pattern,
        df_all=df_all_data,
        var_list=var_selector,
        scenario_list=scen_selector,
        unit_choice=unit_selector,
        stat_choice=monthly_stat_sel,
        c_default_units=c_default_units,
        s_comparison=s_comparison,
        c_field_list=c_field_list,
        period_choice=period_selector,
        li_wyt_selected=wyt_selector
    )

    # Monthly pattern differences plot
    bound_monthly_diffs_plot = pn.bind(
        monthly_pattern,
        df_all=df_diffs,
        var_list=var_selector,
        scenario_list=scen_selector,
        unit_choice=unit_selector,
        stat_choice=monthly_stat_sel,
        c_default_units=c_default_units,
        s_comparison=s_comparison,
        c_field_list=c_field_list,
        period_choice=period_selector,
        li_wyt_selected=wyt_selector
    )

    if s_module=='temperature':
        o_year_selector = pn.widgets.IntInput(name='Year', value=1923, step=1, start=1922, end=2021, width=100)
        o_reservoir_toggle = pn.widgets.RadioButtonGroup(
            name='Units selector',
            options=['Shasta', 'Folsom'],
            button_style='outline',
            button_type='primary',
            width=200,
            margin=32
        )
        # add in other plots
        bound_one_year_plots = pn.bind(
            plot_single_year,
            scenario_list=scen_selector,
            df_all=df_all_data,
            c_field_list=c_field_list,
            s_reservoir=o_reservoir_toggle,
            i_year=o_year_selector
        )


    # TODO make sure this works - maybe move to own function
    if s_module=='hydro_out':  # only create spatial plot if shapefile is present for hydro
        #get variables from field list

        #special case for DP
        def get_spatial_prefix(field):
            if field.startswith('DP_') and field.endswith(('_EXT', '_INT')):
                suffix = field.split('_')[-1]  # 'EXT' or 'INT'
                return f'DP_{suffix}'  # -> 'DP_EXT' or 'DP_INT'
            return field.split('_')[0]

        ls_spatial_prefixes = sorted(set(get_spatial_prefix(field) for field in c_field_list.keys()))
        spatial_var_sel = pn.widgets.Select(
            name='Spatial Variable Selector',
            options=ls_spatial_prefixes,
            width=400
        )

        # Import the Shapefiles based on variable
        c_gdf_by_prefix = {}
        for var in ls_spatial_prefixes:
            if var == "DP" or var == "SR":
                s_shapefile_path=path.abspath(path.join(path.dirname(__file__), 'WBAs/WBAs/WBAs.shp'))
                id_col = 'WBA_ID'
            else:
                s_shapefile_path=path.abspath(path.join(path.dirname(__file__), 'DUs/DemandUnits~2015.shp'))
                id_col = 'DU_ID'

            b_have_shapefile = path.exists(s_shapefile_path)
            if b_have_shapefile:
                gdf = gpd.read_file(s_shapefile_path)
                print("Shapefile columns:", gdf.columns.tolist())
                gdf = gdf[[id_col, 'geometry']]
                gdf = gdf.to_crs(4326)  # HVplot requires lat/lon to plot with 'geo=True'
                c_gdf_by_prefix[var] = gdf
            else:
                print(f"Shapefile n ot found for {var}: {s_shapefile_path}")

            # Spatial plots

            bound_plot_spatial = pn.bind(
                plot_spatial,
                scenario_list=scen_selector,
                var_list=var_selector,
                unit_choice=unit_selector,
                df_all=df_all_data,
                c_default_units_all=c_default_units,
                period_choice=period_selector,
                s_comparison=s_comparison,
                spatial_var_choice=spatial_var_sel,
                c_gdf=c_gdf_by_prefix
            )

            bound_plot_spatial_diff = pn.bind(
                plot_spatial,
                scenario_list=scen_selector,
                var_list=var_selector,
                unit_choice=unit_selector,
                df_all=df_diffs,
                c_default_units_all=c_default_units,
                period_choice=period_selector,
                s_comparison=s_comparison,
                spatial_var_choice=spatial_var_sel,
                c_gdf=c_gdf_by_prefix
            )

       # Titles for each plot, same order as the plots
    ts_title = pn.pane.Markdown("# Timeseries Plot"
                                )

    diffs_ts_title = pn.pane.Markdown("# Timeseries Plot (Difference from " + s_comparison + ")"
                                      )

    grouped_title = pn.bind(create_plot_title,
                            s_title="Time-Aggregated Plot",
                            s_comparison='',
                            s_period=period_selector)

    grouped__diff_title = pn.bind(create_plot_title,
                                  s_title="Time-Aggregated Plot",
                                  s_comparison=s_comparison,
                                  s_period=period_selector)

    exceedance_title = pn.bind(create_plot_title,
                               s_title="Exceedance Plot",
                               s_comparison='',
                               s_period=period_selector)

    exceedance_diff_title = pn.bind(create_plot_title,
                                    s_title="Exceedance Plot",
                                    s_comparison=s_comparison,
                                    s_period=period_selector)

    single_var_title = pn.bind(create_plot_title,
                               s_title="Bar Plot",
                               s_comparison='',
                               s_period=period_selector,
                               s_stat=bar_stat_sel)

    single_var_diff_title = pn.bind(create_plot_title,
                                    s_title="Bar Plot",
                                    s_comparison=s_comparison,
                                    s_period=period_selector,
                                    s_stat=bar_stat_sel)

    monthly_title = pn.bind(create_plot_title,
                            s_title="Monthly Pattern",
                            s_stat=monthly_stat_sel)

    monthly_diffs_title = pn.bind(create_plot_title,
                                  s_title="Monthly Pattern",
                                  s_comparison=s_comparison,
                                  s_stat=monthly_stat_sel)


    if s_module=='hydro_out' and b_have_shapefile: # only create spatial plot for hydro
        spatial_title = pn.bind(create_plot_title,
                                s_title="Spatial Plot",
                                s_comparison='',
                                s_period=period_selector,
                                s_stat = spatial_var_sel)

        spatial__diff_title = pn.bind(create_plot_title,
                                s_title="Spatial Plot",
                                s_comparison=s_comparison,
                                s_period=period_selector,
                                s_stat = spatial_var_sel)


        # Create the different tables of metadata
    o_metadata = create_metadata(scenario_names, c_field_list, c_default_units, s_module)

    # Add widgets to header row in template and refresh objects
    header.append(scen_selector)
    header.append(var_selector)
    header.append(pn.Column(period_selector, pn.Column(wyt_selector, pn.Row(wyt_period_selector_year, wyt_period_selector), visible=False), max_width=300))
    header.append(unit_selector)
    header.param.trigger("objects")

    # Lay out the plots and titles
    # These will hold the plots
    single_var_plots = pn.Column()
    timeseries_plots = pn.Row()
    grouped_plots = pn.Row()
    exceedance_plots = pn.Row()
    monthly_plots = pn.Column()

    if s_module=='hydro_out':
        spatial_plots = pn.Column()

    if s_module=='temperature':
        one_year_plots = pn.Column()

    # Add everything into these containers
    single_var_widgets = pn.Row(bar_stat_sel)

    single_var_plots.append(single_var_widgets)
    single_var_plots.append(pn.Row(pn.Column(single_var_title,bound_single_var_plot),pn.Column(single_var_diff_title,bound_single_var_diff_plot)))

    timeseries_plots.append(pn.Column(ts_title,bound_plot_ts))
    timeseries_plots.append(pn.Column(diffs_ts_title,bound_plot_diffs_ts))

    grouped_plots.append(pn.Column(grouped_title,bound_plot_grouped))
    grouped_plots.append(pn.Column(grouped__diff_title,bound_plot_grouped_diff))

    exceedance_plots.append(pn.Column(exceedance_title, bound_plot_exceedance, exceedance_show_year_check))
    exceedance_plots.append(pn.Column(exceedance_diff_title, bound_plot_diffs_exceedance, exceedance_show_year_check_diffs))

    monthly_plots.append(pn.Row(monthly_stat_sel))
    monthly_plots.append(pn.Row(pn.Column(monthly_title, bound_monthly_plot), pn.Column(monthly_diffs_title, bound_monthly_diffs_plot)))

    if s_module=='temperature':
        one_year_plots.append(pn.Row(o_year_selector, o_reservoir_toggle))
        one_year_plots.append(bound_one_year_plots)


    if s_module=='hydro_out' and b_have_shapefile:  # only create spatial plot for hydro if shapefile present
        spatial_plots.append(pn.Row(spatial_var_sel))
        spatial_plots.append(pn.Row(pn.Column(spatial_title, bound_plot_spatial),
                                    pn.Column(spatial__diff_title, bound_plot_spatial_diff)))

    # create the tabs with each page of plots
    if s_module=='calsim' or s_module=='salinity':
        tabs = pn.Tabs(
            ('Bar Plot', single_var_plots),
            ('Timeseries', timeseries_plots),
            ('Time-Aggregated', grouped_plots),
            ('Exceedance', exceedance_plots),
            ('Monthly Pattern', monthly_plots),
            ('Metadata', o_metadata)
        )
    elif s_module=='temperature':
        tabs = pn.Tabs(
            ('Single Year Plots', one_year_plots),
            ('Bar Plot', single_var_plots),
            ('Timeseries', timeseries_plots),
            ('Time-Aggregated', grouped_plots),
            ('Exceedance', exceedance_plots),
            ('Monthly Pattern', monthly_plots),
            ('Metadata', o_metadata)
        )

    elif s_module=='hydro_out':
        tabs = pn.Tabs(
            ('Bar Plot', single_var_plots),
            ('Timeseries', timeseries_plots),
            ('Time-Aggregated', grouped_plots),
            ('Exceedance', exceedance_plots),
            ('Monthly Pattern', monthly_plots),
            ('Spatial', spatial_plots),
            ('Metadata', o_metadata)
        )

    # append the tabs to the row
    tabs_row.append(tabs)
    tabs_row.param.trigger("objects")


def add_run_names_widget(event, s_module, file_picker_col_tracker, run_name_col_tracker, field_col_tracker, file_picker_display, header, tabs_row):
    """
    Adds the widgets to take in the file names

    Parameters
    ----------
    event: object
        Event that the continue button was clicked
    s_module: str
        Which module this picker belongs to (e.g. 'calsim', 'hydro_out')
    file_picker_col_tracker: list
        Tracks what is in the file picker column and where
    run_name_col_tracker: list
        Tracks what is in the run name column and where
    field_col_tracker: list
        Tracks what is in the field column and where
    file_picker_display: object
        Panel Row containing the widgets on the page
    header: object
        Panel Row for widget to go in
    tabs_row: object
        Panel Row for tabs to go in
    Returns
    -------
        none
    """
    # Pull out each column from the file picker display
    file_picker_column = file_picker_display[0]
    run_name_column = file_picker_display[1][0]
    field_column = file_picker_display[1][1]

    # look for old error message and remove
    if 'error_message' in field_col_tracker:
        error_index = field_col_tracker.index('error_message')
        field_column.pop(error_index)
        field_col_tracker.pop(error_index)

    # check if we have already pressed the button and remove everything if so
    if 'add_field_text' in field_col_tracker:
        for _ in range(len(field_col_tracker)):
            field_col_tracker.pop(0)
            field_column.pop(0)
        for _ in range(len(run_name_col_tracker)):
            run_name_col_tracker.pop(0)
            run_name_column.pop(0)

    files = file_picker_column[file_picker_col_tracker.index("dss_file")].value
    # Check if user is running previous scenario or new
    if len(files) > 0:
        # Temperature will pass in folders
        if path.isdir(files[0]):
            run_name_instructions = pn.pane.Markdown(""" 
                            # Enter a scenario name for each folder (e.g. NAA, Alt1, etc.). 
                            """, renderer='markdown'
                                                     )
            run_name_instructions_comparison = pn.pane.Markdown("""                
                            ## <span style="color:red">One run must be marked for comparison.</span>
                            """, renderer='markdown'
                                                                )
            run_name_instructions_tooltip = pn.widgets.TooltipIcon(value='A plot of differences will be created based off this scenario.')
            run_name_column.append(pn.Column(run_name_instructions, pn.Row(run_name_instructions_comparison, run_name_instructions_tooltip)))
            run_name_col_tracker.append("run_name_instructions")

            # have user provide run names for each file, new scenario has been selected
            for folder in files:
                dss_run_file_label = pn.pane.Markdown("### Folder name: " + folder)

                comparison_check = pn.widgets.Checkbox(name='Comparison scenario')
                dss_run_name = pn.widgets.TextInput(max_width=500, placeholder='Enter name for scenario')
                dss_run_name_tooltip = pn.widgets.TooltipIcon(value='Enter the name you want displayed for this run.')

                run_name_column.append(dss_run_file_label)
                run_name_col_tracker.append("dss_run_file_label")
                run_name_column.append(comparison_check)
                run_name_col_tracker.append("dss_comparison_checkbox")
                run_name_column.append(pn.Row(dss_run_name, dss_run_name_tooltip))
                run_name_col_tracker.append("dss_run_name")
        # DSS files
        elif "dss" in files[0].rsplit(".", 1)[1]:
            run_name_instructions = pn.pane.Markdown(""" 
                # Enter a run name for each file (e.g. Baseline, Alt1, etc.). 
                """, renderer='markdown'
                                                     )
            run_name_instructions_comparison = pn.pane.Markdown("""                
                ## <span style="color:red">One run must be marked for comparison.</span>
                """, renderer='markdown'
                                                                )
            run_name_instructions_tooltip = pn.widgets.TooltipIcon(value='A plot of differences will be created based off this scenario.')
            run_name_column.append(pn.Column(run_name_instructions, pn.Row(run_name_instructions_comparison, run_name_instructions_tooltip)))
            run_name_col_tracker.append("run_name_instructions")

            #have user provide run names for each file, new scenario has been selected
            for file in files:
                dss_run_file_label = pn.pane.Markdown("### File name: " + file)

                comparison_check = pn.widgets.Checkbox(name='Comparison scenario')
                dss_run_name = pn.widgets.TextInput(max_width=500, placeholder='Enter name for file')
                dss_run_name_tooltip = pn.widgets.TooltipIcon(value='Enter the name you want displayed for this run.')

                run_name_column.append(dss_run_file_label)
                run_name_col_tracker.append("dss_run_file_label")
                run_name_column.append(comparison_check)
                run_name_col_tracker.append("dss_comparison_checkbox")
                run_name_column.append(pn.Row(dss_run_name, dss_run_name_tooltip))
                run_name_col_tracker.append("dss_run_name")

        #using picked files
        else:
            # check to make sure all pickle files have been selected
            b_diffs_flag = False
            b_values_flag = False
            b_units_flag = False
            b_fields_flag = False
            for file in files:
                if 'diffs' in file:
                    b_diffs_flag = True
                if 'values' in file:
                    b_values_flag = True
                if 'units' in file:
                    b_units_flag = True
                if 'fields' in file:
                    b_fields_flag = True
            if not (b_units_flag and b_diffs_flag and b_values_flag and b_fields_flag):
                error_message = pn.pane.Markdown("## Make sure all pickle files are selected.")
                field_column.append(error_message)
                field_col_tracker.append("error_message")
                return
            # no need for fields section, just start pulling the files
            update_run_names(event, file_picker_column, file_picker_col_tracker, run_name_column, run_name_col_tracker, field_column, field_col_tracker, file_picker_display, header, tabs_row, s_module)

        # add option to override TR_fields.txt
        override_TR_fields_instructions = pn.pane.Markdown("""
        # OPTIONAL override default fields:""", renderer='markdown')
        if s_module in ('calsim', 'hydro_out'):
            # if calsim, only need the b part for the fields
            override_TR_fields_instructions_deatils = pn.pane.Markdown("""
    
            ## If you would like to override the built in default fields, select a text file with your preferred fields.
    
            ### Each line must be a field with the variable name followed by a tab and the description of the variable. This is the default format if copied and pasted from an excel sheet.
    
            ### Example:
    
            > S_FOLSM\tFolsom Storage
            >
            > S_SHSTA\tShasta Storage
            >
            > ...
            """, renderer='markdown')
            override_TR_fields_instructions_tooltip = pn.widgets.TooltipIcon(
                value='A default list of fields and descriptions is built in. If you want to override this list, upload a new list here. If no file is selected, the built-in list is used.')
        elif s_module in ('temperature', 'salinity'):
            override_TR_fields_instructions_deatils = pn.pane.Markdown("""

                        ## If you would like to override the built in default fields, select a text file with your preferred fields.

                        ### Each line must be a field with the variable name followed by a tab and the description of the variable. This is the default format if copied and pasted from an excel sheet.

                        ### Example:

                        > Stor-Temp/FOLSOM/STORAGE\tFolsom Storage
                        >
                        > AMERICAN/BLW FOLSOM DAM/FLOW\tAmerican River below Folsom Dam Flow
                        >
                        > ...
                        """, renderer='markdown')
            override_TR_fields_instructions_tooltip = pn.widgets.TooltipIcon(value='A default list of fields and descriptions is built in. If you want to override this list, upload a new list here. Specify the A, B, and C parts of the DSS path. If no file is selected, the built-in list is used.')

        field_column.append(pn.Column(pn.Row(override_TR_fields_instructions, override_TR_fields_instructions_tooltip), override_TR_fields_instructions_deatils))
        field_col_tracker.append("override_instructions")

        override_file = pn.widgets.FileInput(accept='.txt', multiple=False, max_width=500)

        field_column.append(override_file)
        field_col_tracker.append("override_file")

        #Also add optional field add text box
        add_field_instructions = pn.pane.Markdown("""
        # OPTIONAL additional fields: """, renderer='markdown')
        if s_module in ('calsim', 'hydro_out'):
            # if calsim, only need the b part for the fields
            add_field_instructions_details = pn.pane.Markdown("""
    
            ## Add additional fields to visualize that are not present in the default list (or your chosen list). 
    
            ### Each line is a field with the variable name followed by a tab and the the description of the variable. This is the default format if copied and pasted from an excel sheet.
    
            ### Example:
    
            > S_FOLSM\tFolsom Storage
            >
            > S_SHSTA\tShasta Storage
            >
            >...
    
            """, renderer='markdown')
            add_field_instructions_tooltip = pn.widgets.TooltipIcon(value='If you want to include fields that are not in the default list, add them here. If left blank, only the default list will be pulled from files.')
        elif s_module in ('temperature', 'salinity'):
            add_field_instructions_details = pn.pane.Markdown("""

            ## Add additional fields to visualize that are not present in the default list (or your chosen list). 

            ### Each line is a field with the variable name followed followed by a tab and the description of the variable. This is the default format if copied and pasted from an excel sheet.

            ### Example:

            > Stor-Temp/FOLSOM/STORAGE\tFolsom Storage
            >
            > AMERICAN/BLW FOLSOM DAM/FLOW\tAmerican River below Folsom Dam Flow
            >
            >...

            """, renderer='markdown')
            add_field_instructions_tooltip = pn.widgets.TooltipIcon(
                value='If you want to include fields that are not in the default list, add them here. Specify the A, B, and C parts of the DSS path. If left blank, only the default list will be pulled from files.')

        field_column.append(pn.Column(pn.Row(add_field_instructions, add_field_instructions_tooltip), add_field_instructions_details))
        field_col_tracker.append("add_field_instructions")

        if s_module in ('calsim', 'hydro_out'):
            add_field_text = pn.widgets.TextAreaInput(name='', placeholder='S_FOLSM\tFolsom Storage\nS_SHSTA\tShasta Storage', auto_grow=True, width=500)
        elif s_module in ('temperature', 'salinity'):
            add_field_text = pn.widgets.TextAreaInput(name='', placeholder='Stor-Temp/FOLSOM/STORAGE\tFolsom Storage\nAMERICAN/BLW FOLSOM DAM/FLOW\tAmerican River below Folsom Dam Flow', auto_grow=True, width=500)

        field_column.append(add_field_text)
        field_col_tracker.append("add_field_text")

        # Add another continue button for when user is done adding run names to files
        done_naming = pn.widgets.Button(name="Continue", width=500, button_type='primary')
        # When user is done adding file/run names, save inputs to variables
        done_naming.on_click(partial(update_run_names, file_picker_column=file_picker_column, file_picker_col_tracker=file_picker_col_tracker, run_name_column=run_name_column,
                                     run_name_col_tracker=run_name_col_tracker, field_column=field_column, field_col_tracker=field_col_tracker,
                                     file_picker_display=file_picker_display, header=header, tabs_row=tabs_row, s_module=s_module))

        field_column.append(done_naming)
        field_col_tracker.append("done_naming")

    #Refresh field file_picker_column
    field_column.param.trigger("objects")

    #Refresh run names file_picker_column
    run_name_column.param.trigger("objects")  # Trigger UI update


def update_run_names(event, file_picker_column, file_picker_col_tracker, run_name_column,
                     run_name_col_tracker, field_column, field_col_tracker,
                     file_picker_display, header, tabs_row, s_module):
    """
    Looks at what files are selected and reads in the pickle files or DSS files. If DSS, gets the inputted run names and calls the file reading functions. Creates the pickles.

    Parameters
    ----------
    event: object
        Event that the continue button was clicked
    file_picker_column: object
        Panel Column with file selector
    file_picker_col_tracker: list
        Tracks what is in the file picker column and where
    run_name_column: object
        Panel Column with run name widgets
    run_name_col_tracker: list
        Tracks what is in the run name column and where
    field_column: object
        Panel Column with field wisgets
    field_col_tracker: list
        Tracks what is in the field column and where
    file_picker_display: object
        Panel Row containing the widgets on the page
    header: object
        Panel Row for widget to go in
    tabs_row: object
        Panel Row for tabs to go in
    s_module: str
        Which module this picker belongs to (e.g. 'calsim', 'hydro_out')

    Returns
    -------
        none
    """

    # Get selected files
    files = file_picker_column[file_picker_col_tracker.index("dss_file")].value  # Access the global variable

    # look for old error message and remove
    if 'error_message' in field_col_tracker:
        error_index = field_col_tracker.index('error_message')
        field_column.pop(error_index)
        field_col_tracker.pop(error_index)

    #check if we have exactl one file marked for comparison and if not give an error
    if path.isdir(files[0]) or "dss" in files[0].rsplit(".",1)[1]:
        if sum([run_name_column[i].value for i, x in enumerate(run_name_col_tracker) if x == "dss_comparison_checkbox"]) != 1:
            error_message = pn.pane.Markdown("## Please make sure that exactly one file is marked for comparison.")
            field_column.append(error_message)
            field_col_tracker.append('error_message')
            return

    # row to indicate that the files are being read and it is loading
    loading_row = pn.Row(pn.indicators.LoadingSpinner(
        value=True, height=30, width=30, color="primary"
    ), pn.pane.Markdown("""
            ## Loading in data. New files will take longer than previously generated visuals.

            ### Once new files have been read in, they will be saved to pickle files that can be used on the previously generated visuals tab for faster startup.
            """))
    field_column.append(loading_row)
    field_col_tracker.append('loading_row')

    #Check if files are dss or pkl or folders
    # Temperature will pass in folders
    if path.isdir(files[0]):

        # Get indices of dss run names
        folder_name_indices = [i for i, x in enumerate(run_name_col_tracker) if x == "dss_run_name"]

        # get the value of the checkbox for each run
        comparison_indices = [run_name_column[i].value for i, x in enumerate(run_name_col_tracker) if x == "dss_comparison_checkbox"]

        # Get file names
        folders = file_picker_column[file_picker_col_tracker.index("dss_file")].value

        # Get default fields and any added ones
        # pulling from TR_fields_temperature.txt
        if s_module == 'temperature':
            c_tr_fields = get_trend_fields('TR_fields_temperature.txt')
        elif s_module == 'salinity':
            c_tr_fields = get_trend_fields('TR_fields_salinity.txt')

        # get the overridden fields
        override_TR_fields = field_column[field_col_tracker.index("override_file")].value
        c_override_fields = {}
        if override_TR_fields:
            override_TR_fields_text = override_TR_fields.decode()
            for line in override_TR_fields_text.split('\n'):
                line = line.strip()
                new_field = line.split('\t')
                if len(new_field) == 0:
                    continue
                elif len(new_field) == 1:
                    field = new_field[0]
                    field = field.strip(' ').upper()
                    if field in c_tr_fields.keys():
                        c_override_fields[field] = c_tr_fields[field]
                    else:
                        c_override_fields[field] = field
                else:
                    field, description = new_field

                    if '/' not in field:
                        # this happens for calsim and those are always uppercase
                        field = field.strip(' ').upper()
                    else:
                        field = field.strip(' ')
                    description = description.strip('\n')
                    description = description + ' (' + field + ')'
                    c_override_fields[field] = description

        # to hold the ones entered in the optional field
        c_new_fields = {}
        if field_column[field_col_tracker.index("add_field_text")].value != '':
            for line in field_column[field_col_tracker.index("add_field_text")].value.split('\n'):
                line = line.strip()
                new_field = line.split('\t')
                if len(new_field) == 0:
                    continue
                elif len(new_field) == 1:
                    field = new_field[0]
                    field = field.strip(' ').upper()
                    c_new_fields[field] = field
                else:
                    field, description = new_field

                    if '/' not in field:
                        # this happens for calsim and those are always uppercase
                        field = field.strip(' ').upper()
                    else:
                        field = field.strip(' ')
                    description = description.strip('\n')
                    description = description + ' (' + field + ')'
                    c_new_fields[field] = description
        if override_TR_fields:
            c_field_list = c_override_fields | c_new_fields
        else:
            c_field_list = c_tr_fields | c_new_fields
        runs = []

        # Pair file names with user entered run names
        for file_index, run_index in enumerate(folder_name_indices):
            # structure of runs is [["Description_1", ("File_1.dss")],
            #               ["Description_2", ("File_2.dss")],
            #          ...  ["Description_n", ("File_n.dss")]]
            # The names can be anything though, e.g. ["Alt2v1", Alt2v1_VAs.dss"]

            # find where the box is checked for comparison and set comparison name tracker to files name
            if comparison_indices[file_index]:
                # define comparison name variable
                s_comparison = run_name_column[run_index][0].value
            if s_module == 'temperature':
                c_dss_paths = {'calsim_DV': '',
                               'calsim_SV': '',
                               'AR_WQ_Report': '',
                               'a_CALSIMII_HEC5Q': '',
                               'SR_WQ_Report': '',
                               's_CALSIMII_HEC5Q': ''
                               }
                for s_file in os.listdir(files[file_index]):
                    s_curr_path = os.path.join(folders[file_index], s_file)
                    if os.path.isfile(s_curr_path):
                        if 'SV' in s_file or 'sv' in s_file:
                            c_dss_paths['calsim_SV'] = s_curr_path
                        elif 'DV' in s_file or 'dv' in s_file:
                            c_dss_paths['calsim_DV'] = s_curr_path
                    elif s_file == 'american':
                        c_dss_paths['AR_WQ_Report'] = os.path.join(s_curr_path, 'AR_WQ_Report.dss')
                        c_dss_paths['a_CALSIMII_HEC5Q'] = os.path.join(s_curr_path,  'CALSIMII_HEC5Q.dss')
                    elif s_file == 'sacramento':
                        c_dss_paths['SR_WQ_Report'] = os.path.join(s_curr_path, 'SR_WQ_Report.dss')
                        c_dss_paths['s_CALSIMII_HEC5Q'] = os.path.join(s_curr_path, 'CALSIMII_HEC5Q.dss')
            elif s_module == 'salinity':
                c_dss_paths = {
                    "flow": '',
                    "ec": ''
                }
                for s_file in os.listdir(files[file_index]):
                    s_curr_path = os.path.join(folders[file_index], s_file)
                    if os.path.isfile(s_curr_path):
                        if 'EC' in s_file or 'ec' in s_file:
                            c_dss_paths['ec'] = s_curr_path
                        elif 'FLOW' in s_file or 'flow' in s_file:
                            c_dss_paths['flow'] = s_curr_path

            runs.append([run_name_column[run_index][0].value, c_dss_paths])
        print(runs)
        append_list, baseline_stack, c_default_units, c_field_list = file_reader(runs, c_field_list, s_comparison, s_module)
        pickler(append_list, baseline_stack, c_default_units, c_field_list, s_module)

        # This runs no matter what. The pickle files allow you to come back and
        # pull the same variables without waiting for the file reads to complete
        df_all_data, df_diffs, c_default_units, c_field_list = load_pickles([], s_module)

        # Write to Excel.
        # try:
        #     df_all_data.to_excel("DSS_contents.xlsx")
        # except:
        #     print("Error writing output file. ")

        print(f'Pulled: {len(runs)} files')
        print(runs)
    # dss files (calsim)
    elif "dss" in files[0].rsplit(".",1)[1]:
        # Get indices of dss run names
        dss_name_indices = [i for i, x in enumerate(run_name_col_tracker) if x == "dss_run_name"]
        # get the value of the checkbox for each run
        comparison_indices = [run_name_column[i].value for i, x in enumerate(run_name_col_tracker) if x == "dss_comparison_checkbox"]

        # Get file names
        files = file_picker_column[file_picker_col_tracker.index("dss_file")].value

        # Get default fields and any added ones
        # pulling from TR_fields.txt
        if s_module == 'calsim':
            c_tr_fields = get_trend_fields('TR_fields.txt')
        elif s_module == 'hydro_out':
            c_tr_fields = get_trend_fields('TR_fields_CSH.txt')

        # get the overridden fields
        override_TR_fields = field_column[field_col_tracker.index("override_file")].value
        c_override_fields = {}
        if override_TR_fields:
            override_TR_fields_text = override_TR_fields.decode()
            for line in override_TR_fields_text.split('\n'):
                line = line.strip()
                new_field = line.split(maxsplit=1)
                if len(new_field) == 0:
                    continue
                elif len(new_field) == 1:
                    field = new_field[0]
                    field = field.strip(' ').upper()
                    if field in c_tr_fields.keys():
                        c_override_fields[field] = c_tr_fields[field]
                    else:
                        c_override_fields[field] = field
                else:
                    field, description = new_field

                    field = field.strip(' ').upper()
                    description = description.strip('\n')
                    description = description + ' (' + field + ')'
                    c_override_fields[field] = description

        # to hold the ones entered in the optional field
        c_new_fields = {}
        if field_column[field_col_tracker.index("add_field_text")].value != '':
            for line in field_column[field_col_tracker.index("add_field_text")].value.split('\n'):
                line = line.strip()
                new_field = line.split(maxsplit=1)
                if len(new_field) == 0:
                    continue
                elif len(new_field) == 1:
                    field = new_field[0]
                    field = field.strip(' ').upper()
                    c_new_fields[field] = field
                else:
                    field, description = new_field

                    field = field.strip(' ').upper()
                    description = description.strip('\n')
                    description = description + ' (' + field + ')'
                    c_new_fields[field] = description
        if override_TR_fields:
            c_field_list = c_override_fields | c_new_fields
        else:
            c_field_list = c_tr_fields | c_new_fields
        runs = []
        #Pair file names with user entered run names
        for file_index, run_index in enumerate(dss_name_indices):
            # structure of runs is [["Description_1", ("File_1.dss")],
            #               ["Description_2", ("File_2.dss")],
            #          ...  ["Description_n", ("File_n.dss")]]
            # The names can be anything though, e.g. ["Alt2v1", Alt2v1_VAs.dss"]

            # find where the box is checked for comparison and set comparison name tracker to files name
            if comparison_indices[file_index]:
                # define comparison name variable
                s_comparison = run_name_column[run_index][0].value

            runs.append([run_name_column[run_index][0].value, (files[file_index])])
        print(runs)
        append_list, baseline_stack, c_default_units, c_field_list = file_reader(runs, c_field_list, s_comparison, s_module)

        pickler(append_list, baseline_stack, c_default_units, c_field_list, s_module)

        # This runs no matter what. The pickle files allow you to come back and
        # pull the same variables without waiting for the file reads to complete
        df_all_data, df_diffs, c_default_units, c_field_list = load_pickles([], s_module)

        # Write to Excel.
        # try:
        #     df_all_data.to_excel("DSS_contents.xlsx")
        # except:
        #     print("Error writing output file. ")

        print(f'Pulled: {len(runs)} files')
        print(runs)

    #Load pickles from previous run
    else:
        df_all_data, df_diffs, c_default_units, c_field_list = load_pickles(files, s_module)

    # need to pull comparison scenario from un pickled files
    s_comparison = c_default_units['comparison scenario']

    #Now that pickles have been created/loaded, move forward with initiating other tabs
    scenario_names = df_all_data['Scenario'].unique().tolist()

    # removing loading before adding tabs
    loading_index = field_col_tracker.index('loading_row')
    field_column.pop(loading_index)
    field_col_tracker.pop(loading_index)
    field_column.param.trigger("objects")

    #Fill in widgets for other tabs
    create_plots(scenario_names, c_field_list, df_all_data, c_default_units, df_diffs, s_comparison, header, tabs_row, s_module)

    # once we have the widgets and graphs, remove the file picker
    for _ in range(len(file_picker_display)):
        file_picker_display.pop(0)
