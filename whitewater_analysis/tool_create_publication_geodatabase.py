"""
Provide tool bindings to create a denormalized publication geodatabase.
"""
# minimal imports to enable the tool to open faster
from utilities.publishing_utilities import create_publication_geodatabase
from arcpy import GetParameterAsText

# call the tool
create_publication_geodatabase(
    analysis_gdb=GetParameterAsText(0),
    publication_gdb=GetParameterAsText(1)
)