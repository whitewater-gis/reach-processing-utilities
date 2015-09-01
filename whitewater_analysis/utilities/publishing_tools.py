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


def get_reach_id_field(feature_class):
    """
    Get the reach id field.
    :param feature_class: Feature class with a reach id field.
    :return: String name of the reach id field.
    """
    # get the reach id field possibly dorked up through the join
    return [field.name for field in arcpy.ListFields(feature_class, '*reach_id*')][0]


def field_valid(field):
    """
    Utility to exclude fields not user added
    :param field: arcpy field object
    :return: boolean
    """
    # exclude object id
    if field.type == 'OID':
        return False

    # exclude global id field
    if field.type == 'GlobalID':
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

    # exclude the reach id feature class...if it is needed, add it explicitly
    elif field.name == 'reach_id':
        return False

    # if it falls through this far, it must be good to go
    else:
        return True


def add_fields_from_table(input_table, add_table):
    """
    Append attribute fields to the input table from the add table. This function does not populate the values. Rather,
    it only reads the input field properties from the add table and adds these fields to the input table.
    :param input_table: Table to add the fields to.
    :param append_table: Table with fields to be added to the input table.
    :return: List of fields added.
    """
    # get a list of fields from the table
    meta_field_list = [field for field in arcpy.ListFields(add_table) if field_valid(field)]

    # get list of fields from input table
    input_field_list = [field.name for field in arcpy.ListFields(input_table)]

    # iterate the fields and add the field
    for field in meta_field_list:

        # check to make sure the field does not already exist
        if field.name not in input_field_list:

            # add each field
            arcpy.AddField_management(
                in_table=input_table,
                field_name=field.name,
                field_type=field.type,
                field_precision=field.precision,
                field_scale=field.scale,
                field_length=field.length,
                field_alias=field.aliasName
            )

    # return list of field objects added to the table
    return meta_field_list


def get_hydroline_centroid(hydroline_fc, reach_id):
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
    return arcpy.PointGeometry(arcpy.Point(centroid_x, centroid_y))


def create_hydropoint_feature_class(reach_hydroline_feature_class, output_centroid_feature_class):
    """
    Find the centroid of the reach hydroline feature class per reach. This workflow compensates for the possibility of
    reaches having multiple segments.
    :param reach_hydroline_feature_class: Feature class with reach hydrolines.
    :param output_centroid_feature_class: The full path to the name and location where the centroids will be saved.
    :return:
    """

    # create a hydroline point feature class
    centroid_feature_class = arcpy.CreateFeatureclass_management(
        out_path=os.path.dirname(output_centroid_feature_class),
        out_name=os.path.basename(output_centroid_feature_class),
        geometry_type='POINT',
        spatial_reference=arcpy.Describe(reach_hydroline_feature_class).spatialReference
    )[0]

    # explicitly add reach id field
    arcpy.AddField_management(
        in_table=centroid_feature_class,
        field_name='reach_id',
        field_type='TEXT',
        field_length='20',
        field_alias='Reach ID'
    )

    # add fields to output feature class
    hydroline_field_list = add_fields_from_table(centroid_feature_class, reach_hydroline_feature_class)

    # get a list of field names
    field_name_list = [field.name for field in hydroline_field_list]

    # get a list of unique reach id's
    reach_id_list = set([row[0] for row in arcpy.da.SearchCursor(reach_hydroline_feature_class, 'reach_id')])

    # create an insert cursor to add features
    with arcpy.da.InsertCursor(centroid_feature_class, field_name_list + ['SHAPE@']) as insert_cursor:

        # iterate the reach_id_list
        for reach_id in reach_id_list:

            # get the centroid
            centroid = get_hydroline_centroid(reach_hydroline_feature_class, reach_id)

            # get the rest of the field values
            field_value_list = [row for row in arcpy.da.SearchCursor(
                reach_hydroline_feature_class,
                field_name_list,
                "reach_id = '{}'".format(reach_id)
            )][0]

            # add the centroid geometry onto the end of the tuple
            field_value_list += (centroid,)

            # use the insert cursor to add a new row
            insert_cursor.insertRow(field_value_list)

    # return the path to the output
    return output_centroid_feature_class


def create_feature_class_with_meta(input_feature_class, meta_table, target_feature_class):
    """
    Add meta to output feature class for publishing.
    :param input_feature_class: The feature class only identified by the reach id.
    :param meta_table: Table containing all meta information associated with the Reach ID.
    :param target_feature_class: Output feature class to be created with all information contained in it.
    :return: Path to the output feature class.
    """

    # copy the feature class to the output location
    out_fc = arcpy.CopyFeatures_management(
        in_features=input_feature_class,
        out_feature_class=target_feature_class
    )[0]

    # add valid fields to feature class and get result
    valid_field_list = add_fields_from_table(out_fc, meta_table)

    # extract the field names in a list
    meta_field_name_list = ['reach_id'] + [field.name for field in valid_field_list]

    # create a dictionary of meta
    meta_list = [row for row in arcpy.da.SearchCursor(meta_table, meta_field_name_list)]

    # use update cursor to populate meta values
    with arcpy.da.UpdateCursor(out_fc, meta_field_name_list) as update_cursor:

        # iterate the rows
        for row in update_cursor:

            # find the right reach meta using the reach id field in the row
            meta_row = [item for item in meta_list if item[0] == row[0]]

            # if something found
            if len(meta_row):

                # update the row using the meta values
                update_cursor.updateRow(meta_row[0])

    # return the path to the output data
    return out_fc


