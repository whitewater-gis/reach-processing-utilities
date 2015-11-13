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
import unittest
import itertools
import os.path
import arcpy

# import local modules
import utilities.nhd_data
import utilities.validate
import utilities.reach_processing
import utilities.publishing_tools


# variables
access_fc = r'F:\reach-processing\aggregate\data_v2.gdb\access'
hydro_net = r'F:\reach-processing\subregions\1711.gdb\Hydrography\HYDRO_NET'
huc4 = r'F:\reach-processing\aggregate\data_v2.gdb\WBDHU4'
test_gdb = arcpy.env.scratchGDB
test_dir = arcpy.env.scratchFolder


class TestCaseDownloadSmallest(unittest.TestCase):

    def test_download_from_usgs(self):

        subregion_huc4 = '2003'
        output_directory = r'D:\dev\reach-processing-tools\resources\scratch'

        fgdb = utilities.nhd_data._get_nhd_subregion(subregion_huc4, output_directory)

        self.assertTrue(arcpy.Exists(fgdb))


class TestCaseSingleReach2170(unittest.TestCase):

    # single reach id causing problems
    single_reach_id = '2170'

    def test_reach_has_putin_and_takeout(self):

        status = utilities.validate._validate_has_putin_and_takeout(
            reach_id=self.single_reach_id,
            access_fc=access_fc
        )
        self.assertTrue(
            status,
            'Reach id {} does not appears to have a putin and takeout.'.format(self.single_reach_id)
        )

    def test_reach_accesses_coincident_with_hydrolines(self):
        self.assertTrue(
            utilities.validate._validate_putin_takeout_conicidence(self.single_reach_id, access_fc, hydro_net),
            'Although reach id {} appears to have a putin and takeout, the accesses are not coincident. They are not on the USGS hyrdrolines.'.format(self.single_reach_id)
        )

    def test_reach_putin_upstream_from_takeout(self):
        self.assertTrue(
            utilities.validate._validate_putin_upstream_from_takeout(
                reach_id=self.single_reach_id,
                access_fc=access_fc,
                hydro_network=hydro_net
            ),
            'The putin does not appear to be upstream of the takeout for reach id {}.'.format(self.single_reach_id)
        )

    def test_get_reach_geometry(self):
        reach = utilities.reach_processing.process_reach(
            reach_id=self.single_reach_id,
            access_fc=access_fc,
            hydro_network=hydro_net
        )
        # initially set to true and if any of the segments do not have a geometry, fail
        status = True
        for geometry in reach['geometry_list']:
            if not geometry.length:
                status = False

        self.assertTrue(
            status,
            'At least one of the returned geometries appears not to have a length for reach id {}'.format(
                self.single_reach_id
            )
        )


class TestCaseSingleReach2171(unittest.TestCase):

    # single reach id causing problems
    single_reach_id = '2171'

    def test_reach_has_putin_and_takeout(self):

        status = utilities.validate._validate_has_putin_and_takeout(
            reach_id=self.single_reach_id,
            access_fc=access_fc
        )
        self.assertTrue(
            status,
            'Reach id {} does not appears to have a putin and takeout.'.format(self.single_reach_id)
        )

    def test_reach_accesses_coincident_with_hydrolines(self):
        self.assertTrue(
            utilities.validate._validate_putin_takeout_conicidence(self.single_reach_id, access_fc, hydro_net),
            'Although reach id {} appears to have a putin and takeout, the accesses are not coincident. They are not on the USGS hyrdrolines.'.format(self.single_reach_id)
        )

    def test_reach_putin_upstream_from_takeout(self):
        self.assertTrue(
            utilities.validate._validate_putin_upstream_from_takeout(
                reach_id=self.single_reach_id,
                access_fc=access_fc,
                hydro_network=hydro_net
            ),
            'The putin does not appear to be upstream of the takeout for reach id {}.'.format(self.single_reach_id)
        )

    def test_get_reach_geometry(self):
        reach = utilities.reach_processing.process_reach(
            reach_id=self.single_reach_id,
            access_fc=access_fc,
            hydro_network=hydro_net
        )
        # initially set to true and if any of the segments do not have a geometry, fail
        status = True
        for geometry in reach['geometry_list']:
            if not geometry.length:
                status = False

        self.assertTrue(
            status,
            'At least one of the returned geometries appears not to have a length for reach id {}'.format(
                self.single_reach_id
            )
        )


