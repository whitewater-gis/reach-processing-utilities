"""
author:     Joel McCune (joel.mccune+gis@gmail.com)
dob:        03 Dec 2014
purpose:    Provide the utilities to process and work with whitewater reach data.

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
import zipfile
import urllib
import re
import logging
import arcpy


def download_nhd_subregion(huc4, output_directory):
    """
    Download a subregion from the USGS, download it and set up the data for analysis.
    :param huc4: String four digit HUC to download
    :param output_directory: Directory where the downloaded subregion file geodatabase will be stored.
    :return: String path to output file geodatabase.
    """
    # add a little information to the user
    logging.info('Downloading data from the USGS for subregion {}.'.format(huc4))

    # download the zipped resource
    temp_zip = urllib.urlretrieve('https://prd-tnm.s3.amazonaws.com/StagedProducts/Hydrography/NHD/HU4/' +
                                  'HighResolution/GDB/NHD_H_{HU4}_GDB.zip'.format(HU4=huc4))[0]

    # create a zipfile object to work with
    zfile = zipfile.ZipFile(temp_zip)

    # get a list of folders in the archive
    archive_folder_list = [_ for _ in zfile.namelist() if _.endswith('/')]

    # get the geodatabase out of the list of folders - likely redundant, but just in case
    zip_gdb = [_ for _ in archive_folder_list if re.search(r'(.*?NHD_H_{}.*?gdb)'.format(huc4), _) is not None][0]

    # extract the file geodatabase folder from the archive
    gdb = zfile.extract(zip_gdb, output_directory)

    # now get all the items in the archive in the file geodatabase, and extract them as well
    gdb_object_list = [_ for _ in zfile.namelist() if _.startswith(zip_gdb)]
    for gdb_zip_obj in gdb_object_list:
        zfile.extract(gdb_zip_obj, output_directory)

    # delete the zfile object and the archive on disk
    del zfile
    os.remove(temp_zip)

    # return the path to the subregion gdb
    return gdb


def create_output_geodatabase_and_hydro_net(nhd_gdb, output_directory):
    """
    Using a USGS NHD subregion database as a source, extract the flowlines and create a new geometric network with them.
    :param nhd_gdb: The source NHD subregion geodatabase.
    :param output_directory: The directory where the geodatabase will reside
    :return: String path to the hydrology network.
    """
    # get the subregion four digit huc
    huc4 = re.search(ur'NHD_H_(?P<huc4>.*?)_GDB\.gdb', nhd_gdb).group('huc4')

    # output file geodatabase name
    out_fgdb_name = '{}.gdb'.format(huc4)

    # ensure the output does not already exist...most likely only a problem during testing
    arcpy.Delete_management(os.path.join(arcpy.env.scratchFolder, out_fgdb_name))

    # create the database for the subregion
    staging_fgdb = arcpy.CreateFileGDB_management(
        out_folder_path=arcpy.env.scratchFolder,
        out_name=out_fgdb_name
    )[0]

    # create the hydrology feature dataset
    output_featuredataset = arcpy.CreateFeatureDataset_management(
        out_dataset_path=staging_fgdb,
        out_name='Hydrography',
        spatial_reference=arcpy.Describe(os.path.join(nhd_gdb, 'Hydrography')).spatialReference
    )[0]

    # copy the nhd flowlines into the new feature dataset
    arcpy.CopyFeatures_management(
        in_features=os.path.join(nhd_gdb, 'Hydrography', 'NHDFlowline'),
        out_feature_class=os.path.join(output_featuredataset, 'NHDFlowline')
    )

    # create a geometric network with using the flowlines
    geometric_network = arcpy.CreateGeometricNetwork_management(
        in_feature_dataset=output_featuredataset,
        out_name='HYDRO_NET',
        in_source_feature_classes='NHDFlowline SIMPLE_EDGE NO'
    )[0]

    # set the flow direction so tracing will work
    arcpy.SetFlowDirection_management(
        in_geometric_network=geometric_network,
        flow_option="WITH_DIGITIZED_DIRECTION"
    )

    # move to final location...this accommodates slower io to file servers
    final_gdb = arcpy.Copy_management(
        in_data=staging_fgdb,
        out_data=os.path.join(output_directory, out_fgdb_name)
    )[0]

    # report success
    logging.info('Analysis database for subregion {} is ready.'.format(huc4))

    # return the path to the final result
    return final_gdb


def get_nhd_subregion(huc4, subregion_directory):
    """
    Since geometric networks are faster in a file geodatabase, the opted for storage alternative is a current file
    geodatabase. Supporting this paradigm is this function, downloading the data to a staging location, extracting the
    contents, copying only what we need to a current file geodatabase and deleting any intermediate data.
    :param huc4: String four digit identifier for the subregion.
    :param subregion_directory: Directory where all subregion geodatabases will be saved for
    :return: String path to the subregion geodatabase.
    """
    # use the scratch folder as the staging location
    temp_directory = arcpy.env.scratchFolder

    # download and extract the NHD subregion from the USGS
    try:
        staged_gdb = download_nhd_subregion(huc4, temp_directory)

        # create the output geodatabase and hydrology network for analysis
        analysis_gdb = create_output_geodatabase_and_hydro_net(staged_gdb, subregion_directory)

        # delete the staging geodatabase
        arcpy.Delete_management(staged_gdb)

        # return the path to the geodatabase
        return analysis_gdb

    except Exception as e:

        # clean out any returns from the error text
        e = e.message.replace('\n', ' ').replace('\r', ' ')

        # report what happened, and on which reach
        logging.error('Could not process subregion {HU4}. Error Message: {err}'.format(
            HU4=huc4, err=e))


def build_subregion_directory_logic(subregion_directory, nhd_subregions):
    """
    For a file server or some other location with a LOT of storage where all the subregions can be staged for follow
    on analysis, use this function to download and process all the subregions.
    :param subregion_directory: String directory where all the subregions will live.
    :return:
    """
    # get a list of all subregions currently in the directory...if any
    regex = re.compile(r'(?P<huc4>\d{4})\.gdb')
    local_subregions = [regex.match(obj).group('huc4') for obj in os.listdir(subregion_directory) if regex.match(obj)]

    # remove any subregions already downloaded from the nhd list...sorted, because I am anal retentive like that
    nhd_subregions = sorted([huc4 for huc4 in nhd_subregions if huc4 not in local_subregions])

    # iterate the nhd list and set up the subregion directory
    for huc4 in nhd_subregions:
        get_nhd_subregion(huc4, subregion_directory)


def build_subregion_directory(subregion_directory, huc4_polygon_feature_class):
    """
    Provide brute force wrapper to keep trying when encountering errors (typically associated with file io issues).
    :param subregion_directory: String directory where all the subregions will live.
    :param huc4_polygon_feature_class: Feature class of HUC4 polygons from the USGS to use as a list for downloading
        NHD subregions.
    :return:
    """
    # set up logging
    logging.basicConfig(
        filename=os.path.join(subregion_directory, 'nhd_data_log.log'),
        format='%(asctime)s %(levelname)s %(message)s',
        datefmt='%Y%m%d %H:%M:%S',
        level=0
    )

    # keep track of errors encountered
    error_count = 0

    # create a list of all the four digit HUCs
    huc4_list = [row[0] for row in arcpy.da.SearchCursor(huc4_polygon_feature_class, 'huc4')]

    # keep diving in if less than 10 errors encountered
    if error_count < 10:

        # get in there and run the analysis
        try:
            build_subregion_directory_logic(subregion_directory, huc4_list)

        # if something blows up
        except Exception as e:

            # increment the error counter
            error_count += 1

            # if there are less than 10 errors
            if error_count < 10:

                # report something blew up
                logging.error('Attempting to recover from an error. Error Message:{err}'.format(err=e))

            # otherwise
            else:
                logging.error(e)
