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
import multiprocessing
import math
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


class ReachPoint(object):

    def __init__(self, reach_id, tags=None, geometry=None):
        self.reach_id = int(reach_id)
        if tags is None:
            self.tags = []
        elif type(tags) != list:
            raise Exception('ReachPoint tags must be a list of strings.')
        else:
            self.tags = tags
        self.geometry = geometry


class Reach:

    def __init__(self, reach_id):
        self.reach_id = int(reach_id)
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
        self.digitize = None
        self.points = []
        self.point = None
        self._accesses_collected = False

    def download(self):
        response = requests.get(self.url)
        if response.status_code == 200:
            raw_json = response.json()
            self._parse_json(raw_json)
        else:
            raise Warning('American Whitewater server could not be reached for reach ID {}.'.format(self.reach_id))

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
        if len(match_string):
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
            if not len(value):
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
        self.river_name = self._validate_aw_json(reach_info, 'river');
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
                    tags=['access', 'putin'],
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
                    tags=['access', 'takeout'],
                    geometry=arcpy.PointGeometry(
                        arcpy.Point(float(reach_info['tlon']), float(reach_info['tlat'])),
                        arcpy.SpatialReference(4326)
                    )
                )
            )

        # set the centroid based on the available put-in, and take-out location information
        self.set_centroid()

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
                    self.points.append(ReachPoint(self.reach_id, ['access', access_type], access_geometry))

        # set the centroid
        self.set_centroid()

        # set the flag to true
        self._accesses_collected = True

    def set_centroid(self):
        """
        If possible, set the centroid for the reach from the accesses contained in the reach points.
        :return:
        """
        # get the putin and takeout reach points from the list
        putin = self.get_putin_reachpoint()
        takeout = self.get_takeout_reachpoint()

        # if both accesses, use the mean center, but if only one, use the one we have to work with
        if takeout is not None and putin is not None:
            self.point = self._get_mean_point_geometry(putin.geometry, takeout.geometry)
        elif takeout is not None:
            self.point = takeout.geometry
        elif putin is not None:
            self.point = putin.geometry

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
        if self.get_putin_reachpoint() and self.get_takeout_reachpoint():
            self.error = False
            return True
        else:
            self.error = True
            self.notes = 'reach does not have both a put-in and take-out'
            return False

    def _validate_putin_takeout_coincidence(self, access_fc, hydro_network):
        """
        Ensure the putin and takeout are coincident with the USGS hydrolines. Just to compensate for error, the access
        points will be snapped to the hydrolines if they are within 500 feet since there can be a slight discrepancy in
        data sources' idea of exactly where the river center line actually is.
        :param access_fc: The point feature class for accesses. There must be an attribute named putin and another named
            takeout. These fields must store the AW id for the point role as a putin or takeout.
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

        # get the path to the accesses feature class
        data_source = arcpy.Describe(access_fc).path

        # sql statement
        sql_select = "{0} = '{1}' AND( {2} = 'putin' OR {3} = 'takeout' )".format(
            arcpy.AddFieldDelimiters(data_source, 'reach_id'),
            self.reach_id,
            arcpy.AddFieldDelimiters(data_source, 'type'),
            arcpy.AddFieldDelimiters(data_source, 'type')
        )

        # create an access layer
        access_lyr = arcpy.MakeFeatureLayer_management(
            access_fc, 'putin_takeout_coincidence{}'.format(uuid.uuid4()),
            where_clause=sql_select
        )[0]

        # snap the putin & takeout to the hydro lines - this does not affect the permanent data set, only this analysis
        arcpy.Snap_edit(access_lyr, [[hydroline_lyr, 'EDGE', '500 Feet']])

        # select by location, selecting accesses coincident with the hydrolines
        arcpy.SelectLayerByLocation_management(access_lyr, "INTERSECT", hydroline_lyr, selection_type='NEW_SELECTION')

        # if successful, two access features should be selected, the put in and the takeout
        if int(arcpy.GetCount_management(access_lyr)[0]) == 2:
            self.error = False
            return True
        else:
            self.error = True
            self.notes = 'reach putin and takeout are not coincident with hydrolines'
            return False

    def _validate_putin_upstream_from_takeout(self, access_fc, hydro_network):
        """
        Ensure the putin is indeed upstream of the takeout.
        :param putin_geometry: Point Geometry object for the putin.
        :param takeout_geometry: Point Geometry object for the takeout.
        :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology Dataset
        :return: boolean: Indicates if when tracing the geometric network upstream from the takeout, if the putin is
                          upstream from the takeout.
        """
        # get the path to the accesses feature class
        data_source = arcpy.Describe(access_fc).path

        # create selection sql
        def get_where(reach_id, access_type):
            return "{}='{}' AND {}='{}'".format(
                arcpy.AddFieldDelimiters(data_source, 'reach_id'),
                reach_id,
                arcpy.AddFieldDelimiters(data_source, 'type'),
                access_type
            )

        # get geometry object for putin and takeout
        takeout_geometry = arcpy.Select_analysis(access_fc, arcpy.Geometry(), get_where(self.reach_id, 'takeout'))[0]
        putin_geometry = arcpy.Select_analysis(access_fc, arcpy.Geometry(), get_where(self.reach_id, 'putin'))[0]

        # trace upstream from the takeout
        group_layer = arcpy.TraceGeometricNetwork_management(hydro_network, 'upstream{}'.format(uuid.uuid4()),
                                                             takeout_geometry, 'TRACE_UPSTREAM')[0]

        # extract the flowline layer with upstream features selected from the group layer
        hydroline_layer = arcpy.mapping.ListLayers(group_layer, '*Flowline')[0]

        # get geometry objects of upstream flowline
        geometry_list = [row[0] for row in arcpy.da.SearchCursor(hydroline_layer, 'SHAPE@')]

        # iterate the hydroline geometry objects
        for hydroline_geometry in geometry_list:

            # test if the putin is coincident with the hydroline geometry segment
            if putin_geometry.within(hydroline_geometry):

                # if coincident, good to go, and exiting function
                self.error = False
                return True

        # if every hydroline segment gets tested, and none of them are coincident with the putin, error
        self.error = True
        self.notes = 'reach put-in is not upstream from take-out'
        return False

    def validate(self, access_fc, hydro_network):
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

            # run all the tests
            if (
                self._validate_has_putin_and_takeout() and
                self._validate_putin_takeout_coincidence(access_fc, hydro_network) and
                self._validate_putin_upstream_from_takeout(access_fc, hydro_network)
            ):
                arcpy.AddMessage('{} is valid.'.format(self.reach_id))
                return True
            # if there is not an error
            else:
                return False


        # if something goes wrong
        except Exception as e:

            # return false and let user know this reach is problematic
            self.error = True
            message = e.message.replace('\n', ' ').replace('\r', ' ')
            self.notes = message
            arcpy.AddMessage('{} caused an unspecified error - '.format(self.reach_id, message))
            return False

    def _get_reach_points(self, point_tag_list=None, inclusive=True):
        """
        Retrieve reach points using tags.
        :param point_tag_list: List of tags to use for retrieving reach points.
        :param inclusive: Boolean indicating if all supplied tags must be true for every point, or just one of the
            provided tags to include the point in the returned list.
        :return: List of reach points fulfilling the request.
        """
        # create dummy variable
        points = []

        # if no tags are provided, simply populate with all points
        if point_tag_list is None:
            points = self.points

        # if inclusive is true, and each point must contain all the supplied tags
        elif inclusive and len(self.points) and len(point_tag_list):

            # create a list of points with tags matching all the provided tags
            points = [point for point in self.points if set(point_tag_list).issubset(set(point.tags))]

        # if not inclusive, and each point must only contain one of the supplied tags
        elif not inclusive and len(self.points) and len(point_tag_list):

            # create a list of points with tags matching any of the provided tags
            points = [point for point in self.points if set(point_tag_list).intersection(set(point.tags))]

        # return what ever points turns out to be...an empty list or otherwise
        return points

    def get_access_points(self, access_type=None):
        """
        Get a list of hydropoints based on the access type specified.
        :param access_type: Type of access, either putin, takeout, or intermediate.
        :return: List of hydropoints of the specified type if they exist, or none if it does not.
        """

        # if an access type is specified
        if access_type is not None:

            # convert the access type provided to lower case and strip out any dashes or spaces
            access_type = access_type.lower().replace('-', '').replace(' ', '')

            # if the access type is not putin, takeout, or intermediate, raise error
            if access_type not in ['putin', 'takeout', 'intermediate']:
                raise Exception('Access type for get_access_points must be either putin, takeout, or intermediate')

            # retrieve the accesses from the reach points
            access_points = self._get_reach_points(['access', access_type])

        # if an access type is not specified, just get the accesses
        else:
            access_points = [point for point in self.points if 'access' in point.tags]

        if len(access_points):
            return access_points
        else:
            return []

    def get_putin_reachpoint(self):
        putin_list = self.get_access_points('putin')
        if len(putin_list):
            return putin_list[0]
        else:
            return None

    def get_takeout_reachpoint(self):
        takeout_list = self.get_access_points('takeout')
        if len(takeout_list):
            return takeout_list[0]
        else:
            return None

    def get_centroid_row(self):
        """
        Get a centroid row for writing out to a feature class.
        :return: Centroid row as a list.
        """
        # remap error to text
        if self.error:
            error = 'true'
        else:
            error = 'false'

        # get the centroid
        centroid = self.point.centroid.geometry
        return [self.reach_id, error, self.notes, self.abstract, self.description, self.difficulty,
                self.difficulty_minimum, self.difficulty_maximum, self.difficulty_outlier, centroid.geometry]

    def get_hydroline_row(self):
        """
        Get a hydroline row for writing out to a feature class.
        :return: Hydroline row as a list.
        """
        return [self.reach_id, self.digitize, self.hydroline]

    @staticmethod
    def set_hydroline_geometry_multithreaded(params):
        """
        Multiprocessing wrapper for set hydroline geometry object.
        :param params: HydrolineProcessing object.
        :return: Reach object
        """
        return Reach.set_hydroline_geometry(params.reach, params.access_fc, params.hydro_network)

    def set_hydroline_geometry(self, access_fc, hydro_network):
        """
        Set hydroline geometry for the reach using the putin and takeout access points identified using the self id.
        :param access_fc: The point feature class for accesses. There must be an attribute named putin and another named
                          takeout. These fields must store the reach id for the point role as a putin or takeout.
        :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology
            Dataset.
        :return: Polyline Geometry object representing the reach hydroline.
        """
        # if the reach is not manaully digitized
        if not self.digitize:

            # run validation tests
            valid = self.validate(access_fc, hydro_network)

            # if the reach validates
            if valid:

                # catch undefined errors being encountered
                try:

                    # get putin and takeout geometry
                    takeout_geometry = (self.get_putin_reachpoint()).geometry
                    putin_geometry = (self.get_takeout_reachpoint()).geometry

                    # trace network connecting the putin and the takeout, this returns all intersecting line segments
                    group_layer = arcpy.TraceGeometricNetwork_management(hydro_network, 'downstream',
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

                    # return the reach hydroline geometry
                    return self.hydroline

                # if something bombs, at least record what the heck happened and keep from crashing the entire run
                except Exception as e:

                    # remove newline characters with space in error string
                    message = e.message.replace('\n', ' ')

                    # report error to front end
                    arcpy.AddWarning(
                        'Although {} passed validation, it still bombed the process. ERROR: {}'.format(
                            self.reach_id, message))

                    # populate the error properties
                    self.error = True
                    self.notes = message

                    # return nothing since it blew up
                    return None


class _FeatureCollection(object):
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
            self._add_text_field('reach_id', 'Reach ID')

        # if not already added, add a text boolean domain
        if 'boolean' not in [domain.name for domain in arcpy.da.ListDomains(workspace)]:
            arcpy.CreateDomain_management(in_workspace=workspace, domain_name='boolean', field_type='TEXT',
                                          domain_type='CODED')
            arcpy.AddCodedValueToDomain_management(in_workspace=workspace, domain_name='boolean', code='false',
                                                   code_description='false')
            arcpy.AddCodedValueToDomain_management(in_workspace=workspace, domain_name='boolean', code='true',
                                                   code_description='true')

    # short helper to consolidate adding all the text fields
    def _add_text_field(self, field_name, field_alias, field_length=10):
        arcpy.AddField_management(in_table=self.path, field_name=field_name, field_alias=field_alias,
                                  field_type='TEXT', field_length=field_length)

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


class FeatureCollectionHydroline(_FeatureCollection):

    # set the name for the feature class
    _name = 'hydroline'
    _row_name_list = ['reach_id', 'manual_digitize', 'SHAPE@']

    def _create_feature_class(self):
        """
        Create the output hydroline feature class.
        :return: Path to created resource
        """
        # create output hydroline feature class
        hydroline_fc = arcpy.CreateFeatureclass_management(out_path=self.path, out_name=self._name,
                                                           geometry_type='POLYLINE',
                                                           spatial_reference=self.spatial_reference)[0]

        # add field to track digitizing source
        digitize_field = 'manual_digitize'
        self._add_text_field(digitize_field, 'Manually Digitized')
        arcpy.AssignDomainToField_management(in_table=hydroline_fc, field_name=digitize_field,
                                             domain_name='boolean')

    def is_hydroline_manually_digitized(self, reach_id):
        """
        Check to see if the hydroline feature class has been manually digitized.
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

    @staticmethod
    def process_reaches_multithreaded(access_fc, hydro_network, output_workspace):
        """
        Create a hydropoint and hydroline feature class using an access feature class with putins and takeouts to 
            determine the hydropoints from the averaged centroid, and trace the USGS NHD hydrolines to get the
            hydrolines.
        :param access_fc: The point feature class for accesses. There must be an attribute named putin and another
            named takeout. These fields must store the reach id for the point role as a putin or takeout.
        :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology
            Dataset.
        :param output_workspace: File geodatabase where the data will be stored.
        :return:
        """

        # class for combining parameters for multiprocessing
        class HydrolineProcessingParams:

            def __init__(self, reach):
                self.reach = reach
                self.access_fc = access_fc
                self.hydro_network = hydro_network

        # helper function to break apart lists into sublists
        def blow_chunks(full_list, sublist_length):
            for i in range(0, len(full_list), sublist_length):
                yield full_list[i:i + sublist_length]

        # get list of reach id's from the accesses not including the NULL or zero values
        reach_id_list = set(row[0] for row in arcpy.da.SearchCursor(access_fc, 'reach_id',
                                                                    "reach_id IS NOT NULL AND reach_id <> '0'"))

        # give a little beta to the front end
        arcpy.AddMessage('{} reaches queued for processing.'.format(len(reach_id_list)))

        # get the spatial reference from the input access feature class, typically nad83 to match the NHD data
        spatial_reference = arcpy.Describe(access_fc).spatialReference

        # progress tracker
        valid_count = 0

        # get the list of batching chunks based on the number of cores available
        cpu_count = multiprocessing.cpu_count()
        chunk_count = math.ceil(len(reach_id_list) / cpu_count)

        # create feature collections for centroids and hydrolines
        centroid_feature_collection = FeatureCollectionCentroid(output_workspace, spatial_reference)
        hydroline_feature_collection = FeatureCollectionHydroline(output_workspace, spatial_reference)

        # break apart the reach id list into sublists for chunked processing and iterate
        for reach_id_chunk in blow_chunks(reach_id_list, cpu_count):

            # create a list of reach object instances for the chunk of reach id's
            reach_instance_chunk = [Reach(reach_id) for reach_id in reach_id_chunk]

            # for set the centroid geometry for each reach instance
            for reach_instance in reach_instance_chunk:
                reach_instance.get_centroid_reachpoint

            # factor the reach instance chunk into a list of hydroline processing parameter object instances
            params_list = [HydrolineProcessingParams(reach) for reach in reach_instance_chunk]

            # use multiprocessing to do the heavy lifting
            with multiprocessing.Pool(cpu_count) as pool:
                reach_instance_chunk = pool.map(Reach.set_hydroline_geometry_multithreaded, params_list)

            # write all the centroids
            centroid_feature_collection.write_rows([reach.get_centroid_row() for reach in reach_instance_chunk])

            # write the valid reaches to the hydrolines
            hydroline_feature_collection.write_rows([reach.get_hydroline_row() for reach in reach_instance_chunk
                                                     if not reach.error])


class FeatureCollectionCentroid(_FeatureCollection):

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
