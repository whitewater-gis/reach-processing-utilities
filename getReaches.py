# import modules
import arcpy
import os.path


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
    arcpy.SelectLayerByAttribute_management(accessLayer, 'NEW_SELECTION', sql)

    # select by location to see if conincident with hydrolines
    selection = arcpy.SelectLayerByLocation_management(
        in_layer=hydrolinesLayer,
        overlap_type='INTERSECT',
        select_features=accessLayer,
        selection_type='NEW_SELECTION'
    )

    # if concident, one hydroline feature should be selected and we return true
    if selection.outputCount:
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


def getReachGeometry(putin, takeout, geometricNetwork):
    """
    Extract the geometry for a reach.
    @putin - layer with a single putin selected by awid
    @takeout = layer with a single takeout selected by awid
    @geometricNetwork - NHD geometric network
    """
    # trace from the putin to the takeout
    traceLayer = arcpy.TraceGeometricNetwork_management(
        in_geometric_network=geometricNetwork,
        out_network_layer="Downstream",
        in_flags=putin,
        in_trace_task_type="TRACE_DOWNSTREAM",
        in_barriers=takeout
    )[0]

    # Trace returns a group layer with the joints and edges selected. Get the layer for the selected edges.
    lineLyr = arcpy.mapping.ListLayers(traceLayer)[2]

    # the last line segment does not get selected, so pick it up
    arcpy.SelectLayerByLocation_management(lineLyr, "INTERSECT", takeout, selection_type="ADD_TO_SELECTION")

    # split at the putin
    reachSplitPutinFc = arcpy.SplitLineAtPoint_management(lineLyr, putin, os.path.join('in_memory', 'reachSplitPutinFc'))[0]

    # split at the takeout
    reachSegmentedFc = arcpy.SplitLineAtPoint_management(reachSplitPutinFc, takeout, os.path.join('in_memory', 'reachSegmentedFc'))[0]

    # trim off dangles upstream and downstream of the identified reach
    arcpy.TrimLine_edit(reachSegmentedFc)

    # dissolve into single feature
    reachFc = arcpy.Dissolve_management(reachSegmentedFc, 'reachFc')

    # use list comprehension to get geometry out
    geometryList = [row[0] for row in arcpy.da.SearchCursor(reachFc, 'SHAPE@')]

    # make sure there actually is a geometry
    if len(geometryList) == 0:
        return False

    # otherwise, give up the goods
    else:
        return geometryList[0]


def getReaches(putinFc, takeoutFc, geometricNetwork, outputWorkspace):
    """
    Get valid AW reaches.
    """
    # TODO: add parameter switch for optionally including validation(snapping)

    # Set the output workspace
    arcpy.env.workspace = outputWorkspace

    # If NHD data the hydrolines will always be named NHDFlowline, and we can hard code this.
    hydrolineFc = os.path.join(os.path.dirname(geometricNetwork), 'NHDFlowline')

    # create layers from input feature classes
    putinLyr = arcpy.MakeFeatureLayer_management(putinFc, 'putins')[0]
    takeoutLyr = arcpy.MakeFeatureLayer_management(takeoutFc, 'takeouts')[0]
    hydrolineLyr = arcpy.MakeFeatureLayer_management(hydrolineFc, 'hydrolines')[0]

    # create a target feature class for exporting valid awid reach hydrolines
    outFc = arcpy.CreateFeatureclass_management(
        out_path=outputWorkspace,
        out_name='awHydrolines',
        geometry_type='POLYLINE',
        spatial_reference=arcpy.Describe(putinLyr).spatialReference
    )[0]

    # add awid field to feature class
    arcpy.AddField_management(outFc, 'awid', 'TEXT', '8')

    # get list of awid's
    awidList = [row[0] for row in arcpy.da.SearchCursor(putinLyr, 'awid')]
    grossCount = len(awidList)

    # of the gross count, get the valid count
    validReaches = getValidReaches(awidList, putinLyr, takeoutLyr, hydrolineLyr)
    validCount = len(validReaches)

    # TODO: add logging or reporting for this
    print('{} of {} ({}%) reaches are valid'.format(validCount, grossCount, validCount/grossCount*100.0))

    # create insert cursor for the lines feature class
    insertCursor = arcpy.da.InsertCursor(outFc, ('awid', 'SHAPE@'))

    # data workspace
    wksp = os.path.dirname(arcpy.Describe(putinLyr).catalogPath)

    # add field delimters based on the source workspace
    sqlStub = arcpy.AddFieldDelimiters(wksp, 'awid')

    # extract the hydrolines for each valid awid
    for awid in validReaches:

        # finish the sql string
        sql = "{} = '{}'".format(sqlStub, awid)

        # select both the putin and the takeout points
        for access in (putinLyr, takeoutLyr):

            # select putin & takeout by awid
            arcpy.SelectLayerByAttribute_management(access, 'NEW_SELECTION', sql)

        # get the geometry for the awid
        reachGeometry = getReachGeometry(putinLyr, takeoutLyr, geometricNetwork)

        # if the reachGeometry finds a geometry
        if reachGeometry:

            # insert the awid & geometry into the new feature class
            insertCursor.insertRow((awid, reachGeometry))

        # get rid of the cursor, freeing up memory and releasing the schema lock
        del insertCursor


# run the script as standalone
if __name__ == "__main__":

    # variables for testing
    putinFc = r'D:\spatialData\aw_Snoqualmie\dataAwSnqul.gdb\hydro_nad83\accessPutin_nad83'
    takeoutFc = r'D:\spatialData\aw_Snoqualmie\dataAwSnqul.gdb\hydro_nad83\accessTakeout_nad83'
    geometricNetwork = r'D:\spatialData\aw_Snoqualmie\resources\NHDH1711.gdb\Hydrography\HYDRO_NET'
    outputGdb = r'C:\Users\joel5174\Documents\ArcGIS\aw-temp.gdb'

    # overwrite previous runs
    arcpy.env.overwriteOutput = True

    # run the thing
    getReaches(putinFc, takeoutFc, geometricNetwork, outputGdb)