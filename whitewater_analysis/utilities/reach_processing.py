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
import time
import arcpy

from validate import validate_reach


def create_hydroline_feature_class(full_path_to_hydroline_feature_class, spatial_reference):
    """
    Create the output hydroline feature class.
    :param full_path_to_hydroline_feature_class: The full path to where the data is intended to be stored.
    :return: Path to created resource
    """
    # create output hydroline feature class
    hydroline_fc = arcpy.CreateFeatureclass_management(
        out_path=os.path.dirname(full_path_to_hydroline_feature_class),
        out_name=os.path.basename(full_path_to_hydroline_feature_class),
        geometry_type='POLYLINE',
        spatial_reference=spatial_reference
    )[0]

    # add reach id field
    arcpy.AddField_management(in_table=hydroline_fc, field_name='reach_id', field_type='TEXT', field_length=10)

    # add field to track digitizing source
    arcpy.AddField_management(in_table=hydroline_fc, field_name='manual_digitize', field_type='SHORT')

    # return the path to the feature class
    return hydroline_fc


def create_invalid_table(full_path_to_invalid_table):
    """
    Create the invalid table.
    :param full_path_to_invalid_table: Full path where the invalid table will reside.
    :return: Path to the invalid table.
    """
    # create output invalid reach table
    invalid_tbl = arcpy.CreateTable_management(
        out_path=os.path.dirname(full_path_to_invalid_table),
        out_name=os.path.basename(full_path_to_invalid_table)
    )

    # add field for the reach id in the invalid table
    arcpy.AddField_management(in_table=invalid_tbl, field_name='reach_id', field_type='TEXT', field_length=10)

    # add field in invalid table for reason
    arcpy.AddField_management(in_table=invalid_tbl, field_name='reason', field_type='TEXT', field_length=500)


def check_if_hydroline_manually_digitized(hydroline_feature_class, reach_id):
    """
    Check to see if the hydroline feature class has been manually digitized.
    :param hydroline_feature_class: Path to the hydroline feature class.
    :param reach_id: Reach id being processed.
    :return: Boolean indicating if reach is manually digitized.
    """
    # create a feature layer and select the feature using the reach id and manually digitized fields
    hydro_layer = arcpy.MakeFeatureLayer_management(
        in_features=hydroline_feature_class,
        out_layer='hydroline_{}'.format(reach_id),
        where_clause="reach_id = '{}' AND manual_digitize = 1".format(reach_id)
    )

    # if the feature count is zero, it is false, but if any other number, it will return a true value
    return int(arcpy.GetCount_management(hydro_layer)[0])


def process_reach(reach_id, access_fc, hydro_network):
    """
    Get the hydroline geometry for the reach using the putin and takeout access points identified using the reach id.
    :param reach_id: The reach id for the reach.
    :param access_fc: The point feature class for accesses. There must be an attribute named putin and another named
                      takeout. These fields must store the reach id for the point role as a putin or takeout.
    :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology Dataset.
    :return: Polyline Geometry object representing the reach hydroline.
    """
        
    # run validation tests
    validation = validate_reach(reach_id, access_fc, hydro_network)

    # if the reach does not validate
    if not validation['valid']:

        # return the reason for failing validation
        return validation

    # catch undefined errors being encountered
    try:

        # get putin and takeout geometry
        takeout_geometry = arcpy.Select_analysis(access_fc, arcpy.Geometry(),  "takeout='{}'".format(reach_id))[0]
        putin_geometry = arcpy.Select_analysis(access_fc, arcpy.Geometry(),  "putin='{}'".format(reach_id))[0]

        # trace network connecting the putin and the takeout, this returns all intersecting line segments
        group_layer = arcpy.TraceGeometricNetwork_management(hydro_network, 'downstream',
                                                             [putin_geometry, takeout_geometry], 'FIND_PATH', )[0]

        # extract the flowline layer with upstream features selected from the group layer
        hydroline_layer = arcpy.mapping.ListLayers(group_layer, '*Flowline')[0]

        # dissolve into minimum segments and save back into a geometry object
        hydroline = arcpy.Dissolve_management(hydroline_layer, arcpy.Geometry())

        # split hydroline at the putin and takeout, generating dangling hydroline line segments dangles above and below
        # the putin and takeout and saving as in memory feature class since trim line does not work on a geometry list
        for access in [putin_geometry, takeout_geometry]:
            hydroline = arcpy.SplitLineAtPoint_management(
                hydroline,
                access,
                'in_memory/split{}'.format(int(time.time()*1000))
            )[0]

        # trim ends of reach off above and below the putin and takeout
        arcpy.TrimLine_edit(hydroline)

        # pull out just geometry objects
        hydroline_geometry = [row[0] for row in arcpy.da.SearchCursor(hydroline, 'SHAPE@')]

        # assemble into a success dictionary and return result
        return {
            'valid': True,
            'reach_id': reach_id,
            'geometry_list': hydroline_geometry
        }

    # if something bombs, at least record what the heck happened and keep from crashing the entire run
    except Exception as e:

        # remove newline characters with space in error string
        e = e.message.replace('\n', ' ')

        # report error to front end
        arcpy.AddWarning('Although {} passed validation, it still bombed the process. Here is the error:\n{}'.format(
            reach_id, e))

        # return result as failed reach to be logged in invalid table
        return {'valid': False, 'reach_id': reach_id, 'reason': e}


