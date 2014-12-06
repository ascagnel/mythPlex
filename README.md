mythPlex
========

Convert MythTV recordings to XBMC/Plex compatible names using the built-in MythTV APIs

This uses the built-in [MythTV Services API](http://www.mythtv.org/wiki/Services_API) to create symlinks from the Myth recordings to XBMC/Plex-friendly formats.

Tested on MythBuntu 14.04, Python 2.7.6, and PMS 0.9.9.12.

Instructions
------------

1. Take note of all configured MythTV recording directories.  Fill in the "mythtv\_recording\_directories" variable with them.  They must be readable by the user that will be running this script.  Note that the files must be readable from a local path -- mounting a network share should be enough to do it. You may need to add or remove items from the list.
2. Change the IP and port number (host\_url and host\_port) to match your setup.
3. Set up the directory you would like the linked files to reside in, and change "plex\_library\_directory" to match.

Remuxing
--------

If you would prefer to outright copy the file, without changing its makeup, you may do so by changing the "avconv\_remux\_enabled" option to "True".

Commercial Skipping (new as of December 2014)
---------------------------------------------

mythPlex can now take advantage of Myth TV's built-in commercial skipping!  
To use it, make sure you have the automatic commercial skipping turned off for new recordings from MythFrontend.
After, simply make sure you have both the "avconv\_remux\_enabled" and "avonv\_mythcommflag\_enabled" flags turned on.  
If you start seeing issues with incorrect skips, also turn on "avconv\_mythcommflag\_verbose" to monitor the frame numbers.

Planned Changes
---------------

* Re-encoding to save space.

Uninstallation
--------------

Simply delete the mythPlex directory from your system.
