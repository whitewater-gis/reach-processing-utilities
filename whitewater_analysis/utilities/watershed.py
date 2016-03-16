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


def get_watershed(input_point):
    """
    Get a watershed using the points in the input.
    :param input_points: Point feature class with a single point selected.
    :return: List of watersheds represented as the reach_id and point geometry objects in a two item list.
    """

    # run the hydrology tool and return the result
    result = arcpy.Hydrology.Watershed(
        InputPoints=input_point,
        PointIDField='reach_id',
        SnapDistance='500',
        SnapDistanceUnits='Feet',
        Generalize='true',
        ReturnSnappedPoints="true"
    )

    # now continually check for the result to be returned from the server
    while result.status < 4:
        time.sleep(0.2)

    # if the result status is four, success, continue execution
    if result.status == 4:

        # get the reach_id and the geometry as a tuple
        watershed = [row for row in arcpy.da.SearchCursor(result[0], ['PourPtID', 'SHAPE@'])][0]

        # once finished, return the result
        return watershed

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
    valid_reach_id_list = [row[0] for row in arcpy.da.SearchCursor(reach_hydroline_feature_class, 'reach_id')]

    # get the workspace path
    workspace = os.path.dirname(arcpy.Describe(access_feature_class).catalogPath)

    # start the sql string
    sql_root = "{} = 'putin'".format(arcpy.AddFieldDelimiters(workspace, 'type'))

    # for each reach id
    for reach_id in valid_reach_id_list:

        # select the reach from accesses
        selected_reach = arcpy.Select_analysis(
            in_features=access_feature_class,
            out_feature_class='in_memory/access_selected{}'.format(int(time.time()*1000)),
            where_clause="{} AND {} = '{}'".format(
                sql_root,
                arcpy.AddFieldDelimiters(workspace, 'reach_id'),
                reach_id
            )
        )[0]

        # get the hydroshed tuple
        hydroshed = get_watershed(selected_reach)

        # if the processing fails, break and go to the next one
        if not hydroshed:
            break

        # use an edit session to insert the reach
        edit = arcpy.da.Editor(workspace)
        edit.startEditing(False)
        edit.startOperation()

        # write the hydroshed to the watershed feature class
        with arcpy.da.InsertCursor(watershed_feature_class, ['reach_id', 'type', 'SHAPE@']) as insert_cursor:

            # insert the new hydroshed
            insert_cursor.insertRow([hydroshed[0], 'putin', hydroshed[1]])

        # wrap up the edit
        edit.startOperation()
        edit.stopEditing(True)
        del edit

    # return the path to the updated watershed feature class
    return watershed_feature_class