def get_reach_line_fc(access_fc, hydro_network, reach_hydroline_fc, reach_invalid_tbl):
    """
    Get an output reach feature class using an access feature class with putins and takeouts.
    :param access_fc: The point feature class for accesses. There must be an attribute named putin and another named
                      takeout. These fields must store the reach id for the point role as a putin or takeout.
    :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology Dataset.
    :param reach_hydroline_fc: Output line feature class for output hydrolines.
    :param reach_invalid_tbl: Output table listing invalid reaches with the reason.
    :return:
    """
    # get list of reach id's from the takeouts not including the NULL or zero values
    reach_id_list = [row[0] for row in arcpy.da.SearchCursor(access_fc,
                                                         'takeout', "takeout IS NOT NULL AND takeout <> '0'")]

    # give a little beta to the front end
    arcpy.AddMessage('{} reach id accesses successfully located'.format(len(reach_id_list)))

    # if the output hydroline feature class does not already exist, create it
    if not arcpy.Exists(reach_hydroline_fc):
        create_hydroline_feature_class(reach_hydroline_fc, arcpy.Describe(access_fc).spatialReference)

    # if the invalid table does not already exist, create it
    if not arcpy.Exists(reach_invalid_tbl):
        create_invalid_table(reach_invalid_tbl)

    # progress tracker
    valid_count = 0

    # for every reach
    for reach_id in reach_id_list:

        # check to see if the reach is manually digitized, and if it has been, leave it alone
        if not check_if_hydroline_manually_digitized(reach_hydroline_fc, reach_id):

            # process the current reach
            reach = process_reach(reach_id, access_fc, hydro_network)

            # if the reach is valid
            if reach['valid']:

                # create an insert cursor
                with arcpy.da.InsertCursor(reach_hydroline_fc, ('reach_id', 'manual_digitize', 'SHAPE@')) as cursor:

                    # iterate the geometry objects in the list
                    for geometry in reach['geometry_list']:

                        # insert a record in the feature class for the geometry
                        cursor.insertRow((reach['reach_id'], 0, geometry))

                # increment the valid counter
                valid_count += 1

            # if the reach is not valid
            elif not reach['valid']:

                # create an insert cursor
                with arcpy.da.InsertCursor(reach_invalid_tbl, ('reach_id', 'reason')) as cursor_invalid:

                    # insert a record in the feature class for the geometry
                    cursor_invalid.insertRow((str(reach['reach_id']), reach['reason']))

    # at the very end, report the success rate...or if nothing found...report this as well
    if valid_count:
        arcpy.AddMessage('{}% ({}/{}) reaches were processed.'.format(int(float(valid_count)/len(reach_id_list)*100),
                                                                      valid_count, len(reach_id_list)))

    else:
        arcpy.AddMessage('No reaches found or processed.')


