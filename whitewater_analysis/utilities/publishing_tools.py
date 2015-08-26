"""
author:     Joel McCune (joel.mccune+gis@gmail.com)
dob:        03 Dec 2014
purpose:    Provide the utilities to process and publish whitewater reach data.

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
import os
import numpy
import arcpy


def field_valid(field):
    """
    Utility to exclude fields not user added
    :param field: arcpy field object
    :return: boolean
    """
    # exclude object id
    if field.type == 'OID':
        return False

    # exclude the geometry field
    elif field.type == 'Geometry':
        return False

    # exclude the autogenerated length field
    elif field.name == 'Shape_Length':
        return False

    # exclude the autogenerated area field
    elif field.name == 'Shape_Area':
        return False

    # if it falls through this far, it must be good to go
    else:
        return True


def get_centroid(hydroline_fc, reach_id):
    """
    Return a centroid geometry object based on one or more centroids for the reach id.
    :param hydroline_fc: Hydroline feature class.
    :param reach_id: Reach ID to get the centroid for.
    :return: Point geometry object representing the combined centroid.
    """
    # get a list of centroids for this reach id
    centroid_list = [row[0] for row in arcpy.da.SearchCursor(
        hydroline_fc,
        'SHAPE@TRUECENTROID',
        "reach_id = '{}'".format(reach_id)
    )]

    # get the mean x and y
    centroid_x = numpy.mean([shape[0] for shape in centroid_list])
    centroid_y = numpy.mean([shape[1] for shape in centroid_list])

    # create a point geometry from the average x and y
    return arcpy.PointGeometry(centroid_x, centroid_y)


def create_reach_centroids(reach_hydroline_feature_class, output_centroid_feature_class):
    """
    Find the centroid of the reach hydroline feature class per reach. This workflow compensates for the possibility of
    reaches having multiple segments.
    :param reach_hydroline_feature_class: Feature class with reach hydrolines.
    :param output_centroid_feature_class: The full path to the name and location where the centroids will be saved.
    :return:
    """

    # get a list of all fields in the reach hydroline feature class
    hydroline_field_list = [field for field in arcpy.ListFields(reach_hydroline_feature_class) if field_valid(field)]

    # create a hydroline point feature class
    centroid_feature_class = arcpy.CreateFeatureclass_management(
        out_path=os.path.dirname(output_centroid_feature_class),
        out_name=os.path.basename(output_centroid_feature_class),
        geometry_type='POINT',
        spatial_reference=arcpy.Describe(reach_hydroline_feature_class).spatialReference
    )[0]

    # iterate the fields and add the field
    for field in hydroline_field_list:

        # add each field
        arcpy.AddField_management(
            in_table=centroid_feature_class,
            field_name=field.name,
            field_type=field.type,
            field_precision=field.precision,
            field_scale=field.scale,
            field_length=field.length,
            field_alias=field.aliasName
        )

    # get a list of field names
    field_name_list = [field.name for field in hydroline_field_list]

    # get a list of unique reach id's
    reach_id_list = list(set([row[0] for row in arcpy.da.SearchCursor(reach_hydroline_feature_class, 'reach_id')]))

    # create an insert cursor to add features
    with arcpy.da.InsertCursor(centroid_feature_class, field_name_list + ['Geometry']) as insert_cursor:

        # iterate the reach_id_list
        for reach_id in reach_id_list:

            # get the centroid
            centroid = get_centroid(reach_hydroline_feature_class, reach_id)

            # get the rest of the field values
            field_value_list = [row for row in arcpy.da.SearchCursor(
                reach_hydroline_feature_class,
                field_name_list,
                'reach_id'
            )][0]

            # add the centroid geometry onto the end of the list
            field_value_list += centroid

            # use the insert cursor to add a new row
            insert_cursor.insertRow(field_value_list)

    # return the path to the output
    return output_centroid_feature_class
