from src.widgets import *
import panel as pn
from os import path
import holoviews as hv
from functools import partial

import pyproj
# Set some default behavior
pn.extension(sizing_mode='stretch_width')
pn.extension(notifications=True)
# change default colors to first go through Reclamation colors and then original default colors for line plots
hv.opts.defaults(hv.opts.Curve(color=hv.Cycle(['#003E51', '#007396', '#C69214', '#FF671F', '#215732', '#4C12A1', '#9A3324'] + hv.Cycle.default_cycles["default_colors"])))
hv.opts.defaults(hv.opts.Bars(color=hv.Cycle(['#003E51', '#007396', '#C69214', '#FF671F', '#215732', '#4C12A1', '#9A3324'] + hv.Cycle.default_cycles["default_colors"])))
hv.opts.defaults(hv.opts.Scatter(color=hv.Cycle(['#003E51', '#007396', '#C69214', '#FF671F', '#215732', '#4C12A1', '#9A3324'] + hv.Cycle.default_cycles["default_colors"])))

# Visualizer formatting code

# Flag for hydro version
c_flag = {'calsim':False, #todo change back to hydro_in
          'hydro_out':True}
c_modules = {
    'calsim':"CalSim Outputs",
    'hydro_out':"CalSim Hydro Outputs"
}

# path for the compiled executable to find logo
s_logo_path = path.abspath(path.join(path.dirname(__file__), 'inputs', 'usbr_logo.jpg'))

template = pn.template.BootstrapTemplate(
    title="CalView Hydro",
    logo=s_logo_path,
    favicon=s_logo_path,
    header_background='white',
    header_color='black'
)

module_column = pn.Column()
header = pn.Row()
tabs_row = pn.Row()

# Shared widgets - used by all modules

# Create radio button widget to select running with old or new scenario
old_new_sel = pn.widgets.RadioButtonGroup(
    # name='',
    value="New outputs",
    button_style='outline',
    button_type='primary',
    options=["New outputs", "Previously generated visuals"],
    max_width=1000
)
#Add Done Selecting Files button
done_selecting = pn.widgets.Button(name="Continue", max_width=1000, button_type='primary')
done_selecting_row = pn.Row(done_selecting)

#Row for done naming button
done_naming_row = pn.Row()

#row for naming instructions
naming_instructions_row = pn.Row()

c_module_containers = {}
c_old_new_watcher = []
c_done_selecting_watchers = []


def build_module_widgets(s_module):
    """Builds and registers the per-module stage for one module (file picker, additional fields, metadata).
    Returns the display row for that module."""

    file_picker_column = pn.Column()
    file_picker_col_tracker = []
    run_name_column = pn.Column()
    run_name_col_tracker = []
    field_column = pn.Column()
    field_col_tracker = []

    #file picker tab code
    file_picker_title = pn.pane.Markdown("""## Select Files""")
    file_picker_title_tooltip = pn.widgets.TooltipIcon(
        value='Once a set of DSS files have been read in the first time, they are saved to .pkl files that are much quicker to read in later. Note that you cannot pull additional fields when using the pkl files, the DSS files must be re-read in.',
        margin=0)

    # Add all widgets to file_picker_column
    file_picker_column.append(pn.Row(file_picker_title, file_picker_title_tooltip))
    file_picker_col_tracker.append("file_picker_title")
    file_picker_column.append(pn.Row(None, None))
    file_picker_col_tracker.append("instructions")
    file_picker_column.append(None)
    file_picker_col_tracker.append("dss_file")

    # Watch the old_new_sel widget and call remove_widget function to update dss_file if a change event occurs
    choice_watcher = old_new_sel.param.watch(
        partial(update_dss_file_widget, s_module=s_module, file_picker_column=file_picker_column,
                file_picker_col_tracker=file_picker_col_tracker), ['value'], onlychanged=False)
    old_new_sel.value = "New outputs"
    c_old_new_watcher.append(choice_watcher)

    c_module_containers[s_module] = {
        'header': header,
        'tabs_row': tabs_row,
        'file_picker_title': file_picker_title,
        'file_picker_title_tooltip': file_picker_title_tooltip,
        'file_picker_column': file_picker_column,
        'file_picker_col_tracker': file_picker_col_tracker,
        'run_name_column': run_name_column,
        'run_name_col_tracker': run_name_col_tracker,
        'field_column': field_column,
        'field_col_tracker': field_col_tracker,
        'old_new_sel': old_new_sel,
    }

    display = pn.Row(file_picker_column, pn.Column(run_name_column, field_column), margin=20)
    c_module_containers[s_module]['file_picker_display'] = display
    return display

#teardown, rebuild per module pieces
def build_module_sections(event=None):
    #clear out everything from previous build
    for _ in range(len(module_column)):
        module_column.pop(0)
    c_module_containers.clear()

    #remove old on_click callbacks tied to previous module set
    for watcher in c_done_selecting_watchers:
        done_selecting.param.unwatch(watcher)
    c_done_selecting_watchers.clear()

    # remove old watchers tied to the shared old_new_sel from the previous build
    for watcher in c_old_new_watcher:
        old_new_sel.param.unwatch(watcher)
    c_old_new_watcher.clear()

    # make sure the button and module selector are visible again on rebuild
    if done_selecting not in done_selecting_row:
        done_selecting_row.append(done_selecting)
    #show module selector
    module_column.append(mod_selector_row)
    # show old_new_sel once, above all module sections
    module_column.append(pn.pane.Markdown("## Run type"))
    module_column.append(old_new_sel)

    for s_module, is_active in c_flag.items():
        if not is_active:
            continue

        display = build_module_widgets(s_module)

        module_column.append(pn.pane.Markdown(f"## {c_modules.get(s_module, s_module)}"))
        module_column.append(display)

    module_column.append(done_selecting_row)  # clear the button's row once clicked, using the top-level helper instead of a closure

    #wipes the whole page and builds stage 2 fresh
    watcher = done_selecting.on_click(partial(
        build_naming_stage,
        c_module_containers=c_module_containers,
        c_flag=c_flag,
        module_column=module_column,
        c_modules=c_modules,
        header=header,
        tabs_row=tabs_row,
        old_new_sel=old_new_sel
    ))
    c_done_selecting_watchers.append(watcher)

    module_column.param.trigger("objects")

mod_selector = module_selector(c_flag)
mod_selector.param.watch(build_module_sections, 'value')
mod_selector_title = pn.pane.Markdown("""# Select Modules""")
mod_selector_row = pn.Column(pn.Row(mod_selector_title), pn.Row(mod_selector))
template.main.append(module_column)
template.main.append(header)
template.main.append(tabs_row)

build_module_sections()

# when this file is ran, the site will automatically launch
pn.serve(template, show=True)
