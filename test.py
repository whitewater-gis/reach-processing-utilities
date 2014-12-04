"""
Unit testing
"""
# import modules
import unittest
import os
import arcpy
import reach_utlities


class test_case_reach_utilities(unittest.TestCase):

    # overwrite outputs
    arcpy.env.overwriteOutput = True

    # testing variables
    test_reach_id = '2064'
    dir_this = os.path.dirname(__file__)
    gdb_data = os.path.join(dir_this, r'resources\data.gdb')
    gdb_scratch = os.path.join(dir_this, r'resources\scratch.gdb')
    test_access_fc = os.path.join(gdb_data, 'access')
    test_access_subset_fc = os.path.join(gdb_data, 'access_subset')
    test_hydro_network = os.path.join(gdb_data, r'Hydrography\HYDRO_NET')

    def test_reach_has_putin_and_takeout(self):

        status = reach_utlities.validate_has_access(
            reach_id=self.test_reach_id,
            access_fc=self.test_access_fc
        )
        self.assertTrue(status, 'It appears there is not a putin and takeout for reach id {}'.format(self.test_reach_id))

    def test_is_putin_upstream_from_takeout(self):

        # get geometry object for putin and takeout
        takeout_geometry = arcpy.Select_analysis(self.test_access_fc, arcpy.Geometry(),  "takeout='{}'".format(self.test_reach_id))[0]
        putin_geometry = arcpy.Select_analysis(self.test_access_fc, arcpy.Geometry(),  "putin='{}'".format(self.test_reach_id))[0]

        status = reach_utlities.validate_putin_upstream_from_takeout(
            putin_geometry=putin_geometry,
            takeout_geometry=takeout_geometry,
            hydro_network=self.test_hydro_network
        )
        self.assertTrue(status, 'It appears the putin is not upstream of the takeout on the network for reach id {}'. format(self.test_reach_id))

    def test_get_reach_geometry(self):

        reach = reach_utlities.process_reach(
            reach_id=self.test_reach_id,
            access_fc=self.test_access_fc,
            hydro_network=self.test_hydro_network
        )

        status = True

        for geometry in reach['geometry_list']:
            if not geometry.length:
                status = False

        self.assertTrue(status, 'One of the returned geometries appears not to have a length for reach id {}'.format(self.test_reach_id))

    def test_get_reach_fc(self):

        output_fc = os.path.join(self.gdb_scratch, 'reach_line_subset')

        reach_utlities.get_reach_line_fc(
            access_fc=self.test_access_subset_fc,
            hydro_network=self.test_hydro_network,
            output_hydroline_fc=output_fc,
            output_invalid_reach_table=os.path.join(self.gdb_scratch, 'reach_invalid')
        )

        self.assertTrue(arcpy.GetCount_management(output_fc))