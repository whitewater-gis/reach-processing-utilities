def join_table_to_access(access_fc, join_table):
    """
    Append records to access feature class with a permanent join. This is a utility function for denormalizing data
    for publishing as a service.
    :param access_fc: Access feature class with putin, takeout, and intermediate fields populated with reach ids.
    :param join_table: Table, typically either the invalid or meta table. This table MUST have and be ready to use
         a field named reach_id for the join.
    :return: Boolean success or failure.
    """
    # read the fields from the join table
    join_fields = arcpy.ListFields(join_table)

    # list for fields to be used with update cursor
    cursor_field_list = []

    # add these fields, except the reach_id to the access feature class
    for field in join_fields:

        # if the field is not 'reach_id'
        if field.name != 'reach_id' and field.type != 'OID':

            # add the field to the access feature class
            arcpy.AddField_management(
                in_table=access_fc,
                field_name=field.name,
                field_type=field.type,
                field_length=field.length,
                field_alias=field.aliasName
            )

            # add the field to the join field list
            cursor_field_list.append(field.name)

    # create feature layer
    access_lyr = arcpy.MakeFeatureLayer_management(access_fc, 'access_layer')[0]

    # create table view
    join_view = arcpy.MakeTableView_management(join_table, 'join_view')[0]

    # get list of invalid reaches
    join_reach_id_list = [row[0] for row in arcpy.da.SearchCursor(join_table, 'reach_id')]

    # list for storing access types and their respective lists of reach id's
    access_reach_id_list_by_type = []

    # get list of putin, takeout and intermediate access points
    for access_type in ['putin', 'takeout', 'intermediate']:

        # get list of access reach id's for given access type
        access_reach_id_list = [row[0] for row in arcpy.da.SearchCursor(access_fc, access_type)]

        # save the type with the count
        access_reach_id_list_by_type.append(
            {
                type: access_type,
                reach_id_list: access_reach_id_list
            }
        )

    # iterate the invalid reach id's
    for reach_id in join_reach_id_list:

        # make sure no features are selected
        arcpy.SelectLayerByAttribute_management(access_lyr, 'CLEAR_SELECTION')

        # since null values make the script puke, we have to do this
        for access_type in ['putin', 'takeout', 'intermediate']:

            # for every access reach id for this type
            for access_reach_id in access_reach_id_list_by_type['reach_id_list']:

                #if the access id matches the join reach id list
                if access_reach_id == reach_id:

                    # select the reach_id records
                    arcpy.SelectLayerByAttribute_management(
                        in_layer_or_view=access_lyr,
                        selection_type='ADD_TO_SELECTION',
                        where_clause="{} = '{}'".format(access_type, access_reach_id)
                    )

                    # since we found our reach, break out of the loop
                    break

        # select the record in the join table
        join_sel = arcpy.SelectLayerByAttribute_management(
            in_layer_or_view=join_view,
            selection_type='NEW_SELECTION',
            where_clause="reach_id = '{}'".format(reach_id)
        )

        # get array of values in this single row
        join_row = [selRow for selRow in arcpy.da.SearchCursor(join_sel, cursor_field_list)][0]

        # for each of the selected rows
        with arcpy.da.UpdateCursor(access_sel, cursor_field_list) as cursor:
            for row_join in cursor:

                # populate the field with the values from the join table
                row_join = join_row

                # update the records
                cursor.updateRow(row_join)

    # return success, path to feature class
    return access_fc


