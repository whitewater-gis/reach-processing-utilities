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

# some testing variables
this_dir = os.path.dirname(__file__)
project_dir = os.path.dirname(this_dir)
resources_dir = os.path.join(project_dir, 'resources')
test_data_dir = os.path.join(project_dir, 'test_data')
test_data_gdb = os.path.join(test_data_dir, 'test_data.gdb')
test_hydro_net = os.path.join(test_data_dir, '1711.gdb', 'Hydrography', 'HYDRO_NET')


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
        self.assertEqual(self.reach.difficulty_maximum, 'V')

    def test_difficulty_maximum(self):
        self.assertEqual(self.reach.difficulty, 'II-V')

    def test_point_putin_coordinates(self):
        centroid = [point.geometry.centroid for point in self.reach.points if 'putin' in point.tags][0]
        self.assertEqual((centroid.X, centroid.Y), (-124.038, 47.9634))

    def test_point_takeout_coordinates(self):
        centroid = [point.geometry.centroid for point in self.reach.points if 'takeout' in point.tags][0]
        self.assertEqual((centroid.X, centroid.Y), (-124.258, 47.9604))

    def test_point_centroid_coordinates(self):
        centroid = self.reach.point.centroid
        self.assertEqual((centroid.X, centroid.Y), (-124.148, 47.9619))

    def test_datetime_newer_than_local(self):
        local_datetime = datetime.datetime(1995, 01, 01)
        self.assertGreater(self.reach.update_datetime, local_datetime)

    def test_datetime_older_than_local(self):
        local_datetime = datetime.datetime(2030, 01, 01)
        self.assertLess(self.reach.update_datetime, local_datetime)


class TestCaseValidationLocalData(unittest.TestCase):
    """
    Test validation functions with data created to break in the right ways.
    """
    test_access_validate = os.path.join(test_data_gdb, 'access_validate_test')

    def test_validate_has_putin_and_takeout_false(self):
        reach = Reach(1)
        reach.set_access_points_from_access_feature_class(self.test_access_validate)
        result = reach._validate_has_putin_and_takeout()
        self.assertFalse(result)

    def test_validate_has_putin_and_takeout_true(self):
        reach = Reach(4)
        reach.set_access_points_from_access_feature_class(self.test_access_validate)
        result = reach._validate_has_putin_and_takeout()
        self.assertTrue(result)

    def test_validate_reach_invalid_has_putin_and_takeout(self):
        reach = Reach(1)
        result = reach.validate(self.test_access_validate, test_hydro_net)
        self.assertFalse(result)

    def test_validate_putin_takeout_coincidence_false(self):
        reach = Reach(2)
        result = reach._validate_putin_takeout_coincidence(self.test_access_validate, test_hydro_net)
        self.assertFalse(result)

    def test_validate_putin_takeout_coincidence_true(self):
        reach = Reach(4)
        result = reach._validate_putin_takeout_coincidence(self.test_access_validate, test_hydro_net)
        self.assertTrue(result)

    def test_validate_reach_invalid_putin_takeout_coincidence(self):
        reach = Reach(2)
        result = reach.validate(self.test_access_validate, test_hydro_net)
        self.assertFalse(result)

    def test_validate_putin_upstream_from_takeout_false(self):
        reach = Reach(3)
        result = reach._validate_putin_upstream_from_takeout(self.test_access_validate, test_hydro_net)
        self.assertFalse(result)

    def test_validate_putin_upstream_from_takeout_true(self):
        reach = Reach(4)
        result = reach._validate_putin_upstream_from_takeout(self.test_access_validate, test_hydro_net)
        self.assertTrue(result)

    def test_validate_reach_invalid_putin_upstream_from_takeout(self):
        reach = Reach(2)
        result = reach.validate(self.test_access_validate, test_hydro_net)
        self.assertFalse(result)

    def test_validate_reach_valid(self):
        reach = Reach(4)
        result = reach.validate(self.test_access_validate, test_hydro_net)
        self.assertTrue(result)


class TestCaseValidationDownload2204(unittest.TestCase):

    def test_validate_2204(self):
        reach = Reach(2204)
        reach.download()
        self.assertTrue(False)

if __name__ == '__main__':
    unittest.main()
