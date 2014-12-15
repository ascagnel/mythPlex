#!/usr/bin/env python3.4

import os
import xml.etree.ElementTree as ET
import urllib.request
import platform
import re
import calendar
from datetime import datetime, timedelta
import time
import subprocess
import configparser


def main():
    start_time = time.clock()
    print ("mythPlex, Copyright (C) 2014 Andrew Scagnelli")
    print ("mythPlex comes with ABSOLUTELY NO WARRANTY.")
    print ("This is free software, and you are welcome to redistribute it")
    print ("under certain conditions.")
    print ("See LICENSE file for details.\n")

    load_config()

    print ("[INFO] Starting mythEx")
    lib = open_library()
    url = "http://" + config.host_url + ":" + config.host_port
    print ("[INFO] Looking up from MythTV: " + url + '/Dvr/GetRecordedList')

    tree = ET.parse(urllib.request.urlopen(url + '/Dvr/GetRecordedList'))
    root = tree.getroot()

    for program in root.iter('Program'):

        title = program.find('Title').text
        ep_season = program.find('Season').text.zfill(2)
        ep_num = program.find('Episode').text.zfill(2)
        ep_file_extension = program.find('FileName').text[-4:]
        ep_file_name = program.find('FileName').text
        ep_id = program.find('ProgramId').text
        ep_temp = program.find('StartTime').text
        ep_start_time = utc_to_local(datetime.strptime(
                                     ep_temp,
                                     '%Y-%m-%dT%H:%M:%SZ'))
        # parse start time for file-system safe name
        ep_start_time = datetime.strftime(ep_start_time, '%Y-%m-%d %H%M')

        # parse show name for file-system safe name
        title = re.sub('[\[\]/\\;><&*%=+@!#^()|?]', '_', title)

        episode_name = title + " - S" + ep_season + "E" + ep_num
        print ("[INFO] Processing " + episode_name + " ...")

        # Skip previously finished files
        if ep_id in lib:
            print (("[WARN] Matched program ID" + ep_id +
                   ", skipping " + episode_name))
            continue
        elif ep_id is not None:
            print ("[INFO] Adding " + episode_name +
                   " to library [" + ep_id + "]")
            lib.append(ep_id)

        # Handle specials, movies, etc.
        if ep_season == '00' and ep_num == '00':
            if (ep_start_time is not None):
                print ("[INFO] (fallback 2) using start time")
                episode_name = title + " - " + ep_start_time
                print ("[INFO] Changed to " + episode_name)
                link_path = (config.plex_specials_directory +
                             title + separator + episode_name +
                             ep_file_extension)
            else:
                print ("[WARN] no start time available")

        else:
            print ("[INFO] have season and episode.")
            link_path = (config.plex_tv_directory +
                         title + separator + episode_name + ep_file_extension)

        # Symlink path
        print ("[INFO] symlink processing..")

        # Watch for oprhaned recordings!
        source_dir = None
        for myth_dir in config.mythtv_recording_directories[:]:
            source_path = myth_dir + ep_file_name
            if os.path.isfile(source_path):
                source_dir = myth_dir
                break

        if source_dir is None:
            print (("[ERROR] Cannot create symlink for "
                   + episode_name + ", no valid source directory.  Skipping."))
            continue

        if os.path.exists(link_path) or os.path.islink(link_path):
            print ("[WARN] Symlink " + link_path + " already exists.  Skipping.")
            continue

        if (config.plex_tv_directory in link_path):
            if (not os.path.exists(config.plex_tv_directory + title)):
                print ("[INFO] Show folder does not exist, creating.")
                os.makedirs(config.plex_tv_directory + title)

        if (config.plex_movie_directory in link_path):
            if (not os.path.exists(config.plex_movie_directory + title)):
                print ("[INFO] Show folder does not exist, creating.")
                os.makedirs(config.plex_movie_directory + title)

        if (config.plex_specials_directory in link_path):
            if (not os.path.exists(config.plex_specials_directory + title)):
                print ("[INFO] Show folder does not exist, creating.")
                os.makedirs(config.plex_specials_directory + title)

        # avconv (next-gen ffmpeg) support -- convert files to MP4
        # so smaller devices (eg Roku, AppleTV, FireTV, Chromecast)
        # support native playback.
        if config.transcode_enabled is True:
            # Re-encode with avconv
            run_avconv(source_path, link_path)

        elif config.remux_enabled:
            run_avconv_remux(source_path, link_path)

        else:
            print ("[INFO] Linking " + source_path + " ==> " + link_path)
            os.symlink(source_path, link_path)
    close_library(lib)
    print ("[INFO] Finished processing in " + str(time.clock() - start_time) + "s")


