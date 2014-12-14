# IP or hostname of the mythTV server
host_url = "localhost"

# Port number used by the mythTV server
host_port = "6544"

# Path to the location of links
plex_tv_directory = "~/TV Shows/"
plex_movie_directory = "~/Movies/"
plex_specials_directory = "~/TV Shows/Specials/"

# A list of the mythTV recording directories.
mythtv_recording_directories = ["/var/media/disk1/Recordings/"]

moviedb_enabled = False
moviedb_api_key = ""

avconv_enabled = False
avconv_remux_enabled = False
avconv_mythcommflag_enabled = False
avconv_mythcommflag_verbose = False
avconv_transcode_deinterlace = True
avconv_transcode_audiocodec = "copy"
avconv_transcode_threads = 2
avconv_transcode_nicevalue = 0
avconv_transcode_videocodec = "libx264"
avconv_transcode_preset = "veryfast"
avconv_transcode_tune = "film"
