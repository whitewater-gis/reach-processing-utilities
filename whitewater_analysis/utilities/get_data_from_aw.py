# import modules
import requests
import json
import arcpy


# wrap up getting the loaded JSON in a single function
def get_reach_json(reach_id):
    # url for amazon api REST endpoint calling lambda script
    root_url = 'https://oemj2neo2b.execute-api.us-west-2.amazonaws.com/prod/getReachGeoJson'

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
    reach_counter = 1  # coutner to iterate reach id's

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

        # while there are less than 20 consecutive failed requests
        while invalid_count < 20:

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
                            validate_against_field_length(point_json['properties']['description'], 500),
                            (point_json['geometry']['coordinates'][0], point_json['geometry']['coordinates'][1])
                        ]

                        print(row)

                        # save the valid feature to the feature class
                        insert_cursor.insertRow(row)

            # otherwise increment the invalid count
            else:
                invalid_count += 1

            # increment the reachId counter
            reach_counter += 1

    # return the list of reach id's
    return True


# test the thing
get_points(r'H:\reach-processing\resources\scratch_data.gdb\points20150325')