def close_library(lib):
    # Save the list of file IDs
    outstring = ",".join(lib)

    library = open('.library', 'w')
    library.write(outstring)
    library.close()


def mythcommflag_run(source_path):
    mythcommflag_command = 'mythcommflag -f '
    mythcommflag_command += source_path
    mythcommflag_command += ' --outputmethod essentials'
    mythcommflag_command += ' --outputfile .mythExCommflag.edl'
    #mythcommflag_command += ' --method d2_scene'
    mythcommflag_command += ' --skipdb --quiet'
    if config.mythcommflag_verbose:
        mythcommflag_command += ' -v'
    print ("[INFO] Running mythcommflag: {" + mythcommflag_command + "}")
    os.system(mythcommflag_command)
    cutlist = open('.mythExCommflag.edl', 'r')
    cutpoints = []
    pointtypes = []
    starts_with_commercial = False
    for cutpoint in cutlist:
        if 'framenum' in cutpoint:
            line = cutpoint.split()
            print (('[INFO] ' + line[0] + ' - {' + line[1] + '} -- ' +
                   line[2] + ' - {' + line[3] + '}'))
            if line[1] is '0' and line[3] is '4':
                starts_with_commercial = True
            cutpoints.append(line[1])
            pointtypes.append(line[3])
    cutlist.close()
    os.system('rm .mythExCommflag.edl')
    framerate = float(subprocess.call(['echo','avconv -i ' + source_path +
                      ' 2>&1 | sed -n \"s/.*, \\(.*\\) fp.*/\\1/p\"']))
    print ('[INFO] Video frame rate is ' + str(framerate))
    print ('[INFO] Starts with commercial? ' + str(starts_with_commercial))
    print ('[INFO] Found ' + str(len(cutpoints)) + ' cut points.')
    segments = 0
    for cutpoint in cutpoints:
        index = cutpoints.index(cutpoint)
        startpoint = float(cutpoints[index])/framerate
        duration = 0
        if index is 0 and not starts_with_commercial:
            print ('[INFO] Starting with non-commercial')
            duration = float(cutpoints[0])/framerate
            startpoint = 0
        elif pointtypes[index] is '4':
            print ('[INFO] Skipping cut point type 4')
            continue
        elif (index+1) < len(cutpoints):
            duration = (float(cutpoints[index+1]) -
                        float(cutpoints[index]))/framerate
        print ('[INFO] Start point: [' + str(startpoint) + ']')
        print (('[INFO] duration of segment ' +
               str(segments) + ': ' + str(duration)))
        if duration is 0:
            avconv_command = ('avconv -i ' + source_path + ' -ss ' +
                              str(startpoint) + ' -c copy output' +
                              str(segments) + '.mpg')
        else:
            avconv_command = ('avconv -i ' + source_path + ' -ss ' +
                              str(startpoint) + ' -t ' + str(duration) +
                              ' -c copy output' + str(segments) + '.mpg')
        print (('[INFO] running avconv with command line {' +
               avconv_command + '}'))
        os.system(avconv_command)
        segments = segments + 1
    current_segment = 0
    concat_command = 'cat'
    while current_segment < segments:
        concat_command += ' output' + str(current_segment) + '.mpg'
        current_segment = current_segment + 1
    concat_command += ' >> tempfile.mpg'
    print ('[INFO] Merging files with command [' + concat_command + ']')
    os.system(concat_command)
    return 'tempfile.mpg'


def mythcommflag_cleanup():
    print ('[INFO] Cleaning up temporary files.')
    os.system('rm output*.mpg')
    os.system('rm tempfile.mpg')


def run_avconv(source_path, output_path):
    if (config.mythcommflag_enabled is True):
        source_path = mythcommflag_run(source_path)
    avconv_command = "nice -n " + str(config.transcode_nicevalue)
    avconv_command += " avconv -i " + source_path
    avconv_command += " -c:v " + config.transcode_videocodec
    avconv_command += " -preset " + config.transcode_preset
    avconv_command += " -tune " + config.transcode_tune
    if (config.transcode_deinterlace is True):
        avconv_command += " -vf yadif"
    avconv_command += " -profile:v " + config.transcode_profile
    avconv_command += " -level " + config.transcode_level
    avconv_command += " -c:a " + config.transcode_audiocodec
    avconv_command += " -threads " + str(config.transcode_threads)
    output_path = output_path[:-3]
    output_path += "mp4"
    avconv_command += " \"" + output_path + "\""
    print ("[INFO] Running avconv with command line " + avconv_command)
    os.system(avconv_command)
    if (config.mythcommflag_enabled is True):
        mythcommflag_cleanup()


