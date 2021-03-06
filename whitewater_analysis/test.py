"""
author:     Joel McCune (joel.mccune+whitewater-gis@gmail.com)
dob:        03 Dec 2014
purpose:    Test the utilities to clean up and enhance the spatial component of whitewater recreation reaches
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

# import system modules
import os.path
import unittest
import time
import arcpy
import json
import uuid

# import local modules
from .utilities.reach_processing_utilities import *

# variables
hydro_net = r'D:\dev\reach-processing-tools\test_data\1711.gdb\Hydrography\HYDRO_NET'
huc4 = r'H:\reach-processing\aggregate\data_v3.gdb\WBDHU4'
test_gdb = arcpy.env.scratchGDB
test_dir = arcpy.env.scratchFolder
test_reach_id = 2204


class TestCaseDownload2204(unittest.TestCase):
    """
    Validate getting a new reach from American Whitewater.
    """
    reach_id = 2204
    reach = Reach(2204)
    reach.download()

    def test_name(self):
        self.assertEqual(self.reach.name, 'Above Brandeberry Creek to Hyas Creek')

    def test_difficulty_combined(self):
        self.assertEqual(self.reach.difficulty.maximum, 'V')

    def test_difficulty_maximum(self):
        self.assertEqual(self.reach.difficulty.combined, 'II-V')

    def test_point_putin_coordinates(self):
        putin_coordinates = [point.coordinates for point in self.reach.points if 'putin' in point.tags][0]
        self.assertEqual(putin_coordinates)

    def test_point_takeout_coordinates(self):
        takeout_coordinates = [point.coordinates for point in self.reach.points if 'takeout' in point.tags][0]
        self.assertEqual(takeout_coordinates)


class TestCaseValidation(unittest.TestCase):
    """
    Test validation functions with data created to break in the right ways.
    """
    access_validate = r'D:\dev\reach-processing-tools\test_data\test_data.gdb\access_validate_test'

    def test_validate_has_putin_and_takeout_false(self):
        reach = Reach(1)
        result = reach._validate_has_putin_and_takeout()
        self.assertFalse(result)

    def test_validate_has_putin_and_takeout_true(self):
        reach = Reach(4)
        result = reach._validate_has_putin_and_takeout()
        self.assertTrue(result)

    def test_validate_reach_invalid_has_putin_and_takeout(self):
        reach = Reach(1)
        result = reach.validate(self.access_validate, hydro_net)
        self.assertFalse(result)

    def test_validate_putin_takeout_coincidence_false(self):
        reach = Reach(2)
        result = reach._validate_putin_takeout_coincidence(self.access_validate, hydro_net)
        self.assertFalse(result)

    def test_validate_putin_takeout_coincidence_true(self):
        reach = Reach(4)
        result = reach._validate_putin_takeout_coincidence(self.access_validate, hydro_net)
        self.assertTrue(result)

    def test_validate_reach_invalid_putin_takeout_coincidence(self):
        reach = Reach(2)
        result = reach.validate(self.access_validate, hydro_net)
        self.assertFalse(result)

    def test_validate_putin_upstream_from_takeout_false(self):
        reach = Reach(3)
        result = reach._validate_putin_upstream_from_takeout(self.access_validate, hydro_net)
        self.assertFalse(result)

    def test_validate_putin_upstream_from_takeout_true(self):
        reach = Reach(4)
        result = reach._validate_putin_upstream_from_takeout(self.access_validate, hydro_net)
        self.assertTrue(result)

    def test_validate_reach_invalid_putin_upstream_from_takeout(self):
        reach = Reach(2)
        result = reach.validate(self.access_validate, hydro_net)
        self.assertFalse(result['valid'])

    def test_validate_reach_valid(self):
        reach = Reach(4)
        result = reach.validate(self.access_validate, hydro_net)
        self.assertTrue(result['valid'])


# class TestReachProcessing(unittest.TestCase):
#     """
#     Test reach processing tools.
#     """
#     access_validate = r'D:\dev\reach-processing-tools\test_data\test_data.gdb\access_validate_test'
#
#     def test_process_reach(self):
#         reach = Reach(4)
#         result = reach.validate(self.access_validate, hydro_net)
#         self.assertTrue(result)
#
#     def test_get_reach_line_feature_class(self):
#
#         # create testing output feature class paths
#         hydroline_fc = os.path.join(test_gdb, 'hydroline_fc{0}'.format(milliseconds))
#         centroid_fc = os.path.join(test_gdb, 'centroid_fc{0}'.format(milliseconds))
#
#         # run reach processing, and test for the results
#
#         reach_processing.process_reaches(self.access_validate, hydro_net, hydroline_fc, invalid_tbl)
#         feature_count = int(arcpy.GetCount_management(hydroline_fc)[0])
#         self.assertEqual(1, feature_count)


