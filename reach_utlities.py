"""
author:     Joel McCune (joel.mccune+aw@gmail.com)
dob:        03 Dec 2014
purpose:    Provide the utilities to clean up and enhance the spatial component of the American Whitewater reach
            data set.
"""
# import modules
import arcpy
import os


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
    upstream_group_layer = arcpy.TraceGeometricNetwork_management(hydro_network, 'upstream', takeout_geometry,
                                                                  'TRACE_UPSTREAM')[0]

    # extract the flowline layer with upstream features selected from the group layer
    upstream_hydroline_layer = arcpy.mapping.ListLayers(upstream_group_layer, '*Flowline')[0]

    # dissolve into a single geometry object
    upstream_hydroline_geometry = arcpy.Dissolve_management(upstream_hydroline_layer, arcpy.Geometry())[0]

    # test to see if putin is on the upstream hydroline from the putin and return the result (boolean)
    return putin_geometry.within(upstream_hydroline_geometry)


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
    downstream_group_layer = arcpy.TraceGeometricNetwork_management(hydro_network, 'upstream', putin_geometry,
                                                                  'TRACE_DOWNSTREAM', takeout_geometry)[0]

    # extract the flowline layer with upstream features selected from the group layer
    downstream_hydroline_layer = arcpy.mapping.ListLayers(downstream_group_layer, '*Flowline')[0]

    # select the last segment so the reach extends all the way to the takeout
    arcpy.SelectLayerByLocation_management(downstream_hydroline_layer, "INTERSECT", takeout_geometry,
                                           selection_type='ADD_TO_SELECTION')

    # dissolve into a single geometry object
    downstream_hydroline_dissolve = arcpy.Dissolve_management(downstream_hydroline_layer, arcpy.Geometry())[0]

    # split hydroline at the putin and takeout, generating dangling hydroline line segments dangles above and below the
    # putin and takeout
    downstream_hydroline_geometry = arcpy.SplitLineAtPoint_management(downstream_hydroline_dissolve,
                                                                      [putin_geometry, takeout_geometry],
                                                                      arcpy.Geometry())

    # trim the dangles
    arcpy.TrimLine_edit(downstream_hydroline_geometry)

    # assemble into a success dictionary and return result
    return {
        'valid': True,
        'awid': reach_id,
        'geometry_list': downstream_hydroline_geometry
    }


def get_reach_line_fc(access_fc, hydro_network, output_hydroline_fc, output_invalid_reach_table):

    # get list of AW id's from the takeouts
    awid_list = [row[0] for row in arcpy.da.SearchCursor(access_fc, 'takeout')]

    # create output hydroline feature class
    hydroline_fc = arcpy.CreateFeatureclass_management(
        out_path=os.path.dirname(output_hydroline_fc),
        out_name=os.path.basename(output_hydroline_fc),
        geometry_type='POINT',
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
            field_length=10
        )

    # add field in invalid table for reason
    arcpy.AddField_management(
        in_table=invalid_tbl,
        field_name='reason',
        field_length=100
    )

    # for every reach
    for awid in awid_list:

        # TODO JDM: spread this across processes...hyperthreading at hyperspeed
        # process each reach
        reach = process_reach(
            reach_id=awid,
            access_fc=access_fc,
            hydro_network=hydro_network
        )

        # if the reach is valid
        if reach['valid']:

            # start an edit session

            # create an insert cursor

            # for every geometry

                # add a feature to the output feature class

            # stop editing and save edits

        # if the reach is not valid

            # start an edit session

            # create an insert cursor

            # add a record for the invalid reach

            # stop editing and save edits