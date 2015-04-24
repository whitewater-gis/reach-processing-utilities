"""
author:     Joel McCune (joel.mccune+gis@gmail.com)
dob:        13 Dec 2014
purpose:    Provide a tool wrapper for appending data to the master dataset and preparing it for analysis.

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
from arcpy import GetParameterAsText

from whitewater_analysis.utilities.reach_utilities import append_subregion_data


# save path to geodatabase in a variable
sde = GetParameterAsText(1)

# append the subregion data to the master
append_subregion_data(GetParameterAsText(0), sde)

# update the flow direction
#update_flow_direction(sde)