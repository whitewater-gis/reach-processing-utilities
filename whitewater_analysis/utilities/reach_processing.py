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
from validate import get_timestamp


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

        # split hydroline at the putin and takeout, generating dangling hydroline line segments dangles above and below the
        # putin and takeout and saving as in memory feature class since trim line does not work on a geometry list
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
    start_message = '{} reach id accesses successfully located'.format(len(reach_id_list))
    arcpy.SetProgressor(type='default', message=start_message)
    arcpy.AddMessage(start_message)

    # if the output hydrolines does not already exist
    if not arcpy.Exists(reach_hydroline_fc):

        # create output hydroline feature class
        hydroline_fc = arcpy.CreateFeatureclass_management(
            out_path=os.path.dirname(reach_hydroline_fc),
            out_name=os.path.basename(reach_hydroline_fc),
            geometry_type='POLYLINE',
            spatial_reference=arcpy.Describe(access_fc).spatialReference
        )[0]

        # add reach id field
        arcpy.AddField_management(in_table=hydroline_fc, field_name='reach_id', field_type='TEXT', field_length=10)

    # if the invalid table does not already exist
    if not arcpy.Exists(reach_invalid_tbl):

        # create output invalid reach table
        invalid_tbl = arcpy.CreateTable_management(
            out_path=os.path.dirname(reach_invalid_tbl),
            out_name=os.path.basename(reach_invalid_tbl)
        )

        # add field for the reach id in the invalid table
        arcpy.AddField_management(in_table=invalid_tbl, field_name='reach_id', field_type='TEXT', field_length=10)

        # add field in invalid table for reason
        arcpy.AddField_management(in_table=invalid_tbl, field_name='reason', field_type='TEXT', field_length=500)

    # progressor trackers
    progressor_index = 0
    valid_count = 0

    # for every reach
    for reach_id in reach_id_list:

        # index the progressor tracker
        progressor_index += 1

        # provide updates
        arcpy.SetProgressorPosition(progressor_index)
        update_message = '{} Processing reach id {} ({}/{})'.format(get_timestamp(),
                                                                    reach_id, progressor_index, len(reach_id_list))
        arcpy.SetProgressorLabel(update_message)
        arcpy.AddMessage(update_message)

        # process each reach
        reach = process_reach(
            reach_id=reach_id,
            access_fc=access_fc,
            hydro_network=hydro_network
        )

        # if the reach is valid
        if reach['valid']:

            # create an insert cursor
            with arcpy.da.InsertCursor(reach_hydroline_fc, ('reach_id', 'SHAPE@')) as cursor_valid:

                # iterate the geometry objects in the list
                for geometry in reach['geometry_list']:

                    # insert a record in the feature class for the geometry
                    cursor_valid.insertRow((reach['reach_id'], geometry))

            # increment the valid counter
            valid_count += 1

        # if the reach is not valid
        elif not reach['valid']:

            # create an insert cursor
            with arcpy.da.InsertCursor(reach_invalid_tbl, ('reach_id', 'reason')) as cursor_invalid:

                # insert a record in the feature class for the geometry
                cursor_invalid.insertRow((str(reach['reach_id']), reach['reason']))

    # at the very end, report the success rate
    arcpy.AddMessage('{}% ({}/{}) of reaches were processed.'.format(valid_count/len(reach_id_list)*100, valid_count,
                                                                     len(reach_id_list)))


