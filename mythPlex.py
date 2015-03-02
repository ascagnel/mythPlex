#!/usr/bin/env python3.4

import os
import sys
import logging
import xml.etree.ElementTree as ET
import urllib.request
import platform
import re
import calendar
from datetime import datetime, timedelta
import time
import subprocess
import configparser
from errno import EACCES


FORMAT = '%(asctime)-s %(levelname)-s %(message)s'
DATE_FORMAT = '%m-%d-%Y %H:%M:%S'
logging.basicConfig(level=logging.DEBUG,
                    format=FORMAT,
                    datefmt=DATE_FORMAT,
                    #filename = 'output.log')
                    stream=sys.stdout)
logger = logging.getLogger(__name__)


def main():
    start_time = time.time()
    print("mythPlex, Copyright (C) 2014 Andrew Scagnelli")
    print("mythPlex comes with ABSOLUTELY NO WARRANTY.")
    print("This is free software, and you are welcome to redistribute it")
    print("under certain conditions.")
    print("See LICENSE file for details.")

    load_config()

    logger.info("Starting mythEx")
    lib = open_library()
    url = "http://" + config.host_url + ":" + config.host_port
    logger.info("Looking up from MythTV: %s/Dvr/GetRecordedList", url)

    tree = ET.parse(urllib.request.urlopen(url + '/Dvr/GetRecordedList'))
    root = tree.getroot()

    for program in root.iter('Program'):

        start_episode_time = time.time()
        title = program.find('Title').text
        ep_title = program.find('SubTitle').text
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

        if (ep_title is not None):
            ep_title = re.sub('[\[\]/\\;><&*%=+@!#^()|?]', '_', ep_title)
            episode_name = episode_name + " - " + ep_title

        # Skip previously finished files
        if ep_id in lib:
            logger.debug("Matched ID %s, (filename %s)", ep_id, ep_file_name)
            logger.info("Skipping finished episode %s", episode_name)
            continue

        # Handle specials, movies, etc.
        if ep_season == '00' and ep_num == '00':
            if (ep_start_time is not None):
                logger.info("(fallback 2) using start time")
                episode_name = title + " - " + ep_start_time
                logger.info("Changed to %s", episode_name)
                link_path = (config.plex_specials_directory +
                             title + separator + episode_name +
                             ep_file_extension)
            else:
                logger.warning("No start time available")

        else:
            logger.info("Have season and episode.")
            link_path = (config.plex_tv_directory +
                         title + separator + episode_name + ep_file_extension)

        # Watch for oprhaned recordings!
        source_dir = None
        for myth_dir in config.dirs[:]:
            source_path = myth_dir + ep_file_name
            if os.path.isfile(source_path):
                source_dir = myth_dir
                break

        if source_dir is None:
            logger.error("Cannot create symlink for %s, no valid source dir.",
                         episode_name)
            logger.info("Episode processing took %ss",
                        format(time.time() - start_episode_time, '.5f'))
            continue

        if os.path.exists(link_path) or os.path.islink(link_path):
            logger.warning("Symlink %s already exists, skipping.", link_path)
            logger.info("Episode processing took %ss",
                        format(time.time() - start_episode_time, '.5f'))
            continue

        if config.permission:
            try:
                open(source_path)
            except (IOError, OSError) as e:
                if e.errno == EACCES:
                    logger.error("Could not open recording %s", episode_name)
                    logger.error("It will be checked again next run.")
                    continue

        if (config.plex_tv_directory in link_path):
            if (not os.path.exists(config.plex_tv_directory + title)):
                logger.info("Show folder does not exist, creating.")
                os.makedirs(config.plex_tv_directory + title)

        if (config.plex_movie_directory in link_path):
            if (not os.path.exists(config.plex_movie_directory + title)):
                logger.info("Show folder does not exist, creating.")
                os.makedirs(config.plex_movie_directory + title)

        if (config.plex_specials_directory in link_path):
            if (not os.path.exists(config.plex_specials_directory + title)):
                logger.info("Show folder does not exist, creating.")
                os.makedirs(config.plex_specials_directory + title)

        logger.info("Processing %s (path %s)", episode_name, source_path)

        # avconv (next-gen ffmpeg) support -- convert files to MP4
        # so smaller devices (eg Roku, AppleTV, FireTV, Chromecast)
        # support native playback.
        if config.transcode_enabled is True:
            # Re-encode with avconv
            run_avconv(source_path, link_path)

        elif config.remux_enabled:
            run_avconv_remux(source_path, link_path)

        else:
            logger.info("Linking %s to %s", source_path, link_path)
            os.symlink(source_path, link_path)

        # Changing to plex ownership
        os.system("chown plex:plex \"" + link_path + "\"")

        logger.info("Episode processing took %s",
                    format(time.time() - start_episode_time, '.5f'))

        if ep_id is not None:
            logger.info("Adding %s to library [%s]", episode_name, ep_id)
            lib.append(ep_id)
    close_library(lib)
    logger.info("Finished processing in %s",
                format(time.time() - start_time, '.5f'))


