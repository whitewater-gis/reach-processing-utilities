"""
author:     Joel McCune (joel.mccune+gis@gmail.com)
dob:        13 Dec 2014
purpose:    Provide a tool wrapper for downloading subregion data from the USGS and preparing data for analysis.

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
# import minimal modules
from arcpy import da, GetParameter, GetParameterAsText
from reach_utlities import get_and_append_subregion_data, update_flow_direction

# get the list of huc4 codes from the huc4 polygon layer
huc4_list = [row[0] for row in da.SearchCursor(GetParameter(0), 'HUC4')]

# save path to geodatabase in a variable
sde = GetParameterAsText(1)

# for every HUC
for huc4 in huc4_list:

    # download, prep and append the data to the master dataset
    get_and_append_subregion_data(
        huc4=huc4,
        master_geodatabase=sde
    )

# update the flow direction
update_flow_direction(sde)