class TestCaseSingleReach2172(unittest.TestCase):

    # single reach id causing problems
    single_reach_id = '2172'

    def test_reach_has_putin_and_takeout(self):

        status = utilities.validate._validate_has_putin_and_takeout(
            reach_id=self.single_reach_id,
            access_fc=access_fc
        )
        self.assertTrue(
            status,
            'Reach id {} does not appears to have a putin and takeout.'.format(self.single_reach_id)
        )

    def test_reach_accesses_coincident_with_hydrolines(self):
        self.assertTrue(
            utilities.validate._validate_putin_takeout_conicidence(self.single_reach_id, access_fc, hydro_net),
            'Although reach id {} appears to have a putin and takeout, the accesses are not coincident. They are not on the USGS hyrdrolines.'.format(self.single_reach_id)
        )

    def test_reach_putin_upstream_from_takeout(self):
        self.assertTrue(
            utilities.validate._validate_putin_upstream_from_takeout(
                reach_id=self.single_reach_id,
                access_fc=access_fc,
                hydro_network=hydro_net
            ),
            'The putin does not appear to be upstream of the takeout for reach id {}.'.format(self.single_reach_id)
        )

    def test_get_reach_geometry(self):
        reach = utilities.reach_processing.process_reach(
            reach_id=self.single_reach_id,
            access_fc=access_fc,
            hydro_network=hydro_net
        )
        # initially set to true and if any of the segments do not have a geometry, fail
        status = True
        for geometry in reach['geometry_list']:
            if not geometry.length:
                status = False

        self.assertTrue(
            status,
            'At least one of the returned geometries appears not to have a length for reach id {}'.format(
                self.single_reach_id
            )
        )


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

        scratch_gdb = arcpy.env.scratchGDB
        reach_hydroline = os.path.join(scratch_gdb, 'reach_test')
        reach_invalid_out = os.path.join(scratch_gdb, 'reach_test_invalid')

        # collapse query list into single query string
        query_list = ["reach_id = '{}'".format(int(reach_id)) for reach_id in self.reach_id_list]
        query = ' OR '.join(query_list)

        # get features in temporary features class
        access_fc_temp = arcpy.Select_analysis(access_fc, 'in_memory/access_subset', query)

        # run the analysis
        utilities.reach_processing.get_reach_line_fc(access_fc_temp, hydro_net, reach_hydroline, reach_invalid_out)

        # combine the output record length of valid and invalid, it should be 69
        total_processed = (int(arcpy.GetCount_management(reach_hydroline)[0]) +
                           int(arcpy.GetCount_management(reach_invalid_out)[0]))

        # check to make sure 69 records were processed
        self.assertEqual(total_processed, 69)
        
        
class TestCaseMultipleOlympicPeninsula_SDE(unittest.TestCase):

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

        sde = r'C:\Users\joel5174\AppData\Roaming\ESRI\Desktop10.3\ArcCatalog\whitewater (owner.20150920kc).sde'
        access_fc_sde = os.path.join(sde, 'whitewater.owner.access')
        reach_hydroline_sde = os.path.join(sde, 'whitewater.owner.hydroline')
        reach_invalid_sde = os.path.join(sde, 'whitewater.owner.reach_invalid')
        hydro_net = r'F:\reach-processing\subregions\1710.gdb\Hydrography\HYDRO_NET'

        # collapse query list into single query string
        query_list = ["reach_id = '{}'".format(int(reach_id)) for reach_id in self.reach_id_list]
        query = ' OR '.join(query_list)

        # get features in temporary features class
        access_fc_temp = arcpy.Select_analysis(access_fc_sde, 'in_memory/access_subset', query)

        # run the analysis
        utilities.reach_processing.get_reach_line_fc(access_fc_temp, hydro_net, reach_hydroline_sde, reach_invalid_sde)

        # combine the output record length of valid and invalid, it should be 69
        total_processed = (int(arcpy.GetCount_management(reach_hydroline_sde)[0]) +
                           int(arcpy.GetCount_management(reach_invalid_sde)[0]))

        # check to make sure 69 records were processed
        self.assertEqual(total_processed, 69)


class TestCaseJoinMetaToAccess(unittest.TestCase):

    # paths to data
    access_fc = r'F:\reach-processing\aggregate\publish20150721.gdb\access'

    def test_append_meta_table(self):
        join_table = r'F:\reach-processing\aggregate\aggregate20150721.gdb\reach_meta'
        path = utilities.reach_processing.join_table_to_access(access_fc, join_table)
        self.assertTrue(len(path))


class TestCasePublishTasks(unittest.TestCase):

    def test_create_publication_geodatabase(self):
        out_gdb = r'C:\Users\joel5174\Documents\ArcGIS\test_aw01.gdb'
        if arcpy.Exists(out_gdb):
            arcpy.Delete_management(out_gdb)
        utilities.create_publication_geodatabase(r'F:\reach-processing\aggregate\data_v2.gdb', out_gdb)
        self.assertTrue(arcpy.Exists(out_gdb))