def close_library(lib):
    # Save the list of file IDs
    outstring = ",".join(lib)

    library = open('.library', 'w')
    library.write(outstring)
    library.close()


def mythcommflag_run(source_path):

    fps_pattern = re.compile(r'(\d{2}.\d{2}) fps')
    # When calling avconv, it dumps many messages to stderr, not stdout.
    # This may break someday because of that.
    avconv_fps = subprocess.Popen(['avconv', '-i', source_path],
                                  stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE).communicate()[1]
    if (fps_pattern.search(str(avconv_fps))):
        framerate = float(fps_pattern.search(str(avconv_fps)).groups()[0])
    else:
        logger.info("Could not look up FPS, trying PAL format (25FPS).")
        fps_pattern = re.compile(r'(\d{2}) fps')
        framerate = float(fps_pattern.search(str(avconv_fps)).groups()[0])

    logger.debug("Video frame rate: %s", str(framerate))

    mythcommflag_command = 'mythcommflag -f '
    mythcommflag_command += source_path
    mythcommflag_command += ' --outputmethod essentials'
    mythcommflag_command += ' --outputfile .mythExCommflag.edl'
    mythcommflag_command += ' --skipdb --quiet'
    if config.mcf_verbose:
        mythcommflag_command += ' -v'
    logger.info("mythcommflag: [%s]", mythcommflag_command)
    os.system(mythcommflag_command)
    cutlist = open('.mythExCommflag.edl', 'r')
    cutpoints = []
    pointtypes = []
    starts_with_commercial = False
    for cutpoint in cutlist:
        if 'framenum' in cutpoint:
            line = cutpoint.split()
            logger.info("%s - {%s} -- %s - {%s}",
                        line[0], line[1],
                        line[2], line[3])
            if line[1] is '0' and line[3] is '4':
                starts_with_commercial = True
            cutpoints.append(line[1])
            pointtypes.append(line[3])
    cutlist.close()
    os.system('rm .mythExCommflag.edl')
    logger.debug("Starts with commercial? %s",  str(starts_with_commercial))
    logger.debug("Found %s cut points", str(len(cutpoints)))
    segments = 0
    for cutpoint in cutpoints:
        index = cutpoints.index(cutpoint)
        startpoint = float(cutpoints[index])/framerate
        duration = 0
        if index is 0 and not starts_with_commercial:
            logger.debug("Starting with non-commercial")
            duration = float(cutpoints[0])/framerate
            startpoint = 0
        elif pointtypes[index] is '4':
            logger.debug("Skipping cut point type 4")
            continue
        elif (index+1) < len(cutpoints):
            duration = (float(cutpoints[index+1]) -
                        float(cutpoints[index]))/framerate
        logger.debug("Start point [%s]", str(startpoint))
        logger.debug("Duration of segment %s: %s",
                     str(segments),
                     str(duration))
        if duration is 0:
            avconv_command = ('avconv -v 16 -i ' + source_path + ' -ss ' +
                              str(startpoint) + ' -c copy output' +
                              str(segments) + '.mpg')
        else:
            avconv_command = ('avconv -v 16 -i ' + source_path + ' -ss ' +
                              str(startpoint) + ' -t ' + str(duration) +
                              ' -c copy output' + str(segments) + '.mpg')
        logger.info("Running avconv command line {%s}", avconv_command)
        os.system(avconv_command)
        segments = segments + 1
    current_segment = 0
    concat_command = 'cat'
    while current_segment < segments:
        concat_command += ' output' + str(current_segment) + '.mpg'
        current_segment = current_segment + 1
    concat_command += ' >> tempfile.mpg'
    logger.info("Merging files with command %s", concat_command)
    os.system(concat_command)
    return 'tempfile.mpg'


def mythcommflag_cleanup():
    logger.info("Cleaning up temporary files.")
    os.system('rm output*.mpg')
    os.system('rm tempfile.mpg')


