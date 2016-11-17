# import modules
import json

import arcpy

import requests


# status updates
def send_note(message):
    arcpy.AddMessage(message)


# wrap up getting the loaded JSON in a single function
def get_reach_json(reach_id):
    # url for amazon api REST endpoint calling lambda script
    root_url = 'https://oemj2neo2b.execute-api.us-west-2.amazonaws.com/v20161116/getReachGeoJson'

    # get the reach
    response = requests.get('{0}?reachid={1}'.format(root_url, reach_id))

    # if something is returned
    if 'errorMessage' not in response.text:

        # get, load and json
        return json.loads(response.text)

    # otherwise just return falsy
    else:
        return False


def get_points(hydropoint_feature_class):
    invalid_count = 0  # counter to keep track of consecutive failed requests
    reach_counter = 4321  # counter to iterate reach id's

    def validate_against_field_length(data, field_length):
        if data:
            if len(data) > field_length:
                return data[:field_length]
            else:
                return data
        else:
            return None

    # create an insert cursor
    with arcpy.da.InsertCursor(
            hydropoint_feature_class,
            [u'reachId', u'tags', u'name', u'description', u'SHAPE@XY']
    ) as insert_cursor:

        # while there are less than 1000 consecutive failed requests
        while invalid_count < 1000:

            # try to get Reach JSON
            reach_json = get_reach_json(reach_counter)

            # if the reach is valid
            if reach_json is not False:

                # reset the invalid count
                invalid_count = 0

                # for every one of the returned points
                for point_json in reach_json['features']:

                    # if there are coordinates
                    if point_json['geometry']['coordinates'][0] and point_json['geometry']['coordinates'][1]:
                        row = [
                            point_json['properties']['reachId'],
                            point_json['properties']['tags'],
                            validate_against_field_length(point_json['properties']['name'], 50),
                            # validate_against_field_length(point_json['properties']['description'], 500),
                            None,
                            (point_json['geometry']['coordinates'][0], point_json['geometry']['coordinates'][1])
                        ]

                        # save the valid feature to the feature class
                        insert_cursor.insertRow(row)

                # report status
                send_note('{reachid} is valid, and was successfully retrieved and saved.'.format(reachid=reach_counter))

            # otherwise increment the invalid count
            else:
                invalid_count += 1
                # report status
                send_note('{reachid} is not a valid reach.'.format(reachid=reach_counter))

            # increment the reachId counter
            reach_counter += 1

    # return the list of reach id's
    return True


def etl_from_aw_points_to_reach_access(aw_points_fc, reach_access_fc):
    # for the respective putin and takeout point types
    for access_type in ['putin', 'takeout', 'intermediate']:

        # create a layer of just access points
        access_layer = arcpy.MakeFeatureLayer_management(aw_points_fc, 'access_layer', "tags LIKE '%access%'")[0]

        # create an insert cursor to add data
        with arcpy.da.InsertCursor(
                reach_access_fc,
                [u'reach_id', u'type', u'name', 'SHAPE@XY']
        ) as insert_cursor:

            # use a search cursor to itereate all the points of the selected type
            with arcpy.da.SearchCursor(
                    access_layer,
                    [u'reachId', u'name', 'SHAPE@XY'],
                    "tags LIKE '%{}%'".format(access_type)
            ) as search_cursor:
                for search_row in search_cursor:
                    insert_row = [search_row[0], access_type, search_row[1], search_row[2]]
                    insert_cursor.insertRow(insert_row)


# TODO: create script for pulling regular updates external to this module
# test the thing
get_points(r'D:\dev\reach-processing-tools\resources\scratch\staging.gdb\points20161116')
