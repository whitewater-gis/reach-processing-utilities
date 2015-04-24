import arcpy
import os


def _validate_has_access(reach_id, access_fc):
    """
    Ensure the specified reach has a putin and takeout.
    :param reach_id: The AW id for the reach.
    :param access_fc: The point feature class for accesses. There must be an attribute named putin and another named
                      takeout. These fields must store the AW id for the point role as a putin or takeout.
    :return: boolean: Indicates if the specified AW id has a single point for the putin and takeout.
    """
    # get the path to the accesses feature class
    path = arcpy.Describe(access_fc).path

    # overwrite outputs
    arcpy.env.overwriteOutput = True

    # make a feature layer for accesses
    access_lyr = arcpy.MakeFeatureLayer_management(access_fc, 'access_validatae')

    # rather than duplicating code, just use this embedded function
    def get_access_count(layer, access_type, reach_id):

        # create the sql string taking into account the location of the data
        sql = "{} = '{}'".format(arcpy.AddFieldDelimiters(path, access_type), reach_id)

        # select features from the layer
        arcpy.SelectLayerByAttribute_management(in_layer_or_view=layer, where_clause=sql)

        # get the count of selected features in the layer
        return int(arcpy.GetCount_management(layer)[0])

    # if the putin or takeout count is not exactly one, invalidate
    if get_access_count(access_lyr, 'putin', reach_id) == 1 and get_access_count(access_lyr, 'takeout', reach_id) == 1:
        del access_lyr
        return True
    else:
        del access_lyr
        return False


def _validate_putin_takeout_conicidence(reach_id, access_fc, hydro_network):
    """
    Ensure the putin and takeout are coincident with the USGS hydrolines. Just to compensate for error, the access
    points will be snapped to the hydrolines if they are within 200 feet since there can be a slight discrepancy in
    data sources' idea of exactly where the river centerline actually is.
    :param reach_id: The AW id for the reach.
    :param access_fc: The point feature class for accesses. There must be an attribute named putin and another named
                      takeout. These fields must store the AW id for the point role as a putin or takeout.
    :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology Dataset.
    :return: boolean: Indicates if the putin and takeout are coincident with the hydroline feature class.
    """
    # create a hydroline layer
    fds_path = os.path.dirname(arcpy.Describe(hydro_network).catalogPath)
    hydroline_lyr = arcpy.MakeFeatureLayer_management(os.path.join(fds_path, 'NHDFlowline'), 'hydroline_lyr')

    # create an access layer
    access_lyr = arcpy.MakeFeatureLayer_management(access_fc, 'access_lyr')

    # add field delimters for sql
    sql_pi = arcpy.AddFieldDelimiters(fds_path, 'putin')
    sql_to = arcpy.AddFieldDelimiters(fds_path, 'takeout')

    # select the putin and takeout for the reach layer
    arcpy.SelectLayerByAttribute_management(access_lyr, 'NEW_SELECTION',
                                            "{} = '{}' OR {} = '{}'".format(sql_pi, reach_id, sql_to, reach_id))

    # snap the putin and takeout to the hydrolines
    arcpy.Snap_edit(access_lyr, [[hydroline_lyr, 'EDGE', '100 Feet']])

    # select by location, selecting accesses coincident with the hydrolines
    arcpy.SelectLayerByLocation_management(access_lyr, "INTERSECT", hydroline_lyr, selection_type='SUBSET_SELECTION')

    # if successful, two access features should be selected, the put in and the takeout
    if int(arcpy.GetCount_management(access_lyr)[0]) == 2:

        # return success
        return True

    # otherwise, return failure
    else:
        return False


def _validate_putin_upstream_from_takeout(reach_id, access_fc, hydro_network):
    """
    Ensure the putin is indeed upstream of the takeout.
    :param putin_geometry: Point Geometry object for the putin.
    :param takeout_geometry: Point Geometry object for the takeout.
    :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology Dataset.
    :return: boolean: Indicates if when tracing the geometric network upstream from the takeout, if the putin is
                      upstream from the takeout.
    """
    # get geometry object for putin and takeout
    takeout_geometry = arcpy.Select_analysis(access_fc, arcpy.Geometry(),  "takeout='{}'".format(reach_id))[0]
    putin_geometry = arcpy.Select_analysis(access_fc, arcpy.Geometry(),  "putin='{}'".format(reach_id))[0]

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

            # if coincident, return the upstream traced hydroline layer...exiting function
            return True

    # if every hydroline segment is tested and none of them are coincident with the putin, return false
    return False


def validate_reach(reach_id, access_fc, hydro_network):
    """
    Make sure the reach is valid.
    :param reach_id: The AW id for the reach.
    :param access_fc: The point feature class for accesses. There must be an attribute named putin and another named
                      takeout. These fields must store the AW id for the point role as a putin or takeout.
    :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology Dataset.
    :return: Boolean indicating if the reach is valid or not.
    """
    # ensure the reach has a putin and a takeout
    if not _validate_has_access(reach_id, access_fc):
        arcpy.AddMessage(
            '{} does not appear to have both a putin and takeout, and will not be processed.'.format(reach_id)
        )
        return {'valid': False, 'reach_id': reach_id, 'reason': 'does not have a access pair, both a putin and takeout'}

    # ensure the accesses are coincident with the hydrolines
    elif not _validate_putin_takeout_conicidence(reach_id, access_fc, hydro_network):
        arcpy.AddMessage(
            '{} accesses do not appear to be coincident with hydrolines, and will not be processed.'.format(reach_id)
        )
        return {'valid': False, 'reach_id': reach_id, 'reason': 'accesses not coincident with hydrolines'}

    # ensure the putin is upstream of the takeout, and if valid, save upstream trace hydroline layer
    elif not _validate_putin_upstream_from_takeout(reach_id, access_fc, hydro_network):
        arcpy.AddMessage(
            '{} putin does not appear to be upstream of takeout, and will not be processed.'.format(reach_id)
        )
        return {'valid': False, 'reach_id': reach_id, 'reason': 'putin not upstream of takeout'}

    # if everything passes, return true
    else:
        arcpy.AddMessage(
            '{} is valid, and will be processed.'.format(reach_id)
        )
        return {'valid': True}