def run_avconv(source_path, output_path):
    if (config.mcf_enabled is True):
        source_path = mythcommflag_run(source_path)
    avconv_command = "nice -n " + str(config.transcode_nicevalue)
    avconv_command += " avconv -v 16 -i " + source_path
    avconv_command += " -c:v " + config.transcode_videocodec
    avconv_command += " -preset " + config.transcode_preset
    avconv_command += " -tune " + config.transcode_tune
    if (config.transcode_deinterlace is True):
        avconv_command += " -vf yadif"
    avconv_command += " -profile:v " + config.transcode_profile
    avconv_command += " -level " + str(config.transcode_level)
    avconv_command += " -c:a " + config.transcode_audiocodec
    avconv_command += " -threads " + str(config.transcode_threads)
    output_path = output_path[:-3]
    output_path += "mp4"
    avconv_command += " \"" + output_path + "\""
    logger.info("Running avconv command line %s", avconv_command)
    os.system(avconv_command)
    if (config.mcf_enabled is True):
        mythcommflag_cleanup()


def run_avconv_remux(source_path, output_path):
    if (config.mcf_enabled is True):
        source_path = mythcommflag_run(source_path)
    avconv_command = ("avconv -v 16 -i " + source_path + " -c copy \"" +
                      output_path + "\"")
    logger.info("Running avconv remux command line %s", avconv_command)
    os.system(avconv_command)
    if (config.mcf_enabled is True):
        mythcommflag_cleanup()


def load_config():
    if (os.path.isfile("config.ini") is False):
        logger.info("No config file found, writing defaults.")
        create_default_config()
    else:
        logger.info("Config file found, reading...")

    configfile = configparser.ConfigParser()
    configfile.read('config.ini')

    global config
    config.host_url = configfile['Server']['host_url']
    config.host_port = configfile['Server']['host_port']

    config.plex_tv_directory = configfile['Plex']['tv']
    config.plex_movie_directory = configfile['Plex']['movie']
    config.plex_specials_directory = configfile['Plex']['specials']

    config.dirs = configfile['Recording']['directories'].split(',')
    try:
        config.permission = bool(configfile['Recording']['permission_check'])
    except KeyError:
        config.permission = True
        # This space intentionally left blank

    config.transcode_enabled = configfile['Encoder'].getboolean('transcode_enabled')
    config.remux_enabled = configfile['Encoder'].getboolean('remux_enabled')
    config.mcf_enabled = configfile['Encoder'].getboolean('mythcommflag_enabled')
    config.mcf_verbose = configfile['Encoder'].getboolean('mythcommflag_verbose')
    config.transcode_deinterlace = configfile['Encoder'].getboolean('deinterlace')
    config.transcode_audiocodec = configfile['Encoder']['audiocodec']
    config.transcode_threads = int(configfile['Encoder']['threads'])
    config.transcode_nicevalue = int(configfile['Encoder']['nicevalue'])
    config.transcode_videocodec = configfile['Encoder']['videocodec']
    config.transcode_preset = configfile['Encoder']['preset']
    config.transcode_tune = configfile['Encoder']['tune']
    config.transcode_profile = configfile['Encoder']['profile']
    config.transcode_level = int(configfile['Encoder']['level'])


def create_default_config():
    defaultconfig = configparser.ConfigParser()
    defaultconfig['Server'] = {'host_url': 'localhost',
                               'host_port': '6544'}
    defaultconfig['Plex'] = {'tv': '~/TV Shows/',
                             'movie': '~/Movies/',
                             'specials': '~/TV Shows/Specials/'}
    defaultconfig['Recording'] = {'directories': '/var/lib/mythtv/recordings/',
                                  'permission_check': 'True'}
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
        configfile.close()


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
        self.host_url = None
        self.host_port = None
        self.plex_tv_directory = None
        self.plex_movie_directory = None
        self.plex_specials_directory = None
        self.dirs = None
        self.permission = True
        self.transcode_enabled = None
        self.remux_enabled = None
        self.mcf_enabled = None
        self.mcf_verbose = None
        self.transcode_deinterlace = None
        self.transcode_audiocodec = None
        self.transcode_threads = None
        self.transcode_nicevalue = None
        self.transcode_videocodec = None
        self.transcode_preset = None
        self.transcode_tune = None
        self.transcode_profile = None
        self.transcode_level = None


config = Config()

if platform.system() == "Windows":
    separator = "\\"
else:
    separator = "/"

if __name__ == "__main__":
    main()
