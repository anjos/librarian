#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Utilities for converting FFMPEG files into standardized MP4s'''


import os
import sys
import six
import subprocess
import multiprocessing
from xml.etree import ElementTree

import logging
logger = logging.getLogger(__name__)


def probe(filename):
  '''Calls ffprobe and returns parsed output

  The executable ``ffprobe`` should be installed alongside
  :py:attr:`sys.executable`.


  Parameters:

    filename (str): Full path leading to the multimedia file to be parsed


  Returns:

    xml.etree.ElementTree: With all information pre-parsed by the stock XML
    parser. A typical stream has the following structure:

    .. code-block:: xml

     <ffprobe>
       <streams>
         <stream index="0" codec_name="h264" codec_long_name="H.264 / AVC / MPEG-4 AVC / MPEG-4 part 10" profile="Constrained Baseline" codec_type="video" codec_time_base="1/60" codec_tag_string="avc1" codec_tag="0x31637661" width="560" height="320" coded_width="560" coded_height="320" has_b_frames="0" sample_aspect_ratio="0:1" display_aspect_ratio="0:1" pix_fmt="yuv420p" level="30" color_range="tv" color_space="bt709" color_transfer="bt709" color_primaries="bt709" chroma_location="left" refs="1" is_avc="true" nal_length_size="4" r_frame_rate="30/1" avg_frame_rate="30/1" time_base="1/90000" start_pts="0" start_time="0.000000" duration_ts="498000" duration="5.533333" bit_rate="465641" bits_per_raw_sample="8" nb_frames="166">
           <disposition default="1" dub="0" original="0" comment="0" lyrics="0" karaoke="0" forced="0" hearing_impaired="0" visual_impaired="0" clean_effects="0" attached_pic="0" timed_thumbnails="0"/>
           <tag key="creation_time" value="2010-03-20T21:29:11.000000Z"/>
           <tag key="language" value="und"/>
           <tag key="encoder" value="JVT/AVC Coding"/>
         </stream>
         <stream>...</stream>
       </streams>
       <format filename="/Users/andre/Projects/qnap/librarian/librarian/data/movie.mp4" nb_streams="2" nb_programs="0" format_name="mov,mp4,m4a,3gp,3g2,mj2" format_long_name="QuickTime / MOV" start_time="0.000000" duration="5.568000" size="383631" bit_rate="551193" probe_score="100">
         <tag key="major_brand" value="mp42"/>
         <tag key="minor_version" value="0"/>
         <tag key="compatible_brands" value="mp42isomavc1"/>
         <tag key="creation_time" value="2010-03-20T21:29:11.000000Z"/>
         <tag key="encoder" value="HandBrake 0.9.4 2009112300"/>
       </format>
     </ffprobe>


  Raises:

    IOError: In case ``ffprobe`` is not available on your path

  '''

  ffprobe = os.path.join(os.path.dirname(sys.executable), 'ffprobe')

  # checks ffprobe is there...
  if not os.path.exists(ffprobe):
    raise IOError('Cannot find ffprobe exectuable at `%s\' - did you ' \
        'install it?' % ffprobe)

  cmd = [
      ffprobe,
      '-v', 'quiet',
      '-print_format', 'xml',
      '-show_format',
      '-show_streams',
      filename,
      ]

  try:
    data = subprocess.check_output(cmd)
  except Exception as e:
    logger.error("Error running command `%s'" % ' '.join(cmd))
    raise

  return ElementTree.fromstring(data)


def _plan_video(streams, mapping):
  '''Creates a transcoding plan for the (only?) default video stream

  Parameters:

    streams (list): A list of :py:class:`xml.etree.ElementTree` objects
      representing video streams. Most likely, there will be only one

    mapping (dict): Where to place the planning

  '''

  if len(streams) == 1:
    video = streams[0]
  else:
    logger.warn('More than one video stream found - keeping first only')
    # we're only interested in the "default" video stream
    video = [s for s in stream if s.find('disposition').attrib['default'] == 1]
    video = video[0] #we drop all other video streams

  mapping[video]['index'] = 0 #video is always first

  # if the video is not in h264 format, then we'll convert it
  if '264' not in video.attrib['codec_name']:
    logger.info('Video is encoded in %s - transcoding stream to H.264',
        video.attrib['codec_name'])
    mapping[video]['codec'] = 'h264'
  else: #copy whatever
    logger.info('Video is encoded in H.264 - copying stream')
    mapping[video]['codec'] = 'copy'


def _get_stream_language(stream):
  '''Returns the language of the stream'''

  tags = stream.findall('tag')
  lang = [t for t in tags if t.attrib['key'] == 'language']
  if lang:
    return lang[0].attrib['value']
  return 'und' #undefined, ffprobe standard


