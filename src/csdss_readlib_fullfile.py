import datetime
from dateutil.relativedelta import relativedelta
from pydsstools.heclib.dss import HecDss
import pandas as pd
import numpy as np
import time
import pickle
from multiprocessing import Pool
from os import path
import warnings
from collections import Counter
import geopandas as gpd

def get_trend_fields(s_fields_file):
    """
    Gets the fields from TR_fields.txt

    Parameters
    ----------
    s_fields_file: str
        name of fields file

    Returns
    -------
    c_tr_fields: dict
        Dictionary of fields and descriptions
    """
    # dictionary to hold fields and description in the form {field: description}
    c_tr_fields = {}
    try:
        # this line is needed for the file to correctly be found once this is bundled into an executable
        s_path_to_fields = path.abspath(path.join(path.dirname(__file__), '..', 'inputs', s_fields_file))
        with open(s_path_to_fields, "r") as f:
            lines = f.readlines()
    except:
        print('Failed to open TR_fields.txt')

    for line in lines:

        line = line.strip()
        curr_field = line.split('\t')
        if len(curr_field) != 2:
            continue
        else:
            field, description = curr_field
        if '/' not in field:
            # this happens for calsim and those are always uppercase
            field = field.strip(' ').upper()
        else:
            field = field.strip(' ')
        description = description.strip('\n')
        description = description + ' (' + field + ')'
        c_tr_fields[field] = description

    for field, description in c_tr_fields.items():
        if field == '':
            c_tr_fields.pop(field)
    return c_tr_fields

def get_shapefile(s_shapefile_name):
    """
    Loads a shapefile by name and returns a cleand GeoDataFrame with just ID column and geometry, reprojected to lat/lon for spatial plots.
    Parameters
    ----------
    s_shapefile_name: str (name of the shapefile to load as stored in the field metadata)

    Returns
    -------
    o_gdf: GeoDataFrame (ID column + 'geometry')
    s_id_col: str (name of the ID column, for merging)
    """
    c_shapefile_id_cols = {
        'WBAs': 'WBA_ID',
        'DemandUnits~2015': 'DU_ID',
    }
    c_shapefile_paths = {
        'WBAs': path.join('WBAs', 'WBAs', 'WBAs.shp'),
        'DemandUnits~2015':path.join('DUs', 'DemandUnits~2015.shp')
    }
    if s_shapefile_name not in c_shapefile_id_cols:
        print(f"No shapefile mapping for '{s_shapefile_name}'")
        return None, None

    s_id_col = c_shapefile_id_cols[s_shapefile_name]
    s_path = path.abspath(path.join(path.dirname(__file__), c_shapefile_paths[s_shapefile_name]))

    if not path.exists(s_path):
        return None, None

    o_gdf = gpd.read_file(s_path)
    o_gdf = o_gdf[[s_id_col, 'geometry']].to_crs(4326)
    return o_gdf, s_id_col

def pickler(append_list, baseline_stack, c_default_units, c_field_list, s_module):
    """
    Creates a single pickle file of DSS data per module

    Parameters
    ----------
    append_list: list
        List of dataframes of DSS data
    baseline_stack: list
        List of baseline scenario multiple times
    c_default_units: dict
        Dictionary of default units for each field
    c_field_list: dict
        Dictionary of fields and descriptions
    s_module: str
        Key from c_flag of module type (ex 'calsim')
    Returns
    -------
    none
    """
    df_all_data = pd.concat(append_list)
    df_all_data.reset_index(drop=True, inplace=True)
    df_all_data.index.name = "Index"

    df_baseline_stack = pd.concat(baseline_stack)
    df_baseline_stack.reset_index(drop=True, inplace=True)
    df_baseline_stack.index.name = "Index"

    # Calc diffs for the alts vs baseline

    # num_fixed = # of columns that are the same in all cases
    num_fixed = 7

    # columns that shouldn't be subtracted
    li_wyt_cols = [index+num_fixed for index, colname in enumerate(df_all_data.iloc[:, num_fixed:]) if c_default_units[colname] == 'NONE']
    li_fixed_cols_indices = list(range(0, num_fixed)) + li_wyt_cols
    df_fixed_cols = df_all_data.iloc[:, li_fixed_cols_indices]

    li_numeric_col_indices = [i for i in range(len(df_all_data.columns)) if i not in li_fixed_cols_indices]
    df_all_data_numeric = df_all_data.iloc[:, li_numeric_col_indices]

    df_baseline_numeric = df_baseline_stack.iloc[:, li_numeric_col_indices]
    df_diff_numeric = df_all_data_numeric.subtract(df_baseline_numeric)
    df_diffs = pd.concat([df_fixed_cols, df_diff_numeric], axis=1)

    #bundle everything into one dict
    c_module_data = {
        'values': df_all_data,
        'diffs': df_diffs,
        'units': c_default_units,
        'fields': c_field_list
    }

    pickled_module = open(path.abspath(f"module_{s_module}.pkl"), "wb")
    pickle.dump(c_module_data, pickled_module)
    pickled_module.close()