def add_meta_to_hydrolines(hydroline_fc, meta_table):
    """
    After running the analysis to extract valid hydrolines, this adds the relevant metadata from the master metadata
    table.
    :param hydroline_fc: The output from getting the hydrolines above with an reach id field.
    :param meta_table: The master reach metadata table created from the original reach extract.
    :return: boolean: Success or failure.
    """
    # list of attribute fields to be added
    attribute_list = [
        {'name': 'name_river', 'type': 'TEXT', 'length': 255},
        {'name': 'name_section', 'type': 'TEXT', 'length': 255},
        {'name': 'name_common', 'type': 'TEXT', 'length': 255},
        {'name': 'difficulty', 'type': 'TEXT', 'length': 10},
        {'name': 'difficulty_min', 'type': 'TEXT', 'length': 5},
        {'name': 'difficulty_max', 'type': 'TEXT', 'length': 5},
        {'name': 'difficulty_outlier', 'type': 'TEXT', 'length': 5}
    ]

    # add all the fields to hydrolines
    for attribute in attribute_list:
        arcpy.AddField_management(hydroline_fc, attribute['name'], attribute['type'], field_length=attribute['length'])

    # get list of all reach id's
    reach_id_list = set([row[0] for row in arcpy.da.SearchCursor(hydroline_fc, 'reach_id')])

    # create a layer for the hydroline feature class
    hydroline_lyr = arcpy.MakeFeatureLayer_management(hydroline_fc, 'hydroline_lyr')

    # create table view for meta table
    meta_veiw = arcpy.MakeFeatureLayer_management(meta_table, 'meta_view')

    # attributes to transfer for update cursor
    attribute_name_list = ['reach_id'] + [attribute['name'] for attribute in attribute_list]

    # for every reach id found
    for reach_id in reach_id_list:

        # create sql string to select the reach
        sql = "{} = '{}'".format(
            arcpy.AddFieldDelimiters(os.path.dirname(arcpy.Describe(hydroline_fc).catalogPath), 'reach_id'),
            reach_id
        )

        # select features in the hydroline feature class
        arcpy.SelectLayerByAttribute_management(hydroline_lyr, 'NEW_SELECTION', sql)

        # select features in the meta view
        arcpy.SelectLayerByAttribute_management(meta_veiw, 'NEW_SELECTION', sql)

        # load attributes from meta table into cursor and retrieve single record as row
        meta_values = [row for row in arcpy.da.SearchCursor(meta_veiw, attribute_name_list)][0]

        # use update cursor to populate the values in the feature class
        with arcpy.da.UpdateCursor(hydroline_lyr) as update_cursor:

            # iterate selected rows
            for row in update_cursor:

                # use the collected values from the meta table to populate the row in the feature class
                row = meta_values

                # commit the changes
                update_cursor.updateRow(row)

    # return happy
    return True


def get_reach_centroid(reach_hydroline_geometry_list):
    """
    Get the center of the geomtery for the reach from the geometry list of all the line segments.
    :param reach_hydroline_geometry_list: List of line geometry objects comprising the reach.
    :return: Point geometry object at the geometric center of the reach, not necessarily coincident with any line
        geometry.
    """
    # create extent object to work with
    extent = arcpy.Extent()

    # for every line geometry, get the extent
    for line_geometry in reach_hydroline_geometry_list:

        # if the xmin is less than the saved value, save it
        if line_geometry.XMin < extent.XMin:
            extent.XMin = line_geometry.XMin

        # if the ymin is less than the saved value, save it
        if line_geometry.YMin < extent.YMin:
            extent.YMin = line_geometry.YMin

        # if the xmax is greater than the saved value, save it
        if line_geometry.XMax > extent.XMax:
            extent.XMax = line_geometry.XMax

        # if the ymax is greater than the saved value, save it
        if line_geometry.YMax > extent.YMax:
            extent.YMax = line_geometry.YMax

    # create a point centroid and return it
    return arcpy.Point(
        X=extent.XMin + (extent.YMax - extent.YMin) / 2,
        Y=extent.YMin + (extent.YMax - extent.YMin) / 2
    )


def create_reach_centroid_feature_class(reach_hydroline_feature_class, output_reach_centroids):
    """
    Create a feature class consisting of little more than centroids for each reach for symbolizing at smaller scales.
    :param reach_hydroline_feature_class: Reach hydroline feature class.
    :param output_reach_centroids: Location and name for output point feature class.
    :return: String path to output.
    """
    # make feature class using the input hydrolines for a schema template
    arcpy.CreateFeatureclass_management(
        out_path=os.path.dirname(output_reach_centroids),
        out_name=os.path.basename(output_reach_centroids),
        template=reach_hydroline_feature_class
    )