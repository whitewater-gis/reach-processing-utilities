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
import os
import arcpy
import reach_utlities

# variables
access_fc = r'D:\spatialData\aw\aw (owner).sde\aw.owner.accesses'
hydro_net = r'D:\spatialData\aw\aw (owner).sde\aw.owner.Hydrography\aw.owner.HYDRO_NET'
test_gdb = arcpy.env.scratchGDB
test_dir = arcpy.env.scratchFolder


class test_case_subregion_1708(unittest.TestCase):

    # local variables
    aoi_subregion_1708 = r'G:\spatialData\aw\HUC4-1708.lyr'
    reach_fc = os.path.join(test_gdb, 'test_hydroline')
    reach_tbl = os.path.join(test_gdb, 'test_invalid')

    def test_get_reach_line_fc(self):
        """
        test to see if the primary function works...and modify to fit
        :return: success or failure
        """
        reach_utlities.get_reach_line_fc(
            access_fc=access_fc,
            aoi_polygon=self.aoi_subregion_1708,
            hydro_network=hydro_net,
            reach_hydroline_fc=self.reach_fc,
            reach_invalid_tbl=self.reach_tbl
        )

        self.assertTrue(arcpy.GetCount_management(self.reach_fc))

#
#     def test_reach_has_putin_and_takeout(self):
#
#         status = reach_utlities.validate_has_access(
#             reach_id=self.test_reach_id,
#             access_fc=self.test_access_fc
#         )
#         self.assertTrue(status, 'It appears there is not a putin and takeout for reach id {}'.format(self.test_reach_id))
#
#     def test_is_putin_upstream_from_takeout(self):
#
#         # get geometry object for putin and takeout
#         takeout_geometry = arcpy.Select_analysis(self.test_access_fc, arcpy.Geometry(),  "takeout='{}'".format(self.test_reach_id))[0]
#         putin_geometry = arcpy.Select_analysis(self.test_access_fc, arcpy.Geometry(),  "putin='{}'".format(self.test_reach_id))[0]
#
#         status = reach_utlities.validate_putin_upstream_from_takeout(
#             putin_geometry=putin_geometry,
#             takeout_geometry=takeout_geometry,
#             hydro_network=self.test_hydro_network
#         )
#         self.assertTrue(status, 'It appears the putin is not upstream of the takeout on the network for reach id {}'. format(self.test_reach_id))
#
#     def test_get_reach_geometry(self):
#
#         reach = reach_utlities.process_reach(
#             reach_id=self.test_reach_id,
#             access_fc=self.test_access_fc,
#             hydro_network=self.test_hydro_network
#         )
#
#         status = True
#
#         for geometry in reach['geometry_list']:
#             if not geometry.length:
#                 status = False
#
#         self.assertTrue(status, 'One of the returned geometries appears not to have a length for reach id {}'.format(self.test_reach_id))
#
#     def test_get_reach_fc(self):
#
#         output_fc = os.path.join(self.gdb_scratch, 'reach_line_subset')
#
#         reach_utlities.get_reach_line_fc(
#             access_fc=self.test_access_subset_fc,
#             hydro_network=self.test_hydro_network,
#             output_hydroline_fc=output_fc,
#             output_invalid_reach_table=os.path.join(self.gdb_scratch, 'reach_invalid')
#         )
#
#         self.assertTrue(arcpy.GetCount_management(output_fc))