# class TestReachReview(unittest.TestCase):
#     """
#     Test reach review functionality
#     """
#     access_review = r'D:\dev\reach-processing-tools\test_data\test_data.gdb\access_revise_test'
#     hydrolines = r'D:\dev\reach-processing-tools\test_data\test_data.gdb\hydroline_revise_test'
#     invalid_table = r'D:\dev\reach-processing-tools\test_data\test_data.gdb\invalid_revise_test'
#
#     def test_get_new_reach_hydrolines(self):
#
#         milliseconds = int(time.time()*100)
#         temp_hydroline = arcpy.CopyFeatures_management(
#             self.hydrolines,
#             os.path.join(test_gdb, 'hydroline_fc{0}'.format(milliseconds))
#         )[0]
#         temp_invalid = arcpy.CopyRows_management(
#             self.invalid_table,
#             os.path.join(test_gdb, 'invalid_tbl{0}'.format(milliseconds))
#         )[0]
#
#         reach_processing.get_new_hydrolines(
#             access_fc=self.access_review,
#             hydro_network=hydro_net,
#             reach_hydroline_fc=temp_hydroline,
#             reach_invalid_tbl=temp_invalid
#         )
#         feature_count = int(arcpy.GetCount_management(temp_hydroline)[0])
#
#         self.assertEqual(2, feature_count)
#
#
# # class TestUpdate(unittest.TestCase):
# #
# #     def test_get_reach(self):
# #         reachId = 3306
# #         responseJson = update.get_reach(reachId)
# #         responseObject = json.loads(responseJson)
# #         self.assertEqual(reachId, responseObject['features'][0]['properties']['reachId'])
#
# class TestPublishingUtilitites(unittest.TestCase):
#     """
#     Provide at least some minimal tests to enable troubleshooting the publishing workflows.
#     All data is from subregion 1711.
#     """
#     test_gdb = r'D:\dev\reach-processing-tools\resources\scratch\test_publish_data.gdb'
#     publish_gdb = os.path.join(arcpy.env.scratchFolder, 'scratch{}'.format(arcpy.ValidateTableName(uuid.uuid4())))
#
#     def test_publish(self):
#
#         # clean out the scratch directory
#         for dir_top, dir_list, object_list in arcpy.da.Walk(self.publish_gdb):
#             for object in object_list:
#                 arcpy.Delete_management(os.path.join(dir_top, object))
#
#         print(self.publish_gdb)
#
#         scratch_gdb = publishing_utilities.create_publication_geodatabase(
#             analysis_gdb=self.test_gdb,
#             publication_gdb=self.publish_gdb
#         )
#
#         self.assertTrue(True)
#
#     def test_publish_20160328(self):
#
#         analysis_gdb = r'D:\dev\reach-processing-tools\resources\data_20160328.gdb'
#         output_gdb = r'D:\dev\reach-processing-tools\resources\publish_20160328.gdb'
#
#         if arcpy.Exists(output_gdb):
#             arcpy.Delete_management(output_gdb)
#
#         output_gdb = publishing_utilities.create_publication_geodatabase(
#             analysis_gdb=analysis_gdb,
#             publication_gdb=output_gdb
#         )
#
#         self.assertTrue(True)