def load_pickles(ls_files, s_module):
    """
    Reads in the pickle file for a module

    Parameters
    ----------
    ls_files: list
        List of pickled files, can be empty
    s_module: str
        Key from c_flag of module type (ex 'calsim')

    Returns
    -------
    df_all_data: DataFrame
        All of the DSS file data
    df_diffs: DataFrame
        Differences data
    c_default_units: dict
        Dictionary of default units for each field
    c_field_list: dict
        Dictionary of fields and descriptions
    """
    if not ls_files:
        s_module_path = path.abspath(f"module_{s_module}.pkl")
    else:
        #ls_files should contain exactly one file: the module pickle
        s_module_path = ls_files[0]

    try:
        load_module = open(s_module_path, 'rb')
        c_module_data = pickle.load(load_module)
        load_module.close()
        df_all_data = c_module_data['values']
        df_diffs = c_module_data['diffs']
        c_default_units = c_module_data['units']
        c_field_list = c_module_data['fields']
    except FileNotFoundError:
        print(f'Missing "module_{s_module}.pkl". Please run pickler')
        return None, None, None, None
    except (KeyError, pickle.UnpicklingError) as e:
        print(f'Pickle file for module "{s_module}" is malformed or from an older version: {e}')
        return None, None, None, None

    return (df_all_data, df_diffs, c_default_units, c_field_list)


def single_file_pull(dss_file, c_target_ts_list, scenario_name, s_module):
    """
    Reads in a single DSS file

    Parameters
    ----------
    dss_file: str
        Path to DSS file
    c_target_ts_list: dict
        Dictionary of fields to pull
    scenario_name: str
        Name for this scenario
    s_module: str
        Key from c_flag of module type (ex 'calsim')

    Returns
    -------
    df_ts: DataFrame
        Timeseries data that was pulled
    c_target_ts_list_final: dict
        Dictionary with the fields that were actually pulled
    c_default_units: dict
        Dictionary of default units for each field
    """

    fid = HecDss.Open(dss_file)

    # getPathnamesDict returns a dict of pathnames.
    pathNames = fid.search_path()

    dfPaths = pd.DataFrame(pathNames, columns=["AllPaths"])

    # is this is empty, the dss file is empty
    if dfPaths.empty:
        raise Exception(f'No pathnames found in {dss_file}')

    # If the interpreter gives an error
    dfPaths[['blank1', 'A', 'B', 'C', 'D', 'E', 'F', 'blank2']] = \
            dfPaths['AllPaths'].str.split("/", expand=True)
    dfPaths = dfPaths.drop(columns=['AllPaths', 'blank1', 'blank2'])

    dfPaths = dfPaths.sort_values(by=['B', 'D'])
    dfPaths = dfPaths.drop_duplicates(subset=['B', 'C'])
    dfPaths = dfPaths.reset_index()
    dfPaths.drop('index', axis=1, inplace=True)

    # dataframe to hold all the data pulled
    df_ts = pd.DataFrame()

    # list of fields we found, start with all
    c_target_ts_list_final = c_target_ts_list.copy()

    # to hold the units
    c_default_units = {}

    for b_part in c_target_ts_list.keys():
        try:
            if s_module == 'calsim':
                c_part = dfPaths[dfPaths['B'] == b_part]['C'].iloc[0]
                a_part = dfPaths[dfPaths['B'] == b_part]['A'].iloc[0]
                f_part = dfPaths[dfPaths['B'] == b_part]['F'].iloc[0]
                e_part = dfPaths[dfPaths['B'] == b_part]['E'].iloc[0]
                target_pathName = f'/{a_part}/{b_part}/{c_part}//{e_part}/{f_part}/'

            elif s_module == 'temperature':
                f_part = dfPaths[dfPaths[['A', 'B', 'C']].agg('/'.join, axis=1) == b_part]['F'].iloc[0]
                e_part = dfPaths[dfPaths[['A', 'B', 'C']].agg('/'.join, axis=1) == b_part]['E'].iloc[0]
                target_pathName = f'/{b_part}//{e_part}/{f_part}/'

            elif s_module == 'salinity':
                f_part = dfPaths[dfPaths[['A', 'B', 'C']].agg('/'.join, axis=1) == b_part]['F'].iloc[0]
                # pull out the 1 month e part. (1MON for dss6 and 1Month for dss7)
                e_part = dfPaths[dfPaths[['A', 'B', 'C']].agg('/'.join, axis=1) == b_part]['E'].values
                e_part = [part for part in e_part if '1M' in part][0]
                target_pathName = f'/{b_part}//{e_part}/{f_part}/'
            elif s_module == 'hydro_out':
                c_part = dfPaths[dfPaths['B'] == b_part]['C'].iloc[0]
                a_part = dfPaths[dfPaths['B'] == b_part]['A'].iloc[0]
                f_part = dfPaths[dfPaths['B'] == b_part]['F'].iloc[0]
                target_pathName = f'/{a_part}/{b_part.upper()}/{c_part}//1MON/{f_part}/'

            # pull current path
            working_ts = fid.read_ts(target_pathName, trim_missing=True)

            # add in units
            c_default_units[b_part] = working_ts.data_units

            # add it to full dataframe
            ol_times = [o_time.datetime() for o_time in working_ts.times]
            df_working = pd.DataFrame(working_ts.values.astype('float64'), index=ol_times, columns=[b_part])
            df_ts = df_ts.merge(right=df_working, how='outer', left_index=True, right_index=True)

        except:
            # it is fails, remove it from the list
            c_target_ts_list_final.pop(b_part)

    # Close the dss file
    fid.close()

    if not df_ts.empty:
        # move dates back by one day
        df_ts.index = df_ts.index + datetime.timedelta(days=-1)

    # if the dataframe is empty, raise an error
    else:
        if s_module == 'calsim':
            # if calsim fully fail
            raise Exception(f'No fields from field list found in {dss_file}')
        else:
            warnings.warn(f'No fields from field list found in {dss_file}')

    return df_ts, c_target_ts_list_final, c_default_units


