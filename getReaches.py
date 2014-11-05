# import modules
import arcpy
import os

def cleanup(putins, takeouts, hydrolines, snapDistanceFeet):
    """
    Snap the putins and takeouts to the hydrolines and then the takeouts to the
    putins.
    """
    # since the snap tool requires a specifically formatted string, create these
    hydrolinesSnapString = "{0} EDGE '{1} feet'".format(hydrolines, snapDistanceFeet)
    putinSnapString = "{0} VERTEX '{1} feet'".format(putins, takeouts)

    # snap the putins to the hydrolines
    arcpy.Snap_edit(putins, hydrolinesSnapString)

    # snap the takeouts to the hydrolines
    arcpy.Snap_edit(takeouts, hydrolinesSnapString)

    # snap the takeouts to the putins
    arcpy.Snap_edit(takeouts, putinSnapString)

def accessValid(accessLayer, hydrolinesLayer, awid):
    """
    Evaluate the validity of the access (takeout or putin) based on the awid.
    The feature is identified and the coincidence with hydrolines is evaluated.
    """
    # data workspace
    wksp = os.path.dirname(arcpy.Describe(accessLayer).catalogPath)

    # add field delimters based on the source workspace
    sqlStub = arcpy.AddFieldDelimiters(wksp, 'awid')

    # finish the sql string
    sql = "{} = '{}'".format(sqlStub, awid)

    # select takeout by awid
    arcpy.SelectLayerByAttribute_management(
        in_layer_or_view=accessLayer,
        selection_type='NEW_SELECTION',
        where_clause=sql
    )

    # select by location to see if conincident with hydrolines
    arcpy.SelectLayerByLocation_management(
        in_layer=accessLayer,
        overlap_type='INTERSECT',
        select_features=hydrolinesLayer,
        selection_type='SUBSET_SELECTION'
    )

    # if concident, one feature should still be selected and we return true
    if len(arcpy.Describe(accessLayer).FIDSet):
        return True

    # if nothing is selected, it is not coincident, and return false
    else:
        return False

def getValidReaches(awidList, putins, takeouts, hydrolines):
    """
    Get list of valid reach awids.
    """
    # list to store valid aw id's
    validAwidList = []

    # for every awid in the list
    for awid in awidList:

        # if both the putin and takeout are valid
        if accessValid(putins, hydrolines, awid) and accessValid(takeouts, hydrolines, awid):

            # add the awid to the valid list
            validAwidList.append(awid)

    # return the list...sorted because I like things organized
    return sorted(validAwidList)

def getLineGeometry(putin, takeout, hydrolines, geometricNetwork):
    """
    Select and extract geometry using a putin and takeout from hydrolines.
    """
    # get the hydroline using the trace function
    traceLayer = arcpy.TraceGeometricNetwork_management(
        in_geometric_network=geometricNetwork,
        out_network_layer="Downstream",
        in_flags=putin,
        in_trace_task_type="TRACE_DOWNSTREAM",
        in_barriers=takeout
    )[0]

    # Trace returns a list with three layer objects, the first the group layer,
    # the second a layer for junctions and the third is the traced edge. We are
    # interested in the edge
    reachSegments = arcpy.mapping.ListLayers(traceLayer)[2]

    # dissolve the selected segments into one reach
    thisReach = arcpy.Dissolve_management(reachSegments, 'in_memory/thisReach')

    # use a search cursor in a list comprehension to extract the geometry
    reachGeometry = [row[0] for row in arcpy.da.SearchCursor(thisReach, 'SHAPE@')][0]

    # return the geometery
    return reachGeometry

def getAwidReaches(putinFc, takeoutFc, hydrolineFc, geometricNetwork, outputWorkspace):
    """
    Get valid AW reaches.
    """
    # create layers from input feature classes
    putinLyr = arcpy.MakeFeatureLayer_management(putinFc, 'putins')[0]
    takeoutLyr = arcpy.MakeFeatureLayer_management(takeoutFc, 'takeouts')[0]
    hydrolineLyr = arcpy.MakeFeatureLayer_management(hydrolineFc, 'hydrolines')[0]

    # create a target feature class for exporting valid awid reach hydrolines
    outFcValid = arcpy.CreateFeatureclass_management (
        out_path=outputWorkspace,
        out_name='awHydrolines',
        geometry_type='POLYLINE',
        spatial_reference=arcpy.Describe(putinFc).spatialReference
    )[0]

    # add awid field to feature class
    arcpy.AddField_management(
        in_table=outFcValid,
        field_name='awid',
        field_type='TEXT',
        field_length='8'
    )

    # create insert cursor for the lines feature class
    insertCursor = arcpy.da.SearchCursor(outFcValid, 'awid', 'SHAPE@')

    # get list of awid's
    awidList = [row[0] for row in arcpy.da.SearchCursor(putinLyr, 'awid')]

    # extract the hydrolines for each valid awid
    for awid in getValidReaches(awidList, putinLyr, takeoutLyr, hydrolineLyr):

        # data workspace
        wksp = os.path.dirname(arcpy.Describe(putinLyr).catalogPath)

        # add field delimters based on the source workspace
        sqlStub = arcpy.AddFieldDelimeters(wksp, 'awid')

        # finish the sql string
        sql = "{} = '{}'".format(sqlStub, awid)

        # select putin by awid
        putinPoint = arcpy.SelectLayerByAttribute_management(
            in_layer_or_view=putinLyr,
            selection_type='NEW_SELECTION',
            where_clause=sql
        )[0]


        # select takeout by awid
        takeoutPoint = arcpy.SelectLayerByAttribute_management(
            in_layer_or_view=takeoutLyr,
            selection_type='NEW_SELECTION',
            where_clause=sql
        )[0]

        # get the geometry for the awid
        reachGeometry = getLineGeometry(putinPoint, takeoutPoint, hydrolineLyr, geometricNetwork)

        # insert the awid into the new feautre class
        insertCursor.insertRow(awid, reachGeometry)

# run the script as standalone
if __name__ == "__main__":

    # variables for testing
    putinFc = r'D:\spatialData\aw_Snoqualmie\dataAwSnqul.gdb\hydro_nad83\accessPutin_nad83'
    takeoutFc = r'D:\spatialData\aw_Snoqualmie\dataAwSnqul.gdb\hydro_nad83\accessTakeout_nad83'
    hydrolineFc = r'D:\spatialData\aw_Snoqualmie\dataAwSnqul.gdb\hydro_nad83\NHDFlowline'
    geometricNetwork = r'D:\spatialData\aw_Snoqualmie\resources\NHDH1711.gdb\Hydrography\HYDRO_NET'
    outputGdb = r'C:\Users\joel5174\Documents\ArcGIS\Default.gdb'

    # overwrite previous runs
    arcpy.env.overwriteOutput = True

    # run the thing
    getAwidReaches(putinFc, takeoutFc, hydrolineFc, geometricNetwork, outputGdb)