def get_navigation_link(xy_tuple):
    """
    Create a navigation link from a tuple containing an x and y tuple.
    :param xy_tuple: Tuple of (x,y) coordinates.
    :return: String url to be used for navigation.
    """
    return 'http://maps.google.com/maps?daddr={},{}&saddr=Current%20Location'.format(xy_tuple[1], xy_tuple[0])


def add_navigation_links_to_hydrolines(hydroline_feature_class, access_feature_class, parking_feature_class):
    """
    Add navigation link urls to the hydroline feature class for publishing.
    :param hydroline_feature_class: Publication hydroline feature class.
    :param access_feature_class: Access feature class adhering to standard schema.
    :param parking_feature_class: Parking feature class adhering to standard schema.
    :return:
    """
    # add the fields to the table to store navigation hyperlinks
    arcpy.AddField_management(
        in_table=hydroline_feature_class,
        field_name='nav_link_putin',
        field_type='TEXT',
        field_length='300',
        field_alias='Put In Navigation Link'
    )
    arcpy.AddField_management(
        in_table=hydroline_feature_class,
        field_name='nav_link_takeout',
        field_type='TEXT',
        field_length='300',
        field_alias='Take Out Navigation Link'
    )

    # create list for parking and access putin and takeout coordinates
    park_putin_list = [row for row in arcpy.da.SearchCursor(parking_feature_class, ('reach_id', 'SHAPE@XY'), "type = 0")]
    park_takeout_list = [row for row in arcpy.da.SearchCursor(parking_feature_class, ('reach_id', 'SHAPE@XY'), "type = 1")]
    access_putin_list = [row for row in arcpy.da.SearchCursor(access_feature_class, ('reach_id', 'SHAPE@XY'), "type = 0")]
    access_takeout_list = [row for row in arcpy.da.SearchCursor(access_feature_class, ('reach_id', 'SHAPE@XY'), "type = 1")]

    # use an update cursor to iterate the reaches
    with arcpy.da.UpdateCursor(
            hydroline_feature_class, (get_reach_id_field(hydroline_feature_class), 'nav_link_putin', 'nav_link_takeout')
    ) as update_cursor:

        # iterate the rows
        for update_row in update_cursor:

            # try to get the putin coordinates from the putin parking area
            putin = [loc[1] for loc in park_putin_list if loc[0] == update_row[0]]

            # if anything is found in the parking feature class, save it
            if len(putin):
                xy_putin = putin[0]

            # if there is not a parking area
            else:

                # get the putin coordinates from the putin feature class
                xy_putin = [loc[1] for loc in access_putin_list if loc[0] == update_row[0]][0]

            # modify the update cursor putin link with the navigation url
            update_row[1] = get_navigation_link(xy_putin)

            # try to get the takeout coordinates from the takeout parking area
            takeout = [loc[1] for loc in park_takeout_list if loc[0] == update_row[0]]

            # if a takeout parking area is found
            if len(takeout):
                xy_takeout = takeout[0]

            # if there is not a parking area
            else:

                # get the takeout coordinates using the reach_id from the update cursor
                xy_takeout = [loc[1] for loc in access_takeout_list if loc[0] == update_row[0]][0]

            # modify the update cursor takeout link with the navigation url
            update_row[2] = get_navigation_link(xy_takeout)

            # commit the changes
            update_cursor.updateRow(update_row)


def add_link_to_american_whitewater_reach_page(table_with_reach_id):
    """
    Add and populate a field with the link url back to the American Whitewater reach page.
    :param table_with_reach_id: Table with reach id field.
    :return:
    """
    # add the field to store the link
    arcpy.AddField_management(
        in_table=table_with_reach_id,
        field_name='nav_link_aw',
        field_type='TEXT',
        field_length='300',
        field_alias='AW Reach Page Link'
    )

    # get the reach id field since the join can muck up field names
    reach_id_field = [field.name for field in arcpy.ListFields(table_with_reach_id, '*reach_id*')][0]

    # use an update cursor to iterate the rows
    with arcpy.da.UpdateCursor(table_with_reach_id, (reach_id_field, 'nav_link_aw')) as update_cursor:

        # iterate the rows
        for row in update_cursor:

            # combine the reach_id to create the url string
            row[1] = 'http://www.americanwhitewater.org/content/River/detail/id/{}/'.format(row[0])

            # commit the changes
            update_cursor.updateRow(row)


