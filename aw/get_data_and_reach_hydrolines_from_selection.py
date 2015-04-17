"""
author:     Joel McCune (joel.mccune+aw@gmail.com)
dob:        04 Dec 2014
purpose:    Provide a tool wrapper for extracting and saving reach hydrolines.

    Copyright 2014 Joel McCune

    Licensed under the Apache License, Version 2.0 (the "License");
    you may not use this file except in compliance with the License.
    You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

    Unless required by applicable law or agreed to in writing, software
    distributed under the License is distributed on an "AS IS" BASIS,
    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
    See the License for the specific language governing permissions and
    limitations under the License.
"""
# import modules
import arcpy
import os.path
import reach_utlities

# get variables
huc4_layer = arcpy.GetParameter(0)
access_fc = arcpy.GetParameter(1)
output_dir = arcpy.GetParameterAsText(2)

# provide a more intersting message
arcpy.SetProgressor(type='default', message='firing up the redonkulator...stand by')

# get list of awid's selected from

# for every HUC selected
for huc4 in [row[0] for row in arcpy.da.SearchCursor(huc4_layer, 'HUC4')]:

    # download and prep the data
    subregion_gdb = reach_utlities.get_subregion_data(
        huc4=huc4,
        output_dir=output_dir
    )

    # provide a more intersting message
    arcpy.SetProgressor(type='default', message='firing up the redonkulator...stand by')

    # collect input parameters and run functions
    reach_utlities.get_reach_line_fc(
        access_fc=access_fc,
        huc4_fc=os.path.join(subregion_gdb, 'WBDHU4'),
        hydro_network=os.path.join(subregion_gdb, 'Hydrography', 'HYDRO_NET'),
        output_hydroline_fc=os.path.join(subregion_gdb, 'reach_hydroline{}'.format(huc4)),
        output_invalid_reach_table=os.path.join(subregion_gdb, 'reach_invalid{}'.format(huc4))
    )