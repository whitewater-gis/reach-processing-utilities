"""
author:     Joel McCune (joel.mccune+aw@gmail.com)
dob:        03 Dec 2014
purpose:    Provide the utilities to clean up and enhance the spatial component of the American Whitewater reaches
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
# import modules
import arcpy
import os
import time

def validate_has_access(reach_id, access_fc):
    """
    Ensure the specified reach has a putin and takeout.
    :param reach_id: The AW id for the reach.
    :param access_fc: The point feature class for accesses. There must be an attribute named putin and another named
                      takeout. These fields must store the AW id for the point role as a putin or takeout.
    :return: boolean: Indicates if the specified AW id has a single point for the putin and takeout.
    """
    # get the path to the accesses feature class
    path = arcpy.Describe(access_fc).path

    # make a feature layer for accesses
    access_lyr = arcpy.MakeFeatureLayer_management(access_fc, 'access')

    # rather than duplicating code, just use this embedded function
    def get_access_count(layer, access_type, awid):

        # create the sql string taking into account the location of the data
        sql = "{} = '{}'".format(arcpy.AddFieldDelimiters(path, access_type), awid)

        # select features from the layer
        arcpy.SelectLayerByAttribute_management(in_layer_or_view=layer, where_clause=sql)

        # get the count of selected features in the layer
        return int(arcpy.GetCount_management(layer)[0])

    # if the putin or takeout count is not exactly one, invalidate
    if get_access_count(access_lyr, 'putin', reach_id) == 1 and get_access_count(access_lyr, 'takeout', reach_id) == 1:
        return True
    else:
        return False


def validate_putin_upstream_from_takeout(putin_geometry, takeout_geometry, hydro_network):
    """
    Ensure the putin is indeed upstream of the takeout.
    :param putin_geometry: Point Geometry object for the putin.
    :param takeout_geometry: Point Geometry object for the takeout.
    :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology Dataset.
    :return: boolean: Indicates if when tracing the geometric network upstream from the takeout, if the putin is
                      upstream from the takeout.
    """
    # trace upstream from the takeout
    group_layer = arcpy.TraceGeometricNetwork_management(hydro_network, 'upstream', takeout_geometry,
                                                         'TRACE_UPSTREAM')[0]

    # extract the flowline layer with upstream features selected from the group layer
    hydroline_layer = arcpy.mapping.ListLayers(group_layer, '*Flowline')[0]

    # get geometry objects of upstream flowline
    geometry_list = [row[0] for row in arcpy.da.SearchCursor(hydroline_layer, 'SHAPE@')]

    # iterate the hydroline geometry objects
    for hydroline_geometry in geometry_list:

        # test if the putin is coincident with the hydroline geometry segment
        if putin_geometry.within(hydroline_geometry):

            # if coincident, return true...exiting function
            return True

    # if every hydroline segment is tested and none of them are coincident with the putin, return false
    return False


def process_reach(reach_id, access_fc, hydro_network):
    """
    Get the hydroline geometry for the reach using the putin and takeout access points identified using the AW id.
    :param reach_id: The AW id for the reach.
    :param access_fc: The point feature class for accesses. There must be an attribute named putin and another named
                      takeout. These fields must store the AW id for the point role as a putin or takeout.
    :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology Dataset.
    :return: Polyline Geometry object representing the reach hydroline.
    """
    # ensure the reach has a putin and a takeout
    if not validate_has_access(reach_id, access_fc):
        arcpy.AddMessage(
            '{} does not appear to have both a putin and takeout, and will not be processed.'.format(reach_id)
        )
        return {'valid': False, 'awid': reach_id, 'reason': 'does not have a access pair, a putin and takeout'}

    # get geometry object for putin and takeout
    takeout_geometry = arcpy.Select_analysis(access_fc, arcpy.Geometry(),  "takeout='{}'".format(reach_id))[0]
    putin_geometry = arcpy.Select_analysis(access_fc, arcpy.Geometry(),  "putin='{}'".format(reach_id))[0]

    # ensure the putin is upstream of the takeout
    if not validate_putin_upstream_from_takeout(putin_geometry, takeout_geometry, hydro_network):
        arcpy.AddMessage(
            '{} putin does not appear to be upstream of the takeout, and will not be processed.'.format(reach_id)
        )
        return {'valid': False, 'awid': reach_id, 'reason': 'putin is not upstream of takeout'}

    # trace upstream from the takeout
    group_layer = arcpy.TraceGeometricNetwork_management(hydro_network, 'upstream', putin_geometry,
                                                                    'TRACE_DOWNSTREAM', takeout_geometry)[0]

    # extract the flowline layer with upstream features selected from the group layer
    hydroline_layer = arcpy.mapping.ListLayers(group_layer, '*Flowline')[0]

    # select the last segment so the reach extends all the way to the takeout
    arcpy.SelectLayerByLocation_management(hydroline_layer, "INTERSECT", takeout_geometry,
                                           selection_type='ADD_TO_SELECTION')

    # dissolve into a single geometry object
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
        'awid': reach_id,
        'geometry_list': hydroline_geometry
    }


def get_reach_line_fc(access_fc, hydro_network, output_hydroline_fc, output_invalid_reach_table):
    """
    Get an output reach feature class using an access feature class with putins and takeouts.
    :param access_fc: The point feature class for accesses. There must be an attribute named putin and another named
                      takeout. These fields must store the AW id for the point role as a putin or takeout.
    :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology Dataset.
    :param output_hydroline_fc: This will be the output
    :param output_invalid_reach_table:
    :return:
    """

    # get list of AW id's from the takeouts not including the None values
    awid_list = []
    with arcpy.da.SearchCursor(access_fc, 'takeout') as cursor:
        for row in cursor:
            if row[0] is not None:
                awid_list.append(row[0])

    # create output hydroline feature class
    hydroline_fc = arcpy.CreateFeatureclass_management(
        out_path=os.path.dirname(output_hydroline_fc),
        out_name=os.path.basename(output_hydroline_fc),
        geometry_type='POLYLINE',
        spatial_reference=arcpy.Describe(access_fc).spatialReference
    )[0]

    # create output invalid reach table
    invalid_tbl = arcpy.CreateTable_management(
        out_path=os.path.dirname(output_invalid_reach_table),
        out_name=os.path.basename(output_invalid_reach_table)
    )

    # add field for the awid in both the output feature class and invalid table
    for table in [hydroline_fc, invalid_tbl]:
        arcpy.AddField_management(
            in_table=table,
            field_name='awid',
            field_type='TEXT',
            field_length=10
        )

    # add field in invalid table for reason
    arcpy.AddField_management(
        in_table=invalid_tbl,
        field_name='reason',
        field_type='TEXT',
        field_length=100
    )

    # for every reach
    for awid in awid_list:

        # process each reach
        reach = process_reach(
            reach_id=awid,
            access_fc=access_fc,
            hydro_network=hydro_network
        )

        # if the reach is valid
        if reach['valid']:

            # message valid
            arcpy.AddMessage('{} is valid, and will be processed.'.format(awid))

            # create an insert cursor
            with arcpy.da.InsertCursor(output_hydroline_fc, ('awid', 'SHAPE@')) as cursor_valid:

                # iterate the geometry objects in the list
                for geometry in reach['geometry_list']:

                    # insert a record in the feature class for the geometry
                    cursor_valid.insertRow((reach['awid'], geometry))

        # if the reach is not valid
        elif not reach['valid']:

            # create an insert cursor
            with arcpy.da.InsertCursor(output_invalid_reach_table, ('awid', 'reason')) as cursor_invalid:

                # insert a record in the feature class for the geometry
                cursor_invalid.insertRow((str(reach['awid']), reach['reason']))
