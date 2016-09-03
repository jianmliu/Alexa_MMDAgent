#!/usr/bin python
# -*- coding: utf-8 -*-

# mmdagent_snowboy.py --- Wakeup plugin for MMDAgent using snowboy
# Copyright (c) 2016, Jianming Liu
# All rights reserved.

import collections
import pyaudio
import snowboydetect
import time
import wave
import os
import signal
import pygame
import sys
import glib

coding = 'utf8'
TOP_DIR = os.path.dirname(os.path.abspath(__file__))

RESOURCE_FILE = os.path.join(TOP_DIR, "resources/common.res")
DETECT_DING = os.path.join(TOP_DIR, "resources/ding.wav")
DETECT_DONG = os.path.join(TOP_DIR, "resources/dong.wav")

class RingBuffer(object):
    """Ring buffer to hold audio from PortAudio"""
    def __init__(self, size = 4096):
        self._buf = collections.deque(maxlen=size)

    def extend(self, data):
        """Adds data to the end of buffer"""
        self._buf.extend(data)

    def get(self):
        """Retrieves data from the beginning of buffer and clears it"""
        tmp = ''.join(self._buf)
        self._buf.clear()
        return tmp

interrupted = False
def interrupt_callback():
    global interrupted
    return interrupted

def play_audio_file(fname=DETECT_DING):
    """Simple callback function to play a wave file. By default it plays
    a Ding sound.

    :param str fname: wave file name
    :return: None
    """
    pygame.mixer.init()
    pygame.mixer.music.load(fname)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy() == True:
        continue

class HotwordDetector(object):
    """
    Snowboy decoder to detect whether a keyword specified by `decoder_model`
    exists in a microphone input stream.

    :param decoder_model: decoder model file path, a string or a list of strings
    :param resource: resource file path.
    :param sensitivity: decoder sensitivity, a float of a list of floats.
                              The bigger the value, the more senstive the
                              decoder. If an empty list is provided, then the
                              default sensitivity in the model will be used.
    :param audio_gain: multiply input volume by this factor.
    """
    def __init__(self, decoder_model,
                 resource=RESOURCE_FILE,
                 sensitivity=[],
                 audio_gain=1):
        def audio_callback(in_data, frame_count, time_info, status):
            self.ring_buffer.extend(in_data)
            play_data = chr(0) * len(in_data)
            return play_data, pyaudio.paContinue

        self.decoder_model = decoder_model
        tm = type(decoder_model)
        ts = type(sensitivity)
        if tm is not list:
            decoder_model = [decoder_model]
        if ts is not list:
            sensitivity = [sensitivity]
        model_str = ",".join(decoder_model)

        self.detector = snowboydetect.SnowboyDetect(
            resource_filename=resource, model_str=str(model_str))
        self.detector.SetAudioGain(audio_gain)
        self.num_hotwords = self.detector.NumHotwords()

        if len(decoder_model) > 1 and len(sensitivity) == 1:
            sensitivity = sensitivity*self.num_hotwords
        if len(sensitivity) != 0:
            assert self.num_hotwords == len(sensitivity), \
                "number of hotwords in decoder_model (%d) and sensitivity " \
                "(%d) does not match" % (self.num_hotwords, len(sensitivity))
        sensitivity_str = ",".join([str(t) for t in sensitivity])
        if len(sensitivity) != 0:
            self.detector.SetSensitivity(sensitivity_str);

        self.ring_buffer = RingBuffer(
            self.detector.NumChannels() * self.detector.SampleRate() * 5)
        self.audio = pyaudio.PyAudio()

        self.stream_in = self.audio.open(
                                        input=True,
                                        output=True,
                                        format=self.audio.get_format_from_width(self.detector.BitsPerSample() / 8),
                                        channels=self.detector.NumChannels(),
                                        rate=self.detector.SampleRate(),
                                        frames_per_buffer=2048,
                                        #input_device_index=1,
                                        #output_device_index=0,
                                        stream_callback=audio_callback)

    def emit_message(self, message):
        
        print(('SNOWBOY_EVENT_%s|%s' % (message, self.decoder_model)).encode(coding))
        sys.stdout.flush()

    def start(self, detected_callback=play_audio_file,
              interrupt_check=lambda: False,
              sleep_time=0.03):

        """
        Start the voice detector. For every `sleep_time` second it checks the
        audio buffer for triggering keywords. If detected, then call
        corresponding function in `detected_callback`, which can be a single
        function (single model) or a list of callback functions (multiple
        models). Every loop it also calls `interrupt_check` -- if it returns
        True, then breaks from the loop and return.

        :param detected_callback: a function or list of functions. The number of
                                  items must match the number of models in
                                  `decoder_model`.
        :param interrupt_check: a function that returns True if the main loop
                                needs to stop.
        :param float sleep_time: how much time in second every loop waits.
        :return: None
        """
        tc = type(detected_callback)
        if tc is not list:
            detected_callback = [detected_callback]
        if len(detected_callback) == 1 and self.num_hotwords > 1:
            detected_callback *= self.num_hotwords

        assert self.num_hotwords == len(detected_callback), \
            "Error: hotwords in your models (%d) do not match the number of " \
            "callbacks (%d)" % (self.num_hotwords, len(detected_callback))

        # self.check_kill_process("main.py")
        while True:
            #this keeps running
            data = self.ring_buffer.get()

            if len(data) == 0:
                time.sleep(sleep_time)
                continue

            ans = self.detector.RunDetection(data)
            if ans == -1:
                logger.warning("Error initializing streams or reading audio data")
            elif ans > 0:
                self.emit_message("DETECT")
                self.terminate()
                break

    def check_kill_process(self, pstring):
        for line in os.popen("ps ax | grep " + pstring + " | grep -v grep"):
            fields = line.split()
            pid = fields[0]
            os.kill(int(pid), signal.SIGKILL)

    def terminate(self):
        """
        Terminate audio stream. Users cannot call start() again to detect.
        :return: None
        """
        self.stream_in.stop_stream()
        self.stream_in.close()
        self.audio.terminate()

class MainLoop(glib.MainLoop):

    def __init__(self):
        super(MainLoop, self).__init__()
        self.__clear()

    def __clear(self):
        self.__snowboy = None

    def __process_message(self, args):
        #print(('SNOWBOY_DEBUG|%s' % (args[0])).encode(coding))
        #sys.stdout.flush()
        if len(args) >= 1 and args[0] == 'SNOWBOY_START':
            self.__clear()
            #print args[1]
            if args[1]:
                self.__snowboy = HotwordDetector(args[1], sensitivity=0.5)
            else:
                self.__snowboy = HotwordDetector("snowboy.umdl", sensitivity=0.5)
            self.__snowboy.emit_message("START")
            self.__snowboy.start(detected_callback=play_audio_file,
               interrupt_check=interrupt_callback,
               sleep_time=0.03)
        elif len(args) >= 1 and args[0] == 'SNOWBOY_STOP':
            #print "STOP signal"
            #to be fixed, not working at the moment
            if self.__snowboy:
                interrupted = True
                self.__snowboy.emit_message("STOP")
                self.__snowboy.terminate()
                self.__clear()
                exit()

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
