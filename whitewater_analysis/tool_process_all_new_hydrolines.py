"""
author:     Joel McCune (joel.mccune+gis@gmail.com)
dob:        04 Dec 2014
purpose:    Provide a tool wrapper for extracting and saving new reach hydrolines.

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
from utilities import process_all_new_hydrolines

# collect input parameters and run functions
process_all_new_hydrolines(
    access_fc=GetParameterAsText(0),
    huc4_subregion_directory=GetParameterAsText(1),
    huc4_feature_class=GetParameterAsText(2),
    reach_hydroline_fc=GetParameterAsText(3),
    reach_invalid_tbl=GetParameterAsText(4)
)
