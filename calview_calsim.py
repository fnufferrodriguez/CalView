from src.widgets import *
import panel as pn
from os import path
import holoviews as hv
from functools import partial


# Set some default behavior
pn.extension(sizing_mode='stretch_width')
pn.extension(notifications=True)
# change default colors to first go through Reclamation colors and then original default colors for line plots
hv.opts.defaults(hv.opts.Curve(color=hv.Cycle(['#003E51', '#007396', '#C69214', '#FF671F', '#215732', '#4C12A1', '#9A3324'] + hv.Cycle.default_cycles["default_colors"])))
hv.opts.defaults(hv.opts.Bars(color=hv.Cycle(['#003E51', '#007396', '#C69214', '#FF671F', '#215732', '#4C12A1', '#9A3324'] + hv.Cycle.default_cycles["default_colors"])))
hv.opts.defaults(hv.opts.Scatter(color=hv.Cycle(['#003E51', '#007396', '#C69214', '#FF671F', '#215732', '#4C12A1', '#9A3324'] + hv.Cycle.default_cycles["default_colors"])))

# Visualizer formatting code

# Flag for temperature version
c_flag = {'calsim':True}

# path for the compiled executable to find logo
s_logo_path = path.abspath(path.join(path.dirname(__file__), 'inputs', 'usbr_logo.jpg'))

template = pn.template.BootstrapTemplate(
    title="DSS Results Viewer for CalSim 3",
    logo=s_logo_path,
    favicon=s_logo_path,
    header_background='white',
    header_color='black'
)

# Create row that can be added to template to refresh header(template itself is static)
header = pn.Row()
# Now the row can be edited in trigger functions and will refresh to show header/sliders after file picker tab
template.main.append(header)

# Create a row to hols the tabs
tabs_row = pn.Row()
template.main.append(tabs_row)

# Define a Panel Column to hold widgets for the file picker tab
file_picker_column = pn.Column()
file_picker_col_tracker = []

# Define panel file_picker_column to hold file name text input
run_name_column = pn.Column()
run_name_col_tracker = []

# Define panel file_picker_column to hold field selector drop down
field_column = pn.Column()
field_col_tracker = []

###### File Picker Tab code ##################
#Title for file picker tab
file_picker_title = pn.pane.Markdown("""
    # Select Files
""")
file_picker_title_tooltip = pn.widgets.TooltipIcon(value='Once a set of DSS files have been read in the first time, they are saved to .pkl files that are much quicker to read in later. Note that you cannot pull additional fields when using the pkl files, the DSS files must be re-read in.', margin=0)

#Create radio button widget to select running with old or new scenario
old_new_sel = pn.widgets.RadioButtonGroup(
    #name='',
    value="New CalSim outputs",
    button_style='outline',
    button_type='primary',
    options=["New CalSim outputs", "Previously generated visuals"],
    max_width=1000
)

#Add all widgets to file_picker_column
file_picker_column.append(pn.Row(file_picker_title, file_picker_title_tooltip))
file_picker_col_tracker.append("file_picker_title")
file_picker_column.append(old_new_sel)
file_picker_col_tracker.append("old_new_sel")
file_picker_column.append(pn.Row(None, None))
file_picker_col_tracker.append("instructions")
file_picker_column.append(None)
file_picker_col_tracker.append("dss_file")

#Watch the old_new_sel widget and call remove_widget function to update dss_file if a change event occurs
choice_watcher = old_new_sel.param.watch(partial(update_dss_file_widget, file_picker_column=file_picker_column, file_picker_col_tracker=file_picker_col_tracker), ['value'], onlychanged=False)
old_new_sel.value = "New CalSim outputs"
# name of the scenario that will be compared to, Baseline as a default

#Add Done Selecting Files button
done_selecting = pn.widgets.Button(name="Continue", max_width=1000, button_type='primary')

file_picker_column.append(done_selecting)
file_picker_col_tracker.append("done_selecting")

# Set up the initial layout
file_picker_display = pn.Row(file_picker_column, pn.Column(run_name_column, field_column), margin=20)

template.main.append(file_picker_display)
#When done selecting file button is clicked, add text boxes for user to name each file's run
done_selecting.on_click(partial(add_run_names_widget, file_picker_col_tracker=file_picker_col_tracker, run_name_col_tracker=run_name_col_tracker, field_col_tracker=field_col_tracker,
                                file_picker_display=file_picker_display, header=header, tabs_row=tabs_row, c_flag=c_flag))

# when this file is ran, the site will automatically launch
pn.serve(template, show=True)
