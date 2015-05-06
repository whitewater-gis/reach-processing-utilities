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
import arcpy
import os
import zipfile
import ftplib
import re
import shutil


def get_huc4_from_gdb_name(nhd_gdb_archive_name):
    """
    Use regular expression matching to account for version updates when trying to find a specific subregion.
    :param nhd_gdb_archive_name: The name of the staged NHD subregion geodatabase.
    :return: Either the name of the archive or a boolean false.
    """
    # try to get a match
    match = re.match(r'NHDH(?P<huc4>.{4}).*?\.zip', nhd_gdb_archive_name)

    # if a match, return the huc4
    if match:
        return match.group('huc4')

    # otherwise, return false
    else:
        return False


def get_nhd_staged_subregion_dictionary_list(ftp_connection):
    """
    Using a ftp connection to the USGS staged subregions with the current working directory already set, get
    a list of all the subregions.
    :param ftp_connection: FTP connection object
    :return: List of dictonary objects
    """
    # dictionary object to store items
    nhd_dict = {}

    # for every item get the ftp directory
    for obj in ftp_connection.nlst():

        # try to get a match for the object
        huc4 = get_huc4_from_gdb_name(obj)

        # if the object is valid
        if huc4:

            # add it to the dictionary
            nhd_dict[huc4] = obj

    # return the dictionary
    return nhd_dict


def get_subregion_archive_name(huc4, ftp_connection):
    """
    Get the name of the zipped archive corresponding to the four digit hydrologic unit code.
    :param huc4: String of the four digit HUC
    :param ftp_connection: FTP connection object set to the correct current working directory.
    :return: String with the name of the zipped archive.
    """
    # get a dictionary of all the staged subregions
    nhd_dict = get_nhd_staged_subregion_dictionary_list(ftp_connection)

    # iterate the subregion list and get the right name of the zipped archive
    for key, value in nhd_dict.iteritems():

        # if the archive matches
        if key == huc4:

            # return the zipped archive name
            return value


def get_ftp_connection():
    """
    Make it easy to connect to the USGS FTP server
    :return: FTP object
    """
    # open connection to USGS FTP server
    ftp = ftplib.FTP('nhdftp.usgs.gov')
    ftp.login()

    # change directory to where the desired zipped archives live
    ftp.cwd('DataSets/Staged/SubRegions/FileGDB/HighResolution')

    # return the ftp object
    return ftp


def download_nhd_subregion(huc4, output_directory):
    """
    Download a subregion from the USGS, download it and set up the data for analysis.
    :param huc4: String four digit HUC to download
    :param output_fgdb: Directory where the downloaded subregion file geodatabase will be stored.
    :return: String path to output file geodatabase.
    """
    # add a little information to the user
    arcpy.AddMessage('Downloading data from the USGS for subregion {}'.format(huc4))

    # get path to scratch directory to store resources
    scratch_dir = arcpy.env.scratchFolder

    # get ftp connection
    ftp = get_ftp_connection()

    # get the name of the zipped archive to retrieve
    ftp_archive_name = get_subregion_archive_name(huc4, ftp)

    # set the output file path
    temp_zip = os.path.join(scratch_dir, ftp_archive_name)

    # get the archive from the USGS and store it locally
    ftp.retrbinary('RETR {}'.format(ftp_archive_name), open(temp_zip, 'wb').write)

    # close the connection to the USGS FTP server
    ftp.close()
    del ftp

    # unzip the archive to the temp directory
    zfile = zipfile.ZipFile(temp_zip)

    # extract all the contents to the output directory
    zfile.extractall(output_directory)

    # delete the zfile object and the archive on disk
    del zfile
    os.remove(temp_zip)

    # return the path to the subregion gdb
    return os.path.join(output_directory, 'NHDH{}.gdb'.format(huc4))


def create_output_geodatabase_and_hydro_net(nhd_geodatabase, output_directory):
    """
    Using a USGS NHD subregion database as a source, extract the flowlines and create a new geometric network with them.
    :param nhd_geodatabase: The source NHD subregion geodatabase.
    :param output_directory: The directory where the geodatabase will reside
    :return: String path to the hydrology network.
    """
    # get the subregion four digit huc
    huc4 = re.search(ur'NHDH(?P<huc4>.*?)\.gdb', nhd_geodatabase).group('huc4')

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
        spatial_reference=arcpy.Describe(os.path.join(nhd_geodatabase, 'Hydrography')).spatialReference
    )[0]

    # copy the nhd flowlines into the new feature dataset
    arcpy.CopyFeatures_management(
        in_features=os.path.join(nhd_geodatabase, 'Hydrography', 'NHDFlowline'),
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
    shutil.move(staging_fgdb, output_directory)


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

    # download and extract the NHD subregion from the USGS FTP server
    staged_gdb = download_nhd_subregion(huc4, temp_directory)

    # create the output geodatabase and hydrology network for analysis
    return create_output_geodatabase_and_hydro_net(staged_gdb, subregion_directory)


def build_subregion_directory(subregion_directory):
    """
    For a file server or some other location with a LOT of storage where all the subregions can be staged for follow
    on analysis, use this function to download and process all the subregions.
    :param subregion_directory: String directory where all the subregions will live.
    :return:
    """
    local_subregion_list = []
    # get a list of all subregions currently in the directory...if any
    for obj in [x[0] for x in os.walk(subregion_directory)]:
        match = re.search(r'(?P<huc4>\d{4})\.gdb', obj)
        if match:
            local_subregion_list.append(match.group('huc4'))

    # get a list of all subregions on the server
    nhd_subregion_list = [key for key in get_nhd_staged_subregion_dictionary_list(get_ftp_connection()).iterkeys()]

    # remove any subregions already downloaded from the nhd list
    for huc4 in local_subregion_list:
        if huc4 in nhd_subregion_list:
            nhd_subregion_list.remove(huc4)

    # iterate the nhd list and set up the subregion directory
    for huc4 in nhd_subregion_list:
        get_nhd_subregion(huc4, subregion_directory)