def create_invalid_points_feature_class(access_feature_class, invalid_reach_table, invalid_points_feature_class):
    """
    Create a feature class of centroid points for the invalid reaches.
    :param access_feature_class: Point feature class of all accesses.
    :param invalid_reach_table: Table of reaches not passing validation.
    :return: Path to invalid points feature class.
    """
    # create tuple pairs of putin and takeout reach ids and geometries
    putin_list = [(row[0], row[1]) for row in arcpy.da.SearchCursor(access_feature_class, ('reach_id', 'SHAPE@XY'), "type == 0")]
    takeout_list = [(row[0], row[1]) for row in arcpy.da.SearchCursor(access_feature_class, ('reach_id', 'SHAPE@XY'), "type == 1")]

    # create a list of invalid reach id's and invalid reasons
    invalid_list = [(row[0], row[1]) for row in arcpy.da.SearchCursor(invalid_reach_table, ('reach_id', 'reason'))]

    # create a list to store invalid reaches
    invalid_point_list = []

    # for every invalid reach
    for invalid_reach in invalid_list:

        # find the coordinates for the putin and takeout
        putin_coords = [reach_id[1] for reach_id in putin_list if reach_id[0] == invalid_reach[0]][0]
        takeout_coords = [reach_id[1] for reach_id in takeout_list if reach_id[0] == invalid_reach[0]][0]

        # compare the coordinates to ascertain which is min and max, and then calculate the median
        def get_median_coord(putin_coord, takeout_coord):
            if putin_coord is None and takeout_coord is None:
                return None
            elif putin_coord is None:
                return takeout_coord
            elif takeout_coord is None:
                return putin_coord
            elif putin_coord > takeout_coord:
                return putin_coord - (putin_coord - takeout_coord) / 2
            else:
                return takeout_coord - (takeout_coord - putin_coord) / 2

        # get the coordinates
        x = get_median_coord(putin_coords[0], takeout_coords[0])
        y = get_median_coord(putin_coords[1], takeout_coords[1])

        # add the reach to the list
        if x and y:
            invalid_point_list.append((invalid_reach[0], invalid_reach[1], (x, y)))

    # create the output feature class
    out_fc = arcpy.CreateFeatureclass_management(
        out_path=os.path.dirname(invalid_points_feature_class),
        out_name=os.path.basename(invalid_points_feature_class),
        geometry_type='POINT',
        spatial_reference=arcpy.Describe(access_feature_class).spatialReference
    )[0]

    # add the fields
    arcpy.AddField_management(
        in_table=out_fc,
        field_name='reach_id',
        field_type='TEXT',
        field_length=10,
        field_alias='Reach ID'
    )
    arcpy.AddField_management(
        in_table=out_fc,
        field_name='reason',
        field_type='TEXT',
        field_length=200,
        field_alias='Reason'
    )

    # use an insert cursor to add records to the feature class
    with arcpy.da.InsertCursor(out_fc, ('reach_id', 'reason', 'SHAPE@XY')) as cursor:

        # iterate the invalid list
        for invalid_point in invalid_point_list:

            # insert a new record
            cursor.insertRow(invalid_point)

    # return the path to the output feature class
    return out_fc


def create_publication_geodatabase(analysis_gdb, publication_gdb):
    """
    From the lightweight analysis database, create a publication database with denormalized data ready to push to AGOL.
    :param analysis_gdb: Location of analysis geodatabase.
    :param publication_gdb: Path with name of output publication geodatabase.
    :return: Path to publication geodatabase.
    """
    # create the output geodatabase
    out_gdb = arcpy.CreateFileGDB_management(
        out_folder_path=os.path.dirname(publication_gdb),
        out_name=os.path.basename(publication_gdb),
        out_version='CURRENT'
    )[0]

    # save full path to meta table
    meta_table = os.path.join(analysis_gdb, 'reach_meta')

    # for all the needed feature classes, copy to the publication geodatabase with meta added
    for feature_class in ['access', 'hydroline', 'parking', 'rapid', 'trail']:

        # create full path variables to resources
        in_fc = os.path.join(analysis_gdb, feature_class)
        out_fc = os.path.join(out_gdb, feature_class)

        # create and add meta to output feature class
        create_feature_class_with_meta(in_fc, meta_table, out_fc)

        # since they all reference AW reaches, make it easy to link back to AW
        add_link_to_american_whitewater_reach_page(out_fc)

    # add navigation links to hydrolines
    add_navigation_links_to_hydrolines(
        os.path.join(out_gdb, 'hydroline'),
        os.path.join(out_gdb, 'access'),
        os.path.join(out_gdb, 'parking')
    )

    # create hydropoints feature class
    create_hydropoint_feature_class(
        os.path.join(out_gdb, 'hydroline'),
        os.path.join(out_gdb, 'hydropoint')
    )

    # create invalid point feature class
    create_invalid_points_feature_class(
        os.path.join(out_gdb, 'access'),
        os.path.join(analysis_gdb, 'reach_invalid'),
        os.path.join(out_gdb, 'reach_invalid_points')
    )

    # return the path to the newly created publication geodatabase
    return out_gdb
