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
from arcpy import GetParameter
from arcpy import GetParameterAsText
from arcpy import SetProgressor
from reach_utlities import get_reach_line_fc

# provide a more interesting message
SetProgressor(type='default', message='firing up the redonkulator...stand by')

# collect input parameters and run functions
get_reach_line_fc(
    access_fc=GetParameter(0),
    aoi_polygon=GetParameter(1),
    hydro_network=GetParameter(2),
    reach_hydroline_fc=GetParameterAsText(3),
    reach_invalid_tbl=GetParameterAsText(4)
)