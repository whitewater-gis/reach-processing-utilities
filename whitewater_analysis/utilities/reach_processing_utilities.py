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


def _get_valid_uuid(workspace):
    """
    Helper function to get uuid formatted for table names.
    :param workspace: Path to workspace being used for object storage.
    :return: Validated uuid string without underscores.
    """
    return arcpy.ValidateTableName(name=uuid.uuid4(), workspace=workspace).replace('_', '')


class ReachPoint:

    def __init__(self, reach_id):
        self.reach_id = reach_id
        self.tags = []
        self.geometry = None


class Reach:

    def __init__(self, reach_id):
        self.reach_id = str(int(reach_id))
        self.error = None
        self.notes = None
        self.abstract = None
        self.description = None
        self.difficulty = None
        self.difficulty_minimum = None
        self.difficulty_maximum = None
        self.difficulty_outlier = None
        self.geometry_line = None
        self.line_manual = None
        self.points = []
        self._accesses_collected = False

    def set_access_points_from_access_feature_class(self, access_feature_class):
        """
        Get the access points from the access feature class for the reach, and also set the centroid point as well.
        :param access_feature_class: String path to the access feature class.
        :return:
        """

        # helper to calculate the centroids
        def get_mean_coordinate(first_coordinate, second_coordinate):
            return min(first_coordinate, second_coordinate) + abs(first_coordinate - second_coordinate) / 2

        # for each of the three geometry types
        for access_type in ['putin', 'takeout', 'intermediate']:

            # declare variables
            putin_geometry = None
            takeout_geometry = None

            # get a list of geometry objects for each type
            access_geometries = self._get_access_geometries_from_access_fc(access_feature_class, access_type)

            # if any geometries were extracted
            if len(access_geometries):

                # itereate each geometry, create a hydropoint, and add this hydropoint to the list
                for access_geometry in access_geometries:
                    access = ReachPoint(self.reach_id)
                    access.tags = ['access', access_type]
                    access.geometry = access_geometry
                    self.points.append(access)

                    # save the putin and takeout geometries
                    if access_type == 'putin':
                        putin_geometry = access_geometry
                    elif access_type == 'takeout':
                        takeout_geometry = access_geometry

                # if there is at least one, a putin or a takeout
                if putin_geometry or takeout_geometry:

                    # scaffold out a reach centroid point
                    centroid_point = ReachPoint(self.reach_id)
                    centroid_point.tags.append('centroid')

                    # if there is only one access, use this as the centroid
                    if not putin_geometry:
                        centroid_point.geometry = takeout_geometry
                    elif not takeout_geometry:
                        centroid_point.geometry = putin_geometry

                    # if there is both a putin and takeout, then use the mean coordinates as the centroid
                    else:
                        centroid_x = get_mean_coordinate(putin_geometry.geometry.centroid.X,
                                                         takeout_geometry.geometry.centroid.X)
                        centroid_y = get_mean_coordinate(putin_geometry.geometry.centroid.Y,
                                                         takeout_geometry.geometry.centroid.Y)
                        centroid_point.geometry = arcpy.Geometry('POINT', arcpy.Point(centroid_x, centroid_y))

                    # add the reach point to the reach point list
                    self.points.append(centroid_point)

        # set the flag to true
        self._accesses_collected = True

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
        # if the accesses have not been set, do this now
        if not self._accesses_collected:
            self.set_access_points_from_access_feature_class(access_fc)

        # although kind of kludgy, since we keep encountering an error I cannot sort out, this is a catch all to keep
        # the script running
        try:

            # run all the tests
            if (
                self._validate_has_putin_and_takeout() and
                self._validate_putin_takeout_coincidence(access_fc, hydro_network) and
                self._validate_putin_upstream_from_takeout(access_fc, hydro_network)
            ):
                arcpy.AddMessage('{} is valid, and will be processed.'.format(self.reach_id))
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
        # if inclusive is true, and each point must contain all the supplied tags
        if inclusive and len(self.points):

            # create a list of points with tags matching all the provided tags
            points = [point for point in self.points if set(point_tag_list).issubset(set(point.tags))]

        # if not inclusive, and each point must only contain one of the supplied tags
        elif not inclusive and len(self.points):

            # create a list of points with tags matching any of the provided tags
            points = [point for point in self.points if set(point_tag_list).intersection(set(point.tags))]

        # return an empty list if there are no points or the created list of points if any found
        if len(points):
            return points
        else:
            return []

    def get_access_points(self, access_type=None):
        """
        Get a list of hydropoints based on the access type specified.
        :param access_type: Type of access, either putin, takeout, or intermediate.
        :return: List of hydropoints of the specified type if they exist, or none if it does not.
        """
        # convert the access type provided to lower case and strip out any dashes or spaces
        access_type = access_type.lower().replace('-', '').replace(' ', '')

        # if the access type is not putin, takeout, or intermediate, raise error
        if access_type not in ['putin', 'takeout', 'intermediate']:
            raise Exception('Access type for get_access_points must be either putin, takeout, or intermediate')

        if access_type is not None:
            access_points = self._get_reach_points(['access', access_type])
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

    def get_centroid_reachpoint(self):
        """
        From two geometry objects, one for the location of the putin and another for the location of the takeout,
        calculate the middle, halfway between the two, to use as a marker, the centroid for the reach.
        :param access_fc: Access feature class to find the accesses.
        :return:
        """
        # if the centroid property has already been set, return it
        centroid_point_list = [point for point in self.points if set('centroid').intersection(set(point.tags))]
        if len(centroid_point_list):
            return centroid_point_list[0]

        # otherwise, create the reach point, and then return it
        else:
            self._create_centroid_reachpoint
            return [point for point in self.points if set('centroid').intersection(set(point.tags))][0]

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
        return [self.reach_id, error, self.notes, self.abstract, self.description, self.difficulty,
                self.difficulty_minimum, self.difficulty_maximum, self.difficulty_outlier, self._geometry_centroid]

    def get_hydroline_row(self):
        """
        Get a hydroline row for writing out to a feature class.
        :return: Hydroline row as a list.
        """
        return [self.reach_id, self.line_manual, self.geometry_line]

    @staticmethod
    def set_hydroline_geometry_multithreaded(params):
        """
        Multiprocessing wrapper for set hydroline geometry object.
        :param params: HydrolineProcessing object.
        :return: Reach object
        """
        return Reach.set_hydroline_geometry(params.reach, params.access_fc, params.hydro_network)

    @staticmethod
    def set_hydroline_geometry(reach, access_fc, hydro_network):
        """
        Set hydroline geometry for the reach using the putin and takeout access points identified using the reach id.
        :param access_fc: The point feature class for accesses. There must be an attribute named putin and another named
                          takeout. These fields must store the reach id for the point role as a putin or takeout.
        :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology
            Dataset.
        :return: Polyline Geometry object representing the reach hydroline.
        """
        # if the reach is not manaully digitized
        if not reach.line_manual:

            # run validation tests
            valid = reach.validate(access_fc, hydro_network)

            # if the reach validates
            if valid:

                # catch undefined errors being encountered
                try:

                    # get putin and takeout geometry
                    takeout_geometry = reach.get_putin_reachpoint()
                    putin_geometry = reach.get_takeout_reachpoint()

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
                    fc_name = _get_valid_uuid('in_memory')
                    for access in [putin_geometry, takeout_geometry]:
                        hydroline = arcpy.SplitLineAtPoint_management(hydroline, access,
                                                                      'in_memory/split{}'.format(fc_name))[0]

                    # trim ends of reach off above and below the putin and takeout
                    arcpy.TrimLine_edit(hydroline)

                    # pull out just geometry objects
                    hydroline_geometry = [row[0] for row in arcpy.da.SearchCursor(hydroline, 'SHAPE@')]

                    # assemble save results
                    reach.error = False
                    reach.geometry_line = hydroline_geometry

                    # return the reach
                    return reach

                # if something bombs, at least record what the heck happened and keep from crashing the entire run
                except Exception as e:

                    # remove newline characters with space in error string
                    message = e.message.replace('\n', ' ')

                    # report error to front end
                    arcpy.AddWarning(
                        'Although {} passed validation, it still bombed the process. ERROR: {}'.format(
                            reach.reach_id, message))

                    # populate the error properties
                    reach.error = True
                    reach.notes = message

                    # return the reach
                    return reach


class _FeatureCollection:
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
    def process_reaches(access_fc, hydro_network, output_workspace):
        """
        Create a hydropoint and hydroline feature class using an access feature class with putins and takeouts to determine
            the hydropoints from the averaged centroid, and trace the USGS NHD hydrolines to get the hydrolines.
        :param access_fc: The point feature class for accesses. There must be an attribute named putin and another named
                          takeout. These fields must store the reach id for the point role as a putin or takeout.
        :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology Dataset.
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