def add_meta_to_hydrolines(hydroline_fc, meta_table):
    """
    After running the analysis to extract valid hydrolines, this adds the relevant metadata from the master metadata
    table.
    :param hydroline_fc: The output from getting the hydrolines above with an reach id field.
    :param meta_table: The master reach metadata table created from the original reach extract.
    :return: boolean: Success or failure.
    """
    # list of attribute fields to be added
    attribute_list = [
        {'name': 'name_river', 'type': 'TEXT', 'length': 255},
        {'name': 'name_section', 'type': 'TEXT', 'length': 255},
        {'name': 'name_common', 'type': 'TEXT', 'length': 255},
        {'name': 'difficulty', 'type': 'TEXT', 'length': 10},
        {'name': 'difficulty_min', 'type': 'TEXT', 'length': 5},
        {'name': 'difficulty_max', 'type': 'TEXT', 'length': 5},
        {'name': 'difficulty_outlier', 'type': 'TEXT', 'length': 5}
    ]

    # add all the fields to hydrolines
    for attribute in attribute_list:
        arcpy.AddField_management(hydroline_fc, attribute['name'], attribute['type'], field_length=attribute['length'])

    # get list of all reach id's
    reach_id_list = set([row[0] for row in arcpy.da.SearchCursor(hydroline_fc, 'reach_id')])

    # create a layer for the hydroline feature class
    hydroline_lyr = arcpy.MakeFeatureLayer_management(hydroline_fc, 'hydroline_lyr')

    # create table view for meta table
    meta_veiw = arcpy.MakeFeatureLayer_management(meta_table, 'meta_view')

    # attributes to transfer for update cursor
    attribute_name_list = ['reach_id'] + [attribute['name'] for attribute in attribute_list]

    # for every reach id found
    for reach_id in reach_id_list:

        # create sql string to select the reach
        sql = "{} = '{}'".format(
            arcpy.AddFieldDelimiters(os.path.dirname(arcpy.Describe(hydroline_fc).catalogPath), 'reach_id'),
            reach_id
        )

        # select features in the hydroline feature class
        arcpy.SelectLayerByAttribute_management(hydroline_lyr, 'NEW_SELECTION', sql)

        # select features in the meta view
        arcpy.SelectLayerByAttribute_management(meta_veiw, 'NEW_SELECTION', sql)

        # load attributes from meta table into cursor and retrieve single record as row
        meta_values = [row for row in arcpy.da.SearchCursor(meta_veiw, attribute_name_list)][0]

        # use update cursor to populate the values in the feature class
        with arcpy.da.UpdateCursor(hydroline_lyr) as update_cursor:

            # iterate selected rows
            for row in update_cursor:

                # use the collected values from the meta table to populate the row in the feature class
                row = meta_values

                # commit the changes
                update_cursor.updateRow(row)

    # return happy
    return True


def get_reach_centroid(reach_hydroline_geometry_list):
    """
    Get the center of the geomtery for the reach from the geometry list of all the line segments.
    :param reach_hydroline_geometry_list: List of line geometry objects comprising the reach.
    :return: Point geometry object at the geometric center of the reach, not necessarily coincident with any line
        geometry.
    """
    # create extent object to work with
    extent = arcpy.Extent()

    # for every line geometry, get the extent
    for line_geometry in reach_hydroline_geometry_list:

        # if the xmin is less than the saved value, save it
        if line_geometry.XMin < extent.XMin:
            extent.XMin = line_geometry.XMin

        # if the ymin is less than the saved value, save it
        if line_geometry.YMin < extent.YMin:
            extent.YMin = line_geometry.YMin

        # if the xmax is greater than the saved value, save it
        if line_geometry.XMax > extent.XMax:
            extent.XMax = line_geometry.XMax

        # if the ymax is greater than the saved value, save it
        if line_geometry.YMax > extent.YMax:
            extent.YMax = line_geometry.YMax

    # create a point centroid and return it
    return arcpy.Point(
        X=extent.XMin + (extent.YMax - extent.YMin) / 2,
        Y=extent.YMin + (extent.YMax - extent.YMin) / 2
    )


def create_reach_centroid_feature_class(reach_hydroline_feature_class, output_reach_centroids):
    """
    Create a feature class consisting of little more than centroids for each reach for symbolizing at smaller scales.
    :param reach_hydroline_feature_class: Reach hydroline feature class.
    :param output_reach_centroids: Location and name for output point feature class.
    :return: String path to output.
    """
    # make feature class using the input hydrolines for a schema template
    arcpy.CreateFeatureclass_management(
        out_path=os.path.dirname(output_reach_centroids),
        out_name=os.path.basename(output_reach_centroids),
        template=reach_hydroline_feature_class
    )
