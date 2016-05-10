"""
author:     Joel McCune (joel.mccune+gis@gmail.com)
dob:        13 Nov 2015
purpose:    Provide the utilities to create watershed catchment areas using whitewater reach data.

    Copyright 2015 Joel McCune

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
import time
import os.path

# import the hydrology toolbox using SSO credientials
arcpy.ImportToolbox('http://hydro.arcgis.com/arcgis/rest/services; Tools/Hydrology; UseSSOIdentityIfPortalOwned')


def get_watershed_tuples(input_points):
    """
    Get a watershed using the points in the input.
    :param input_points: Point feature set with less than 100 points.
    :return: List of watersheds represented as the reach_id and point geometry objects in a two item list.
    """
    # check to ensure there are not more than the maximum number of points, 100
    if int(arcpy.GetCount_management(input_points)[0]) > 100:
        raise(Exception,
              "Cannot process more than 100 input points at a time. Please reduce the count of input points.")

    # run the hydrology tool and return the result
    result = arcpy.Hydrology.Watershed(
        InputPoints=input_points,
        PointIDField='reach_id',
        Generalize='true',
        ReturnSnappedPoints='true'
    )

    # now continually check for the result to be returned from the server every second...it will take a few
    while result.status < 4:
        time.sleep(1)

    # if the result status is four, success, continue execution
    if result.status == 4:

        # get the reach_id and the geometry as a tuple
        watershed_list = [row for row in arcpy.da.SearchCursor(result[0], ['PourPtID', 'SHAPE@'])]

        # once finished, return the result
        return watershed_list

    else:
        return False
        arcpy.AddMessage('Processing hydroshed failed.')


def get_watersheds(reach_hydroline_feature_class, access_feature_class, watershed_feature_class):
    """
    Populate a hydroshed feature class using the putin as the point to calculate the hydrosheds from. Only valid
    reaches will be processed.
    :param reach_hydroline_feature_class: Reach hydroline feature class used to get the list of valid reach ID's.
    :param access_feature_class: Used to get the putin locations used as the pour points to create hydrosheds.
    :param watershed_feature_class: Output feature class to populate with the hydrosheds for each reach.
    :return: Path to the hydroshed feature class.
    """
    # get a list of valid reach ID's
    hydroline_reach_id_list = list(set(row[0] for row in arcpy.da.SearchCursor(reach_hydroline_feature_class, 'reach_id')))

    # get a list of reach id's already processed as hydrosheds
    hydroshed_reach_id_list = list(set(row[0] for row in arcpy.da.SearchCursor(watershed_feature_class, 'reach_id')))

    # now get only reach id's in hydrolines not already processed into hydrosheds
    valid_reach_id_list = [x for x in hydroline_reach_id_list if x not in hydroshed_reach_id_list]

    # split the reach id's into processable chunks, less than 100 reach id's
    reach_id_chunk_list = [valid_reach_id_list[x:x + 99] for x in range(0, len(valid_reach_id_list), 99)]

    # get the workspace path
    workspace = os.path.dirname(arcpy.Describe(access_feature_class).catalogPath)

    # start the sql string to only select putins using a definition query
    sql_putin_select = "{} = 'putin'".format(arcpy.AddFieldDelimiters(workspace, 'type'))

    # create a new layer with just putins
    putin_layer = arcpy.MakeFeatureLayer_management(
        in_features=access_feature_class,
        out_layer='putin_layer',
        where_clause=sql_putin_select
    )[0]

    # start the sql string to only select putins using a definition query
    sql_takeout_select = "{} = 'takeout'".format(arcpy.AddFieldDelimiters(workspace, 'type'))

    # create a new layer with just putins
    takeout_layer = arcpy.MakeFeatureLayer_management(
        in_features=access_feature_class,
        out_layer='takeout_layer',
        where_clause=sql_putin_select
    )[0]

    # for each reach id
    for i, reach_id_chunk in enumerate(reach_id_chunk_list):

        # report progress
        arcpy.AddMessage('Processing {} of {} chunks.'.format(i+1, len(reach_id_chunk_list)))

        # for each reach id in the chunk, build up the sql to select all the reach ids in the chunk
        sql_list = map(
            lambda reach_id: "{} = '{}'".format(arcpy.AddFieldDelimiters(workspace, 'reach_id'), reach_id),
            reach_id_chunk
        )
        sql = " OR ".join(sql_list)

        for x, access_layer in enumerate([putin_layer, takeout_layer]):

            # select the reach id's from the layer
            reach_feature_set = arcpy.FeatureSet(arcpy.Select_analysis(
                in_features=putin_layer,
                out_feature_class='in_memory/selected_features',
                where_clause=sql
            ))

            # get the list of hydroshed tuples
            hydroshed_tuples = get_watershed_tuples(reach_feature_set)

            # delete the in memory data
            arcpy.Delete_management('in_memory/selected_features')

            # in case nothing is processed False is returned
            if hydroshed_tuples is False:

                # report the issue
                arcpy.AddWarning('No reaches processed and no watersheds created.')

            # otherwise
            else:

                # set the correct access type
                if x == 0:
                    access_type = 'putin'
                else:
                    access_type = 'takeout'

                # write the hydroshed to the watershed feature class
                with arcpy.da.InsertCursor(watershed_feature_class, ['reach_id', 'type', 'SHAPE@']) as insert_cursor:

                    # iterate the hydrosheds created
                    for hydroshed_tuple in hydroshed_tuples:

                        # insert the new hydroshed
                        insert_cursor.insertRow([hydroshed_tuple[0], access_type, hydroshed_tuple[1]])

    # return the path to the updated watershed feature class
    return watershed_feature_class
