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
import itertools
import os.path

# variables
access_fc = r'D:\spatialData\aw\aw (owner).sde\aw.owner.accesses'
hydro_net = r'D:\spatialData\aw\aw (owner).sde\aw.owner.Hydrography\aw.owner.HYDRO_NET'
huc4 = r'D:\spatialData\aw\aw (owner).sde\aw.owner.WBDHU4'
test_gdb = arcpy.env.scratchGDB
test_dir = arcpy.env.scratchFolder


class TestCaseSingleReach(unittest.TestCase):

    # single reach id known to be valid
    single_reach_id = '00003491'

    def test_reach_has_putin_and_takeout(self):

        status = reach_utlities._validate_has_access(
            reach_id=self.single_reach_id,
            access_fc=access_fc
        )
        self.assertTrue(status, 'It appears there is not a putin and takeout for reach id {}'.format(single_reach_id))

    def test_reach_accesses_coincident(self):
        self.assertTrue(
            reach_utlities._validate_putin_takeout_conicidence(single_reach_id, access_fc, hydro_net),
            'Reach id {} appears to have a putin and takeout.'.format(single_reach_id)
        )

    def test_reach_putin_upstream_from_takeout(self):
        self.assertTrue(
            reach_utlities._validate_putin_upstream_from_takeout(
                reach_id=self.single_reach_id,
                access_fc=access_fc,
                hydro_network=hydro_net
            ),
            'The putin appears to be upstream of the takeout for reach id {}.'.format(single_reach_id)
        )

    def test_get_reach_geometry(self):
        reach = reach_utlities._process_reach(
            reach_id=self.single_reach_id,
            access_fc=access_fc,
            hydro_network=hydro_net
        )
        # initially set to true and if any of the segments do not have a geometry, fail
        status = True
        for geometry in reach['geometry_list']:
            if not geometry.length:
                status = False

        self.assertTrue(status, 'At least one of the returned geometries appears not to have a length for reach id {}'.format(single_reach_id))


class TestCaseMultipleOlympicPeninsula(unittest.TestCase):

    # reach id list of all reaches on Olympic Peninsula
    reach_id_list = [u'00002065', u'00002098', u'00002119', u'00002131', u'00002163', u'00002182', u'00002204',
                     u'00002215', u'00002227', u'00002236', u'00002275', u'00003148', u'00003317', u'00003343',
                     u'00003353', u'00003578', u'00002071', u'00003305', u'00002108', u'00002134', u'00002161',
                     u'00002191', u'00002197', u'00002207', u'00002230', u'00002258', u'00002067', u'00002070',
                     u'00002072', u'00002088', u'00002096', u'00002097', u'00002104', u'00002106', u'00002107',
                     u'00002109', u'00002110', u'00002111', u'00002112', u'00002113', u'00002121', u'00002126',
                     u'00002127', u'00002129', u'00002130', u'00002132', u'00002133', u'00002135', u'00002158',
                     u'00002183', u'00002192', u'00002193', u'00002194', u'00002195', u'00002196', u'00002208',
                     u'00002225', u'00002226', u'00002228', u'00002229', u'00002231', u'00002232', u'00003288',
                     u'00003315', u'00003316', u'00003319', u'00003354', u'00004214', u'00004373']

    def test_get_reach_line_fc(self):

        scratch_gdb = r'D:\spatialData\aw\scratch\data_scratch.gdb'
        reach_hydroline = os.path.join(scratch_gdb, 'reach_test')
        reach_invalid_out = os.path.join(scratch_gdb, 'reach_test_invalid')

        # create query string for all accesses
        def get_query_snippet(reach_id):
            return "putin = '{}' OR takeout = '{}'".format(reach_id, reach_id)

        # collapse query list into single query string
        query = ' OR '.join(itertools.imap(get_query_snippet, self.reach_id_list))

        # get features in temporary features class
        access_fc_temp = arcpy.Select_analysis(access_fc, 'in_memory/access_subset', query)

        # select the huc4 polygon for the aoi
        huc4_sel = arcpy.MakeFeatureLayer_management(huc4, 'huc4_aoi', "huc4 = '1710'")

        # run the analysis
        reach_utlities.get_reach_line_fc(access_fc_temp, huc4_sel, hydro_net, reach_hydroline, reach_invalid_out)

        # combine the output record length of valid and invalid, it should be 69
        total_processed = (int(arcpy.GetCount_management(reach_hydroline)[0]) +
                           int(arcpy.GetCount_management(reach_invalid_out)[0]))

        # check to make sure 69 records were processed
        self.assertEqual(total_processed, 69)