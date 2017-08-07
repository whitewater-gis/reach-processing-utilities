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


if __name__ == '__main__':
    unittest.main()
