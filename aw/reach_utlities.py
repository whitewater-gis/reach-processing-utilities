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
import os.path
import time
import ftplib
import zipfile


def get_subregion_data(huc4, output_dir):
    """
    Download a subregion from the USGS, download it and set up the data for analysis.
    :param huc4: String four digit HUC to download
    :param output_dir: Directory to store output geodatabase
    :return: Boolean success or failure
    """
    # get path to scratch directory to store resources
    scratch_dir = arcpy.env.scratchFolder

    # open connection to USGS FTP server
    ftp = ftplib.FTP('nhdftp.usgs.gov')
    ftp.login()

    # change directory to where the desired zipped archives live
    ftp.cwd('DataSets/Staged/SubRegions/FileGDB/HighResolution')

    # set the output file path
    temp_zip = os.path.join(scratch_dir, 'NHDH{}_931v220.zip'.format(huc4))

    # get the archive from the USGS and store it locally
    ftp.retrbinary('RETR NHDH{}_931v220.zip'.format(huc4), open(temp_zip, 'wb').write)

    # close the connection to the USGS FTP server
    ftp.close()

    # unzip the archive to the temp directory
    zfile = zipfile.ZipFile(temp_zip)

    # extract all the contents to the output directory
    zfile.extractall(output_dir)

    # unzip the archive to the temp directory
    zfile = zipfile.ZipFile(temp_zip)

    # extract all the contents to the output directory
    zfile.extractall(output_dir)

    # create the final output geodatabase
    output_gdb = arcpy.CreateFileGDB_management(output_dir, '{}.gdb'.format(huc4))[0]

    # For some reason, copy keeps bombing with the geometric network, so copy the feature dataset first. Then delete
    # everything from the geodatabase not directly required for the analysis we need to do. True, this is not the most
    # efficient method...but given the circumstances, at least it works.
    # copy the geometric network into the output geodatabase
    arcpy.Copy_management(
        os.path.join(output_dir, 'NHDH{}.gdb'.format(huc4), 'Hydrography'),
        os.path.join(output_gdb, 'Hydrography')
    )

    # use walk to iterate everything in the geodatabase
    for parent_dir, dir_list, obj_list in arcpy.da.Walk(output_gdb):
        for obj in obj_list:

            # if the object encountered is not one of the four objects we need to retain, toss it
            if obj != 'Hydrography' and obj != 'HYDRO_NET' and obj != 'HYDRO_NET_Junctions' and obj != 'NHDFlowline':
                arcpy.Delete_management(os.path.join(parent_dir, obj))

    # extract out the only the huc4 polygon
    arcpy.Select_analysis(
        os.path.join(output_dir, 'NHDH{}.gdb'.format(huc4), 'WBD', 'WBDHU4'),
        os.path.join(output_gdb, 'WBDHU4'),
        "HUC4 = '{}'".format(huc4)
    )

    # delete the staging geodatabase
    arcpy.Delete_management(os.path.join(output_dir, 'NHDH{}.gdb'.format(huc4)))

    # return the path to the geodatabase
    return output_gdb


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

    # overwrite outputs
    arcpy.env.overwriteOutput = True

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
        del access_lyr
        return True
    else:
        del access_lyr
        return False

