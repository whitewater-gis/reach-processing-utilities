"""
author:     Joel McCune (joel.mccune+aw@gmail.com)
dob:        03 Dec 2014
purpose:    Test the utilities to clean up and enhance the spatial component of the American Whitewater reaches
            data set.

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
import unittest
import arcpy
import reach_utlities

# variables
access_fc = r'D:\spatialData\aw\aw (owner).sde\aw.owner.accesses'
hydro_net = r'D:\spatialData\aw\aw (owner).sde\aw.owner.Hydrography\aw.owner.HYDRO_NET'
test_gdb = arcpy.env.scratchGDB
test_dir = arcpy.env.scratchFolder
single_reach_id = '00003491'


class test_case_reach_3491(unittest.TestCase):

    def test_reach_has_putin_and_takeout(self):

        status = reach_utlities.validate_has_access(
            reach_id=single_reach_id,
            access_fc=access_fc
        )
        self.assertTrue(status, 'It appears there is not a putin and takeout for reach id {}'.format(single_reach_id))

    # select reach 3491 putin and takeout
    putin_lyr = arcpy.MakeFeatureLayer_management(
        in_features=access_fc,
        out_layer='putin',
        where_clause="putin='{}'".format(single_reach_id)
    )[0]
    takeout_lyr = arcpy.MakeFeatureLayer_management(
        in_features=access_fc,
        out_layer='takeout',
        where_clause="takeout='{}'".format(single_reach_id)
    )[0]

    def test_reach_accesses_coincident(self):
        self.assertTrue(
            reach_utlities.validate_conicidence(single_reach_id, access_fc, hydro_net),
            'Reach id {} appears to have a putin and takeout.'.format(single_reach_id)
        )

    def test_reach_putin_upstream_from_takeout(self):
        self.assertTrue(
            reach_utlities.validate_putin_upstream_from_takeout(
                putin_geometry=arcpy.CopyFeatures_management(self.putin_lyr, arcpy.Geometry())[0],
                takeout_geometry=arcpy.CopyFeatures_management(self.takeout_lyr, arcpy.Geometry())[0],
                hydro_network=hydro_net
            ),
            'The putin appears to be upstream of the takeout for reach id {}.'.format(single_reach_id)
        )

    def test_get_reach_geometry(self):
        reach = reach_utlities.process_reach(
            reach_id=single_reach_id,
            access_fc=access_fc,
            hydro_network=hydro_net
        )
        # initially set to true and if any of the segments do not have a geometry, fail
        status = True
        for geometry in reach['geometry_list']:
            if not geometry.length:
                status = False

        self.assertTrue(status, 'At least one of the returned geometries appears not to have a length for reach id {}'.format(single_reach_id))