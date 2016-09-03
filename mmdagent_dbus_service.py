#! /usr/bin/env python

# mmdagent_dbus_service.py --- MMDAgent DBus service
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

# This is a sample program of MMDAgent SubProcess plugin and provides DBus
# service which allows external programs to control MMDAgent.

# Usage:

# Save this file in the same directory as your .mdf file, and put
# SUBPROC_START command in your .fst file like below:
#
# 1    2    <eps>       SUBPROC_START|service|python|mmdagent_dbus_service.py

# ChangeLog:

# 2011-12-10  S. Irie
#         * Version 0.4.0
#         * Don't split arguments by "," separators
#         * Remove trailing newline characters from strings of signals
#         * Initial release
#
# 2011-12-05  S. Irie
#         * Version 0.2.0
#         * Ignore errors while convert character encoding
#         * Remove newline characters from message strings in methods
#
# 2011-11-30  S. Irie
#         * Version 0.1.0
#         * Handle gobject.IO_HUP in main loop
#
# 2011-11-29  S. Irie
#         * Version 0.0.1
#         * Add command line option '-c'
#         * Fix error when empty line is read from stdin
#
# 2011-11-27  S. Irie
#         * Version 0.0.0
#         * Test

import dbus
import dbus.service
import dbus.mainloop.glib
import gobject
import sys
import re


coding = 'utf8'

if __name__ == '__main__':

    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option("-c", "--coding", dest="coding",
                      help="specify character encoding for stdin/stdout")
    options, args = parser.parse_args()
    if options.coding:
        coding = options.coding


class Object(dbus.service.Object):

    def __init__(self, bus):
        self.__name = dbus.service.BusName("org.mmdagent.MMDAgent", bus)
        super(Object, self).__init__(bus, "/org/mmdagent/MMDAgent")
        self.__re = re.compile('[\n\r]')

    __interface = "org.mmdagent.MMDAgent"
    
    @dbus.service.method(__interface, in_signature='sas', out_signature='')
    def EmitMessage(self, event, args):
        args.insert(0, event)
        print('%s' % self.__re.sub("", '|'.join(args).encode(coding, 'ignore')))
        sys.stdout.flush()

    @dbus.service.signal(__interface, signature='sas')
    def Message(self, event, args):
        pass

class MainLoop(gobject.MainLoop):

    def __init__(self, service):
        super(MainLoop, self).__init__()
        self.__service = service

    def __stdin_cb(self, fd, condition):
        if condition & gobject.IO_IN:
            line = sys.stdin.readline().decode(coding, 'ignore').rstrip('\n\r')
            if len(line) > 0:
                args = line.split('|')
                self.__service.Message(args[0], args[1:])				
        if condition & gobject.IO_HUP:
            exit()
        return True

    def run(self):
        gobject.io_add_watch(0, gobject.IO_IN | gobject.IO_HUP, self.__stdin_cb)
        super(MainLoop, self).run()


if __name__ == '__main__':

    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

    service = Object(dbus.SessionBus())
    mainloop = MainLoop(service)

    mainloop.run()
