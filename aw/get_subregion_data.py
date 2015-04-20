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
import re

# provide a more intersting message
arcpy.SetProgressor(type='default', message='firing up the redonkulator...stand by')

# save path to geodatabase in a variable
sde = arcpy.GetParameterAsText(1)

# collect input parameters and run functions
reach_utlities.get_and_append_subregion_data(
    huc4=arcpy.GetParameterAsText(0),
    master_geodatabase=sde
)

# get network path taking into account it may be in an SDE
for top_dir, dir_list, obj_list in arcpy.da.Walk(sde):

    # iterate the objects
    for obj in obj_list:

        # use regular expression matching to filter out HYDRO_NET
        if re.match(r'^.+HYDRO_NET', obj):

            # save full path to a variable
            hydro_net = '{}\{}'.format(top_dir, obj)

        # if the hydro net does not exist
        else:

            # throw an error
            raise Exception('HYDRO_NET geometric network does not appear to exist in {}'.format(sde))

# update the geometric network with the flow direction
arcpy.SetFlowDirection_management(hydro_net, 'WITH_DIGITIZED_DIRECTION')