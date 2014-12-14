mythPlex
========

Convert MythTV recordings to XBMC/Plex compatible names using the built-in MythTV APIs

This uses the built-in [MythTV Services API](http://www.mythtv.org/wiki/Services_API) to create symlinks from the Myth recordings to XBMC/Plex-friendly formats.

Tested on MythBuntu 14.04, Python 2.7.6, and PMS 0.9.9.12.

Note that this script requires local access to recordings.  The drives holding the recordings must either be attached to the system or available via a network share.

Instructions
------------

1. Take note of all configured MythTV recording directories.  Fill in the "mythtv\_recording\_directories" variable with them; if there are multiple directories, please use a comma-separated list.
2. Change the IP and port number (host\_url and host\_port) to match your setup.  The default values will work if the script is run locally.
3. Set up the directory you would like the linked files to reside in, and change "plex\_library\_directory" to match.

Remuxing
--------

Remuxing is off by default.

If you would prefer to outright copy the file, without changing its makeup, you may do so by changing the "remux\_enabled" option to "True".  The original container will be maintained.

Remuxing can be combined with commercial skipping.

Commercial Skipping
------------------- 

Commercial skipping is off by default.

Before enabling commercial skipping, make sure you have the automatic commercial skipping turned off for new recordings from MythFrontend, as this script will re-run the commercial flagger.

To enable commercial skipping, set "mythcommflag\_enabled" to 'True' in config.py.  If you are seeing odd commercial jumps, setting "mythcommflag\_verbose" to 'True' will log the times and frame numbers of skip points.

Transcoding Recordings
----------------------

Transcoding is off by default.

mythPlex can re-encode MythTV recordings to save space and play them back across more devices without requiring Plex to transcode on each playback.

To enable transcoding, set "transcode\_enabled" to 'True' in config.py.

If your recordings tend to be deinterlaced, setting "transcode\_deinterlace" will resolve this using avconv's built-in "yadif" filter.

To set a different audio or video codec, you can do so from the "transcode\_audicodec" and "transcode\_videocodec" variables.  By default, the original audio stream will be copied, and the video will be transcoded into H264.

Quality Presets
===============

If you would like higher or lower quality, you can change the "transcode\_preset".  Valid values are as follows (from the [libav wiki](https://wiki.libav.org/Encoding/h264#Preset_and_Tune)):

* ultrafast
* superfast
* veryfast (default value)
* faster
* fast
* medium
* slow
* slower
* veryslow
* placebo

Each setting is approximately twice as slow as the one before it.

Tunings
=======

You can tune the transcoder based on the type of media you are sending in.  Valid values are as follows (from the [libav wiki](https://wiki.libav.org/Encoding/h264#Preset_and_Tune)):

* film (default)
* animation
* grain
* stillimage
* psnr
* ssim
* fastdecode
* zerolatency

Uninstallation
--------------

Simply delete the mythPlex directory from your system.
