"""
author:     Joel McCune (joel.mccune+gis@gmail.com)
dob:        03 Dec 2014
purpose:    Provide the utilities to process and work with whitewater reach data.

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
import os.path
import arcpy
import uuid
import re
import requests
import datetime
from .html2text import html2text


def _get_valid_uuid(workspace):
    """
    Helper function to get uuid formatted for table names.
    :param workspace: Path to workspace being used for object storage.
    :return: Validated uuid string without underscores.
    """
    return arcpy.ValidateTableName(name=uuid.uuid4(), workspace=workspace).replace('_', '')


def _add_uid(input_string):
        """
        Helper function to add the UID string to names for intermediate data.
        :return: String with uuid appended.
        """
        return '{}_{}'.format(input_string, str(uuid.uuid4()).replace('-', ''))


class ReachPoint(object):

    def __init__(self, reach_id, category, subcategory=None, geometry=None):
        self.reach_id = int(reach_id)
        self.category = category
        if isinstance(subcategory, str) and len(subcategory) > 0:
            self.subcategory = subcategory
        self.geometry = geometry


class Reach:

    def __init__(self, reach_id):
        self.reach_id = int(reach_id)
        self.name = None
        self.river_name = None
        self.river_alternate_name = None
        self.url = 'https://www.americanwhitewater.org/content/River/detail/id/{}/.json'.format(reach_id)
        self.error = None
        self.notes = None
        self.abstract = None
        self.description = None
        self.difficulty = None
        self.difficulty_minimum = None
        self.difficulty_maximum = None
        self.difficulty_outlier = None
        self.hydroline = None
        self.manual_digitize = None
        self.points = []
        self._accesses_collected = False
        self._has_location = False

    def download(self):
        response = requests.get(self.url)
        if response.status_code == 200:
            raw_json = response.json()
            self._parse_json(raw_json)
            print('Successfully retrieved reach id {} for the {} section of the {}.'.format(self.reach_id, self.name,
                                                                                            self.river_name))
            return True
        else:
            print('American Whitewater server could not be reached for reach ID {}.'.format(self.reach_id))
            return False

    def _parse_difficulty_string(self, difficulty_combined):
        match = re.match(
            '^([I|IV|V|VI|5\.\d]{1,3}(?=-))?-?([I|IV|V|VI|5\.\d]{1,3}[+|-]?)\(?([I|IV|V|VI|5\.\d]{0,3}[+|-]?)',
            difficulty_combined
        )
        self.difficulty_minimum = self._get_if_length(match.group(1))
        self.difficulty_maximum = self._get_if_length(match.group(2))
        self.difficulty_outlier = self._get_if_length(match.group(3))

    @staticmethod
    def _get_if_length(match_string):
        if match_string and len(match_string):
            return match_string
        else:
            return None

    def _validate_aw_json(self, json_block, key):

        # check to ensure a value exists
        if key not in json_block.keys():
            return None

        else:

            # clean up the text garbage...because there is a lot of it
            value = self._cleanup_string(json_block[key])

            # now, ensure something is still there...not kidding, this frequently is the case...it is all gone
            if not value:
                return None
            elif not len(value):
                return None

            else:
                # now check to ensure there is actually some text in the block, not just blank characters
                if not re.match(r'^( |\r|\n|\t)+$', value) and value != 'N/A':

                    # if everything is good, return a value
                    return value
                else:
                    return None

    @staticmethod
    def _cleanup_string(input_string):

        # ensure something to work with
        if not input_string:
            return input_string

        # convert to markdown first, so any reasonable formatting is retained
        cleanup = html2text(input_string)

        # since people love to hit the space key multiple times in stupid places, get rid of multiple space, but leave
        # newlines in there since they actually do contribute to formatting
        cleanup = re.sub(r'\s{2,}', ' ', cleanup)

        # apparently some people think it is a good idea to hit return more than twice...account for this foolishness
        cleanup = re.sub(r'\n{3,}', '\n\n', cleanup)

        # get rid of any trailing newlines at end of entire text block
        cleanup = re.sub(r'\n+$', '', cleanup)

        # get rid of any leading or trailing spaces
        cleanup = cleanup.strip();

        # finally call it good
        return cleanup

    def _parse_json(self, raw_json):

        # pluck out the stuff we are interested in
        self._reach_json = raw_json['CContainerViewJSON_view']['CRiverMainGadgetJSON_main']

        # pull a bunch of attributes through validation and save as properties
        reach_info = self._reach_json['info']
        self.river_name = self._validate_aw_json(reach_info, 'river')
        self.river_alternate_name = self._validate_aw_json(reach_info, 'altname')
        self.name = self._validate_aw_json(reach_info, 'section')
        self.huc = self._validate_aw_json(reach_info, 'huc')
        self.description = self._validate_aw_json(reach_info, 'description')
        self.abstract = self._validate_aw_json(reach_info, 'abstract')
        self.length = float(self._validate_aw_json(reach_info, 'length'))

        # save the update datetime as a true datetime object
        self.update_datetime = datetime.datetime.strptime(reach_info['edited'], '%Y-%m-%d %H:%M:%S')

        # process difficulty
        self.difficulty = self._validate_aw_json(reach_info, 'class')
        self._parse_difficulty_string(str(self.difficulty))

        # ensure putin coordinates are present, and if so, add the put-in point to the points list
        if reach_info['plon'] is not None and reach_info['plat'] is not None:
            self.points.append(
                ReachPoint(
                    reach_id=self.reach_id,
                    category='access',
                    subcategory='putin',
                    geometry=arcpy.PointGeometry(
                        arcpy.Point(float(reach_info['plon']), float(reach_info['plat'])),
                        arcpy.SpatialReference(4326)
                    )
                )
            )

        # ensure take-out coordinates are present, and if so, add take-out point to points list
        if reach_info['tlon'] is not None and reach_info['tlat'] is not None:
            self.points.append(
                ReachPoint(
                    reach_id=self.reach_id,
                    category='access',
                    subcategory='takeout',
                    geometry=arcpy.PointGeometry(
                        arcpy.Point(float(reach_info['tlon']), float(reach_info['tlat'])),
                        arcpy.SpatialReference(4326)
                    )
                )
            )

    @staticmethod
    def _get_mean_point_geometry(first_point_geometry, second_point_geometry):
        """
        Helper method to get the mean point between two points - useful for calculating the centroid.
        :param first_point_geometry: ArcPy Point geometry.
        :param second_point_geometry: ArcPy Point geometry.
        :return: ArcPy point geometry mean between the two input geometries.
        """
        def _get_mean_coordinate(first_coordinate, second_coordinate):
            return min(first_coordinate, second_coordinate) + abs(first_coordinate - second_coordinate) / 2

        x = _get_mean_coordinate(first_point_geometry.centroid.X, second_point_geometry.centroid.X)
        y = _get_mean_coordinate(first_point_geometry.centroid.Y, second_point_geometry.centroid.Y)

        return arcpy.PointGeometry(arcpy.Point(x, y), arcpy.SpatialReference(4326))

    def set_access_points_from_access_feature_class(self, access_feature_class):
        """
        Get the access points from the access feature class for the reach, and also set the centroid point as well.
        :param access_feature_class: String path to the access feature class.
        :return:
        """

        # for each of the three access types
        for access_type in ['putin', 'takeout', 'intermediate']:

            # get a list of geometry objects for each type
            access_geometries = self._get_access_geometries_from_access_fc(access_feature_class, access_type)

            # if any geometries were extracted
            if len(access_geometries):

                # iterate each geometry, create a reach point, and add this reach point to the list
                for access_geometry in access_geometries:
                    self.points.append(ReachPoint(self.reach_id, 'access', access_type, access_geometry))

        # set the flag to true
        self._accesses_collected = True

    @property
    def centroid(self):
        """
        Return centroid geometry for the reach.
        :return: Geometry representing the centroid for the reach.
        """
        # get the putin and takeout reach points from the list
        putin = self.reachpoint_putin
        takeout = self.reachpoint_takeout

        # if both accesses, use the mean center, but if only one, use the one we have to work with
        if takeout is None and putin is None:
            return None
        elif takeout is not None and putin is not None:
            return self._get_mean_point_geometry(putin.geometry, takeout.geometry)
        elif takeout is not None:
            return takeout.geometry
        elif putin is not None:
            return putin.geometry

    def _get_access_geometries_from_access_fc(self, access_fc, access_type):
        """
        Get a geometry list for the prescribed access type.
        :param access_fc: Feature class containing all the accesses.
        :param access_type: Type of access, either putin, takeout, or intermediate.
        :return: List of geometries if the access type exists, or none if it does not.
        """
        query_string = "reach_id='{}' AND type='{}'".format(self.reach_id, access_type)
        access_geometry_list = arcpy.Select_analysis(access_fc, arcpy.Geometry(), query_string)
        if len(access_geometry_list):
            return access_geometry_list
        else:
            return []

    def _validate_has_putin_and_takeout(self):
        """
        Ensure the specified reach has a putin and takeout.
        :return:
        """
        if self.reachpoint_putin and self.reachpoint_takeout:
            self.error = False
            return True
        else:
            self.error = True
            self.notes = 'reach does not have both a put-in and take-out'
            return False

    def _replace_point(self, category, subcategory, new_point):
        """
        Helper function to replace a point in the list of points based on tags uniquely selecting only one point.
        :param category: Category used to identify the point.
        :param subcategory: Point subcaegory used to replace the point.
        :param new_point: New point object to replace the old one with.
        :return:
        """
        # ensure supplied point is a point type
        if not isinstance(new_point, ReachPoint):
            raise Exception('The point being used for replacement is not a ReachPoint. Please supply a ReachPoint.')

        this_point_list = [p for p in self.points if p.category == category and p.subcategory == subcategory]

        # ensure there is only one point returned
        if len(this_point_list) > 1:
            raise Exception('More than one point is being selected when trying to replace a point. Please use more specific identifiers for the point.')

        # update the point list to remove said point
        self.points = [p for p in self.points if not (p.category == category and  p.subcategory == subcategory)]

        # add new point to points list
        self.points.append(new_point)

    def _snap_points_to_hydroline(self, hydroline_feature_layer, category, subcategory=None):
        """
        Snap points in points list to hydrolines if within 500 feet.
        :param hydroline_feature_layer: Hydroline feature layar or feature class to snap points to.
        :param category: Categorical description for points.
        :param subcategory: Optional subcategory to identify points.
        :return:
        """
        # if the subcategory is provided, extract these points from the points list, and remove them from the master
        if subcategory:
            update_points = [p for p in self.points if p.category == category and p.subcategory == subcategory]
            self.points = [p for p in self.points if p.category != category and p.subcategory != subcategory]

        # otherwise, just extract based on the category
        else:
            update_points = [p for p in self.points if p.category == category]
            self.points = [p for p in self.points if p.category != category]

        # now, create a feature class from a list of the geometries
        these_points_feature_class = arcpy.CopyFeatures_management(
            in_features=[r.geometry for r in update_points],
            out_feature_class=os.path.join('in_memory', _add_uid('these_points'))
        )[0]

        # then create a layer, since this is what the edit toolbox tools have to have...such bullshit
        these_points_layer = arcpy.MakeFeatureLayer_management(these_points_feature_class)[0]

        # ensure the hydroline feature layer is, in fact, an actual layer
        hydroline_feature_layer = arcpy.MakeFeatureLayer_management(hydroline_feature_layer, _add_uid('hydroline'))

        # all of that, just so we can run this tool, and snap some points
        arcpy.Snap_edit(these_points_layer, [[hydroline_feature_layer, 'EDGE', '500 Feet']])

        # get the updated geometries back out
        updated_geometry_list = [_[0] for _ in arcpy.da.SearchCursor(these_points_layer, 'SHAPE@')]

        # now, update the points back together with the updated geometries
        for i in xrange(len(update_points)):
            update_points[i].geometry = updated_geometry_list[i]

        # add the points back to the object property
        self.points = self.points + update_points

    def _snap_accesses_to_hydrolines(self, hydroline_feature_layer):
        """
        Convenience wrapper to snap access points to the hydrolines.
        :param hydroline_feature_layer: Hydroline feature layar or feature class to snap points to.
        :return:
        """
        self._snap_points_to_hydroline(hydroline_feature_layer, 'access')

    def _project_points_to_hydro_net(self, hydro_net):
        """
        Since the spatial reference of the data, and the hydro network must be the same, and the coordinates are
        coming in as WGS84, and the network data from the USGS is NAD83, this is a helper to project all the data.
        :param hydro_net: Hydrology network being used to do tracing.
        :return:
        """
        # create a spatial reference object for the output collected from the hydro_net
        output_spatial_reference = arcpy.Describe(os.path.dirname(hydro_net)).spatialReference

        # reproject all the points
        for point in self.points:
            point.geometry = self._reproject_geometry_object(point.geometry, output_spatial_reference)

    def _reproject_geometry_object(self, geometry_in, spatial_reference_out):
        """
        :param geometry_in: Geometry object to be reprojected.
        :param spatial_reference_out: Spatial reference object for the output geometry object.
        :return: Geometry object in desired output spatial reference.
        """
        # read the spatial reference from the input geometry
        spatial_reference_in = geometry_in.spatialReference

        # if the input and output spatial references are different
        if spatial_reference_in.factoryCode != spatial_reference_out.factoryCode:

            # get a list of transformations we can use
            transformation = arcpy.ListTransformations(spatial_reference_in, spatial_reference_out)

            # if the geographic coordinate systems are different, there will be transformations - use the first one
            if len(transformation):
                return geometry_in.projectAs(spatial_reference_out, transformation[0])

            # if the geographic coordinate systems are the same, we don't need a transformation, so run without
            else:
                return geometry_in.projectAs(spatial_reference_out)

        # if the input and output spatial references are the same, just make the output the same as the input
        else:
            return geometry_in

    def _validate_putin_takeout_coincidence(self, hydro_network):
        """
        Ensure the putin and takeout are coincident with the USGS hydrolines. Just to compensate for error, the access
        points will be snapped to the hydrolines if they are within 500 feet since there can be a slight discrepancy in
        data sources' idea of exactly where the river center line actually is.
        :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology
            Dataset.
        :return: boolean: Indicates if the putin and takeout are coincident with the hydroline feature class.
        """
        # create a hydroline layer
        fds_path = os.path.dirname(arcpy.Describe(hydro_network).catalogPath)

        # set workspace so list feature classes works
        arcpy.env.workspace = fds_path

        # create layer for NHD hydrolines
        hydroline_lyr = arcpy.MakeFeatureLayer_management(
            in_features=os.path.join(fds_path, arcpy.ListFeatureClasses('*Flowline')[0]),
            out_layer='hydroline_lyr{}'.format(uuid.uuid4())
        )

        # create an in memory feature class to use for snapping, since the freaking editing toolbox will not let us
        # snap geometries...bullshit
        access_list = [self.reachpoint_putin, self.reachpoint_takeout]
        access_geometry_list = [access.geometry for access in access_list]
        temporary_access_feature_class = arcpy.CopyFeatures_management(
            in_features=access_geometry_list,
            out_feature_class=os.path.join(arcpy.env.scratchGDB, 'temp_access{}'.format(_get_valid_uuid('in_memory')))
        )[0]

        # create an access layer
        access_lyr = arcpy.MakeFeatureLayer_management(
            temporary_access_feature_class, 'putin_takeout_coincidence{}'.format(_get_valid_uuid('in_memory')),
        )[0]

        # snap the putin & takeout to the hydro lines
        arcpy.Snap_edit(access_lyr, [[hydroline_lyr, 'EDGE', '250 Meters']])

        # select by location, selecting accesses coincident with the hydrolines
        arcpy.SelectLayerByLocation_management(access_lyr, "INTERSECT", hydroline_lyr, selection_type='NEW_SELECTION')

        # if successful, two access features should be selected, the put in and the takeout
        if int(arcpy.GetCount_management(access_lyr)[0]) == 2:
            self.error = False  # set the error flag to false

            # update the put-in and take-out reach point geometry objects
            for index in xrange(0, len(access_list)):
                access_list[index].geometry = access_geometry_list[index]

            # update the put-in and take-out geometries from the snapped points
            self._replace_point('access', 'putin', access_list[0])
            self._replace_point('access', 'takeout', access_list[1])

            return True
        else:
            self.error = True
            self.notes = 'reach putin and takeout are not coincident with hydrolines'
            return False

    def _validate_putin_upstream_from_takeout(self, hydro_network):
        """
        Ensure the putin is indeed upstream of the takeout.
        :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology Dataset
        :return: boolean: Indicates if when tracing the geometric network upstream from the takeout, if the putin is
                          upstream from the takeout.
        """
        # get geometry object list for putin and takeout
        geometry_list = [self.reachpoint_putin.geometry, self.reachpoint_takeout.geometry]

        # project the geometry to the same as the geometric network
        projected_putin_takeout = arcpy.Project_management(
            in_dataset=geometry_list,
            out_dataset=os.path.join(arcpy.env.scratchGDB,
                                     'projected_access{}'.format(_get_valid_uuid(arcpy.env.scratchGDB))),
            out_coor_system=arcpy.Describe(os.path.dirname(hydro_network)).spatialReference
        )

        # rip the geometries from the access out into a list
        projected_geometry_list = [row[0] for row in arcpy.da.SearchCursor(projected_putin_takeout, 'SHAPE@')]

        # create feature layer for the trace tool
        oid_takeout = [_[0] for _ in arcpy.da.SearchCursor(projected_putin_takeout, 'OID@')][1]
        oid_field_name = [f.name for f in arcpy.ListFields(projected_putin_takeout) if f.type == 'OID'][0]
        lyr_takeout = arcpy.MakeFeatureLayer_management(
            in_features=projected_putin_takeout,
            where_clause="{} = {}".format(oid_field_name, oid_takeout)
        )

        # trace upstream from the takeout
        group_layer = arcpy.TraceGeometricNetwork_management(hydro_network, _add_uid('upstream'),
                                                             lyr_takeout, 'TRACE_UPSTREAM')[0]

        # extract the flowline layer with upstream features selected from the group layer
        hydroline_layer = arcpy.mapping.ListLayers(group_layer, '*Flowline')[0]

        # get geometry objects of upstream flowline
        geometry_list = [row[0] for row in arcpy.da.SearchCursor(hydroline_layer, 'SHAPE@')]

        # iterate the hydroline geometry objects
        for hydroline_geometry in geometry_list:

            # test if the putin is coincident with the hydroline geometry segment
            if projected_geometry_list[0].within(hydroline_geometry):

                # if coincident, good to go, and exiting function
                self.error = False
                return True

        # if every hydroline segment gets tested, and none of them are coincident with the putin, error
        self.error = True
        self.notes = 'reach put-in is not upstream from take-out'
        return False

    def validate(self, hydro_network):
        """
        Make sure the reach is valid.
        :param access_fc: The point feature class for accesses. There must be an attribute named putin and another
            named takeout. These fields must store the AW id for the point role as a putin or takeout.
        :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology
            Dataset.
        :return: Boolean indicating if the reach is valid or not.
        """
        # although kind of kludgy, since we keep encountering an error I cannot sort out, this is a catch all to keep
        # the script running
        try:

            # first, check if there are even two accesses to work with
            if not self._validate_has_putin_and_takeout():
                return False

            # create a hydroline layer
            fds_path = os.path.dirname(arcpy.Describe(hydro_network).catalogPath)

            # set workspace so list feature classes works
            arcpy.env.workspace = fds_path

            # create layer for NHD hydrolines
            hydroline_lyr = arcpy.MakeFeatureLayer_management(
                in_features=os.path.join(fds_path, arcpy.ListFeatureClasses('*Flowline')[0]),
                out_layer='hydroline_lyr{}'.format(uuid.uuid4())
            )

            # project the points to match the hydro_net, so the snapping will work
            self._project_points_to_hydro_net(hydro_network)

            # to give the data the benefit of doubt, snap the points to the hydrolines within 500 feet
            self._snap_accesses_to_hydrolines(hydroline_lyr)

            # now test for put-in and take-out coincidence with hydrolines
            if not self._validate_putin_takeout_coincidence(hydro_network):
                return False

            # also test to ensure hydroline is traceable
            if not self._validate_putin_upstream_from_takeout(hydro_network):
                return False

            # set the hydroline geometry
            if not self.set_hydroline_geometry(hydro_network):
                return False

            # if all the tests passed and tracing the hydroline was successful
            else:
                self.error = False
                return True

        # if something goes wrong
        except Exception as e:

            # return false and let user know this reach is problematic
            self.error = True
            message = e.message.replace('\n', ' ').replace('\r', ' ')
            self.notes = message
            arcpy.AddMessage('{} caused an unspecified error - '.format(self.reach_id, message))
            return False

    def _get_reach_points(self, category=None, subcategory=None):
        """
        Retrieve reach points using category and subcategory identifiers.
        :param category: Primary point category as string.
        :param subcategory: Secondary point category as a string.
        :return: List of reach points fulfilling the request.
        """
        # if only the category is provided
        if len(category) and subcategory is None:
            return [point for point in self.points if point.category == category]

        # if only the subcategory is provided
        elif len(subcategory) and category is None:
            return [point for point in self.points if point.subcategory == subcategory]

        # if both the category and subcategory are provided
        elif len(category) and len(subcategory):
            return [point for point in self.points if point.category == category and point.subcategory == subcategory]

        # otherwise, just give back all the points
        else:
            return self.points

    def get_access_points(self, access_type=None):
        """
        Get a list of reach points based on the access type specified.
        :param access_type: Type of access, either putin, takeout, or intermediate.
        :return: List of reach points of the specified type if they exist, or none if it does not.
        """

        # if an access type is specified
        if access_type is not None:

            # convert the access type provided to lower case and strip out any dashes or spaces
            access_type = access_type.lower().replace('-', '').replace(' ', '')

            # if the access type is not putin, takeout, or intermediate, raise error
            if access_type not in ['putin', 'takeout', 'intermediate']:
                raise Exception('Access type for get_access_points must be either putin, takeout, or intermediate')

            # retrieve the accesses from the reach points
            access_points = self._get_reach_points('access', access_type)

        # if an access type is not specified, just get the accesses
        else:
            access_points = self._get_reach_points('access')

        if len(access_points):
            return access_points
        else:
            return []

    @property
    def reachpoint_putin(self):
        putin_list = self.get_access_points('putin')
        if len(putin_list):
            return putin_list[0]
        else:
            return None

    @property
    def reachpoint_takeout(self):
        takeout_list = self.get_access_points('takeout')
        if len(takeout_list):
            return takeout_list[0]
        else:
            return None

    @property
    def row_centroid(self):
        """
        Get a centroid row for writing out to a feature class.
        :return: Centroid row as a list.
        """
        # remap error to text
        if self.error:
            error = 'true'
        else:
            error = 'false'

        # output a row with relevant information for possibly fixing the errors
        return [self.reach_id, self.name, self.river_name, self.river_alternate_name, error, self.notes, self.centroid]

    @property
    def row_hydroline(self):
        """
        Get a hydroline row for writing out to a feature class.
        :return: Hydroline row as a list.
        """
        return [self.reach_id, self.manual_digitize, self.hydroline]

    @property
    def rows_access(self):
        """
        Get access rows for writing out to a feature class.
        :return: List of lists representing all the accesses.
        """
        # create a list of lists using a list comprehension, and return the result
        return [[a.reach_id, a.category, a.subcategory, 'AW'] for a in self.get_access_points()]

    def set_hydroline_geometry(self, hydro_network):
        """
        Set hydroline geometry for the reach using the putin and takeout access points identified using the self id.
        :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology
            Dataset.
        :return: Polyline Geometry object representing the reach hydroline.
        """
        # if the reach is not manually digitized
        if not self.manual_digitize:

            # get putin and takeout geometry
            putin_geometry = self.reachpoint_putin.geometry
            takeout_geometry = self.reachpoint_takeout.geometry

            # trace network connecting the putin and the takeout, this returns all intersecting line segments
            group_layer = arcpy.TraceGeometricNetwork_management(hydro_network, _add_uid('downstream'),
                                                                 [putin_geometry, takeout_geometry],
                                                                 'FIND_PATH', )[0]

            # extract the flowline layer with upstream features selected from the group layer
            hydroline_layer = arcpy.mapping.ListLayers(group_layer, '*Flowline')[0]

            # dissolve into minimum segments and save back into a geometry object
            hydroline = arcpy.Dissolve_management(hydroline_layer, arcpy.Geometry())

            # split hydroline at the putin and takeout, generating dangling hydroline line segments dangles
            # above and below the putin and takeout and saving as in memory feature class since trim line does
            # not work on a geometry list
            for access in [putin_geometry, takeout_geometry]:
                hydroline = arcpy.SplitLineAtPoint_management(
                    hydroline, access, 'in_memory/split{}'.format(_get_valid_uuid('in_memory'))
                )[0]

            # trim ends of reach off above and below the putin and takeout
            arcpy.TrimLine_edit(hydroline)

            # pull out just geometry objects
            hydroline_geometry = [row[0] for row in arcpy.da.SearchCursor(hydroline, 'SHAPE@')]

            # assemble save results
            self.error = False
            self.hydroline = hydroline_geometry

            # return the success status
            return True


class _FeatureSet(object):
    """
    Parent template class for both hydropoints and hydrolines. This class is not intended to be used outside this module
    autonomously.
    """

    _name = 'placeholder'  # name for feature class to be overridden
    _row_name_list = []  # list of field names for the insert cursor

    def __init__(self, workspace, spatial_reference=None):
        self.workspace = workspace
        self.path = os.path.join(workspace, self._name)

        # if no spatial reference provided, set to NAD83, what all the USGS data is in
        if spatial_reference is None:
            self.spatial_reference = arcpy.SpatialReference(4269)

        # if the feature class does not already exist, add it with the reach id field
        if not arcpy.Exists(self.path):
            self._create_feature_class()
            self._add_text_field('reach_id', 'Reach ID', field_is_nullable=False)

        # if not already added, add a text boolean domain
        domain_name = 'boolean'
        if domain_name not in [domain.name for domain in arcpy.da.ListDomains(workspace)]:
            arcpy.CreateDomain_management(in_workspace=workspace, domain_name=domain_name, field_type='TEXT',
                                          domain_type='CODED')
            for value in ['true', 'false']:
                arcpy.AddCodedValueToDomain_management(in_workspace=workspace, domain_name=domain_name, code=value,
                                                       code_description=value)

    # short helper to consolidate adding all the text fields
    def _add_text_field(self, field_name, field_alias, field_length=10, field_is_nullable=True):
        arcpy.AddField_management(in_table=self.path, field_name=field_name, field_alias=field_alias,
                                  field_type='TEXT', field_length=field_length, field_is_nullable=field_is_nullable)

    def _create_feature_class(self):
        pass

    def write_rows(self, list_of_rows):
        """
        When provied with a list of rows, also as lists, so a list of lists, use an update cursor to write these to the
            feature class.
        :param list_of_rows: Properly formatted list of rows
        :return:
        """
        # remove rows if they already exist
        sql_query = ' OR '.join(["reach_id = {id}".format(id=row[0]) for row in self._row_name_list])
        layer = arcpy.MakeFeatureLayer_management(self.path, 'delete_rows', sql_query)
        arcpy.DeleteFeatures_management(layer)

        # insert the new rows
        with arcpy.da.InsertCursor(self.path, self._row_name_list) as insert_cursor:
            for row in list_of_rows:
                insert_cursor.insertRow(row)

    def update_rows(self, list_of_rows):
        """
        Wrapper to write rows for submitting updates.
        :param list_of_rows: Properly formatted list of rows
        :return:
        """
        self.write_rows(list_of_rows)


class FeatureSetHydroline(_FeatureSet):

    # set the name for the feature class
    _name = 'hydroline'
    _row_name_list = ['reach_id', 'manual_digitize', 'SHAPE@']

    def _create_feature_class(self):
        """
        Create the output hydroline feature class.
        :return: Path to created resource
        """
        # create output hydroline feature class
        hydroline_fc = arcpy.CreateFeatureclass_management(out_path=os.path.dirname(self.path), out_name=self._name,
                                                           geometry_type='POLYLINE',
                                                           spatial_reference=self.spatial_reference)[0]

        # add field to track digitizing source
        digitize_field = 'manual_digitize'
        self._add_text_field(digitize_field, 'Manually Digitized', field_is_nullable=False)
        arcpy.AssignDomainToField_management(in_table=hydroline_fc, field_name=digitize_field, domain_name='boolean')
        arcpy.AssignDefaultToField_management(in_table=hydroline_fc, field_name=digitize_field, default_value='false')

    def is_hydroline_manually_digitized(self, reach_id):
        """
        Check to see if the hydroline feature has been manually digitized.
        :param reach_id: Reach id being processed.
        :return: Boolean indicating if reach is manually digitized.
        """
        # create a feature layer and select the feature using the reach id and manually digitized fields
        hydro_layer = arcpy.MakeFeatureLayer_management(
            in_features=self.path,
            out_layer='hydroline_{}'.format(reach_id),
            where_clause="reach_id = '{}' AND manual_digitize = 'true'".format(reach_id)
        )

        # if the feature count is zero, it is false, but if any other number, it will return a true value
        if int(arcpy.GetCount_management(hydro_layer)[0]):
            return True
        else:
            return False


class FeatureSetCentroid(_FeatureSet):

    # set the name of the feature class
    _name = 'centroid'
    _row_name_list = ['reach_id', 'error', 'notes', 'abstract', 'description', 'difficulty', 'difficulty_minimum',
                      'difficulty_maximum', 'difficulty_outlier', 'SHAPE@']

    def _create_feature_class(self):
        """
        Create centroid output feature class.
        :return: Path to the created feature class.
        """
        # workspace where data will be stored
        gdb = os.path.dirname(self.path)

        # create output hydroline feature class
        centroid_fc = arcpy.CreateFeatureclass_management(out_path=gdb, out_name=os.path.basename(self.path),
                                                          geometry_type='POINT',
                                                          spatial_reference=self.spatial_reference)[0]

        # add all the text fields
        self._add_text_field('reach_id', 'Reach ID')
        self._add_text_field('error', 'Error')
        self._add_text_field('notes', 'Notes', 700)
        self._add_text_field('abstract', 'Abstract', 1000)
        self._add_text_field('description', 'Description', 50000)
        self._add_text_field('difficulty', 'Difficulty')
        self._add_text_field('difficulty_minimum', 'Difficulty - Minimum')
        self._add_text_field('difficulty_maximum', 'Difficulty - Maximum')
        self._add_text_field('difficulty_outlier', 'Difficulty- Outlier')

        # assign the boolean domain to the error field
        arcpy.AssignDomainToField_management(in_table=centroid_fc, field_name='error', domain_name='boolean')

        return centroid_fc


class FeatureSetAccess(_FeatureSet):

    _name = 'access'
    _row_name_list = ['reach_id', 'category', 'subcategory']

    def _create_feature_class(self):
        """
        Create access output feature class.
        :return: Path to the created feature class.
        """
        # workspace where data will be stored
        gdb = os.path.dirname(self.path)

        # create output hydroline feature class
        access_fc = arcpy.CreateFeatureclass_management(out_path=gdb, out_name=os.path.basename(self.path),
                                                        geometry_type='POINT',
                                                        spatial_reference=self.spatial_reference)[0]

        # add the text fields
        self._add_text_field('reach_id', 'Reach ID')
        self._add_text_field('category', 'Category')
        self._add_text_field('subcategory', 'Subcategory')
        self._add_text_field('updated_by', 'Updated By')

        return access_fc


class ReachCollection(object):

    def __init__(self, output_geodatabase):
        self._consecutive_fail_count = 0
        self._reach_id_current = 1
        self.hydroline = FeatureSetHydroline(output_geodatabase)
        self.centroid = FeatureSetCentroid(output_geodatabase)
        self.access = FeatureSetAccess(output_geodatabase)

    @staticmethod
    def _lookup_huc4(reach_centroid_geometry, huc4_polygons, huc4_field='huc4'):
        """
        Since the NHD is broken into HUC4 subregions, use a polygon feature class to look up the HUC4 code.
        :param reach_centroid_geometry: Centroid as a point geometry for the reach.
        :param huc4_polygons: Feature class or feature layer delineating HUC4 regions.
        :param huc4_field: Field in HUC4 feature class containing the HUC4 code.
        :return: String with HUC4 code.
        """
        # iterate the geometries of the huc4 polygons and return the one first intersecting with the centroid
        for row in arcpy.da.SearchCursor(huc4_polygons, [huc4_field, 'SHAPE@']):

            # if the reach centroid falls within the current HUC4 geometry, return the HUC4 code as a string
            if reach_centroid_geometry.within(row[1]):
                return '{}'.format(row[0]).strip()

        # otherwise, just return nothing
        return None

    def download_validate_and_save(self, nhd_directory, huc4_polygons):
        """
        Download all the data from American Whitewater, and create a geodatabase with the results.
        :return: Tuple with paths to output resources.
        """

        # while the consecutive missing reach count is less than 100
        while self._consecutive_fail_count < 1000:

            # create a reach object instance with the current reach id
            reach = Reach(self._reach_id_current)

            # attempt to download the reach, and record the status
            download_success = reach.download()

            # if the download was successful
            if download_success:

                # reset the fail count
                self._consecutive_fail_count = 0

                # ensure there is geometry to work with
                if reach.reachpoint_putin or reach.reachpoint_takeout:

                    # validate the reach using a path to the relevant geometric network assembled using the location
                    reach.validate(os.path.join(
                        nhd_directory,
                        '{}.gdb'.format(self._lookup_huc4(reach.centroid, huc4_polygons)),
                        'Hydrography',
                        'HYDRO_NET'
                    ))

                    # save the results of the validation with the centroid
                    self.centroid.write_rows([reach.row_centroid])

                    # save the accesses
                    self.access.write_rows([reach.rows_access])

                    # if valid, write out the geometry for the hydroline
                    if reach.error == 'false':
                        self.hydroline.write_rows([reach.row_hydroline])

            # if the download did not work, increment the fail count
            else:
                self._consecutive_fail_count += 1

            # increment the reach id
            self._reach_id_current += 1