def validate_conicidence(reach_id, access_fc, hydro_network):
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
    arcpy.Snap_edit(access_lyr, [[hydroline_lyr, 'EDGE', '500 Feet']])

    # select by location, selecting accesses coincident with the hydrolines
    arcpy.SelectLayerByLocation_management(access_lyr, "INTERSECT", hydroline_lyr, selection_type='SUBSET_SELECTION')

    # if successful, two access features should be selected, the put in and the takeout
    if int(arcpy.GetCount_management(access_lyr)[0]) == 2:

        # return success
        return True

    # otherwise, return failure
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

            # if coincident, return the upstream traced hydroline layer...exiting function
            return hydroline_layer

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
        return {'valid': False, 'awid': reach_id, 'reason': 'does not have a access pair, both a putin and takeout'}

    # ensure the accesses are coincident with the hydrolines
    if not validate_conicidence(reach_id, access_fc, hydro_network):
        arcpy.AddMessage(
            '{} accesses do not appear to be coincident with hydrolines, and will not be processed.'.format(reach_id)
        )
        return {'valid': False, 'awid': reach_id, 'reason': 'accesses not coincident with hydrolines'}

    # get geometry object for putin and takeout
    takeout_geometry = arcpy.Select_analysis(access_fc, arcpy.Geometry(),  "takeout='{}'".format(reach_id))[0]
    putin_geometry = arcpy.Select_analysis(access_fc, arcpy.Geometry(),  "putin='{}'".format(reach_id))[0]

    # ensure the putin is upstream of the takeout, and if valid, save upstream trace hydroline layer
    valid_upstream_trace = validate_putin_upstream_from_takeout(putin_geometry, takeout_geometry, hydro_network)
    if not valid_upstream_trace:
        arcpy.AddMessage(
            '{} putin does not appear to be upstream of takeout, and will not be processed.'.format(reach_id)
        )
        return {'valid': False, 'awid': reach_id, 'reason': 'putin not upstream of takeout'}

    # trace downstream from the takeout
    group_layer = arcpy.TraceGeometricNetwork_management(hydro_network, 'downstream', putin_geometry,
                                                         'TRACE_DOWNSTREAM', )[0]

    # extract the flowline layer with upstream features selected from the group layer
    hydroline_layer = arcpy.mapping.ListLayers(group_layer, '*Flowline')[0]

    # select by location to only get the intersecting segments from both the upstream and downstream traces
    # this addresses the problem of braided streams tracing downstream past the takout
    arcpy.SelectLayerByLocation_management(hydroline_layer, 'INTERSECT', valid_upstream_trace,
                                           selection_type='SUBSET_SELECTION')

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


