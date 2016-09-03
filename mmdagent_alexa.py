#! /usr/bin python
# -*- coding: utf-8 -*-

# mmdagent_alexa.py --- 3D character in MMDAgent for Alexa
# Copyright (c) 2016, Jianming Liu
# All rights reserved.

import collections
import signal
import pygame
import sys
import glib
import logging
import os
import random
import time
import pyaudio
import wave
from creds import *
import requests
import json
import re
from memcache import Client
import vlc
import threading
import cgi
import email
import optparse
import getch
import fileinput
import datetime
from os.path import exists
from array import array
from struct import unpack, pack

import tunein
import webrtcvad

coding = 'utf8'

# record format
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 8000
RECORD_SECONDS = 6
WAVE_OUTPUT_FILENAME = "recording.wav"

THRESHOLD = 4000
CHUNK_SIZE = 1024
MAX_NUM_SLIENT = 20

servers = ["127.0.0.1:11211"]
mc = Client(servers, debug=1)
path = os.path.realpath(__file__).rstrip(os.path.basename(__file__))

# Variables
p = ""
nav_token = ""
streamurl = ""
streamid = ""
position = 0
audioplaying = False
button_pressed = False
start = time.time()
tunein_parser = tunein.TuneIn(5000)
vad = webrtcvad.Vad(2)
currVolume = 100

# constants
VAD_SAMPLERATE = 16000
VAD_FRAME_MS = 30
VAD_PERIOD = (VAD_SAMPLERATE / 1000) * VAD_FRAME_MS
VAD_SILENCE_TIMEOUT = 1000
VAD_THROWAWAY_FRAMES = 10
MAX_RECORDING_LENGTH = 6
MAX_VOLUME = 100
MIN_VOLUME = 30

TOP_DIR = os.path.dirname(os.path.abspath(__file__))
DETECT_DING = os.path.join(TOP_DIR, "resources/ding.wav")
DETECT_DONG = os.path.join(TOP_DIR, "resources/dong.wav")

interrupted = False
def interrupt_callback():
    global interrupted
    return interrupted

def gettoken():
    token = mc.get("access_token")
    refresh = refresh_token
    if token:
        return token
    elif refresh:
        payload = {"client_id": Client_ID, "client_secret": Client_Secret, "refresh_token": refresh,
                   "grant_type": "refresh_token",}
        url = "https://api.amazon.com/auth/o2/token"
        r = requests.post(url, data=payload)
        resp = json.loads(r.text)
        mc.set("access_token", resp['access_token'], 3570)
        return resp['access_token']
    else:
        return False