def _plan_audio(streams, languages, ios_audio, mapping):
  '''Creates a transcoding plan for audio streams

  Parameters:

    streams (list): A list of :py:class:`xml.etree.ElementTree` objects
      representing audio streams. There is at least one in every video file,
      but there may be many

    languages (list, tuple): The list of secondary audio and subtitle streams
      to retain, in order of preference. Languages should be encoded using a
      3-character string (ISO 639 language codes). The audio languages that are
      available on the stream will be selected and organized according to this
      preference. The main audio stream of the file will be kept and will make
      up audio[0] and audio[1] (if ``ios_audio`` is set to ``True``). The
      following audio tracks will be organized as defined. For subtitle tracks,
      all tracks will be off by default. The order of tracks is defined by this
      variable.

    ios_audio (:py:class:`bool`, optional): If set to ``True``, then audio[1]
      will contain a stereo AC3 encoded track which is suitable to play on iOS
      devices

    mapping (dict): Where to place the planning

  Returns:

    str: The default audio language of the original movie file. This is a
    3-character string following the ISO 639 specifications.

  '''

  # now, let's handle the default audio bands
  default_audio = [s for s in streams \
      if s.find('disposition').attrib['default'] == "1"]
  default_audio = default_audio[0] #first audio stream is the default
  mapping[default_audio] = {'index': 1}

  default_lang = _get_stream_language(default_audio)

  # if the default audio is already in AAC, just copy it
  default_channels = int(default_audio.attrib['channels'])
  if 'aac' not in default_audio.attrib['codec_name']:
    logger.info('Default audio stream is encoded in %s - transcoding ' \
        'stream to AAC, profile = LC, channels = %d, language = %s',
        default_audio.attrib['codec_name'], default_channels, default_lang)
    mapping[default_audio]['index'] = 1
    mapping[default_audio]['codec'] = 'aac'
  else: #copy whatever
    logger.info('Default audio is encoded in AAC - copying stream')
    mapping[default_audio]['codec'] = 'copy'

  secondary_audio = [s for s in streams if s != default_audio]

  ios_stream = None

  if ios_audio and default_channels > 2:

    # tries to find a stream, with the same language as the default audio
    # stream, but with only 2 audio channels (stereo), that is still encoded as
    # AAC or AC3. copy that prioritarily if available
    for s in secondary_audio:
      if default_lang == _get_stream_language(s) and \
          int(s.attrib['channels']) == 2:
        ios_stream = s #found it
        mapping[s]['index'] = 2
        if 'aac' not in s.attrib['codec_name']:
          logger.info('iOS audio stream is encoded in %s - transcoding ' \
              'stream to AAC, profile = LC, channels = 2, language = %s',
              default_audio.attrib['codec_name'], default_lang)
          mapping[s]['codec'] = 'aac'
        else: #copy whatever
          logger.info('iOS audio is encoded in AAC - copying stream')
          mapping[s]['codec'] = 'copy'

    # if, at this point, ios_stream was not found, transcode from the default
    # audio stream
    if ios_stream is None:
      logger.info('iOS audio stream is encoded in %s - transcoding ' \
          'stream to AAC, profile = LC, channels = 2, language = %s',
          default_audio.attrib['codec_name'], default_lang)
      mapping['__ios__'] = {'original': default_audio}
      mapping['__ios__']['index'] = 2
      mapping['__ios__']['codec'] = 'aac'

  else:
    logger.info('Skipping creation of optimized iOS audio track')

  # eventually, exclude used iOS audio stream
  secondary_audio = [s for s in secondary_audio if s != ios_stream]

  # remove anything that is in the main language
  secondary_audio = [s for s in secondary_audio \
      if _get_stream_language(s) not in ('und', default_lang)]

  # re-organize the input languages to that the default language, which already
  # has 1 or 2 streams guaranteed, does not reappear
  languages = [k for k in languages if k != default_lang]

  # we now want to re-arrange the other streams in such a way as to respect the
  # language selection from the user. we also transcode those streams to aac if
  # that is not the case already
  curr_index = len([(k,v) for k,v in mapping.items() if v])
  for k in languages:
    used_stream = None
    for s in secondary_audio:
      lang = _get_stream_language(s)
      if lang == k:
        # incorporate stream into the output file
        used_stream = s
        mapping[s] = {'index': curr_index}
        curr_index += 1
        if 'aac' not in s.attrib['codec_name']:
          channels = int(s.attrib['channels'])
          logger.info('Audio stream (language=%s, index=%d) is encoded in %s ' \
              '- transcoding stream to AAC, profile = LC, channels = %d',
              lang, curr_index-1, s.attrib['codec_name'], channels)
          mapping[s]['codec'] = 'aac'
        else: #copy whatever
          logger.info('Audio stream (language=%s, index=%d) is encoded in ' \
              'AAC - copying stream', lang, curr_index-1)
          mapping[s]['codec'] = 'copy'

    # remove any used stream so we don't iterate over it again
    secondary_audio = [s for s in secondary_audio if s != used_stream]

    # remove any other stream that matches the same language
    secondary_audio = [s for s in secondary_audio \
        if _get_stream_language(s) != k]

  return default_lang


