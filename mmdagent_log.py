#! /usr/bin/env python
# -*- coding: utf-8 -*-

# mmdagent_time_signal.py --- 3D character in MMDAgent says time signal
# Copyright (c) 2011, S. Irie
# All rights reserved.

version = "0.4.0"

# This program is free software.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:

# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED
# TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# Commentary:

# This is a sample program of MMDAgent SubProcess plugin which provides new
# commands TIMESIGNAL_START and TIMESIGNAL_STOP to VIManager plugin.
# TIMESIGNAL_START command sets up the model and its voice used for Open_JTalk
# plugin to speak the time signal at the top of the hour. TIMESIGNAL_STOP
# command resets the model and the voice set up by TIMESIGNAL_START.
# Once TIMESIGNAL_START command is processed, 3D character in MMDAgent also
# tells current time interactively when you ask the time like "今、何時?"

# Usage:

# Specifications of additional commands are as follows:
#
# TIMESIGNAL_START|(model alias)|(voice alias)|(interval in min.)|(sound file name)
# TIMESIGNAL_START|(model alias)|(voice alias)|(interval in min.)
# TIMESIGNAL_START|(model alias)|(voice alias)
# TIMESIGNAL_STOP|(model alias)
#
# Where arguments (interval in min.) and (sound file name) in TIMESIGNAL_START
# command are optional. (interval in min.) is a time interval of the signals and
# should be a divisor of 60 or zero. Here, the value of zero means don't say
# time signal periodically. Omitting the interval means use default value 60.
# If (sound file name) is given, the sound file will be played before speaking.
#
# For example, save this file in the same directory as your .mdf file, and put
# SUBPROC_START command in your .fst file like below:
#
# 11 12 <eps>                      SUBPROC_START|tsign|python|mmdagent_time_signal.py
# 12 13 SUBPROC_EVENT_START|tsign  TIMESIGNAL_START|mei|mei_voice_normal|30

# ChangeLog:

# 2011-12-10  S. Irie
#         * Version 0.4.0
#         * Tell current time interactively as answer to question like "今、何時？"
#         * Don't say time signal periodically if time interval is zero
#         * Don't split arguments by "," separators
#         * Remove trailing newline characters from strings of signals
#         * Convert directory separators in sound file name
#         * Check if sound file exists before sending SOUND_START conmmand
#         * Initial release
#
# 2011-12-05  S. Irie
#         * Version 0.2.0
#         * Time interval can be specified in minutes
#         * Play audio file using Audio plugin if filename is given
#
# 2011-12-03  S. Irie
#         * Version 0.0.0
#         * Test

from datetime import datetime
import glib
import sys
import os
from sys import stdout
from os.path import exists
from array import array
from struct import unpack, pack

coding = 'utf8'
LOG_FILE = 'MMDAgent.log'

if __name__ == '__main__':

    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-c", "--coding", dest="coding",
                      help="specify character encoding for stdin/stdout")
    options, args = parser.parse_args()
    if options.coding:
        coding = options.coding

class MainLoop(glib.MainLoop):

    def __init__(self):
        super(MainLoop, self).__init__()
        self.__log = None
		
    def __process_message(self, args):
        self.__log = open(LOG_FILE,'a')
        time = datetime.now()
        self.__log.write(str((time.hour + 11) % 12 + 1)+':'+str(time.minute)+'|')
        for i in range(0,len(args)-1):
            self.__log.write(args[i].encode(coding)+'|')
        self.__log.write(args[len(args)-1].encode(coding))
        self.__log.write('\n')
        self.__log.close()

    def __stdin_cb(self, fd, condition):
        if condition & glib.IO_IN:
            line = sys.stdin.readline().decode(coding, 'ignore').rstrip('\n\r')
            if len(line) > 0:
                args = line.split('|')
                self.__process_message(args)
        if condition & glib.IO_HUP:
            exit()
        return True

    def run(self):
        glib.io_add_watch(0, glib.IO_IN | glib.IO_HUP, self.__stdin_cb)
        super(MainLoop, self).run()


if __name__ == '__main__':

    mainloop = MainLoop()
    mainloop.run()
