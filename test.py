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
    test_fc_accesses = os.path.join(dir_this, r'resources\data.gdb\access')
    test_network_hydro = os.path.join(dir_this, r'resources\data.gdb\Hydrography\HYDRO_NET')

    def test_reach_has_putin_and_takeout(self):

        status = reach_utlities.validate_has_access(
            reach_id=self.test_reach_id,
            access_fc=self.test_fc_accesses
        )
        self.assertTrue(status, 'It appears there is not a putin and takeout for reach id {}'.format(self.test_reach_id))

    def test_is_putin_upstream_from_takeout(self):

        status = reach_utlities.validate_putin_upstream_from_takeout(
            reach_id=self.test_reach_id,
            access_fc=self.test_fc_accesses,
            hydro_network=self.test_network_hydro
        )
        self.assertTrue(status, 'It appears the putin is not upstream of the takeout on the network for reach id {}'. format(self.test_reach_id))

    def test_get_reach_geometry(self):

        reachGeometry = reach_utlities.process_reach(
            reach_id=self.test_reach_id,
            access_fc=self.test_fc_accesses,
            hydro_network=self.test_network_hydro
        )
        self.assertTrue(reachGeometry[0].length, 'The returned geometry appears not to have a length for reach id {}'.format(self.test_reach_id))