def get_new_hydrolines(access_fc, hydro_network, reach_hydroline_fc, reach_invalid_tbl):
    """
    Process accesses that do not yet have a hydroline.
    :param access_fc: The point feature class for accesses. There must be an attribute named putin and another named
                  takeout. These fields must store the reach id for the point role as a putin or takeout.
    :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology Dataset.
    :param reach_hydroline_fc: Output line feature class for output hydrolines.
    :param reach_invalid_tbl: Output table listing invalid reaches with the reason.
    :return:
    """
    # get a list of all unique permutations of reach ids in the hydroline feature class
    hydroline_reach_id_list = set(row[0] for row in arcpy.da.SearchCursor(reach_hydroline_fc, 'reach_id'))

    # get a list of all unique permutations of reach ids in the access feature class
    putin_reach_id_list = [row[0] for row in arcpy.da.SearchCursor(access_fc, 'putin')]
    takeout_reach_id_list = [row[0] for row in arcpy.da.SearchCursor(access_fc, 'takeout')]
    access_reach_id_list = set(putin_reach_id_list + takeout_reach_id_list)

    # get list of reach ids not in the hydroline feature class, those we need to process
    reach_id_queue = [reach_id for reach_id in access_reach_id_list if reach_id not in hydroline_reach_id_list]

    # where clause to select all putins and takeouts in the reach id queue
    where_list = ["putin = '{}' OR takeout = '{}'".format(reach_id, reach_id) for reach_id in reach_id_queue]
    where_string = ' OR '.join(where_list)

    # create an access feature layer using monster where clause
    access_lyr = arcpy.MakeFeatureLayer_management(access_fc, 'access_lyr', where_string)[0]

    # now, with only the unprocessed reaches selected, stand back and let the big dog eat
    get_reach_line_fc(access_lyr, hydro_network, reach_hydroline_fc, reach_invalid_tbl)


def revise_invalid_table(reach_hydroline_feature_class, reach_invalid_table):
    """
    Remove records from the invalid table which have been successfully traced and are now in the hydrolines.
    :param reach_hydroline_feature_class: Feature class with traced or manually digitized hydrolines.
    :param reach_invalid_table: Table used for tracking invalid reaches.
    :return:
    """
    # create a list of all hydroline reach id's, representing successful traces
    hydroline_reach_id_list = set(row[0] for row in arcpy.da.SearchCursor(reach_hydroline_feature_class, 'reach_id'))

    # create update cursor for deleting rows now validated from the invalid table
    with arcpy.da.UpdateCursor(reach_invalid_table, 'reach_id') as update_cursor:

        # iterate the rows in the invalid table
        for row in update_cursor:

            # iterate the hydroline reach id list
            for hydroline_reach_id in hydroline_reach_id_list:

                # if the current invalid reach id matches this successfully traced hydroline
                if row[0] == hydroline_reach_id:

                    # remove the row from the invalid table
                    update_cursor.deleteRow()

                    # break out of the loop
                    break

    # delete duplicates
    arcpy.DeleteIdentical_management(reach_invalid_table, 'reach_id')


def process_all_new_hydrolines(access_fc, huc4_subregion_directory, huc4_feature_class, reach_hydroline_fc,
                               reach_invalid_tbl):
    """
    :param access_fc: The point feature class for accesses. There must be an attribute named putin and another named
                  takeout. These fields must store the reach id for the point role as a putin or takeout.
    :param huc4_subregion_directory: Directory where downloaded file geodatabases reside for
    :param huc4_feature_class: Polygon feature class delineating HUC4 regions.
    :param reach_hydroline_fc: Hydroline feature class where hydrolines will be written to.
    :param reach_invalid_tbl: Table where invalid features will be written to.
    :return:
    """
    # iterate huc4 feature class and create list of hash's with huc4 and geometry
    huc4_dict_list = [{'huc4': row[0], 'geometry': row[1]} for row in arcpy.da.SearchCursor(huc4_feature_class, ['HUC4', 'SHAPE@'])]

    # create an access layer from the input access feature class
    access_layer = arcpy.MakeFeatureLayer_management(access_fc, 'access_layer')[0]

    # for each huc4 dict object
    for huc4_dict in huc4_dict_list:

        # use the huc4 geometry to select the accesses
        arcpy.SelectLayerByLocation_management(access_layer, "INTERSECT", huc4_dict['geometry'])

        # if there are no reaches in the subregion
        if not int(arcpy.GetCount_management(access_layer)[0]):
            arcpy.AddMessage('HUC4 Subregion {} has no reaches.'.format(huc4_dict['huc4']))

        # otherwise, if there are reaches
        else:
            # provide information to front end
            arcpy.AddMessage('Starting to process HUC4 Subregion {}'.format(huc4_dict['huc4']))

            # using the selected accesses, use the correct subregion geometric network to extract hydrolines
            get_new_hydrolines(
                access_fc=access_layer,
                hydro_network=os.path.join(huc4_subregion_directory, '{}.gdb'.format(huc4_dict['huc4']), 'HYDROGRAPHY',
                                           'HYDRO_NET'),
                reach_hydroline_fc=reach_hydroline_fc,
                reach_invalid_tbl=reach_invalid_tbl
            )

            # provide information to front end
            arcpy.AddMessage('Finished processing HUC4 Subregion {}'.format(huc4_dict['huc4']))

    # update invalid table
    revise_invalid_table(reach_hydroline_fc, reach_invalid_tbl)


