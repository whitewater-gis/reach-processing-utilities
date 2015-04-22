"""
author:     Joel McCune (joel.mccune+gis@gmail.com)
dob:        13 Dec 2014
purpose:    Provide a tool wrapper for updating the tracking field in the HUC4 feature class for downloaded regions.

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
from reach_utilities import update_download_tracking

# run function
update_download_tracking(
    hydrolines_feature_class=GetParameterAsText(0),
    huc4_feature_class=GetParameterAsText(1)
)