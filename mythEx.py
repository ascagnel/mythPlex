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
from MythTV.tmdb3 import set_key
import calendar
from datetime import datetime, timedelta

def utc_to_local(utc_dt):
    # get integer timestamp to avoid precision lost
    timestamp = calendar.timegm(utc_dt.timetuple())
    local_dt = datetime.fromtimestamp(timestamp)
    assert utc_dt.resolution >= timedelta(microseconds=1)
    return local_dt.replace(microsecond=utc_dt.microsecond)

def open_library():
    if os.path.isfile('.library') or os.path.islink('.library'):
        library = open('.library', 'r')
        lib = re.split(",", library.read())
        library.close()
    else:
        lib = ""
    return lib

def main():
    print "[INFO] Starting mythEx"
    lib = open_library()
    url = "http://" + config.host_url + ":" + config.host_port
    print "[INFO] Looking up from MythTV: " + url + '/Dvr/GetRecordedList'

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
        ep_temp = program.find('StartTime').text
        ep_start_time = utc_to_local(datetime.strptime(ep_temp, '%Y-%m-%dT%H:%M:%SZ'))
        # parse start time for file-system safe name
        ep_start_time = datetime.strftime(ep_start_time, '%Y-%m-%d %H%M')

        # parse show name for file-system safe name
        title = re.sub('[\[\]/\\;><&*%=+@!#^()|?]', '_', title)

        episode_name = title + " - S" + ep_season + "E" + ep_num
        print "[INFO] Processing " + episode_name + " ..."

        # Skip previously finished files
        if len(lib) > 0:
            if ep_id in lib and (ep_season != '00' or ep_num != '00'):
                print "[WARN] Matched program ID" + ep_id + ", skipping " + episode_name
                continue
            else:
                print "[INFO] Adding " + episode_name + " to library"
                lib.append(ep_id)

        # Handle specials, movies, etc.
        if ep_season == '00' and ep_num == '00':
            #Fallback 1: Check TheMovieDB
            print "[WARN] no season or episode info - trying fallbacks"
            moviedb_successful = False
            moviedb_run = False
            if (config.moviedb_enabled):
                print "[INFO] (fallback 1) Querying TheMovieDB for " + title
                res = searchMovie(title)
                if (len(res) is 0):
                    moviedb_successful = False
                    print "[WARN] " + episode_name + "not found in TheMovieDB"
                else: 
                    print "[INFO] Successfully looked up in MovieDB"
                    moviedb_successful = True
                    print (res[0].title)
                    title = re.sub('[\[\]/\\;><&*%=+@!#^()|?]', '_', res[0].title)
                    episode_name = title
     
        #Fallback 2: start time 
            if (ep_start_time is not None): 
                if (moviedb_run is False or (moviedb_run is True and
                                             moviedb_successful is False)):
                    print "[INFO] (fallback 2) using start time"
                    episode_name = title + " - " + ep_start_time
                    print "[INFO] Changed to " + episode_name
            else:
                print "[WARN] no start time available"

        else:
            print "[INFO] have season and episode."

        # Symlink path
        print "[INFO] symlink processing.."
        link_path = (config.plex_tv_directory +
                     title + separator + episode_name + ep_file_extension)
        #print "[INFO] link path is " + link_path

        # Watch for oprhaned recordings!
        source_dir = None
        for myth_dir in config.mythtv_recording_directories[:]:
            source_path = myth_dir + ep_file_name
            if os.path.isfile(source_path):
                source_dir = myth_dir
                break

        if source_dir is None:
            print ("[ERROR] Cannot create symlink for "
                   + episode_name + ", no valid source directory.  Skipping.")
            continue

        if os.path.exists(link_path) or os.path.islink(link_path):
            print "[WARN] Symlink " + link_path + " already exists.  Skipping."
            continue

        if not os.path.exists(config.plex_tv_directory + title):
            print "[INFO] Show folder does not exist, creating."
            os.makedirs(config.plex_tv_directory + title)
        
        # avconv (next-gen ffmpeg) support -- convert files to MP4
        # so smaller devices (eg Roku, AppleTV, FireTV, Chromecast)
        # support native playback.
        if config.avconv_enabled is True:
            mthcommflag_exists = False
            # MythTV's mythcommflag can be used to remove commercials,
            # shrinking recordings and improving viewing.
            if config.avconv_mythcommflag_enabled is True:
                run_mythcommflag()

            # Re-encode with avconv
            run_avconv()
            
        elif config.avconv_remux_enabled:
            run_avconv_remux()

        else:
            print "Linking " + source_path + " ==> " + output_path
                os.symlink(source_path, output_path)

        print "[INFO] Linking " + source_path + " ==> " + link_path
        os.symlink(source_path, link_path)
    close_library(lib)

def close_library(lib):
    # Save the list of file IDs
    outstring = ""
    for item in lib:
        outstring += item + ","

    library = open('.library', 'w')
    library.write(outstring)
    library.close()

def run_mythcommflag():
    mythcommflag_command = 'mythcommflag -f '
    mythcommflag_command += source_path
    mythcommflag_command += ' --outputfile ~/.mythExCommflag.edl'
    # mythcommflag_command += ' --method 7'
    if config.avconv_mythcommflag_verbose:
        mythcommflag_command += ' -v'
    os.system(mythcommflag_command)


def run_avconv():
    avconv_command = "nice -n " + str(avconv_nicevalue)
    avconv_command += " avconv -i " + source_path
    avconv_command += " -itsoffset " + str(avconv_audio_offset)
    avconv_command += " -i " + source_path
    avconv_command += " -map 0:0 -map 1:1"
    avconv_command += " -acodec " + avconv_audiocodec
    avconv_command += " -ar " + avconv_audiofrequency
    avconv_command += " -ac " + str(avconv_audiochannels)
    avconv_command += " -ab " + avconv_audiobitrate
    avconv_command += " -async 1"
    avconv_command += " -copyts"
    avconv_command += " -s " + avconv_size
    avconv_command += " -f " + avconv_filetype
    avconv_command += " -vcodec " + avconv_videocodec
    avconv_command += " -b:v " + avconv_videobitrate
    avconv_command += " -threads " + str(avconv_threads)
    avconv_command += " -level 31"
    avconv_command += " -vf \"yadif\" "
    avconv_command += "\"" + output_path + "\""
    print "Running avconv with command line " + avconv_command
    os.system(avconv_command)

def run_avconv_remux():
    avconv_command = "avconv -i " + source_path + " -c copy \"" + output_path + "\""
    print "Running avconv remux with command " + avconv_command
    os.system(avconv_command)

# globals
avconv_deinterlace = False
avconv_size = "hd1080"
avconv_audiocodec = "copy"
avconv_audiobitrate = "192k"
avconv_audiofrequency = "48000"
avconv_audiochannels = 6
avconv_filetype = "mp4"
avconv_threads = 2
avconv_nicevalue = 0
avconv_videocodec = "libx264"
avconv_videobitrate = config.avconv_bitrate
if config.avconv_audio_offset_enabled:
    avconv_audio_offset = config.avconv_audio_offset_time
else:
    avconv_audio_offset = 0

if config.moviedb_enabled:
    set_key(config.moviedb_api_key)
    if config.moviedb_testmode:
        moviedb = 'http://private-dc013f25e-themoviedb.apiary-mock.com/3/search/movie'
    else:
        moviedb = 'http://api.themoviedb.org/3/search/movie'

if platform.system() == "Windows":
    separator = "\\"
else:
    separator = "/"

if __name__ == "__main__" : main()
