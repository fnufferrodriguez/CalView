import warnings

import panel as pn
import os
import pandas as pd
from src.cs3_plotlib import *
from functools import partial
from src.csdss_readlib_fullfile import *


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

def clear_container(event, container):
    """
    Empties a Panel container of all its children.

    Parameters
    ----------
    event: obj
        Event from the button/widget that triggered this (unused, but required by on_click/watch)
    container: obj
        Panel container (Row, Column, etc.) to clear

    Returns
    -------
        none
    """
    for _ in range(len(container)):
        container.pop(0)

def filter_vars_to_module(selected_vars, c_module_fields):
    """
    Filters a selected variable list down to only those fields belonging to a
    given module. Used so each module's difference plot receives only the fields
    present in that module's dataframe, avoiding KeyErrors on absent columns.

    Parameters
    ----------
    selected_vars: list
        Currently selected variables from the shared variable selector
    c_module_fields: dict
        This module's field -> description dictionary (its c_field_list)

    Returns
    -------
    list
        The subset of selected_vars that exist in this module
    """
    return [var for var in selected_vars if var in c_module_fields]

def build_naming_stage(event, c_module_containers, c_flag, module_column, c_modules, header, tabs_row, old_new_sel):
    """
    Clears the file-picker stage entirely and rebuilds the page as the naming stage:
    shared instructions, then each active module's run-naming/field-overwriting/
    additional-fields section stacked, then one shared Continue button

    Parameters
    ----------
    event: obj
        Event from the button/widget that triggered this (unused, but required by on_click/watch)
    c_module_containers: dict
        Per-module dict of the Panel containers (file_picker_col_tracker, file_picker_display,
        header, tabs_row) needed to build that module's naming section
    c_flag: dict
        Dictionary of module options (keys are module names, values are booleans for active/inactive)
    module_column: obj
        Panel Column that holds the naming stage; cleared and rebuilt by this function
    c_modules: dict
        Dictionary mapping module keys to their display names, used for Card titles
    header: obj
        Panel Row for shared widgets to go in, passed through to create_plots
    tabs_row: obj
        Panel Row for tabs to go in, passed through to create_plots
    old_new_sel: obj
        Run-type radio button widget; its value determines whether the pickle-loading
        path or the DSS-naming path is used

    Returns
    -------
        none
    """
    for _ in range(len(module_column)):
        module_column.pop(0)


    if old_new_sel.value == "Previously generated visuals":
        module_results = []
        for s_module, is_active in c_flag.items():
            if not is_active:
                continue
            containers = c_module_containers[s_module]
            result = add_run_names_widget(
                event, s_module=s_module,
                file_picker_col_tracker=containers['file_picker_col_tracker'],
                run_name_col_tracker=[], field_col_tracker=[],
                file_picker_display=containers['file_picker_display'],
                header=containers['header'], tabs_row=containers['tabs_row'],
                run_name_column=pn.Column(), field_column=pn.Column(),
            )
            if result is not None:
                module_results.append(result)
        create_plots(event, module_results=module_results, module_column=module_column,
                     header=header, tabs_row=tabs_row, c_modules=c_modules)
        return

    ls_update_run_names_kwargs = []
    any_module_needs_naming = False

    # Build per-module sections first (into fresh containers, not tied to the old file-picker layout), so we know whether to show shared instructions
    # before finalizing the page order.
    module_sections = []  # list of (s_module, section_display) to append in order

    for s_module, is_active in c_flag.items():
        if not is_active:
            continue
        containers = c_module_containers[s_module]

        run_name_column = pn.Column()
        run_name_col_tracker = []
        field_column = pn.Column()
        field_col_tracker = []

        result = add_run_names_widget(
            event,
            s_module=s_module,
            file_picker_col_tracker=containers['file_picker_col_tracker'],
            run_name_col_tracker=run_name_col_tracker,
            field_col_tracker=field_col_tracker,
            file_picker_display=containers['file_picker_display'],
            header=containers['header'],
            tabs_row=containers['tabs_row'],
            run_name_column=run_name_column,
            field_column=field_column,
        )

        if result is not None:
            ls_update_run_names_kwargs.append(result)
            any_module_needs_naming = True
            module_sections.append((
                s_module,
                pn.Card(
                    run_name_column,
                    field_column,
                    title=c_modules.get(s_module, s_module),
                    collapsible=True,
                    margin=10,
                    header_background='#003E51',
                    header_color='white',
                    styles={'border': '2px solid #003E51'},
                )
            ))
        # If result is None (pickle path or error), that module has nothing to
        # show in the naming stage; error messages (if any) were already appended
        # to field_column inside add_run_names_widget before returning None —
        # but since field_column here is fresh/local, an error path needs its
        # own visible section too, so show it if field_column got populated:
        elif len(field_column) > 0:
            module_sections.append((
                s_module,
                pn.Column(
                    pn.pane.Markdown(f"## {s_module} — Run Names & Fields"),
                    field_column,
                )
            ))

    # Shared instructions, shown once, only if at least one module has naming widgets
    if any_module_needs_naming:
        run_name_instructions = pn.pane.Markdown(""" 
            # Enter a run name for each file (e.g. Baseline, Alt1, etc.). 
            """, renderer='markdown')
        run_name_instructions_comparison = pn.pane.Markdown("""                
            ## <span style="color:red">One run must be marked for comparison per module.</span>
            """, renderer='markdown')
        run_name_instructions_tooltip = pn.widgets.TooltipIcon(
            value='A plot of differences will be created based off this scenario.')
        module_column.append(
            pn.Column(run_name_instructions, pn.Row(run_name_instructions_comparison, run_name_instructions_tooltip))
        )

    # Stack each module's section, in order
    for s_module, section in module_sections:
        module_column.append(section)

    # Shared Continue button
    if len(ls_update_run_names_kwargs) > 0:
        def on_continue(event, ls_kwargs):
            module_results = []
            for kwargs in ls_kwargs:
                result = update_run_names(event, **kwargs)
                if result is not None:
                    module_results.append(result)
            create_plots(event, module_results=module_results, module_column=module_column,
                         header=header, tabs_row=tabs_row, c_modules=c_modules)

        done_naming = pn.widgets.Button(name="Continue", width=500, button_type='primary')
        done_naming.on_click(partial(on_continue, ls_kwargs=ls_update_run_names_kwargs))
        module_column.append(done_naming)

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
def module_selector(c_flag, c_modules):
    """
    Widget that allows user selection for module type (ex. calsim hydro inputs and outputs)

    Parameters
    ----------
    c_flag: dict
        Dictionary of module options (keys are module names, values are booleans)
    c_modules: dict
        Dictionary mapping module keys to display names

    Returns
    -------
    mod_selector: object
        widget
    """
    #options shown to the user are firendly display names
    c_display_to_key = {c_modules.get(key, key): key for key in c_flag.keys()}

    mod_selector = pn.widgets.MultiChoice(
        name='Module Selector',
        options=c_display_to_key,
        value=[key for key, is_active in c_flag.items() if is_active],
        option_limit=len(c_display_to_key),
        search_option_limit=len(c_display_to_key),
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
            # new temperature, salinity, hydro in
            elif s_module in ('temperature', 'salinity', 'hydro_in'):
                o_instructions = pn.pane.Markdown("### Select the folders to be read in.")
                o_instructions_tooltip = pn.widgets.TooltipIcon(value="Move all folders from 'File Browser' section to 'Selected files' section then click 'Continue'")
                dss_file = pn.widgets.FileSelector(
                    name='',
                    only_files=False,
                    max_width=1000,
                    root_directory=os.path.abspath(os.sep)
                )
            #new hydro out
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
            o_instructions = pn.pane.Markdown('### <span style="color:red">Select the module pickle file previously created (module_&lt;name&gt;.pkl)</span>')
            o_instructions_tooltip = pn.widgets.TooltipIcon(value="Move the pkl file from 'File Browser' section to 'Selected files' section then click 'Continue'")
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
    if len(header) > 1:
        # check if a WYT is selected
        if isinstance(event.new, str) and ('WYT' in event.new or 'SHASTABIN_' in event.new):
            # turn on the visibility
            header[1][1].visible = True
        else:
            # turn it off
            header[1][1].visible = False
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
    temp_unit_selector: obj
        Temp unit toggle widget
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
        option_limit=len(scenario_names) + 10,
        search_option_limit=len(scenario_names) + 10,
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
    # Toggle for temperature units
    temp_unit_selector = pn.widgets.RadioButtonGroup(
        name='Temperature units selector',
        options=['F', 'C'],
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

    # Create checkbox widget to specify CalSimHydro Files w/  Spatial Data todo remove
    wba_spatial_sel = pn.widgets.Checkbox(
        name='Create Spatial Plot (only select if data has WBA specific values, i.e. CalSimHydro Files)'
    )

    # Check boxed for showing years in exceedance tables
    exceedance_show_year_check = pn.widgets.Checkbox(name='Show year in table')
    exceedance_show_year_check_diffs = pn.widgets.Checkbox(name='Show year in table')

    # Return all these widgets
    return scen_selector, unit_selector, temp_unit_selector, period_selector, wyt_selector, wyt_period_selector, wyt_period_selector_year, bar_stat_sel, monthly_stat_sel, exceedance_show_year_check, exceedance_show_year_check_diffs, wba_spatial_sel


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
    df_field_names: DataFrame
        Field-level metadata (description, default units, module...) indexed by field
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

    elif s_module=='hydro_in':
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

    # Module for each field
    df_field_names['Module'] = s_module

    # temperature eligibility
    if s_module == 'temperature':
        df_field_names['Single Year Eligible'] = True
    else:
        df_field_names['Single Year Eligible'] = False

        # Shapefile assignment per field - must match groups from get_spatial_group
        c_module_shapefiles = {
            'hydro_out': {'AWO': 'DemandUnits~2015', 'AWR': 'DemandUnits~2015', 'AWW': 'DemandUnits~2015',
                          'TW': 'DemandUnits~2015',
                          'UD': 'DemandUnits~2015', 'WW': 'DemandUnits~2015', 'FR': 'DemandUnits~2015',
                          'DP': 'WBAs', 'SR': 'WBAs', 'DP_EXT': 'WBAs', 'DP_INT': 'WBAs'},
            'hydro_in': {'AL ET': 'WBAs', 'AP ET': 'WBAs', 'CO ET': 'WBAs', 'CR ET': 'WBAs', 'CU ET': 'WBAs', 'DB ET': 'WBAs',
                        'FI ET': 'WBAs', 'GR ET': 'WBAs', 'ID ET': 'WBAs', 'OG ET': 'WBAs', 'OR ET': 'WBAs', 'PA ET': 'WBAs',
                        'PO ET': 'WBAs', 'RF ET': 'WBAs', 'RI ET': 'WBAs', 'RV ET': 'WBAs', 'SB ET': 'WBAs', 'SF ET': 'WBAs',
                        'SL ET': 'WBAs', 'SO ET': 'WBAs', 'TH ET': 'WBAs', 'TM ET': 'WBAs', 'TR ET': 'WBAs', 'UR ET': 'WBAs',
                        'VI ET': 'WBAs', 'WL ET': 'WBAs', 'NV ET': 'WBAs', 'RefETO': 'WBAs'}
        }
        if s_module in c_module_shapefiles:
            c_prefix_to_shapefile = c_module_shapefiles[s_module]
            ls_shapefiles = []
            for s_field in df_field_names.index:
                s_prefix = get_spatial_group(s_field, s_module)
                ls_shapefiles.append(c_prefix_to_shapefile.get(s_prefix))
            df_field_names['Shapefile'] = ls_shapefiles

        else:
            df_field_names['Shapefile'] = None

    # Title for fields and descriptions
    o_field_names_title = pn.pane.Markdown("# Fields and descriptions")

    # Dictionary with formulas for calculated fields TODO specify which of these are for which calview, add hydro calcs to here
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

    # hydro DP combined fields
    if s_module == 'hydro_out':
        for field in c_field_list.keys():
            if not field.startswith('DP_'):
                continue
            ext_field = f'{field}_EXT'
            int_field = f'{field}_INT'
            if ext_field in c_field_list and int_field in c_field_list:
                c_used_calc_fields[field] = f'{ext_field} + {int_field}'

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

    return o_metadata, df_field_names


def create_plots(event, module_results, module_column, header, tabs_row, c_modules=None):
    """
    Combines each active module's loaded data into shared structures, builds each
    module's metadata panel, clears the naming stage, and builds the shared plotting
    tabs. Works identically whether module_results came from the pickle-loading path
    or the DSS-naming path, since both produce the same per-module tuple shape via
    update_run_names.

    Each plotting tab gets its own independent variable selector, filtered to only
    the fields valid for that tab based on the combined field metadata (e.g. the
    Spatial tab's selector only offers fields marked Spatial Eligible).

    Parameters
    ----------
    event: obj
        Event from the button/widget that triggered this (unused, but required by on_click/watch)
    module_results: list
        List of per-module tuples, each in the form
        (df_all_data, df_diffs, c_default_units, c_field_list, s_comparison,
        scenario_names, s_module), as returned by update_run_names for each active module
    module_column: obj
        Panel Column holding the naming stage; cleared once all modules' data is combined
    header: obj
        Panel Row that shared widgets (scenario selector, period selector, unit selector) are appended to
    tabs_row: obj
        Panel Row that the final tabs (Bar Plot, Timeseries, Spatial, Metadata, etc.) are appended to
    c_modules: dict, optional
        Dictionary mapping module keys to their display names, used for tab/card titles

    Returns
    -------
        none (mutates module_column, header, and tabs_row in place)
    """
    #all modules failed validation
    if len(module_results)==0:
        return

    #combining all module data
    ls_df_all = []
    ls_df_diffs = []
    c_field_list_all = {}
    c_default_units_all = {}
    ls_all_comparisons = []
    ls_metadata_panels = []
    ls_field_names_dfs = []
    single_year_scenarios = []

    for df_all_data, df_diffs, c_default_units, c_field_list, s_mod_comparison, scenario_names, s_module in module_results:
        ls_df_all.append(df_all_data)
        ls_df_diffs.append(df_diffs)
        c_field_list_all.update(c_field_list)
        c_default_units_all.update(c_default_units)
        ls_all_comparisons.append(s_mod_comparison)

        #create metadata
        o_metadata, df_field_names = create_metadata(scenario_names, c_field_list, c_default_units, s_module)
        ls_metadata_panels.append((c_modules.get(s_module, s_module), o_metadata))
        ls_field_names_dfs.append(df_field_names)

        if df_field_names['Single Year Eligible'].any():
            single_year_scenarios.extend(scenario_names)

    df_all_data_combined = pd.concat(ls_df_all, ignore_index=True)
    df_diffs_combined = pd.concat(ls_df_diffs, ignore_index=True)
    df_field_names_combined = pd.concat(ls_field_names_dfs)
    scenario_names_combined = df_all_data_combined['Scenario'].unique().tolist()

    # remove comparison scen from the differences dataframe as all values are zero
    df_diffs_combined = df_diffs_combined[~df_diffs_combined.Scenario.isin(ls_all_comparisons)]

    # naming stage no longer needed now that all modules' data is loaded and combined
    for _ in range(len(module_column)):
        module_column.pop(0)

    # Create the shared widgets
    (scen_selector, unit_selector, temp_unit_selector,period_selector, wyt_selector, wyt_period_selector, wyt_period_selector_year,
      bar_stat_sel, monthly_stat_sel, exceedance_show_year_check, exceedance_show_year_check_diffs, wba_spatial_sel) = create_widgets(scenario_names_combined, c_field_list_all)
    #spatial plotting is always on for hydro (intentially not using wba_spatial_sel
    # to update the visibility when period is changed todo remove?
    wyt_watcher = period_selector.param.watch(partial(hide_show_wyt, header=header), 'value')

    header.append(scen_selector)
    header.append(pn.Column(period_selector, pn.Column(wyt_selector, pn.Row(wyt_period_selector_year, wyt_period_selector), visible=False), max_width=300))
    header.append(unit_selector)
    header.append(temp_unit_selector)
    header.param.trigger("objects")

    # Build one exceedance section per module since exceedance plots are module specific
    exceedance_sections = []
    for df_all_data, df_diffs, c_default_units, c_field_list, s_mod_comparison, scenario_names, s_module in module_results:
        #strip this module's own comparison scenario out of its own diffs scen
        df_diffs_m_filtered = df_diffs[df_diffs.Scenario != s_mod_comparison]
        mod_description_to_field = {desc: field for field, desc in c_field_list.items()}
        mod_var_selector_exceedance = pn.widgets.MultiChoice(
            name='Variable Selector',
            options=mod_description_to_field,
            value=[list(mod_description_to_field.values())[0]] if mod_description_to_field else [],
            option_limit=len(mod_description_to_field) if mod_description_to_field else 1,
            search_option_limit=len(mod_description_to_field) if mod_description_to_field else 1,
            width=400
        )

        mod_exceedance_show_year_check = pn.widgets.Checkbox(name='Show year in table')
        mod_exceedance_show_year_check_diffs = pn.widgets.Checkbox(name='Show year in table')

        mod_bound_plot_exceedance = pn.bind(
            plot_time_exceedance,
            scenario_list=scen_selector,
            var_list=mod_var_selector_exceedance,
            unit_choice=unit_selector,
            df_all=df_all_data_combined,
            c_default_units=c_default_units,
            period_choice=period_selector,
            s_comparison=s_mod_comparison,
            c_field_list=c_field_list,
            li_wyt_selected=wyt_selector,
            b_wyt_period_year=wyt_period_selector_year,
            li_wyt_period_months=wyt_period_selector,
            b_show_year=mod_exceedance_show_year_check,
            s_module=s_module,
            temp_unit_choice=temp_unit_selector,
        )

        mod_bound_plot_diffs_exceedance = pn.bind(
            plot_time_exceedance,
            scenario_list=scen_selector,
            var_list=mod_var_selector_exceedance,
            unit_choice=unit_selector,
            df_all=df_diffs_m_filtered,
            c_default_units=c_default_units,
            period_choice=period_selector,
            s_comparison=s_mod_comparison,
            c_field_list=c_field_list,
            li_wyt_selected=wyt_selector,
            b_wyt_period_year=wyt_period_selector_year,
            li_wyt_period_months=wyt_period_selector,
            b_show_year=mod_exceedance_show_year_check_diffs,
            s_module=s_module,
            temp_unit_choice=temp_unit_selector,
        )

        mod_exceedance_title = pn.bind(create_plot_title,
                                       s_title=c_modules.get(s_module, s_module) + " Exceedance Plot",
                                       s_comparison='',
                                       s_period=period_selector)

        mod_exceedance_diff_title = pn.bind(create_plot_title,
                                            s_title=c_modules.get(s_module, s_module) + " Exceedance Plot",
                                            s_comparison=s_mod_comparison,
                                            s_period=period_selector)

        exceedance_sections.append((
            c_modules.get(s_module, s_module),
            pn.Row(
                pn.Column(mod_var_selector_exceedance, mod_exceedance_title, mod_bound_plot_exceedance,
                          mod_exceedance_show_year_check),
                pn.Column(mod_exceedance_diff_title, mod_bound_plot_diffs_exceedance,
                          mod_exceedance_show_year_check_diffs)
            )
        ))

    # Build one spatial section per module since spatial plots are module specific
    spatial_sections = []
    spatial_fields = df_field_names_combined.loc[df_field_names_combined['Shapefile'].notna()].index.tolist()
    b_have_spatial = len(spatial_fields) > 0
    c_gdf_by_name = {}
    if b_have_spatial:
        for df_all_m, df_diffs_m, c_units_m, c_fields_m, s_mod_comp_m, scen_names_m, s_mod_m in module_results:
            # remove comparison scen from this module's differences dataframe as all values are zero
            df_diffs_m = df_diffs_m[df_diffs_m.Scenario != s_mod_comp_m]

            #this module's own field metadata, filtered to just this module's row
            df_field_names_m = df_field_names_combined[df_field_names_combined['Module'] == s_mod_m]
            spatial_fields_m = df_field_names_m.loc[df_field_names_m['Shapefile'].notna()].index.tolist()

            if not spatial_fields_m:
                continue #this module has no spatial fields, skip its tab entirely

            ls_spatial_prefixes_m = sorted(set(get_spatial_group(s_field, s_mod_m) for s_field in spatial_fields_m))

            mod_spatial_var_sel = pn.widgets.Select(
                name='Spatial Variable Selector',
                options=ls_spatial_prefixes_m,
                width=400
            )

            #map each prefix (in this module) to its shapefile name
            c_prefix_to_shapefile_m = {}
            for s_field in spatial_fields_m:
                s_prefix = get_spatial_group(s_field, s_mod_m)
                s_shapefile_name = df_field_names_m['Shapefile'].get(s_field)
                if not pd.isna(s_shapefile_name):
                    c_prefix_to_shapefile_m[s_prefix] = s_shapefile_name

            #load each unique shapefile once
            c_gdf_by_prefix_m = {}
            b_have_shapefile_m = False
            for s_prefix, s_shapefile_name in c_prefix_to_shapefile_m.items():
                if s_shapefile_name not in c_gdf_by_name:
                    o_gdf, s_id_col = get_shapefile(s_shapefile_name)
                    c_gdf_by_name[s_shapefile_name] = o_gdf
                    if o_gdf is None:
                        print(f"Shapefile not found for '{s_shapefile_name}'")
                o_gdf = c_gdf_by_name[s_shapefile_name]
                if o_gdf is not None:
                    c_gdf_by_prefix_m[s_prefix] = o_gdf
                    b_have_shapefile_m = True
            if not b_have_shapefile_m:
                continue # no usable shapefiles for this module, skip this tab

            mod_bound_plot_spatial = pn.bind(
                plot_spatial,
                scenario_list=scen_selector,
                unit_choice=unit_selector,
                df_all=df_all_m,
                df_diffs=df_diffs_m,
                c_default_units_all=c_units_m,
                period_choice=period_selector,
                s_comparison=s_mod_comp_m,
                spatial_var_choice=mod_spatial_var_sel,
                c_gdf=c_gdf_by_prefix_m,
                li_wyt_selected=wyt_selector,
                b_wyt_period_year=wyt_period_selector_year,
                li_wyt_period_months=wyt_period_selector,
                c_field_list=c_fields_m,
                s_module=s_mod_m
                )

            mod_spatial_title = pn.bind(create_plot_title,
                                        s_title=c_modules.get(s_mod_m, s_mod_m) + " Spatial Plot",
                                        s_period=period_selector)
            spatial_sections.append((
                c_modules.get(s_mod_m, s_mod_m),
                pn.Column(mod_spatial_title, mod_spatial_var_sel, mod_bound_plot_spatial)
            ))
        b_have_spatial = len(spatial_sections) > 0

    #per tab variable selectors, each filtered by combined field metadata
    c_description_to_field_all = {desc: field for field, desc in c_field_list_all.items()}

    def make_var_selector(name, valid_fields):
        options = {desc: field for desc, field in c_description_to_field_all.items() if field in valid_fields}
        return pn.widgets.MultiChoice(
            name=name,
            options=options,
            value=[list(options.values())[0]] if options else [],
            option_limit=len(options) if options else 1,
            search_option_limit=len(options) if options else 1,
            width=400
        )

    all_fields = df_field_names_combined.index.tolist()

    single_year_fields = df_field_names_combined[df_field_names_combined['Single Year Eligible']].index.tolist()
    b_have_single_year = len(single_year_fields) > 0

    var_selector_bar = make_var_selector('Variable Selector', all_fields)
    var_selector_ts = make_var_selector('Variable Selector', all_fields)
    var_selector_grouped = make_var_selector('Variable Selector', all_fields)
    var_selector_monthly = make_var_selector('Variable Selector', all_fields)

    # Create other plots

    # Timeseries plot
    bound_plot_ts = pn.bind(
        plot_values,
        scenario_list=scen_selector,
        var_list=var_selector_ts,
        unit_choice=unit_selector,
        df_all=df_all_data_combined,
        c_default_units=c_default_units_all,
        ls_comparison=ls_all_comparisons,
        c_field_list=c_field_list_all,
        temp_unit_choice=temp_unit_selector,
    )

    # Time aggregated plot
    bound_plot_grouped = pn.bind(
        plot_time_group,
        scenario_list=scen_selector,
        var_list=var_selector_grouped,
        unit_choice=unit_selector,
        df_all=df_all_data_combined,
        c_default_units=c_default_units_all,
        period_choice=period_selector,
        ls_comparison=ls_all_comparisons,
        c_field_list=c_field_list_all,
        li_wyt_selected=wyt_selector,
        b_wyt_period_year=wyt_period_selector_year,
        li_wyt_period_months=wyt_period_selector,
        temp_unit_choice=temp_unit_selector,
    )

    # Bar plot
    bound_single_var_plot = pn.bind(
        plot_bars,
        df_all=df_all_data_combined,
        period_choice=period_selector,
        var_list=var_selector_bar,
        scenario_list=scen_selector,
        unit_choice=unit_selector,
        stat_choice=bar_stat_sel,
        c_default_units=c_default_units_all,
        ls_comparison=ls_all_comparisons,
        c_field_list=c_field_list_all,
        li_wyt_selected=wyt_selector,
        b_wyt_period_year=wyt_period_selector_year,
        li_wyt_period_months=wyt_period_selector,
        temp_unit_choice=temp_unit_selector,
    )

    # Monthly pattern plot
    bound_monthly_plot = pn.bind(
        monthly_pattern,
        df_all=df_all_data_combined,
        var_list=var_selector_monthly,
        scenario_list=scen_selector,
        unit_choice=unit_selector,
        stat_choice=monthly_stat_sel,
        c_default_units=c_default_units_all,
        ls_comparison=ls_all_comparisons,
        c_field_list=c_field_list_all,
        period_choice=period_selector,
        li_wyt_selected=wyt_selector,
        temp_unit_choice=temp_unit_selector,
    )

    #module specific comparison plots
    c_diff_plots = {'ts':[], 'grouped': [], 'bar': [], 'monthly': []}
    for df_all_m, df_diffs_m, c_units_m, c_fields_m, s_mod_comp_m, scen_names_m, s_mod_m in module_results:
        # remove comparison scen from this module's differences dataframe as all values are zero
        df_diffs_m = df_diffs_m[df_diffs_m.Scenario != s_mod_comp_m]
        #filtered var list
        mod_var_ts = pn.bind(filter_vars_to_module, var_selector_ts, c_fields_m)
        mod_var_grouped = pn.bind(filter_vars_to_module, var_selector_grouped, c_fields_m)
        mod_var_bar = pn.bind(filter_vars_to_module, var_selector_bar, c_fields_m)
        mod_var_monthly = pn.bind(filter_vars_to_module, var_selector_monthly, c_fields_m)

        #time series comparison plots
        c_diff_plots['ts'].append((s_mod_m, s_mod_comp_m, pn.bind(
            plot_values,
            scenario_list=scen_selector, var_list=mod_var_ts,
            unit_choice=unit_selector, df_all=df_diffs_m,
            c_default_units=c_units_m, ls_comparison=[s_mod_comp_m],
            c_field_list=c_fields_m, temp_unit_choice=temp_unit_selector
        )))
        #time aggregated differences plots
        c_diff_plots['grouped'].append((s_mod_m, s_mod_comp_m, pn.bind(
            plot_time_group,
            scenario_list=scen_selector, var_list=mod_var_grouped,
            unit_choice=unit_selector, df_all=df_diffs_m,
            c_default_units=c_units_m, period_choice=period_selector,
            ls_comparison=[s_mod_comp_m], c_field_list=c_fields_m,
            li_wyt_selected=wyt_selector, b_wyt_period_year=wyt_period_selector_year,
            li_wyt_period_months=wyt_period_selector, temp_unit_choice=temp_unit_selector
        )))
        #difference bar plot
        c_diff_plots['bar'].append((s_mod_m, s_mod_comp_m, pn.bind(
            plot_bars,
            df_all=df_diffs_m, period_choice=period_selector,
            var_list=mod_var_bar, scenario_list=scen_selector,
            unit_choice=unit_selector, stat_choice=bar_stat_sel,
            c_default_units=c_units_m, ls_comparison=[s_mod_comp_m],
            c_field_list=c_fields_m, li_wyt_selected=wyt_selector,
            b_wyt_period_year=wyt_period_selector_year,
            li_wyt_period_months=wyt_period_selector, temp_unit_choice=temp_unit_selector
        )))
        #monthly pattern differences plot
        c_diff_plots['monthly'].append((s_mod_m, s_mod_comp_m, pn.bind(
            monthly_pattern,
            df_all=df_diffs_m, var_list=mod_var_monthly,
            scenario_list=scen_selector, unit_choice=unit_selector,
            stat_choice=monthly_stat_sel, c_default_units=c_units_m,
            ls_comparison=[s_mod_comp_m], c_field_list=c_fields_m,
            period_choice=period_selector, li_wyt_selected=wyt_selector, temp_unit_choice=temp_unit_selector
        )))
    #temperature plots
    if b_have_single_year:
        c_field_list_single_year = {f: d for f, d in c_field_list_all.items() if f in single_year_fields}
        o_year_selector = pn.widgets.IntInput(name='Year', value=1923, step=1, start=1922, end=2021, width=100)
        o_reservoir_toggle = pn.widgets.RadioButtonGroup(
            name='Units selector',
            options=['Shasta', 'Folsom'],
            button_style='outline',
            button_type='primary',
            width=200,
            margin=32
        )
        var_selector_single_year = make_var_selector('Variable Selector', single_year_fields)
        # add in other plots
        bound_one_year_plots = pn.bind(
            plot_single_year,
            scenario_list=single_year_scenarios,
            df_all=df_all_data_combined,
            c_field_list=c_field_list_single_year,
            s_reservoir=o_reservoir_toggle,
            i_year=o_year_selector,
            temp_unit_choice=temp_unit_selector
        )

    # Titles for each plot, same order as the plots
    ts_title = pn.pane.Markdown("# Timeseries Plot"
                                )

    grouped_title = pn.bind(create_plot_title,
                            s_title="Time-Aggregated Plot",
                            s_comparison='',
                            s_period=period_selector)

    single_var_title = pn.bind(create_plot_title,
                               s_title="Bar Plot",
                               s_comparison='',
                               s_period=period_selector,
                               s_stat=bar_stat_sel)

    monthly_title = pn.bind(create_plot_title,
                            s_title="Monthly Pattern",
                            s_stat=monthly_stat_sel)

    def make_diff_tabs(ls_diff, s_plot_type, target_column, c_modules):
        if not ls_diff:
            return
        diff_tabs = pn.Tabs(tabs_location='left')
        for s_mod_m, s_mod_comp_m, bound_plot_m in ls_diff:
            mod_title = pn.pane.Markdown(
                f"# {c_modules.get(s_mod_m, s_mod_m)} {s_plot_type} (Difference from {s_mod_comp_m})")
            diff_tabs.append((
                c_modules.get(s_mod_m, s_mod_m),
                pn.Column(mod_title, bound_plot_m)
            ))
        target_column.append(pn.Column(pn.pane.Markdown("### Modules"), diff_tabs))

    # Lay out the plots and titles
    # These will hold the plots
    single_var_plots = pn.Column()
    timeseries_plots = pn.Column()
    grouped_plots = pn.Column()
    exceedance_plots = pn.Tabs(tabs_location='left')
    monthly_plots = pn.Column()
    if b_have_spatial:
        spatial_plots = pn.Tabs(tabs_location='left')
    if b_have_single_year:
        one_year_plots = pn.Column()

    # Add everything into these containers
    # Bar
    single_var_widgets = pn.Row(bar_stat_sel, var_selector_bar)
    single_var_plots.append(single_var_widgets)
    single_var_plots.append(pn.Column(single_var_title, bound_single_var_plot))
    make_diff_tabs(c_diff_plots['bar'], "Bar Plot", single_var_plots, c_modules)

    # Timeseries
    timeseries_plots.append(pn.Column(ts_title, var_selector_ts, bound_plot_ts))
    make_diff_tabs(c_diff_plots['ts'], "Timeseries", timeseries_plots, c_modules)

    # Time-Aggregated
    grouped_plots.append(pn.Column(grouped_title, var_selector_grouped, bound_plot_grouped))
    make_diff_tabs(c_diff_plots['grouped'], "Time-Aggregated Plot", grouped_plots, c_modules)

    # Monthly
    monthly_plots.append(pn.Row(monthly_stat_sel))
    monthly_plots.append(pn.Column(monthly_title, var_selector_monthly, bound_monthly_plot))
    make_diff_tabs(c_diff_plots['monthly'], "Monthly Pattern", monthly_plots, c_modules)

    for s_module_name, section in exceedance_sections:
        exceedance_plots.append((s_module_name, section))

    if b_have_single_year:
        one_year_plots.append(pn.Row(o_year_selector, o_reservoir_toggle))
        one_year_plots.append(bound_one_year_plots)

    if b_have_spatial:
        for s_module_name, section in spatial_sections:
            spatial_plots.append((s_module_name, section))

    # create the tabs with each page of plots
    ls_tabs = [
        ('Bar Plot', single_var_plots),
        ('Timeseries', timeseries_plots),
        ('Time-Aggregated', grouped_plots),
        ('Monthly Pattern', monthly_plots),
        ('Exceedance', pn.Column(pn.pane.Markdown("### Modules"), exceedance_plots)),
    ]
    if b_have_single_year:
        ls_tabs.append(('Temperature Plots', one_year_plots))
    if b_have_spatial:
        ls_tabs.append(('Spatial', pn.Column(pn.pane.Markdown("### Modules"), spatial_plots)))

    metadata_plots = pn.Tabs(tabs_location='left')
    for s_module_name, panel in ls_metadata_panels:
        metadata_plots.append((s_module_name, panel))

    ls_tabs.append(('Metadata', pn.Column(pn.pane.Markdown("### Modules"), metadata_plots)))

    tabs = pn.Tabs(*ls_tabs)

    # append the tabs to the row
    tabs_row.append(tabs)
    tabs_row.param.trigger("objects")


def add_run_names_widget(event, s_module, file_picker_col_tracker, run_name_col_tracker, field_col_tracker, file_picker_display, header, tabs_row, run_name_column, field_column):
    """
    Creates the widgets to take in the file names for one module

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
    file_picker_column = file_picker_display[0]

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
            # check that a module pickle file has been selected
            if not any ('module_' in file for file in files):
                error_message = pn.pane.Markdown("## Please select the module pickel file (module_<name>.pkl).")
                field_column.append(error_message)
                field_col_tracker.append("error_message")
                return None
            result = update_run_names(event, file_picker_column, file_picker_col_tracker, run_name_column, run_name_col_tracker, field_column, field_col_tracker, file_picker_display, header, tabs_row, s_module)
            return result
        # add option to override TR_fields.txt
        override_TR_fields_instructions = pn.pane.Markdown("""
        # OPTIONAL override default fields:""", renderer='markdown')
        if s_module in ('calsim', 'hydro_out', 'hydro_in'):
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
        if s_module in ('calsim', 'hydro_out', 'hydro_in'): #todo add hydro in to this section
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

        if s_module in ('calsim', 'hydro_out', 'hydro_in'):
            add_field_text = pn.widgets.TextAreaInput(name='', placeholder='S_FOLSM\tFolsom Storage\nS_SHSTA\tShasta Storage', auto_grow=True, width=500)
        elif s_module in ('temperature', 'salinity'):
            add_field_text = pn.widgets.TextAreaInput(name='', placeholder='Stor-Temp/FOLSOM/STORAGE\tFolsom Storage\nAMERICAN/BLW FOLSOM DAM/FLOW\tAmerican River below Folsom Dam Flow', auto_grow=True, width=500)

        field_column.append(add_field_text)
        field_col_tracker.append("add_field_text")
    else:
        clear_container(event,file_picker_display)
        return None

    return {
        'file_picker_column': file_picker_column,
        'file_picker_col_tracker': file_picker_col_tracker,
        'run_name_column': run_name_column,
        'run_name_col_tracker': run_name_col_tracker,
        'field_column': field_column,
        'field_col_tracker': field_col_tracker,
        'file_picker_display': file_picker_display,
        'header': header,
        'tabs_row': tabs_row,
        's_module': s_module,
    }


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
    df_all_data: DataFrame
        DataFrame with all of the data that can be plotted for this module
    df_diffs: DataFrame
        Dataframe of difference from comparison scenario data for this module
    c_default_units: dict
        Dictionary of default units for all fields in this module
    c_field_list: dict
        Dictionary of field name and descriptions for this module
    s_comparison: str
        Name of comparison scenario for this module
    scenario_names: list
        List of scenario names loaded for this module
    s_module: str
        Which module this data belongs to (passed through unchanged, for use by the caller
        when combining results across modules)
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
            error_message = pn.pane.Markdown("## Please make sure that exactly one file is marked for comparison for each module.")
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
        elif s_module == 'hydro_in':
            c_tr_fields = get_trend_fields('TR_fields_hydro_in.txt')

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
            elif s_module == 'hydro_in':
                c_dss_paths = {
                    "et": '',
                    "eto": ''
                }
                for s_file in os.listdir(files[file_index]):
                    s_curr_path = os.path.join(folders[file_index], s_file)
                    if os.path.isfile(s_curr_path):
                        if 'RefETo' in s_file or 'refeto' in s_file.lower():
                            c_dss_paths['eto'] = s_curr_path
                        elif 'ET' in s_file:
                            c_dss_paths['et'] = s_curr_path

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
            c_tr_fields = get_trend_fields('TR_fields_CSH_out.txt')

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

    return df_all_data, df_diffs, c_default_units, c_field_list, s_comparison, scenario_names, s_module