def _plan_subtitles(streams, filename, default_language, languages, mapping):
  '''Creates a transcoding plan for subtitle streams

  Parameters:

    streams (list): A list of :py:class:`xml.etree.ElementTree` objects
      representing subtitle streams. There may be none

    filename (str): Full path leading to the movie original filename. We use
      this path to potentially discover subtitles we will incorporate in the
      final MP4 file. Subtitles are encoded using ``mov_text``.

    default_language: The default movie language of the original movie file.
      This is a 3-character string following the ISO 639 specifications.

    languages (list, tuple): The list of secondary audio and subtitle streams
      to retain, in order of preference. Languages should be encoded using a
      3-character string (ISO 639 language codes). The audio languages that are
      available on the stream will be selected and organized according to this
      preference. The main audio stream of the file will be kept and will make
      up audio[0] and audio[1] (if ``ios_audio`` is set to ``True``). The
      following audio tracks will be organized as defined. For subtitle tracks,
      all tracks will be off by default. The order of tracks is defined by this
      variable.

    mapping (dict): Where to place the planning

  '''

  # finally, we handle the subtitles, keep language priority and suppress any
  # other languages. there are 2 options here: (1) the stream is encoded within
  # the file. in such a case, we leave it as is if already in mov_text type,
  # otherwise transcode it into this type. (2) there is a subtitle text file of
  # type SRT alongside the original file. in such a case we import it into a
  # mov_text subtitle, setting the language adequately.

  # re-arrange the languages so the default language comes first, if a subtitle
  # for it exists.
  languages = [k for k in languages if k != default_language]
  languages = [default_language] + languages
  curr_index = len([(k,v) for k,v in mapping.items() if v])

  for k in languages:
    used_stream = None
    for s in streams:
      tags = s.findall('tag')
      lang = _get_stream_language(s)
      if lang == k:
        # incorporate stream into the output file
        mapping[s] = {'index': curr_index}
        curr_index += 1
        if s.attrib['codec_name'] != 'mov_text':
          mapping[s]['codec'] = 'mov_text'
        else: #copy whatever
          mapping[s]['codec'] = 'copy'
        break #go to the next language, don't pay attention to SRT files

      # if you get at this point, it is because we never entered the if clause
      # in this case, look for an external subtitle file on the target language
      candidate = os.path.splitext(filename)[0] + '.' + k + '.srt'
      if os.path.exists(candidate):
        mapping[candidate] = {'index': curr_index}
        curr_index += 1
        mapping[candidate]['codec'] = 'mov_text'
        mapping[candidate]['options'] = {'language': k}

    # remove any used stream so we don't iterate over it again
    streams = [s for s in streams if s != used_stream]

    # remove any other stream that matches the same language
    streams = [s for s in streams if _get_stream_language(s) != k]


def _uniq(seq, idfun=None):
  """Very fast, order preserving uniq function"""

  # order preserving
  if idfun is None:
      def idfun(x): return x
  seen = {}
  result = []
  for item in seq:
      marker = idfun(item)
      # in old Python versions:
      # if seen.has_key(marker)
      # but in new ones:
      if marker in seen: continue
      seen[marker] = 1
      result.append(item)
  return result


