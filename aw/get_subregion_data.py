"""
author:     Joel McCune (joel.mccune+aw@gmail.com)
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
# import modules
import arcpy
import reach_utlities

# provide a more intersting message
arcpy.SetProgressor(type='default', message='firing up the redonkulator...stand by')

# collect input parameters and run functions
reach_utlities.get_subregion_data(
    huc4=arcpy.GetParameterAsText(0),
    output_dir=arcpy.GetParameterAsText(1)
)