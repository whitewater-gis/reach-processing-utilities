import arcpy
import os
import zipfile
import ftplib
import re


def _get_nhd_subregion(huc4, output_directory):
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

    # open connection to USGS FTP server
    ftp = ftplib.FTP('nhdftp.usgs.gov')
    ftp.login()

    # change directory to where the desired zipped archives live
    ftp.cwd('DataSets/Staged/SubRegions/FileGDB/HighResolution')

    # set the output file path
    temp_zip = os.path.join(scratch_dir, 'NHDH{}_931v220.zip'.format(huc4))

    # get the archive from the USGS and store it locally
    ftp.retrbinary('RETR NHDH{}_931v220.zip'.format(huc4), open(temp_zip, 'wb').write)

    # close the connection to the USGS FTP server
    ftp.close()

    # unzip the archive to the temp directory
    zfile = zipfile.ZipFile(temp_zip)

    # extract all the contents to the output directory
    zfile.extractall(scratch_dir)

    # unzip the archive to the temp directory
    zfile = zipfile.ZipFile(temp_zip)

    # extract all the contents to the output directory
    zfile.extractall(output_directory)

    # return the path to the subregion gdb
    return os.path.join(output_directory, 'NHDH{}.gdb'.format(huc4))


def append_subregion_data(nhd_subregion_fgdb, master_geodatabase):
    """
    Append the hydrolines from a downloaded USGS NHD subregion geodatabase to a master dataset.
    :param nhd_subregion_fgdb: USGS NHD subregion geodatabase downloaded from the USGS.
    :param master_geodatabase: Master geodatabase storing the NHD data.
    :return:
    """
    # provide a little user information
    arcpy.AddMessage('Appending data from {}'.format(os.path.basename(nhd_subregion_fgdb)))

    # variable for the full path to the NHD Flowline feature class
    source_hydroline = os.path.join(nhd_subregion_fgdb, 'Hydrography', 'NHDFlowline')

    # get path to output paths, taking into account it may be in an SDE
    for top_dir, dir_list, obj_list in arcpy.da.Walk(master_geodatabase):
        for obj in obj_list:

            # use regular expression matching to find NHDFlowline
            if re.match(r'^.*NHDFlowline', obj):

                # full path to target hydroline feature class
                target_hydroline = '{}\{}'.format(top_dir, obj)

    # set the environment variable to leave indexes untouched during processing...this allows features to be appended
    arcpy.env.maintainSpatialIndex = True

    # append features for subregion
    arcpy.Append_management(
        inputs=source_hydroline,
        target=target_hydroline
    )

    # TODO: get rebuild indexes working & add analyze!
    # rebuild indexes for this feature class, excluding system tables since using the data owner connection
    # arcpy.RebuildIndexes_management(
    #     input_database=master_geodatabase,
    #     include_system=False,
    #     in_datasets=target_hydroline
    # )

    # return to be complete
    return


def update_flow_direction(master_geodatabase):
    """
    Update the flow direcation for HYDRO_NET geometric network.
    :param master_geodatabase: The master geodatabase where all the NHD flowlines are being stored.
    :return:
    """
    # provide a little information
    arcpy.AddMessage("Updating geometric network flow direction.")

    # get network path taking into account it may be in an SDE
    for top_dir, dir_list, obj_list in arcpy.da.Walk(master_geodatabase):

        # iterate the objects
        for obj in obj_list:

            # use regular expression matching to filter out HYDRO_NET
            if re.match(r'^.+HYDRO_NET', obj):

                # save full path to a variable
                hydro_net = '{}\{}'.format(top_dir, obj)

            # if the hydro net does not exist
            else:

                # throw an error
                raise Exception('HYDRO_NET geometric network does not appear to exist in {}'.format(master_geodatabase))

    # update the geometric network with the flow direction
    arcpy.SetFlowDirection_management(hydro_net, 'WITH_DIGITIZED_DIRECTION')


def get_and_append_subregion_data(huc4, master_geodatabase):
    """
    Download a subregion from the USGS, download it and set up the data for analysis.
    :param huc4: String four digit HUC to download
    :param master_geodatabase: Master geodatabase where data likely will reside.
    :return:
    """
    # download the data and save the file geodatabase in the scratch directory
    usgs_subregion_fgdb = _get_nhd_subregion(huc4, arcpy.env.scratchFolder)

    # append the data to an existing geodatabase
    append_subregion_data(usgs_subregion_fgdb, master_geodatabase)

    # delete the staging geodatabase
    arcpy.Delete_management(usgs_subregion_fgdb)

    # return to be complete
    return


def update_download_tracking(hydrolines_feature_class, huc4_feature_class):
    """
    Update an integer field with boolean values in the huc4 feature class, flowlines_downloaded, to track downloaded
    subregions.
    :param hydrolines_feature_class: Hydrolines representing the
    :param huc4_feature_class:
    :return:
    """

    # list comprehension enclosed in set slicing off first four characters of huc codes for hydrolines, creating
    # unique list of four digit huc codes
    subregion_code_list = set([row[0][0:4] for row in arcpy.da.SearchCursor(hydrolines_feature_class, 'reachcode')])

    # create update cursor
    with arcpy.da.UpdateCursor(huc4_feature_class, ['huc4', 'flowlines_downloaded']) as update_cursor:

        # for every row in the table
        for row in update_cursor:

            # set the row initially to falsy
            row[1] = 0

            # test the current subregion against the hydrolines code list
            for code in subregion_code_list:

                # if the code exists
                if code == row[0]:

                    # update the row truthy
                    row[1] = 1

            # update the row
            update_cursor.updateRow(row)

    # return...just because
    return