def get_reach_line_fc(access_fc, aoi_polygon, hydro_network, reach_hydroline_fc, reach_invalid_tbl):
    """
    Get an output reach feature class using an access feature class with putins and takeouts.
    :param access_lyr: The point feature class for accesses. There must be an attribute named putin and another named
                      takeout. These fields must store the AW id for the point role as a putin or takeout.
    :param hydro_network: This must be the geometric network from the USGS as part of the National Hydrology Dataset.
    :param reach_hydroline_fc: This will be the output
    :param reach_invalid_tbl:
    :return:
    """
    # create access feature layer
    access_lyr = arcpy.MakeFeatureLayer_management(access_fc)[0]

    # create huc4 layer
    aoi_lyr = arcpy.MakeFeatureLayer_management(aoi_polygon)[0]

    # select the accesses in the area of interest (typically selected subregions)
    arcpy.SelectLayerByLocation_management(access_lyr, 'INTERSECT', aoi_lyr)

    # get list of AW id's from the takeouts not including the None values
    awid_list = []
    with arcpy.da.SearchCursor(access_lyr, 'takeout') as cursor:
        for row in cursor:

            # when in the file geodatabase, the values are none, but once in an SDE, they become zeros
            if not (row[0] is None or int(row[0]) == 0):
                awid_list.append(row[0])

    # give a little beta to the front end
    arcpy.SetProgressor(type='default', message='{} reach id accesses successfully were located'.format(len(awid_list)))

    # if the output hydrolines does not already exist
    if not arcpy.Exists(reach_hydroline_fc):

        # create output hydroline feature class
        hydroline_fc = arcpy.CreateFeatureclass_management(
            out_path=os.path.dirname(reach_hydroline_fc),
            out_name=os.path.basename(reach_hydroline_fc),
            geometry_type='POLYLINE',
            spatial_reference=arcpy.Describe(access_lyr).spatialReference
        )[0]

        # add awid field
        arcpy.AddField_management(
            in_table=hydroline_fc,
            field_name='awid',
            field_type='TEXT',
            field_length=10
        )

    # if the invalid table does not already exist
    if not arcpy.Exists(reach_invalid_tbl):

        # create output invalid reach table
        invalid_tbl = arcpy.CreateTable_management(
            out_path=os.path.dirname(reach_invalid_tbl),
            out_name=os.path.basename(reach_invalid_tbl)
        )

        # add field for the awid in the invalid table
        arcpy.AddField_management(
            in_table=invalid_tbl,
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

    # keep providing updates
    arcpy.SetProgressor('step', 'Ready to see how many reaches we can process.', 0, len(awid_list), 1)

    # progressor trackers
    progressor_index = 0
    valid_count = 0

    # for every reach
    for awid in awid_list:

        # index the progressor tracker
        progressor_index += 1

        # provide updates
        arcpy.SetProgressorPosition(progressor_index)
        arcpy.SetProgressorLabel('Processing reach id {} ({}/{})'.format(awid, progressor_index, len(awid_list)))

        # process each reach
        reach = process_reach(
            reach_id=awid,
            access_fc=access_lyr,
            hydro_network=hydro_network
        )

        # if the reach is valid
        if reach['valid']:

            # message valid
            arcpy.AddMessage('{} is valid, and will be processed.'.format(awid))

            # create an insert cursor
            with arcpy.da.InsertCursor(reach_hydroline_fc, ('awid', 'SHAPE@')) as cursor_valid:

                # iterate the geometry objects in the list
                for geometry in reach['geometry_list']:

                    # insert a record in the feature class for the geometry
                    cursor_valid.insertRow((reach['awid'], geometry))

            # increment the valid counter
            valid_count += 1

        # if the reach is not valid
        elif not reach['valid']:

            # create an insert cursor
            with arcpy.da.InsertCursor(reach_invalid_tbl, ('awid', 'reason')) as cursor_invalid:

                # insert a record in the feature class for the geometry
                cursor_invalid.insertRow((str(reach['awid']), reach['reason']))

    # at the very end, report the success rate
    arcpy.AddMessage('{}% ({}/{}) of reaches were processed.'.format(valid_count/len(awid_list)*100, valid_count,
                                                                     len(awid_list)))


def add_meta_to_hydrolines(hydroline_fc, meta_table, out_point_fc):
    """
    After running the analysis to extract valid hydrolines, this adds the relevant metadata from the master metadata
    table.
    :param hydroline_fc: The output from getting the hydrolines above with an awid field.
    :param meta_table: The master reach metadata table created from the original reach extract.
    :return: boolean: Success or failure.
    """
    # list of attribute fields to be added
    attribute_list = (
        {'name': 'name_river', 'type': 'TEXT', 'length': 255},
        {'name': 'name_section', 'type': 'TEXT', 'length': 255},
        {'name': 'name_common', 'type': 'TEXT', 'length': 255},
        {'name': 'difficulty', 'type': 'TEXT', 'length': 10},
        {'name': 'difficulty_min', 'type': 'TEXT', 'length': 5},
        {'name': 'difficulty_max', 'type': 'TEXT', 'length': 5},
        {'name': 'difficulty_outlier', 'type': 'TEXT', 'length': 5}
    )

    # add all the fields to hydrolines
    for attribute in attribute_list:
        arcpy.AddField_management(hydroline_fc, attribute['name'], attribute['type'], field_length=attribute['length'])

    # get list of all AW id's
    awid_list = set([row[0] for row in arcpy.da.SearchCursor(hydroline_fc, 'awid')])

    # create a layer for the hydroline feature class
    hydroline_lyr = arcpy.MakeFeatureLayer_management(hydroline_fc, 'hydroline_lyr')

    # create table view for meta table
    meta_veiw = arcpy.MakeFeatureLayer_management(meta_table, 'meta_view')

    # for every AW id found
    for awid in awid_list:

        # create sql string
        sql = "{} = '{}'".format(
            arcpy.AddFieldDelimiters(os.path.dirname(arcpy.Describe(hydroline_fc).catalogPath), 'awid'),
            awid
        )

        # select features in the hydroline feature class
        arcpy.SelectLayerByAttribute_management(hydroline_lyr, 'NEW_SELECTION', sql)

        # select features in the meta view
        arcpy.SelectLayerByAttribute_management(meta_veiw, 'NEW_SELECTION', sql)

        # attributes to transfer
        attribute_name_list = ['awid']
        for attr in attribute_list:
            attribute_name_list.append(attribute_list['name'])

        # load attributes from meta table into cursor
        meta_values = [row for row in arcpy.da.SearchCursor(meta_veiw, attribute_name_list)][0]

        # use update cursor to populate the values in the feature class
        with arcpy.da.UpdateCursor(hydroline_lyr) as update_cursor:

            # iterate selected rows
            for row in update_cursor:

                # use the collected values from the meta table to populate the row in the feature class
                row = meta_values

                # commit the changes
                update_cursor.updateRow(row)