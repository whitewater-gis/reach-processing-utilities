"""
author:     Joel McCune (joel.mccune+gis@gmail.com)
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
from utilities import process_reaches

from arcpy import AddMessage

# collect input parameters and run functions
process_reaches(
    access_fc=GetParameter(0),
    hydro_network=GetParameter(1),
    reach_hydroline_fc=GetParameterAsText(2),
    centroid_fc=GetParameterAsText(3)
)

AddMessage('starting processing')
