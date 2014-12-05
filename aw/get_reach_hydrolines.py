"""
author:     Joel McCune (joel.mccune+aw@gmail.com)
dob:        04 Dec 2014
purpose:    Provide a tool wrapper for extracting and saving reach hydrolines.
"""
# import modules
import arcpy
import reach_utlities

# collect input parameters and run functions
reach_utlities.get_reach_line_fc(
    access_fc=arcpy.GetParameter(0),
    hydro_network=arcpy.GetParameter(1),
    output_hydroline_fc=arcpy.GetParameterAsText(2),
    output_invalid_reach_table=arcpy.GetParameterAsText(3)
)