def run_avconv_remux(source_path, output_path):
    if (config.mythcommflag_enabled is True):
        source_path = mythcommflag_run(source_path)
    avconv_command = ("avconv -i " + source_path + " -c copy \"" +
                      output_path + "\"")
    print ("Running avconv remux with command " + avconv_command)
    os.system(avconv_command)
    if (config.mythcommflag_enabled is True):
        mythcommflag_cleanup()


def load_config():
    if (os.path.isfile("config.ini") is False):
        print('[INFO] No config file found, writing defaults.')
        defaultconfig = configparser.ConfigParser()
        defaultconfig['Server'] = {'host_url': 'localhost',
                                   'host_port': '6544'}
        defaultconfig['Plex'] = {'tv': '~/TV Shows/',
                                 'movie': '~/Movies/',
                                 'specials': '~/TV Shows/Specials/'}
        defaultconfig['Recording'] = {'directories': '/var/media/disk1/Recordings/'}
        defaultconfig['Encoder'] = {'transcode_enabled': 'False',
                                    'remux_enabled': 'False',
                                    'mythcommflag_enabled': 'False',
                                    'mythcommflag_verbose': 'False',
                                    'deinterlace': 'True',
                                    'audiocodec': 'copy',
                                    'threads': '2',
                                    'nicevalue': '0',
                                    'videocodec': 'libx264',
                                    'preset': 'veryfast',
                                    'tune': 'film',
                                    'profile': 'high',
                                    'level': '41'}
        with open('config.ini', 'w') as configfile:
            defaultconfig.write(configfile)
    else:
        print('[INFO] Config file found, reading...')

    configfile = configparser.ConfigParser()
    configfile.read('config.ini')
    
    global config
    config.host_url = configfile['Server']['host_url']
    config.host_port = configfile['Server']['host_port']

    config.plex_tv_directory = configfile['Plex']['tv']
    config.plex_movie_directory = configfile['Plex']['movie']
    config.plex_specials_directory = configfile['Plex']['specials']

    config.mythtv_recording_directories = configfile['Recording']['directories'].split(',')

    config.transcode_enabled = bool(configfile['Encoder']['transcode_enabled'])
    config.remux_enabled = bool(configfile['Encoder']['remux_enabled'])
    config.mythcommflag_enabled = bool(configfile['Encoder']['mythcommflag_enabled'])
    config.mythcommflag_verbose = bool(configfile['Encoder']['mythcommflag_verbose'])
    config.transcode_deinterlace = bool(configfile['Encoder']['deinterlace']) 
    config.transcode_audiocodec = configfile['Encoder']['audiocodec']
    config.transcode_threads = int(configfile['Encoder']['threads'])
    config.transcode_nicevalue = int(configfile['Encoder']['nicevalue'])
    config.transcode_videocodec = configfile['Encoder']['videocodec']
    config.transcode_preset = configfile['Encoder']['preset']
    config.transcode_tune = configfile['Encoder']['tune']
    config.transcode_profile = configfile['Encoder']['profile']
    config.transcode_level = int(configfile['Encoder']['level'])


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
        lib = []
    return lib


class Config(object):
    def __init__(self):
        self.host_url=None
        self.host_port=None
        self.plex_tv_directory=None
        self.plex_movie_directory=None
        self.plex_specials_directory=None
        self.mythtv_recording_directories=None
        self.transcode_enabled=None
        self.remux_enabled=None
        self.mythcommflag_enabled=None
        self.mythcommflag_verbose=None
        self.transcode_deinterlace=None
        self.transcode_audiocodec=None
        self.transcode_threads=None
        self.transcode_nicevalue=None
        self.transcode_videocodec=None
        self.transcode_preset=None
        self.transcode_tune=None
        self.transcode_profile=None
        self.transcode_level=None


config = Config()

if platform.system() == "Windows":
    separator = "\\"
else:
    separator = "/"

if __name__ == "__main__":
    main()
