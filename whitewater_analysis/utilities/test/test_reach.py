# imprt system modules
from unittest import TestCase
from os import path
import arcpy

# import reach from reach processing utilities
from whitewater_analysis.utilities.reach_processing_utilities import Reach

# variables
test_gdb = r'D:\dev\reach-processing-tools\test_data\test_data.gdb'
access_fc = path.join(test_gdb, 'access_publish_test')
hydro_net = r'D:\dev\reach-processing-tools\test_data\1711.gdb\Hydrography\HYDRO_NET'
huc4 = r'H:\reach-processing\aggregate\data_v3.gdb\WBDHU4'
test_gdb = arcpy.env.scratchGDB
test_dir = arcpy.env.scratchFolder


class TestReach(TestCase):
    def test__get_access_geometries_from_access_fc_putin(self):
        reach = Reach(4)
        reach.set_access_points_from_access_feature_class(access_fc)
        geometry_list = reach._get_access_geometries_from_access_fc(access_fc, 'putin')
        self.assertEqual(1, len(geometry_list))

    def test_set_access_points_from_access_feature_class_assert_point_count(self):
        reach = Reach(4)
        reach.set_access_points_from_access_feature_class(access_fc)
        point_count = len(reach.points)
        self.assertEqual(3, point_count)

    def test_set_access_points_from_access_feature_class_assert_putin(self):
        reach = Reach(4)
        reach.set_access_points_from_access_feature_class(access_fc)
        putin = False
        for point in reach.points:
            if 'putin' in point.tags:
                putin = True
        self.assertTrue(putin)

    def test_set_access_points_from_access_feature_class_assert_takeout(self):
        reach = Reach(4)
        reach.set_access_points_from_access_feature_class(access_fc)
        takeout = False
        for point in reach.points:
            if 'takeout' in point.tags:
                takeout = True
        self.assertTrue(takeout)

    def test_set_access_points_from_access_feature_class_assert_centroid_single(self):
        reach = Reach(1)
        reach.set_access_points_from_access_feature_class(access_fc)
        putin = None
        centroid = None
        for point in reach.points:
            if 'putin' in point.tags:
                putin = point
                break
        for point in reach.points:
            if 'centroid' in point.tags:
                centroid = point
                break
        self.assertEqual(putin.geometry, centroid.geometry)

    def test_get_putin_reachpoint_true(self):
        reach = Reach(4)
        reach.set_access_points_from_access_feature_class(access_fc)
        putin = reach.get_putin_reachpoint()
        self.assertTrue(putin)

    # TODO: get putin false

    def test_get_takeout_reachpoint_true(self):
        reach = Reach(4)
        reach.set_access_points_from_access_feature_class(access_fc)
        takeout = reach.get_takeout_reachpoint()
        self.assertTrue(takeout)

    # TODO: get takeout false

    def test__validate_has_putin_and_takeout_false(self):
        reach = Reach(1)
        reach.set_access_points_from_access_feature_class(access_fc)
        result = reach._validate_has_putin_and_takeout()
        self.assertFalse(result)

    def test__validate_has_putin_and_takeout_true(self):
        reach = Reach(2)
        reach.set_access_points_from_access_feature_class(access_fc)
        result = reach._validate_has_putin_and_takeout()
        self.assertTrue(result)

    def test__validate_putin_takeout_coincidence_false(self):
        reach = Reach(2)
        reach.set_access_points_from_access_feature_class(access_fc)
        result = reach._validate_putin_takeout_coincidence(access_fc, hydro_net)
        self.assertFalse(result)

    def test__validate_putin_takeout_coincidence_true(self):
        reach = Reach(4)
        reach.set_access_points_from_access_feature_class(access_fc)
        result = reach._validate_putin_takeout_coincidence(access_fc, hydro_net)
        self.assertTrue(result)

    def test__validate_putin_upstream_from_takeout_true(self):
        reach = Reach(4)
        reach.set_access_points_from_access_feature_class(access_fc)
        result = reach._validate_putin_upstream_from_takeout(access_fc, hydro_net)
        self.assertTrue(result)

    def test__validate_putin_upstream_from_takeout_false(self):
        reach = Reach(3)
        reach.set_access_points_from_access_feature_class(access_fc)
        reach._validate_putin_takeout_coincidence(access_fc, hydro_net)
        result = reach._validate_putin_upstream_from_takeout(access_fc, hydro_net)
        self.assertFalse(result)

    def test_validate_true(self):
        reach = Reach(4)
        valid = reach.validate(access_fc, hydro_net)
        self.assertTrue(valid)

    def test_validate_false(self):
        reach = Reach(3)
        valid = reach.validate(access_fc, hydro_net)
        self.assertFalse(valid)

    def test__get_reach_points(self):
        reach = Reach(4)
        reach.set_access_points_from_access_feature_class(access_fc)
        result = reach._get_reach_points()
        self.assertEqual(3, len(result))

    def test__get_access_points(self):
        reach = Reach(4)
        reach.validate(access_fc, hydro_net)
        access_points = reach.get_access_points()
        self.assertEqual(2, len(access_points))

    def test_get_access_points_putin(self):
        reach = Reach(4)
        reach.validate(access_fc, hydro_net)
        access_points = reach.get_access_points('putin')
        self.assertEqual(1, len(access_points))

    def test_get_centroid_reachpoint_single(self):
        reach = Reach(1)
        reach.set_access_points_from_access_feature_class(access_fc)
        putin = reach.get_putin_reachpoint()
        centroid = reach.get_centroid_reachpoint()
        self.assertEqual(putin.geometry, centroid.geometry)

    def test_get_centroid_reachpoint_mean(self):
        reach = Reach(4)
        reach.set_access_points_from_access_feature_class(access_fc)
        putin = reach.get_putin_reachpoint()
        centroid = reach.get_centroid_reachpoint()
        self.assertNotEqual(putin.geometry, centroid.geometry)

    # def test_get_centroid_row(self):
    #     self.fail()
    #
    # def test_get_hydroline_row(self):
    #     self.fail()
    #
    # def test_set_hydroline_geometry_multithreaded(self):
    #     self.fail()
    #
    # def test_set_hydroline_geometry(self):
    #     self.fail()