def create_invalid_points_feature_class(access_feature_class, invalid_reach_table, invalid_points_feature_class):
    """
    Create a feature class of centroid points for the invalid reaches.
    :param access_feature_class: Point feature class of all accesses.
    :param invalid_reach_table: Table of reaches not passing validation.
    :return: Path to invalid points feature class.
    """
    # create tuple pairs of putin and takeout reach ids and geometries
    putin_list = [(row[0], row[1]) for row in arcpy.da.SearchCursor(access_feature_class, ('putin', 'SHAPE@XY'), "putin IS NOT NULL AND putin <> '0'")]
    takeout_list = [(row[0], row[1]) for row in arcpy.da.SearchCursor(access_feature_class, ('takeout', 'SHAPE@XY'), "takeout IS NOT NULL AND takeout <> '0'")]

    # create a list of invalid reach id's and invalid reasons
    invalid_list = [(row[0], row[1]) for row in arcpy.da.SearchCursor(invalid_reach_table, ('reach_id', 'reason'))]

    # create a list to store invalid reaches
    invalid_point_list = []

    # for every invalid reach
    for invalid_reach in invalid_list:

        # find the coordinates for the putin and takeout
        putin_coords = [reach_id[1] for reach_id in putin_list if reach_id[0] == invalid_reach[0]][0]
        takeout_coords = [reach_id[1] for reach_id in takeout_list if reach_id[0] == invalid_reach[0]][0]

        # compare the coordinates to ascertain which is min and max, and then calculate the median
        def get_median_coord(putin_coord, takeout_coord):
            if putin_coord is None and takeout_coord is None:
                return None
            elif putin_coord is None:
                return takeout_coord
            elif takeout_coord is None:
                return putin_coord
            elif putin_coord > takeout_coord:
                return putin_coord - (putin_coord - takeout_coord) / 2
            else:
                return takeout_coord - (takeout_coord - putin_coord) / 2

        # get the coordinates
        x = get_median_coord(putin_coords[0], takeout_coords[0])
        y = get_median_coord(putin_coords[1], takeout_coords[1])

        # add the reach to the list
        if x and y:
            invalid_point_list.append((invalid_reach[0], invalid_reach[1], (x, y)))

    # create the output feature class
    out_fc = arcpy.CreateFeatureclass_management(
        out_path=os.path.dirname(invalid_points_feature_class),
        out_name=os.path.basename(invalid_points_feature_class),
        geometry_type='POINT',
        spatial_reference=arcpy.Describe(access_feature_class).spatialReference
    )[0]

    # add the fields
    arcpy.AddField_management(
        in_table=out_fc,
        field_name='reach_id',
        field_type='TEXT',
        field_length=10,
        field_alias='Reach ID'
    )
    arcpy.AddField_management(
        in_table=out_fc,
        field_name='reason',
        field_type='TEXT',
        field_length=200,
        field_alias='Reason'
    )

    # use an insert cursor to add records to the feature class
    with arcpy.da.InsertCursor(out_fc, ('reach_id', 'reason', 'SHAPE@XY')) as cursor:

        # iterate the invalid list
        for invalid_point in invalid_point_list:

            # insert a new record
            cursor.insertRow(invalid_point)

    # return the path to the output feature class
    return out_fc
