#! /usr/bin/env python

import os
import xml.etree.ElementTree as ET
import urllib
import platform
import re
import config
import cgi
import sys
from MythTV.tmdb3 import searchMovie

if config.moviedb_testmode:
    moviedb = 'http://private-dc013f25e-themoviedb.apiary-mock.com/3/search/movie'
else:
    moviedb = 'http://api.themoviedb.org/3/search/movie'

for myth_dir in config.mythtv_recording_directories[:]:
    if os.path.exists(myth_dir) is not True:
        print myth_dir + " is not a valid path.  Aborting"
        quit()

if platform.system() == "Windows":
    separator = "\\"
else:
    separator = "/"

if os.path.isfile('library') or os.path.islink('library'):
    library = open('library', 'r')
    lib = re.split(",", library.read())
    library.close()
else:
    lib = ""

url = "http://" + config.host_url + ":" + config.host_port
print "Beginning symlinking."
print "Looking up from MythTV: " + url + '/Dvr/GetRecordedList'

tree = ET.parse(urllib.urlopen(url + '/Dvr/GetRecordedList'))
root = tree.getroot()

for program in root.iter('Program'):

    title = program.find('Title').text
    ep_title = program.find('SubTitle').text
    ep_season = program.find('Season').text.zfill(2)
    ep_num = program.find('Episode').text.zfill(2)
    ep_file_extension = program.find('FileName').text[-4:]
    ep_file_name = program.find('FileName').text
    ep_id = program.find('ProgramId').text
    ep_airdate = program.find('Airdate').text

    # parse show name for file-system safe name
    title = re.sub('[\[\]/\\;><&*%=+@!#^()|?]', '_', title)

    episode_name = title + " - S" + ep_season + "E" + ep_num

    # Skip previously finished files
    if len(lib) > 0:
        if ep_id in lib:
            print "Matched program ID, skipping " + episode_name
            continue
        else:
            lib.append(ep_id)

    # Handle specials, movies, etc.
    if ep_season == '00' and ep_num == '00':
        #Fallback 1: Check TheMovieDB
        moviedb_successful = False
        moviedb_run = False
        if (config.moviedb_enabled):
            print "Querying TheMovieDB for " + title
            res = searchMovie(title)
            print (res[0])
        #Fallback 2: Air date
        if (ep_airdate is not None and moviedb_run is True and
                moviedb_successful is False):
            episode_name = title + " - " + ep_airdate
        else:
            continue

    # Symlink path
    link_path = (config.plex_tv_directory +
                 title + separator + episode_name + ep_file_extension)

    # Watch for oprhaned recordings!
    source_dir = None
    for myth_dir in config.mythtv_recording_directories[:]:
        source_path = myth_dir + ep_file_name
        if os.path.isfile(source_path):
            source_dir = myth_dir
            break

    if source_dir is None:
        print ("Cannot create symlink for "
               + episode_name + ", no valid source directory.  Skipping.")
        continue

    if os.path.exists(link_path) or os.path.islink(link_path):
        print "Symlink " + link_path + " already exists.  Skipping."
        continue

    if not os.path.exists(config.plex_tv_directory + title):
        print "Show folder does not exist, creating."
        os.makedirs(config.plex_tv_directory + title)

    print "Linking " + source_path + " ==> " + link_path
    os.symlink(source_path, link_path)

# Save the list of file IDs
outstring = ""
for item in lib:
    outstring += item + ","

library = open('library', 'w')
library.write(outstring)
library.close()
