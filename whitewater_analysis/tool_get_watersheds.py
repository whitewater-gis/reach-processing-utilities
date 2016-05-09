"""
Tool binding for processing watersheds.
"""
from utilities.watershed_utilities import get_watersheds
from arcpy import GetParameter

get_watersheds(
    reach_hydroline_feature_class=GetParameter(0),
    access_feature_class=GetParameter(1),
    watershed_feature_class=GetParameter(2)
)