def file_reader(runs: list[list], c_field_list, s_comparison, s_module):
    """
    reads in the list of runs. can be multiproccessing or not by changing multiprocess to True.
    Parameters
    ----------
    runs: list
        list of runs and run names in the form [["Description_1", ("File_1.dss")], ...] or [["Description_1", {'calsim': '...', ...}], ...]
    c_field_list: dict
        dictionary of fields and descriptions {field: description, ...}
    s_comparison: str
        name of the comparison scenario
    s_module: str
        Key from c_flag of module type (ex 'calsim')

    Returns
    -------
    append_list: list
        list of the dataframes of each run
    baseline_stack:
        a list of dataframes of the comparison scenerio as many times as there are runs
    c_default_units: dict
        dictionary of the default units for each field
    c_field_list_final: dict
        dictionary of the final version of c_field_list

    """
    results = {}
    c_default_units_all = {}
    if s_module in ('calsim', 'salinity', 'hydro_out'):
        c_field_list_final = c_field_list.copy()
    elif s_module == 'temperature':
        c_calsim_fields = {field: c_field_list[field] for field in c_field_list if field.split('/')[0] == 'CALSIM'}
        c_hec5q_fields = {field: c_field_list[field] for field in c_field_list if field not in c_calsim_fields}
        c_field_list_final = {}
    multiprocess = False

    # Non-multi version for debug
    if multiprocess == False:
        for run in runs:
            print('Working on', run[0])

            if s_module == 'calsim':
                df_all_data, c_target_ts_list, c_default_units = \
                    single_file_pull(run[1], c_field_list, run[0], s_module)

                # Since these are all monthly, we can drop any rows with nans and only keep rows with all the data
                df_all_data.dropna(how='any', inplace=True)

                # Add in the columns not pulled from the DSS file
                # Calender year, month, water year, contract year
                df_all_data.insert(0, 'JanDecYear', df_all_data.index.year)
                df_all_data.insert(0, 'Month', df_all_data.index.month)
                df_all_data.insert(0, 'Year', df_all_data.index.year)
                df_all_data.insert(0, 'MarFebYear', np.where(df_all_data['Month'] >= 3, df_all_data['Year'], df_all_data['Year'] - 1))
                df_all_data.insert(0, 'OctSeptYear', np.where(df_all_data['Month'] <= 9, df_all_data['Year'], df_all_data['Year'] + 1))

                # add scenario name
                df_all_data.insert(0, 'Scenario', run[0])

                # make date a column
                df_all_data['Date'] = df_all_data.index
                date_temp = df_all_data.pop('Date')
                df_all_data.insert(0, 'Date', date_temp)

                # make sure to remove ones that were not found
                c_field_list_final = {field: c_field_list_final[field] for field in c_field_list_final if field in c_target_ts_list}

                # add into dictionary to store
                c_default_units_all.update(c_default_units)
                results[run[0]] = df_all_data

            elif s_module == 'temperature':
                # run[0] will be name and run[1] will be the dictionary

                # from calsim, we only care about shatabin or wyts
                df_calsim_SV_result, c_calsim_SV_target_ts_list, c_calsim_SV_default_units = single_file_pull(run[1]['calsim_SV'], c_calsim_fields, run[0], s_module)
                df_calsim_DV_result, c_calsim_DV_target_ts_list, c_calsim_DV_default_units = single_file_pull(run[1]['calsim_DV'], c_calsim_fields, run[0], s_module)

                # everything else we will try to pull from the other files
                df_SR_WQ_result, c_SR_WQ_target_ts_list, c_SR_WQ_default_units = single_file_pull(run[1]['SR_WQ_Report'], c_hec5q_fields, run[0], s_module)
                df_AR_WQ_result, c_AR_WQ_target_ts_list, c_AR_WQ_default_units = single_file_pull(run[1]['AR_WQ_Report'], c_hec5q_fields, run[0], s_module)
                df_s_CALSIMII_result, c_s_CALSIMII_target_ts_list, c_s_CALSIMII_default_units = single_file_pull(run[1]['s_CALSIMII_HEC5Q'], c_hec5q_fields, run[0], s_module)
                df_a_CALSIMII_result, c_a_CALSIMII_target_ts_list, c_a_CALSIMII_default_units = single_file_pull(run[1]['a_CALSIMII_HEC5Q'], c_hec5q_fields, run[0], s_module)

                o_field_counts = Counter(c_SR_WQ_target_ts_list.keys())
                o_field_counts.update(c_AR_WQ_target_ts_list.keys())
                o_field_counts.update(c_s_CALSIMII_target_ts_list.keys())
                o_field_counts.update(c_a_CALSIMII_target_ts_list.keys())
                sl_duplicate_fields = [item for item, count in o_field_counts.items() if count > 1]

                for field in sl_duplicate_fields:
                    if field in c_SR_WQ_target_ts_list:
                        # what we will rename to
                        s_new_field = field + ' SR'

                        # update dataframe
                        df_SR_WQ_result.rename(columns={field: s_new_field}, inplace=True)

                        # update dictionaries
                        c_SR_WQ_target_ts_list[s_new_field] = c_SR_WQ_target_ts_list[field][:-1] + ' SR)'
                        c_SR_WQ_target_ts_list.pop(field)
                        c_SR_WQ_default_units[s_new_field] = c_SR_WQ_default_units[field]
                        c_SR_WQ_default_units.pop(field)
                    if field in c_AR_WQ_target_ts_list:
                        # what we will rename to
                        s_new_field = field + ' AR'

                        # update dataframe
                        df_AR_WQ_result.rename(columns={field: s_new_field}, inplace=True)

                        # update dictionaries
                        c_AR_WQ_target_ts_list[s_new_field] = c_AR_WQ_target_ts_list[field][:-1] + ' AR)'
                        c_AR_WQ_target_ts_list.pop(field)
                        c_AR_WQ_default_units[s_new_field] = c_AR_WQ_default_units[field]
                        c_AR_WQ_default_units.pop(field)

                    if field in c_s_CALSIMII_target_ts_list:
                        # what we will rename to
                        s_new_field = field + ' SR in'

                        # update dataframe
                        df_s_CALSIMII_result.rename(columns={field: s_new_field}, inplace=True)

                        # update dictionaries
                        c_s_CALSIMII_target_ts_list[s_new_field] = c_s_CALSIMII_target_ts_list[field][:-1] + ' SR in)'
                        c_s_CALSIMII_target_ts_list.pop(field)
                        c_s_CALSIMII_default_units[s_new_field] = c_s_CALSIMII_default_units[field]
                        c_s_CALSIMII_default_units.pop(field)
                    if field in c_a_CALSIMII_target_ts_list:
                        # what we will rename to
                        s_new_field = field + ' AR in'

                        # update dataframe
                        df_a_CALSIMII_result.rename(columns={field: s_new_field}, inplace=True)

                        # update dictionaries
                        c_a_CALSIMII_target_ts_list[s_new_field] = c_a_CALSIMII_target_ts_list[field][:-1] + ' AR in)'
                        c_a_CALSIMII_target_ts_list.pop(field)
                        c_a_CALSIMII_default_units[s_new_field] = c_a_CALSIMII_default_units[field]
                        c_a_CALSIMII_default_units.pop(field)

                # Crop the calsim results to the rows with all non-nans
                df_calsim_SV_result.dropna(how='any', inplace=True)
                df_calsim_DV_result.dropna(how='any', inplace=True)

                # Crop the input files to the range of the output files
                if not df_a_CALSIMII_result.empty:
                    df_a_CALSIMII_result = df_a_CALSIMII_result[df_AR_WQ_result.index[0]: df_AR_WQ_result.index[-1]]
                if not df_s_CALSIMII_result.empty:
                    df_s_CALSIMII_result = df_s_CALSIMII_result[df_SR_WQ_result.index[0]: df_SR_WQ_result.index[-1]]

                # Combine the data from all the DSS files
                # Keep everything from one data frame but other fields from the rest, so we only have one copy of dat/Year/Month/etc.
                df_all_data = pd.concat([df_s_CALSIMII_result, df_a_CALSIMII_result, df_SR_WQ_result, df_AR_WQ_result, df_calsim_SV_result, df_calsim_DV_result], axis=1, join='outer')

                # Add in the columns not pulled from the DSS file
                # Calender year, month, water year, contract year
                df_all_data.insert(0, 'JanDecYear', df_all_data.index.year)
                df_all_data.insert(0, 'Month', df_all_data.index.month)
                df_all_data.insert(0, 'Year', df_all_data.index.year)
                df_all_data.insert(0, 'MarFebYear', np.where(df_all_data['Month'] >= 3, df_all_data['Year'], df_all_data['Year'] - 1))
                df_all_data.insert(0, 'OctSeptYear', np.where(df_all_data['Month'] <= 9, df_all_data['Year'], df_all_data['Year'] + 1))

                # add scenario name
                df_all_data.insert(0, 'Scenario', run[0])

                # make date a column
                df_all_data['Date'] = df_all_data.index
                date_temp = df_all_data.pop('Date')
                df_all_data.insert(0, 'Date', date_temp)

                # combine all field lists together
                c_field_list_curr = c_calsim_SV_target_ts_list | c_calsim_DV_target_ts_list | c_SR_WQ_target_ts_list | c_AR_WQ_target_ts_list | c_s_CALSIMII_target_ts_list | c_a_CALSIMII_target_ts_list
                c_field_list_final.update(c_field_list_curr)


                # add units into dictionary to store
                c_default_units_all.update(c_calsim_SV_default_units)
                c_default_units_all.update(c_calsim_DV_default_units)
                c_default_units_all.update(c_SR_WQ_default_units)
                c_default_units_all.update(c_AR_WQ_default_units)
                c_default_units_all.update(c_s_CALSIMII_default_units)
                c_default_units_all.update(c_a_CALSIMII_default_units)

                results[run[0]] = df_all_data
            elif s_module == 'salinity':
                df_flow_result, c_flow_target_ts_list, c_flow_default_units = single_file_pull(run[1]['flow'], c_field_list, run[0], s_module)
                df_ec_result, c_ec_target_ts_list, c_ec_default_units = single_file_pull(run[1]['ec'], c_field_list, run[0], s_module)

                # Combine the data from all the DSS files
                # Keep everything from one data frame but other fields from the rest, so we only have one copy of dat/Year/Month/etc.
                df_all_data = pd.concat([df_flow_result, df_ec_result], axis=1, join='outer')

                # Add in the columns not pulled from the DSS file
                # Calender year, month, water year, contract year
                df_all_data.insert(0, 'JanDecYear', df_all_data.index.year)
                df_all_data.insert(0, 'Month', df_all_data.index.month)
                df_all_data.insert(0, 'Year', df_all_data.index.year)
                df_all_data.insert(0, 'MarFebYear', np.where(df_all_data['Month'] >= 3, df_all_data['Year'], df_all_data['Year'] - 1))
                df_all_data.insert(0, 'OctSeptYear', np.where(df_all_data['Month'] <= 9, df_all_data['Year'], df_all_data['Year'] + 1))

                # add scenario name
                df_all_data.insert(0, 'Scenario', run[0])

                # make date a column
                df_all_data['Date'] = df_all_data.index
                date_temp = df_all_data.pop('Date')
                df_all_data.insert(0, 'Date', date_temp)

                # combine all field lists together
                c_field_list_curr = c_flow_target_ts_list | c_ec_target_ts_list
                c_field_list_final.update(c_field_list_curr)

                # add units into dictionary to store
                c_default_units_all.update(c_flow_default_units)
                c_default_units_all.update(c_ec_default_units)

                results[run[0]] = df_all_data
            elif s_module == 'hydro_out':
                df_all_data, c_target_ts_list, c_default_units = single_file_pull(run[1], c_field_list, run[0], s_module)

                #assume all monthly data but TODO check this
                df_all_data.dropna(how='any', inplace=True)

                # Add in the columns not pulled from the DSS file
                # Calender year, month, water year, contract year
                df_all_data.insert(0, 'JanDecYear', df_all_data.index.year)
                df_all_data.insert(0, 'Month', df_all_data.index.month)
                df_all_data.insert(0, 'Year', df_all_data.index.year)
                df_all_data.insert(0, 'MarFebYear', np.where(df_all_data['Month'] >= 3, df_all_data['Year'], df_all_data['Year'] - 1))
                df_all_data.insert(0, 'OctSeptYear', np.where(df_all_data['Month'] <= 9, df_all_data['Year'], df_all_data['Year'] + 1))

                # add scenario name
                df_all_data.insert(0, 'Scenario', run[0])

                # make a date column
                df_all_data['Date'] = df_all_data.index
                date_temp = df_all_data.pop('Date')
                df_all_data.insert(0, 'Date', date_temp)

                # remove ones that werent found
                c_field_list_final = {field: c_field_list_final[field] for field in c_field_list_final if field in c_target_ts_list}

                #add to dictionary to store
                c_default_units_all.update(c_default_units)
                results[run[0]] = df_all_data
    # else:
    #     # create pool
    #     pool = Pool()
    #     # Create and start runs
    #     for run in runs:
    #         print(f'Working on {run[0]} - multiproc')
    #         result, c_target_ts_list, c_default_units = pool.apply_async(single_file_pull,
    #                                                                    args=(run[1], c_field_list, run[0], s_flag)).get()
    #
    #         # make sure to remove ones that were not found
    #         c_field_list_final = {field: c_field_list_final[field] for field in c_field_list_final if field in c_target_ts_list}
    #
    #         # add into dictionary to store
    #         c_default_units_all.update(c_default_units)
    #         results[run[0]] = result
    #
    #     # close the process pool
    #     pool.close()
    #     # wait for all tasks to finish
    #     pool.join()

    # since the set up of the temperature version allowed for fields to be in one run but not another, we need to remove any that are like this
    if s_module in ('temperature', 'salinity'): #todo might need to add hydro to this

        # count the number of times each column is used
        ls_all_fields = np.concatenate([df.columns for df in results.values()], axis=None)
        o_field_counts = Counter(ls_all_fields)

        # if its not one for each run, we will remove
        ls_fields_remove = [field for field in o_field_counts if o_field_counts[field] != len(runs)]

        # remove from dictionaries and dataframes
        for field in ls_fields_remove:
            c_field_list_final.pop(field)
            c_default_units_all.pop(field)
            for run in results:
                results[run].drop(field, axis=1, inplace=True, errors='ignore')

    append_list = []
    baseline_stack = []

    # add calculated fields
    for i in range(len(runs)):
        results[runs[i][0]], c_field_list_temp, c_default_units_temp = calculated_fields(results[runs[i][0]], c_field_list_final, c_default_units_all)

    c_field_list_final = c_field_list_temp
    c_default_units_all = c_default_units_temp

    for i in range(len(runs)):
        append_list.append(results[runs[i][0]])
        baseline_stack.append(results[s_comparison])
    # print(f"Run time for pulling DSS data with multiprocessing = "
    #       f"{(time.time() - start_time)} seconds")
    print(f'Added {list(set(c_field_list_final.keys()) - set(c_field_list.keys()))} to field list.')
    print(f'Removed {list(set(c_field_list.keys()) - set(c_field_list_final.keys()))} from field list.')

    # add s_comparison to c_default_units so we have it stored
    c_default_units_all['comparison scenario'] = s_comparison

    # add the run names in
    for run_name, file_name in runs:
        if s_module == 'calsim':
            c_default_units_all[run_name] = path.basename(file_name)
        elif s_module == 'temperature':
            c_default_units_all[run_name] = file_name
        elif s_module == 'salinity':
            c_default_units_all[run_name] = file_name
        elif s_module == 'hydro_out':
            c_default_units_all[run_name] = path.basename(file_name)

    return append_list, baseline_stack, c_default_units_all, c_field_list_final


