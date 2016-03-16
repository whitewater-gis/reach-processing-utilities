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

import arcpy
# import local modules
import utilities.nhd_data
import utilities.validate as validate
import utilities.reach_processing
import utilities.publishing_tools
import utilities.watershed as watershed

# variables
access_fc = r'D:\dev\reach-processing-tools\test_data\test_data.gdb\access'
hydro_net = r'D:\dev\reach-processing-tools\test_data\1711.gdb\Hydrography\HYDRO_NET'
huc4 = r'H:\reach-processing\aggregate\data_v3.gdb\WBDHU4'
test_gdb = arcpy.env.scratchGDB
test_dir = arcpy.env.scratchFolder


class TestCaseValidation(unittest.TestCase):
    """
    Test validation functions with data created to break in the right ways.
    """
    access_validate = r'D:\dev\reach-processing-tools\test_data\test_data.gdb\access_validate_test'

    def test_validate_has_putin_and_takeout_false(self):
        result = validate._validate_has_putin_and_takeout(1, self.access_validate)
        self.assertFalse(result)

    def test_validate_has_putin_and_takeout_true(self):
        result = validate._validate_has_putin_and_takeout(4, self.access_validate)
        self.assertTrue(result)

    def test_validate_reach_invalid_has_putin_and_takeout(self):
        result = validate.validate_reach(1, self.access_validate, hydro_net)
        self.assertFalse(result['valid'])

    def test_validate_putin_takeout_coincidence_false(self):
        result = validate._validate_putin_takeout_conicidence(2, self.access_validate, hydro_net)
        self.assertFalse(result)

    def test_validate_putin_takeout_coincidence_true(self):
        result = validate._validate_putin_takeout_conicidence(4, self.access_validate, hydro_net)
        self.assertTrue(result)

    def test_validate_reach_invalid_putin_takeout_coincidence(self):
        result = validate.validate_reach(2, self.access_validate, hydro_net)
        self.assertFalse(result['valid'])

    def test_validate_putin_upstream_from_takeout_false(self):
        result = validate._validate_putin_upstream_from_takeout(3, self.access_validate, hydro_net)
        self.assertFalse(result)

    def test_validate_putin_upstream_from_takeout_true(self):
        result = validate._validate_putin_upstream_from_takeout(4, self.access_validate, hydro_net)
        self.assertTrue(result)

    def test_validate_reach_invalid_putin_upstream_from_takeout(self):
        result = validate.validate_reach(4, self.access_validate, hydro_net)
        self.assertFalse(result['valid'])