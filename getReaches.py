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
    arcpy.SelectLayerByLocation_management(
        in_layer=hydrolinesLayer,
        overlap_type='INTERSECT',
        select_features=accessLayer,
        selection_type='NEW_SELECTION'
    )

    # if concident, one hydroline feature should be selected and we return true
    if len(arcpy.Describe(hydrolinesLayer).FIDSet):
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

    # trace returns a group layer with the joints and edges selected. get the layer for the selected edges
    lineLyr = arcpy.mapping.ListLayers(traceLayer)[2]

    # the last line segment does not get selected, so pick it up with this command
    arcpy.SelectLayerByLocation_management(lineLyr, "INTERSECT", takeout, selection_type="ADD_TO_SELECTION")

    # dissolve into single feature
    dissolveFc = arcpy.Dissolve_management(lineLyr, 'in_memory/tempDissolveLine')[0]

    # split at the putin
    split01Fc = arcpy.SplitLineAtPoint_management(dissolveFc, putin, 'in_memory/tempPiLine')[0]

    # split at the takeout
    reachFc = arcpy.SplitLineAtPoint_management(split01Fc, takeout, 'in_memory/tempPiToLine')[0]

    # trim off dangles upstream and downstream of the identified reach
    arcpy.TrimLine_edit(reachFc)

    # return the geometry object
    return [row[0] for row in arcpy.da.SearchCursor(reachFc, 'SHAPE@')][0]


def getReaches(putinFc, takeoutFc, hydrolineFc, geometricNetwork, outputWorkspace):
    """
    Get valid AW reaches.
    """
    # create layers from input feature classes
    putinLyr = arcpy.MakeFeatureLayer_management(putinFc, 'putins')[0]
    takeoutLyr = arcpy.MakeFeatureLayer_management(takeoutFc, 'takeouts')[0]
    hydrolineLyr = arcpy.MakeFeatureLayer_management(hydrolineFc, 'hydrolines')[0]

    # create a target feature class for exporting valid awid reach hydrolines
    outFcValid = arcpy.CreateFeatureclass_management(
        out_path=outputWorkspace,
        out_name='awHydrolines',
        geometry_type='POLYLINE',
        spatial_reference=arcpy.Describe(putinFc).spatialReference
    )[0]

    # add awid field to feature class
    arcpy.AddField_management(outFcValid, 'awid', 'TEXT', '8')

    # create insert cursor for the lines feature class
    insertCursor = arcpy.da.SearchCursor(outFcValid, 'awid', 'SHAPE@')

    # get list of awid's
    awidList = [row[0] for row in arcpy.da.SearchCursor(putinLyr, 'awid')]

    # extract the hydrolines for each valid awid
    for awid in getValidReaches(awidList, putinLyr, takeoutLyr, hydrolineLyr):

        # data workspace
        wksp = os.path.dirname(arcpy.Describe(putinLyr).catalogPath)

        # add field delimters based on the source workspace
        sqlStub = arcpy.AddFieldDelimiters(wksp, 'awid')

        # finish the sql string
        sql = "{} = '{}'".format(sqlStub, awid)

        # select both the putin and the takeout
        for access in (putinLyr, takeoutLyr):
            # select putin by awid
            arcpy.SelectLayerByAttribute_management(access, 'NEW_SELECTION', sql)

        # get the geometry for the awid
        reachGeometry = getReachGeometry(putinLyr, takeoutLyr, geometricNetwork)

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
    getReaches(putinFc, takeoutFc, hydrolineFc, geometricNetwork, outputGdb)