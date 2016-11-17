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
    :param spatial_reference: Spatial reference object for the output feature class.
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


def create_invalid_feature_class(full_path_to_invalid_feature_class, spatial_reference):
    """
    Create the invalid table.
    :param full_path_to_invalid_feature_class: Full path where the invalid feature class will reside.
    :param spatial_reference: Spatial reference object for the output feature class.
    :return: Path to the invalid table.
    """
    # create output invalid reach table
    invalid_feature_class = arcpy.CreateFeatureclass_management(
        out_path=os.path.dirname(full_path_to_invalid_feature_class),
        out_name=os.path.basename(full_path_to_invalid_feature_class),
        geometry_type='POINT',
        spatial_reference=spatial_reference
    )

    # add field for the reach id in the invalid table
    arcpy.AddField_management(in_table=invalid_feature_class, field_name='reach_id', field_type='TEXT', field_length=10)

    # add field in invalid table for reason
    arcpy.AddField_management(in_table=invalid_feature_class, field_name='reason', field_type='TEXT', field_length=500)


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


def get_reach_centroid(putin_geometry, takeout_geometry):
    """
    From two geometry objects, one for the location of the putin and another for the location of the takeout, calculate
    the middle, halfway between the two, to use as a marker, the centroid for the reach.
    :param putin_geometry: Geometry object representing the putin.
    :param takeout_geometry: Geometry object representing the takeout.
    :return: Geometry object at the centroid for the reach.
    """
    # calculate half of the absolute difference between the two coordinates' respective x & y values
    halfdelta_x = abs(putin_geometry.centroid.X, takeout_geometry.centroid.X) / 2
    halfdelta_y = abs(putin_geometry.centroid.Y, takeout_geometry.centroid.Y) / 2

    # add half of the delta to each minimum value
    centroid_x = min(putin_geometry.centroid.X, takeout_geometry.centroid.X) + halfdelta_x
    centroid_y = min(putin_geometry.centroid.Y, takeout_geometry.centroid.Y) + halfdelta_y

    # return a geometry object delineating this new location
    return arcpy.Geometry('POINT', arcpy.Point(centroid_x, centroid_y))


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
        takeout_geometry = arcpy.Select_analysis(access_fc, arcpy.Geometry(),
                                                 "reach_id='{}' AND type='takeout'".format(reach_id))[0]
        putin_geometry = arcpy.Select_analysis(access_fc, arcpy.Geometry(),
                                               "reach_id='{}' AND type='putin'".format(reach_id))[0]

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

        # get the centroid geometry
        centroid_geometry = get_reach_centroid(putin_geometry, takeout_geometry)

        # return result as failed reach to be logged in invalid table
        return {'valid': False, 'reach_id': reach_id, 'reason': e, 'geometry': centroid_geometry}


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
    reach_id_list = set(row[0] for row in arcpy.da.SearchCursor(access_fc, 'reach_id',
                                                                "reach_id IS NOT NULL AND reach_id <> '0'"))

    # give a little beta to the front end
    arcpy.AddMessage('{} reaches queued for processing.'.format(len(reach_id_list)))

    # get the spatial reference from the input access feature class, typically nad83 to match the NHD data
    spatial_reference = arcpy.Describe(access_fc).spatialReference

    # if the output hydroline feature class does not already exist, create it
    if not arcpy.Exists(reach_hydroline_fc):
        create_hydroline_feature_class(reach_hydroline_fc, spatial_reference)

    # if the invalid table does not already exist, create it
    if not arcpy.Exists(reach_invalid_tbl):
        create_invalid_feature_class(reach_invalid_tbl, spatial_reference)

    # progress tracker
    valid_count = 0

    # variables to store valid and invalid reaches
    valid_list = []
    invalid_list = []

    # for every reach
    for reach_id in reach_id_list:

        # check to see if the reach is manually digitized, and if it has been, leave it alone
        if not check_if_hydroline_manually_digitized(reach_hydroline_fc, reach_id):

            # process the current reach
            reach = process_reach(reach_id, access_fc, hydro_network)

            # if the reach is valid
            if reach['valid']:

                # iterate the geometry objects in the list
                for geometry in reach['geometry_list']:

                    # add the valid reach to the list
                    valid_list.append([reach['reach_id'], 0, geometry])

                # increment the valid counter
                valid_count += 1

            # if the reach is not valid
            elif not reach['valid']:

                # add the invalid reach to the invalid list
                invalid_list.append([str(reach['reach_id']), reach['reason'], reach['geometry']])

    # create an insert cursor for the reach feature class
    with arcpy.da.InsertCursor(reach_hydroline_fc, ('reach_id', 'manual_digitize', 'SHAPE@')) as reach_cursor:

        # iterate the valid list
        for valid_reach in valid_list:

            reach_cursor.insertRow(valid_reach)

    # create an insert cursor for the invalid feature class
    with arcpy.da.InsertCursor(reach_invalid_tbl, ('reach_id', 'reason', 'SHAPE@XY')) as invalid_cursor:

        # iterate the invalid list
        for invalid_reach in invalid_list:

            # insert a record in the feature class for the geometry
            invalid_cursor.insertRow(invalid_reach)

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
    access_reach_id_list = set(row[0] for row in arcpy.da.SearchCursor(access_fc, 'reach_id'))

    # get list of reach ids not in the hydroline feature class, those we need to process
    reach_id_queue = [reach_id for reach_id in access_reach_id_list if reach_id not in hydroline_reach_id_list]

    # where clause to select all putins and takeouts in the reach id queue
    where_list = ["reach_id='{}'".format(reach_id) for reach_id in reach_id_queue]
    where_string = ' OR '.join(where_list)

    # create an access feature layer using where clause to identify and only try to process the invalid reaches
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
    :param access_fc: The point feature class for accesses. This point feature class must contain two fields, reach_id
        and type. The reach_id field uniquely identifies each reach the access is associated with and the type
        designates the access type; putin, takeout or intermediate. The input accesses do not need to be already
        selected. Only reaches without a
    :param huc4_subregion_directory: Directory where downloaded file USGS HUC subregion geodatabases reside.
    :param huc4_feature_class: Polygon feature class delineating HUC4 regions. This is used to iterate and look up
        the correct subregion to process.
    :param reach_hydroline_fc: Hydroline feature class where processed reach hydrolines will be written to.
    :param reach_invalid_tbl: Table where invalid features will be logged.
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
                hydro_network=os.path.join(
                    huc4_subregion_directory, '{}.gdb'.format(huc4_dict['huc4']), 'HYDROGRAPHY', 'HYDRO_NET'
                ),
                reach_hydroline_fc=reach_hydroline_fc,
                reach_invalid_tbl=reach_invalid_tbl
            )

            # provide information to front end
            arcpy.AddMessage('Finished processing HUC4 Subregion {}'.format(huc4_dict['huc4']))

    # update invalid table
    revise_invalid_table(reach_hydroline_fc, reach_invalid_tbl)