class Alexa:

    def __init__(self):
        self.__running = True
        self._model = 'snowboy.umdl'
        self._pin = pyaudio.PyAudio() 
        
    def __clear(self):
        self.__running = False

    def is_silent(self, L):
        "Returns `True` if below the 'silent' threshold"
        return max(L) < THRESHOLD

    def normalize(self, L):
        "Average the volume out"
        MAXIMUM = 16384
        times = float(MAXIMUM)/max(abs(i) for i in L)

        LRtn = array('h')
        for i in L:
            LRtn.append(int(i*times))
        return LRtn

    def trim(self, L):
        "Trim the blank spots at the start and end"
        # Trim to the left
        L = self._trim(L)

        # Trim to the right
        L.reverse()
        L = self._trim(L)
        L.reverse()
        return L

    def _trim(self,L):
        snd_started = False
        LRtn = array('h')

        for i in L:
            if not snd_started and abs(i)>THRESHOLD:
                snd_started = True
                LRtn.append(i)

            elif snd_started:
                LRtn.append(i)
        return LRtn

    def add_silence(self, L, seconds):
        "Add silence to the start and end of `L` of length `seconds` (float)"
        LRtn = array('h', [0 for i in xrange(int(seconds*RATE))])
        LRtn.extend(L)
        LRtn.extend([0 for i in xrange(int(seconds*RATE))])
        return LRtn

    def record(self, p):
        """
        Record a word or words from the microphone and 
        return the data as an array of signed shorts.

        Normalizes the audio, trims silence from the 
        start and end, and pads with 0.5 seconds of 
        blank sound to make sure VLC et al can play 
        it without getting chopped off.
        """
        num_silent = 0
        snd_started = False

        LRtn = array('h')

        stream = p.open(format=FORMAT, channels=1, rate=RATE, input=True, output=True, frames_per_buffer=CHUNK_SIZE)
        #while 1:
        for i in range(0, int(RATE/CHUNK_SIZE * MAX_RECORDING_LENGTH)):
            data = stream.read(CHUNK_SIZE)
            L = unpack('<' + ('h'*(len(data)/2)), data) # little endian, signed short
            L = array('h', L)
            LRtn.extend(L)

            #stdout.write('\r' + str(max(L)) + '     ' + str(num_silent) + '   ')
            #stdout.flush()

            silent = self.is_silent(L)
            #print silent, num_silent, L[:10]
            if not silent:
                num_silent = 0

            if silent and snd_started:
                num_silent += 1
            elif not silent and not snd_started:
                snd_started = True
                #stdout.write(str('\r\t\t\trecording     '))
                #stdout.flush()

            if snd_started and num_silent > MAX_NUM_SLIENT:
                self.emit_message("RECORD_END")
                break

        stream.stop_stream()
        stream.close()

        #LRtn = normalize(LRtn)
        LRtn = self.trim(LRtn)
        LRtn = self.add_silence(LRtn, 0.5)
        return LRtn

    def record_to_wave(self, path, p):
        "Records from the microphone and outputs the resulting data to `path`"
        data = self.record(p)
        sample_width = p.get_sample_size(FORMAT)        
        data = pack('<' + ('h'*len(data)), *data)

        wf = wave.open(path, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(sample_width)
        wf.setframerate(RATE)
        wf.writeframes(data)
        wf.close()

    def record_to_flac(self, path, p):
        "Records from the microphone and outputs the resulting data to `path`"
        data = self.record(p)
        sample_width = p.get_sample_size(FORMAT)        
        data = pack('<' + ('h'*len(data)), *data)
        bf = open('data.txt','wb')
        bf.write(data)
        bf.close()
        encoder = flac.Encoder()
        encoder.initialize(RATE, 1, sample_width)
        encoder.encode(data)
        encoder.finish()
        flacBin = encoder.getBinary()
        encoder.destroy()
        ff = open('temp2.flac', 'wb')
        ff.write(flacBin)
        ff.close()

    def wave_to_flac(self, wavefile, flacfile):
        "Convert wave to flac format"
        cmd = 'flac ' + wavefile+' -f -o ' + flacfile
        #os.system(cmd)
        os.popen(cmd)

    def mp3_to_wave(self, mp3file, wavefile):
        "Convert mp3 to wave format"
        cmd = 'lame ' + '--decode' + ' ' + mp3file + ' '+ wavefile
        #os.system(cmd)
        os.popen(cmd)

    def mp3_to_wave(self, mp3file, wavefile):
        "Convert mp3 to wave format"
        cmd = 'lame ' + '--decode' + ' ' + mp3file + ' '+ wavefile
        #os.system(cmd)
        os.popen(cmd)

    def emit_message(self, type, message=None):
        
        if message:
            print(('ALEXA_EVENT_%s|%s' % (type, message)).encode(coding))
        else:
            print(('ALEXA_EVENT_%s' % type).encode(coding))
        sys.stdout.flush()

    def alexa_speech_recognizer(self):
        # https://developer.amazon.com/public/solutions/alexa/alexa-voice-service/rest/speechrecognizer-requests
        url = 'https://access-alexa-na.amazon.com/v1/avs/speechrecognizer/recognize'
        headers = {'Authorization': 'Bearer %s' % gettoken()}
        d = {
            "messageHeader": {
                "deviceContext": [
                    {
                        "name": "playbackState",
                        "namespace": "AudioPlayer",
                        "payload": {
                            "streamId": "",
                            "offsetInMilliseconds": "0",
                            "playerActivity": "IDLE"
                        }
                    }
                ]
            },
            "messageBody": {
                "profile": "alexa-close-talk",
                "locale": "en-us",
                "format": "audio/L16; rate=16000; channels=1"
            }
        }
        with open(path + WAVE_OUTPUT_FILENAME) as inf:
            files = [
                ('file', ('request', json.dumps(d), 'application/json; charset=UTF-8')),
                ('file', ('audio', inf, 'audio/L16; rate=16000; channels=1'))
            ]
            r = requests.post(url, headers=headers, files=files)
        self.process_response(r)


    def alexa_getnextitem(self,nav_token):
        # https://developer.amazon.com/public/solutions/alexa/alexa-voice-service/rest/audioplayer-getnextitem-request
        time.sleep(0.5)
        if audioplaying == False:
            url = 'https://access-alexa-na.amazon.com/v1/avs/audioplayer/getNextItem'
            headers = {'Authorization': 'Bearer %s' % gettoken(), 'content-type': 'application/json; charset=UTF-8'}
            d = {
                "messageHeader": {},
                "messageBody": {
                    "navigationToken": nav_token
                }
            }
            r = requests.post(url, headers=headers, data=json.dumps(d))
            self.process_response(r)


    def alexa_playback_progress_report_request(self,requestType, playerActivity, streamid):
        # https://developer.amazon.com/public/solutions/alexa/alexa-voice-service/rest/audioplayer-events-requests
        # streamId                  Specifies the identifier for the current stream.
        # offsetInMilliseconds      Specifies the current position in the track, in milliseconds.
        # playerActivity            IDLE, PAUSED, or PLAYING
        headers = {'Authorization': 'Bearer %s' % self.gettoken()}
        d = {
            "messageHeader": {},
            "messageBody": {
                "playbackState": {
                    "streamId": streamid,
                    "offsetInMilliseconds": 0,
                    "playerActivity": playerActivity.upper()
                }
            }
        }

        if requestType.upper() == "ERROR":
            # The Playback Error method sends a notification to AVS that the audio player has experienced an issue during playback.
            url = "https://access-alexa-na.amazon.com/v1/avs/audioplayer/playbackError"
        elif requestType.upper() == "FINISHED":
            # The Playback Finished method sends a notification to AVS that the audio player has completed playback.
            url = "https://access-alexa-na.amazon.com/v1/avs/audioplayer/playbackFinished"
        elif requestType.upper() == "IDLE":
            # The Playback Idle method sends a notification to AVS that the audio player has reached the end of the playlist.
            url = "https://access-alexa-na.amazon.com/v1/avs/audioplayer/playbackIdle"
        elif requestType.upper() == "INTERRUPTED":
            # The Playback Interrupted method sends a notification to AVS that the audio player has been interrupted.
            # Note: The audio player may have been interrupted by a previous stop Directive.
            url = "https://access-alexa-na.amazon.com/v1/avs/audioplayer/playbackInterrupted"
        elif requestType.upper() == "PROGRESS_REPORT":
            # The Playback Progress Report method sends a notification to AVS with the current state of the audio player.
            url = "https://access-alexa-na.amazon.com/v1/avs/audioplayer/playbackProgressReport"
        elif requestType.upper() == "STARTED":
            # The Playback Started method sends a notification to AVS that the audio player has started playing.
            url = "https://access-alexa-na.amazon.com/v1/avs/audioplayer/playbackStarted"

        r = requests.post(url, headers=headers, data=json.dumps(d))
        if r.status_code != 204:
            print("{}(alexa_playback_progress_report_request Response){} {}".format(bcolors.WARNING, bcolors.ENDC, r))
        else:
            if debug: print(
                "{}Playback Progress Report was {}Successful!{}".format(bcolors.OKBLUE, bcolors.OKGREEN, bcolors.ENDC))


    def process_response(self,r):
        global nav_token, streamurl, streamid, currVolume, isMute
        nav_token = ""
        streamurl = ""
        streamid = ""
        if r.status_code == 200:
            data = "Content-Type: " + r.headers['content-type'] + '\r\n\r\n' + r.content
            msg = email.message_from_string(data)
            for payload in msg.get_payload():
                if payload.get_content_type() == "application/json":
                    j = json.loads(payload.get_payload())
                    self.emit_message("JSON",json.dumps(j))
                elif payload.get_content_type() == "audio/mpeg":
                    filename = path + "tmpcontent/" + payload.get('Content-ID').strip("<>") + ".mp3"
                    with open(filename, 'wb') as f:
                        f.write(payload.get_payload())
                else:
                    self.emit_message("NEW_CONTENT_TYPE",payload.get_content_type())
            # Now process the response
            if 'directives' in j['messageBody']:
                for directive in j['messageBody']['directives']:
                    if directive['namespace'] == 'SpeechSynthesizer':
                        if directive['name'] == 'speak':
                            self.play_audio(path + "tmpcontent/" + directive['payload']['audioContent'].lstrip("cid:") + ".mp3")
                        for directive in j['messageBody']['directives']:  # if Alexa expects a response
                            if directive[
                                'namespace'] == 'SpeechRecognizer':  # this is included in the same string as above if a response was expected
                                if directive['name'] == 'listen':
                                    self.play_audio(path + 'beep.wav', 0, 100)
                                    timeout = directive['payload']['timeoutIntervalInMillis'] / 116
                                    # listen until the timeout from Alexa
                                    self.silence_listener(timeout)
                                    # now process the response
                                    self.alexa_speech_recognizer()
                    elif directive['namespace'] == 'AudioPlayer':
                        # do audio stuff - still need to honor the playBehavior
                        if directive['name'] == 'play':
                            nav_token = directive['payload']['navigationToken']
                            for stream in directive['payload']['audioItem']['streams']:
                                if stream['progressReportRequired']:
                                    streamid = stream['streamId']
                                    playBehavior = directive['payload']['playBehavior']
                                if stream['streamUrl'].startswith("cid:"):
                                    content = path + "tmpcontent/" + stream['streamUrl'].lstrip("cid:") + ".mp3"
                                else:
                                    content = stream['streamUrl']
                                pThread = threading.Thread(target=play_audio,
                                                           args=(content, stream['offsetInMilliseconds']))
                                pThread.start()
                    elif directive['namespace'] == "Speaker":
                        # speaker control such as volume
                        if directive['name'] == 'SetVolume':
                            vol_token = directive['payload']['volume']
                            type_token = directive['payload']['adjustmentType']
                            if (type_token == 'relative'):
                                currVolume = currVolume + int(vol_token)
                            else:
                                currVolume = int(vol_token)

                            if (currVolume > MAX_VOLUME):
                                currVolume = MAX_VOLUME
                            elif (currVolume < MIN_VOLUME):
                                currVolume = MIN_VOLUME

                            self.emit_message("NEW_VOLUME",str(currVolume))

            elif 'audioItem' in j['messageBody']:  # Additional Audio Iten
                nav_token = j['messageBody']['navigationToken']
                for stream in j['messageBody']['audioItem']['streams']:
                    if stream['progressReportRequired']:
                        streamid = stream['streamId']
                    if stream['streamUrl'].startswith("cid:"):
                        content = path + "tmpcontent/" + stream['streamUrl'].lstrip("cid:") + ".mp3"
                    else:
                        content = stream['streamUrl']
                    pThread = threading.Thread(target=play_audio, args=(content, stream['offsetInMilliseconds']))
                    pThread.start()

            return
        elif r.status_code == 204:
            self.emit_message("NULL_RESPONSE")
        else:
            self.emit_message("PROCESS_RESPONSE_ERROR",str(r.status_code))
            r.connection.close()


    def play_audio(self,file=DETECT_DING, offset=0, overRideVolume=0):
        global currVolume
        if (file.find('radiotime.com') != -1):
            file = tuneinplaylist(file)
        global nav_token, p, audioplaying
        self.emit_message("PLAY_AUDIO",file)
        i = vlc.Instance('--aout=alsa')  # , '--alsa-audio-device=mono', '--file-logging', '--logfile=vlc-log.txt')
        i = vlc.Instance('--aout=alsa', '--alsa-audio-device=plughw:0,0')
        m = i.media_new(file)
        p = i.media_player_new()
        p.set_media(m)
        mm = m.event_manager()
        mm.event_attach(vlc.EventType.MediaStateChanged, self.state_callback, p)
        audioplaying = True

        if (overRideVolume == 0):
            p.audio_set_volume(currVolume)
        else:
            p.audio_set_volume(overRideVolume)

        p.play()
        while audioplaying:
            continue


    def tuneinplaylist(self,url):
        global tunein_parser
        self.emit_message("TUNEIN_URL",url)
        req = requests.get(url)
        lines = req.content.split('\n')

        nurl = tunein_parser.parse_stream_url(lines[0])
        if (len(nurl) != 0):
            return nurl[0]

        return ""


    def state_callback(self,event, player):
        global nav_token, audioplaying, streamurl, streamid
        state = player.get_state()
        # 0: 'NothingSpecial'
        # 1: 'Opening'
        # 2: 'Buffering'
        # 3: 'Playing'
        # 4: 'Paused'
        # 5: 'Stopped'
        # 6: 'Ended'
        # 7: 'Error'
        self.emit_message("PLAYER_STATE",state)
        if state == 3:  # Playing
            if streamid != "":
                rThread = threading.Thread(target=alexa_playback_progress_report_request,
                                           args=("STARTED", "PLAYING", streamid))
                rThread.start()
        elif state == 5:  # Stopped
            audioplaying = False
            if streamid != "":
                rThread = threading.Thread(target=alexa_playback_progress_report_request,
                                           args=("INTERRUPTED", "IDLE", streamid))
                rThread.start()
            streamurl = ""
            streamid = ""
            nav_token = ""
        elif state == 6:  # Ended
            audioplaying = False
            if streamid != "":
                rThread = threading.Thread(target=alexa_playback_progress_report_request,
                                           args=("FINISHED", "IDLE", streamid))
                rThread.start()
                streamid = ""
            if streamurl != "":
                pThread = threading.Thread(target=play_audio, args=(streamurl,))
                streamurl = ""
                pThread.start()
            elif nav_token != "":
                gThread = threading.Thread(target=alexa_getnextitem, args=(nav_token,))
                gThread.start()
        elif state == 7:
            audioplaying = False
            if streamid != "":
                rThread = threading.Thread(target=alexa_playback_progress_report_request, args=("ERROR", "IDLE", streamid))
                rThread.start()
            streamurl = ""
            streamid = ""
            nav_token = ""


    def silence_listener(self):
        self.play_audio(DETECT_DING)
        self.emit_message("RECORD_START")
        self.record_to_wave(path+WAVE_OUTPUT_FILENAME,self._pin)
        self.emit_message("RECORD_END")
        
    def start(self):
        self.play_audio(DETECT_DING)
        self.record_to_wave(path+WAVE_OUTPUT_FILENAME,self._pin)
        self.alexa_speech_recognizer()
        if self._model:
            print(('SNOWBOY_START|%s' % (self._model)).encode(coding))
        else:
            print(('SNOWBOY_START|snowboy.umdl').encode(coding))
        sys.stdout.flush()
        
    def terminate(self):
        self._pin.terminate()
        
class MainLoop(glib.MainLoop):

    def __init__(self):
        super(MainLoop, self).__init__()
        self.__clear()
        self.__alexa = Alexa()
        self._model="snowboy.umdl"

    def __clear(self):
        self.__alexa = None

    def __process_message(self, args):
        if len(args) >= 1 and args[0] == 'ALEXA_START':
            self.__alexa.emit_message("START")
            self.__alexa.start()
        elif len(args) >= 1 and args[0] == 'SNOWBOY_EVENT_DETECT':
            self.__alexa.emit_message("START")
            self.__alexa.start()
        elif len(args) >= 1 and args[0] == 'ALEXA_STOP':
            if self.__alexa:
                self.__alexa.terminate()
                self.__alexa.emit_message("STOP")
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