def plan(probe, languages, ios_audio=True):
  '''Plans the pipeline to convert the input video into a standardised mp4

  This function can plan the conversion of a movie or TV show episode in a
  given format into an MP4 version. It doesn't do anything, it just plans the
  stream information re-ordering according to some logic. If the plan is
  carried on, the resulting MP4 video should be made as one likes and only a
  minimal amount of transcoding taking place. Here is the desired output:

  .. code-block:: text

     format: mp4, independent of the input format

     video: h264 (always copied from source if already in h264 or transcoded)

     audio[0]: audio for the default language, in AAC format. If it is already
     the case, then the audio stream is copied. Otherwise, it is converted so
     that each channel has a bitrate of 128kbs.

     audio[1]: audio for the default language, in AC3 format and stereo. This
     format is more compatible with iOS devices. If audio[0] is already stereo,
     then this is not created. If an AC3 track is detected elsewhere, then it
     is copied as the second audio program if the language match.

     audio[x]: further audio channels, in AAC format, stereo, 128kps per
     channel.

     subtitle[x]: subtitles following the order of preference in
     ``subtitle_languages``. This will be of format MOV_TEXT, which is the one
     that works on iOS devices. If subtitle streams are presented in the
     original file, then they are copied with a potential inversion of the
     order. If a file named ``movie.<lang>.srt`` is found alongside the
     original movie file, and languages match, then it is converted to
     MOV_TEXT and inserted into the file.

  Once the file is converted, it is passed over to ``qtfaststart`` which will
  re-encode the file so it is optimized for streaming.


  Parameters:

    probe (xml.etree.ElementTree): The element tree of the corresponding probed
      input file (through :py:func:`probe`)

    languages (list, tuple): The list of secondary audio and subtitle streams
      to retain, in order of preference. Languages should be encoded using a
      3-character string (ISO 639 language codes). The audio languages that are
      available on the stream will be selected and organized according to this
      preference. The main audio stream of the file will be kept and will make
      up audio[0] and audio[1] (if ``ios_audio`` is set to ``True``). The
      following audio tracks will be organized as defined. For subtitle tracks,
      all tracks will be off by default. The order of tracks is defined by this
      variable.

    ios_audio (:py:class:`bool`, optional): If set to ``True``, then audio[1]
      will contain a stereo AC3 encoded track which is suitable to play on iOS
      devices


  Returns:

    dict: A dictionary with the transcoding plan considering all aspects
    related to the movie file and allowing for minimal CPU effort to take
    place.

  '''

  languages = _uniq(languages)

  mapping = {}
  streams = list(probe.iter('stream'))
  for s in streams: mapping[s] = {}

  def _get_streams(streams, ctype):
    '''Returns streams for a particular codec type'''
    return [k for k in streams if k.attrib['codec_type'] == ctype]

  _plan_video(_get_streams(streams, 'video'), mapping)

  default_language = _plan_audio(_get_streams(streams, 'audio'),
      languages, ios_audio, mapping)

  filename = probe.find('format').attrib['filename']
  _plan_subtitles(_get_streams(streams, 'subtitle'), filename,
      default_language, languages, mapping)

  # return information only for streams that will be used
  return mapping


def options(infile, outfile, planning, threads=multiprocessing.cpu_count()):
  '''Define ffmpeg options to convert the input file into an output file


  Parameters:

    infile (str): The full path leading to the input file to be transcoded

    outfile (str): The full path leading to the output file, where the results
      are going to be stored

    planning (dict): A transcode planning, as defined by by :py:func:`plan`.

    threads (:py:class:`int`, optional): The number of threads for ffmpeg to
      use while transcoding the file

  '''

  # organizes the input stream by index
  keeping = [(k,v) for k,v in planning.items() if v]
  sorted_planning = sorted(keeping, key=lambda k: k[1]['index'])

  mapopt = [] #mapping options
  codopt = [] #codec options
  inopt  = [] #input options
  audcnt = 0 #audio stream count
  subcnt = 0 #subtitle stream count
  extsubcnt = 1 #external subtitle stream count
  for k,v in keeping:

    if isinstance(k, six.string_types):

      if k == '__ios__': #secondary iOS stream
        mapopt += ['-map', '0:'+ str(v['index'])]
        codopt += ['-c:a:%d' % audcnt, 'aac', '-vbr', '5']
        audcnt += 1

      else: #subtitle SRT to bring in
        inopt += ['-i', k]
        mapopt += ['-map', str(extsubcnt) + ':' + str(v['index'])]
        extsubcnt += 1
        codopt += [
            '-c:s:%d' % subcnt,
            'mov_text',
            '-metadata:s:%d' % v['index'],
            'language=%s' % v['options']['language'],
            ]
        subcnt += 1

    else: # normal stream to be moved or transcoded

      mapopt += ['-map', '0:'+str(v['index'])]
      kind = k.attrib['codec_type']

      if kind == 'video': codopt += ['-c:v:0']
      elif kind == 'audio':
        codopt += ['-c:a:%d' % audcnt]
        audcnt += 1
      elif kind == 'subtitle':
        codopt += ['-c:s:%d' % subcnt]
        subcnt += 1

      if v['codec'] == 'copy':
        codopt += ['copy']
      else: #some transcoding
        if kind == 'video':
          codopt += ['libx264', '-preset', 'slower'] #default is medium
        elif kind == 'audio':
          codopt += ['aac', '-vbr', '4'] #good compromise (max is 5)
        elif kind == 'subtitle':
          codopt += [
            'mov_text',
            '-metadata:s:%d' % v['index'],
            'language=%s' % _get_stream_language(k),
            ]

  # replaces qtfaststart need
  codopt += ['-movflags', '+faststart']

  # now we create the mapping specification
  return ['-threads', str(threads)] + ['-i', infile] + inopt + mapopt + \
      codopt + [outfile]