def calculated_fields(df_all, c_field_list, c_default_units):
    """
    Calculates calculated fields

    Parameters
    ----------
    df_all: DataFrame
        Data to calculate fields from
    c_field_list: dict
        Dictionary of fields and descriptions
    c_default_units: dict
            Dictionary of default units for each field

    Returns
    -------
    df_all: DataFrame
        Data including calculated fields
    c_field_list: dict
        Dictionary of fields and descriptions with calculated fields
    c_default_units: dict
            Dictionary of default units for each field with calculated fields
    """
    # Copy input dictionaries
    c_field_list_curr = c_field_list.copy()
    c_default_units_curr = c_default_units.copy()

    # dictionary of what fields each calculated field needs TODO specify which are for which calview version
    c_fields_for_calculated = {
        'Total System Storage SWP and CVP': ['S_TRNTY', 'S_SHSTA', 'S_OROVL', 'S_FOLSM', 'S_SLUIS_CVP', 'S_SLUIS_SWP'],
        'Total Exports SWP and CVP': ['C_CAA003_SWP', 'C_DMC003', 'C_CAA003_CVP'],
        'Total San Luis Storage SWP and CVP': ['S_SLUIS_CVP', 'S_SLUIS_SWP'],
        'Flow Shortage on Sac Reg for Salinity': ['RSREQSACDV', 'JPREQSACDV', 'EMREQSACDV', 'COREQSACDV', 'C_SAC041', 'SP_SAC083_YBP037'],
        'Flow Shortage on X2 Delta Req Outflow': ['MRDO_FINALDV', 'NDOI'],
        'MRDO_SHORT': ['MRDO_FINALDV', 'NDOI_MIN'],
        'Combined Madera and Friant-Kern Canals Diversion': ['D_MLRTN_FRK000', 'D_MLRTN_MDC006'],
        'Stanislaus River Delivery - Oakdale North / SSJID 1+2': ['D_STS059_OAK001', 'D_SSJ004_61_PA1', 'D_WDWRD_61_PA3', 'D_WTPDGT_61_NU2'],
        'CVP Delivery Total': ['DEL_CVP_TOTAL_N', 'DEL_CVP_TOTAL_S'],
        'CVP Delivery PMI N (w CCWD)': ['DEL_CVP_PMI_N', 'D420'],
        'CVP Delivery North (w CCWD)': ['DEL_CVP_TOTAL_N', 'DEL_CVP_PMI_N', 'DEL_CVP_PMI_N_WAMR', 'D420'],
        'ShaSpill': ['CALSIM/C_SHSTA/CHANNEL', 'CALSIM/C_KSWCK_ADD/FLOW-ADDITIONAL-INSTREAM', 'CALSIM/C_SAC120_ADD/FLOW-ADDITIONAL-INSTREAM',
                     'CALSIM/C_NTOMA_ADD/FLOW-ADD-INSTREAM', 'CALSIM/C_AMR004_ADD/FLOW-ADDITIONAL-INSTREAM', 'CALSIM/NDOI_ADD_CVP/FLOW-CHANNEL',
                     'CALSIM/C_SAC017_ADD/FLOW-ADDITIONAL-INSTREAM', 'CALSIM/S_FOLSM/STORAGE', 'CALSIM/S_SHSTALEVEL5DV/STORAGE-LEVEL',
                     'CALSIM/S_FOLSMLEVEL5DV/STORAGE-LEVEL', 'CALSIM/S_SHSTA/STORAGE'],
        'Cold Water Profiles': ['Stor-Temp/Stor-Temp/Storage.lt.45.00F SR', 'Stor-Temp/Stor-Temp/Storage.lt.50.00F SR', 'Stor-Temp/Stor-Temp/Storage.lt.55.00F SR',
                                       'Stor-Temp/Stor-Temp/Storage.lt.60.00F SR', 'Stor-Temp/Stor-Temp/Storage.lt.65.00F SR', 'Stor-Temp/Stor-Temp/Storage.lt.70.00F SR',
                                       'Stor-Temp/Stor-Temp/Storage.lt.99.00F SR', 'Stor-Temp/Stor-Temp/Storage.lt.45.00F AR', 'Stor-Temp/Stor-Temp/Storage.lt.50.00F AR',
                                       'Stor-Temp/Stor-Temp/Storage.lt.55.00F AR', 'Stor-Temp/Stor-Temp/Storage.lt.60.00F AR', 'Stor-Temp/Stor-Temp/Storage.lt.65.00F AR',
                                       'Stor-Temp/Stor-Temp/Storage.lt.70.00F AR', 'Stor-Temp/Stor-Temp/Storage.lt.99.00F AR'],
        'SWP/CVP South Delta Pumping Flow (Total Export)': ['HYDROV8.2.2/CLIFTON_COURT/FLOW-MEAN', 'HYDROV8.2.2/CHDMC006/FLOW-MEAN'],
        'Combined Old and Middle River (OMR) Flow': ['HYDROV8.2.2/ROLD024/FLOW-MEAN', 'HYDROV8.2.2/RMID015_144/FLOW-MEAN', 'HYDROV8.2.2/RMID015_145/FLOW-MEAN'],
        'Old River at Rock Slough Chloride': ['QUALV8.2.2/ROLD024/EC-MEAN']
    }

    # loop through the calculate fields and try and add them
    for calculated_field in list(c_fields_for_calculated.keys()):
        # grab list of required fields
        sl_needed_fields = c_fields_for_calculated[calculated_field]

        # check if every needed field has been pulled
        if set(sl_needed_fields).issubset(set(c_field_list.keys())):

            # get the units
            ls_units = [c_default_units[var] for var in sl_needed_fields]

            # make sure all the units match
            if len(set(ls_units)) > 1:
                print('All units do not match for calculated variable: ', calculated_field)

            # add the default units
            c_default_units_curr[calculated_field] = ls_units[0]

            # add the new calculated variable to the field list dictionary
            c_field_list_curr[calculated_field] = calculated_field + ' (Calculated Field)'

            # add the calculated field to the dataframe
            match calculated_field:
                case 'Total System Storage SWP and CVP':
                    df_all[calculated_field] = df_all['S_TRNTY'] + df_all['S_SHSTA'] + df_all['S_OROVL'] + df_all['S_FOLSM'] + df_all['S_SLUIS_CVP'] + df_all['S_SLUIS_SWP']
                case 'Total Exports SWP and CVP':
                    df_all[calculated_field] = df_all['C_CAA003_SWP'] + df_all['C_DMC003'] + df_all['C_CAA003_CVP']
                case 'Total San Luis Storage SWP and CVP':
                    df_all[calculated_field] = df_all['S_SLUIS_CVP'] + df_all['S_SLUIS_SWP']
                case 'Flow Shortage on Sac Reg for Salinity':
                    df_all[calculated_field] = np.maximum(df_all[['RSREQSACDV', 'JPREQSACDV', 'EMREQSACDV', 'COREQSACDV']].max(axis=1) - (df_all['C_SAC041'] + df_all['SP_SAC083_YBP037']), 0)
                case 'Flow Shortage on X2 Delta Req Outflow':
                    df_all[calculated_field] = np.maximum(df_all['MRDO_FINALDV'] - df_all['NDOI'], 0)
                case 'MRDO_SHORT':
                    df_all[calculated_field] = df_all['MRDO_FINALDV'] - df_all['NDOI_MIN']
                case 'Combined Madera and Friant-Kern Canals Diversion':
                    df_all[calculated_field] = df_all['D_MLRTN_FRK000'] + df_all['D_MLRTN_MDC006']
                case 'Stanislaus River Delivery - Oakdale North / SSJID 1+2':
                    df_all[calculated_field] = df_all['D_STS059_OAK001'] + df_all['D_SSJ004_61_PA1'] + df_all['D_WDWRD_61_PA3'] + df_all['D_WTPDGT_61_NU2']
                case 'CVP Delivery Total':
                    df_all[calculated_field] = df_all['DEL_CVP_TOTAL_N'] + df_all['DEL_CVP_TOTAL_S']
                case 'CVP Delivery PMI N (w CCWD)':
                    df_all[calculated_field] = df_all['DEL_CVP_PMI_N'] + df_all['D420']
                case 'CVP Delivery North (w CCWD)':
                    df_all[calculated_field] = df_all['DEL_CVP_TOTAL_N'] - df_all['DEL_CVP_PMI_N'] + df_all['DEL_CVP_PMI_N_WAMR'] + df_all['D420']
                case 'ShaSpill':
                    # Calculate all the interim fields for the spills
                    df_temp = df_all[['Scenario', 'Date'] + sl_needed_fields].dropna(how='all', subset=sl_needed_fields)
                    df_temp['FolFC'] = np.where(abs(df_temp['CALSIM/S_FOLSM/STORAGE'] - df_temp['CALSIM/S_FOLSMLEVEL5DV/STORAGE-LEVEL']) < 0.1, 1, 0)
                    df_temp['ShaFC'] = np.where(abs(df_temp['CALSIM/S_SHSTA/STORAGE'] - df_temp['CALSIM/S_SHSTALEVEL5DV/STORAGE-LEVEL']) < 0.1, 1, 0)
                    df_temp['DO_CVP'] = np.where(df_temp['FolFC'] + df_temp['ShaFC'] > 0.5, df_temp[['CALSIM/NDOI_ADD_CVP/FLOW-CHANNEL', 'CALSIM/C_SAC017_ADD/FLOW-ADDITIONAL-INSTREAM']].min(axis=1), 0)
                    df_temp['AmerExc'] = np.where(df_temp['FolFC'] > 0.5, df_temp[['CALSIM/C_NTOMA_ADD/FLOW-ADD-INSTREAM', 'CALSIM/C_AMR004_ADD/FLOW-ADDITIONAL-INSTREAM']].min(axis=1), 0)
                    df_temp['SacExc'] = np.where(df_temp['ShaFC'] > 0.5, df_temp[['CALSIM/C_SHSTA/CHANNEL', 'CALSIM/C_KSWCK_ADD/FLOW-ADDITIONAL-INSTREAM', 'CALSIM/C_SAC120_ADD/FLOW-ADDITIONAL-INSTREAM']].min(axis=1), 0)
                    df_temp['TotalExc'] = df_temp['SacExc'] + df_temp['AmerExc']
                    df_temp['TrueSpill'] = df_temp[['TotalExc', 'DO_CVP']].min(axis=1)

                    # Calculate the three spills
                    df_temp['ShaSpill'] = np.where(df_temp['TrueSpill'] > 0, df_temp['SacExc'] * df_temp['TrueSpill'] / (df_temp['SacExc'] + df_temp['AmerExc']), 0)
                    df_temp['FolSpill'] = np.where(df_temp['TrueSpill'] > 0, df_temp['AmerExc'] * df_temp['TrueSpill'] / (df_temp['SacExc'] + df_temp['AmerExc']), 0)
                    df_temp['CVPSpill'] = df_temp['ShaSpill'] + df_temp['FolSpill']

                    # also add FolSpill and CVP spill to the fields
                    c_default_units_curr['FolSpill'] = c_default_units_curr['ShaSpill']
                    c_default_units_curr['CVPSpill'] = c_default_units_curr['ShaSpill']
                    c_field_list_curr['FolSpill'] = 'FolSpill (Calculated Field)'
                    c_field_list_curr['CVPSpill'] = 'CVPSpill (Calculated Field)'

                    # Add Shata spill back into the original data frame
                    df_all = df_all.merge(df_temp[['Scenario', 'Date', 'ShaSpill', 'FolSpill', 'CVPSpill']], how='outer', on=['Date', 'Scenario'])
                case 'Cold Water Profiles':
                    # this calculated field is a little different
                    # We don't actually want Cold Water Profiles Shasta as a field, so first we remove it
                    c_field_list_curr.pop(calculated_field)
                    c_default_units_curr.pop(calculated_field)

                    # first add all of them in as fields with units of TAF
                    ls_cold_water_field = ['<45 (Shasta)', '45-50 (Shasta)', '50-55 (Shasta)', '55-60 (Shasta)', '60-65 (Shasta)', '65-70 (Shasta)', '70+ (Shasta)',
                                           '<45 (Folsom)', '45-50 (Folsom)', '50-55 (Folsom)', '55-60 (Folsom)', '60-65 (Folsom)', '65-70 (Folsom)', '70+ (Folsom)']
                    for field in ls_cold_water_field:
                        c_field_list_curr[field] = field
                        c_default_units_curr[field] = 'TAF'

                    # now we actually calculate them for shasta
                    df_all['<45 (Shasta)'] = df_all['Stor-Temp/Stor-Temp/Storage.lt.45.00F SR'] / 1000
                    df_all['45-50 (Shasta)'] = (df_all['Stor-Temp/Stor-Temp/Storage.lt.50.00F SR'] - df_all['Stor-Temp/Stor-Temp/Storage.lt.45.00F SR']) / 1000
                    df_all['50-55 (Shasta)'] = (df_all['Stor-Temp/Stor-Temp/Storage.lt.55.00F SR'] - df_all['Stor-Temp/Stor-Temp/Storage.lt.50.00F SR']) / 1000
                    df_all['55-60 (Shasta)'] = (df_all['Stor-Temp/Stor-Temp/Storage.lt.60.00F SR'] - df_all['Stor-Temp/Stor-Temp/Storage.lt.55.00F SR']) / 1000
                    df_all['60-65 (Shasta)'] = (df_all['Stor-Temp/Stor-Temp/Storage.lt.65.00F SR'] - df_all['Stor-Temp/Stor-Temp/Storage.lt.60.00F SR']) / 1000
                    df_all['65-70 (Shasta)'] = (df_all['Stor-Temp/Stor-Temp/Storage.lt.70.00F SR'] - df_all['Stor-Temp/Stor-Temp/Storage.lt.65.00F SR']) / 1000
                    df_all['70+ (Shasta)'] = (df_all['Stor-Temp/Stor-Temp/Storage.lt.99.00F SR'] - df_all['Stor-Temp/Stor-Temp/Storage.lt.70.00F SR']) / 1000

                    # calculate for folsom
                    df_all['<45 (Folsom)'] = df_all['Stor-Temp/Stor-Temp/Storage.lt.45.00F AR'] / 1000
                    df_all['45-50 (Folsom)'] = (df_all['Stor-Temp/Stor-Temp/Storage.lt.50.00F AR'] - df_all['Stor-Temp/Stor-Temp/Storage.lt.45.00F AR']) / 1000
                    df_all['50-55 (Folsom)'] = (df_all['Stor-Temp/Stor-Temp/Storage.lt.55.00F AR'] - df_all['Stor-Temp/Stor-Temp/Storage.lt.50.00F AR']) / 1000
                    df_all['55-60 (Folsom)'] = (df_all['Stor-Temp/Stor-Temp/Storage.lt.60.00F AR'] - df_all['Stor-Temp/Stor-Temp/Storage.lt.55.00F AR']) / 1000
                    df_all['60-65 (Folsom)'] = (df_all['Stor-Temp/Stor-Temp/Storage.lt.65.00F AR'] - df_all['Stor-Temp/Stor-Temp/Storage.lt.60.00F AR']) / 1000
                    df_all['65-70 (Folsom)'] = (df_all['Stor-Temp/Stor-Temp/Storage.lt.70.00F AR'] - df_all['Stor-Temp/Stor-Temp/Storage.lt.65.00F AR']) / 1000
                    df_all['70+ (Folsom)'] = (df_all['Stor-Temp/Stor-Temp/Storage.lt.99.00F AR'] - df_all['Stor-Temp/Stor-Temp/Storage.lt.70.00F AR']) / 1000

                    # Remove the original fields, we don't want to be able to plot them
                    for field in sl_needed_fields:
                        c_field_list_curr.pop(field)
                        c_default_units_curr.pop(field)

                    # drop from the dataframe as well
                    df_all.drop(sl_needed_fields, axis=1, inplace=True)
                case 'SWP/CVP South Delta Pumping Flow (Total Export)':
                    df_all[calculated_field] = df_all['HYDROV8.2.2/CLIFTON_COURT/FLOW-MEAN'] - df_all['HYDROV8.2.2/CHDMC006/FLOW-MEAN']
                case 'Combined Old and Middle River (OMR) Flow':
                    df_all[calculated_field] = df_all['HYDROV8.2.2/RMID015_144/FLOW-MEAN'] - df_all['HYDROV8.2.2/RMID015_145/FLOW-MEAN'] + df_all['HYDROV8.2.2/ROLD024/FLOW-MEAN']
                case 'Old River at Rock Slough Chloride':
                    df_all[calculated_field] = np.maximum(0.285 * df_all['QUALV8.2.2/ROLD024/EC-MEAN'] - 50, 0.15 * df_all['QUALV8.2.2/ROLD024/EC-MEAN'] - 12)
                    c_default_units_curr[calculated_field] = 'MG/L'
                case _:
                    pass
    # Dynamically create combined DP fields (EXT + INT) per zone for hydro version
    ls_dp_ext_fields = [f for f in c_field_list_curr.keys() if f.startswith('DP_') and f.endswith('_EXT')]

    for ext_field in ls_dp_ext_fields:
        zone = ext_field[len('DP_'):-len('_EXT')]  # e.g. '02', '07N', '60S'
        int_field = f'DP_{zone}_INT'
        combined_field = f'DP_{zone}'

        # only create the combined field if both EXT and INT exist in the data
        if int_field in c_field_list_curr and ext_field in df_all.columns and int_field in df_all.columns:

            # check units match before combining
            ext_unit = c_default_units_curr.get(ext_field)
            int_unit = c_default_units_curr.get(int_field)
            if ext_unit != int_unit:
                print(f'Units do not match for combined DP field {combined_field}: '
                      f'{ext_field}={ext_unit}, {int_field}={int_unit}')

            # calculate the combined field
            df_all[combined_field] = df_all[ext_field] + df_all[int_field]

            # add to field list and units dictionaries
            c_field_list_curr[combined_field] = f'DP {zone} (Calculated Field)'
            c_default_units_curr[combined_field] = ext_unit

    return df_all, c_field_list_curr, c_default_units_curr
