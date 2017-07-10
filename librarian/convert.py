#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Utilities for converting FFMPEG files into standardized MP4s'''


import os
import re
import sys
import six
import tqdm
import pexpect
import subprocess
import multiprocessing
from xml.etree import ElementTree

import logging
logger = logging.getLogger(__name__)


def ffmpeg_codec_capabilities():
  '''Checks if ffmpeg was compiled with a specific codec returns capabilities


  Returns:

    dict: A dictionary where keys are codec names and values correspond to a
    capabilities dictionary containing the following key/values:

    * 'decode': decoding supported (:py:class:`bool`)
    * 'encode': encoding supported (:py:class:`bool`)
    * 'type'  : codec type, one of 'video', 'audio' or 'subtitle'
    * 'description': full description of the codec, including implementors

  '''

  ffmpeg = os.path.join(os.path.dirname(sys.executable), 'ffmpeg')

  output = subprocess.check_output([ffmpeg, '-codecs'],
      stderr=subprocess.STDOUT)

  codec_re = re.compile(b'^\s(?P<decode>[D\.])(?P<encode>[E\.])(?P<type>[AVS\.])[I\.][L\.][S\.]\s(?P<codec>\w+)\s+(?P<desc>.*)$')
  output = [codec_re.match(k) for k in output.split(b'\n') if codec_re.match(k)]

  decode_translator = {b'D': True, b'.': False}
  encode_translator = {b'E': True, b'.': False}
  type_translator = {b'V': 'video', b'A': 'audio', b'S': 'subtitle'}

  return dict([(k.group('codec').decode(), {
    'decode': decode_translator[k.group('decode')],
    'encode': encode_translator[k.group('encode')],
    'type': type_translator[k.group('type')],
    'description': k.group('desc').decode(),
    }) for k in output])


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
    raise IOError('Cannot find ffprobe executable at `%s\' - did you ' \
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


def _get_streams(streams, ctype):
  '''Returns streams for a particular codec type'''

  return [k for k in streams if k.attrib['codec_type'] == ctype]


def _get_default_stream(streams, ctype):
  '''Returns the default stream of a certain type - first default'''

  assert streams

  r = [s for s in streams if s.find('disposition').attrib['default'] == '1']

  if len(r) == 0:
    logger.warn('No %s streams tagged with "default" - returning first' % ctype)
    return streams[0]

  if len(r) > 1:
    logger.warn('More than one %s stream found - keeping first only' % ctype)
    # we're only interested in the "default" <ctype> stream

  return r[0]


def _copy_or_transcode(stream, name, codec, settings):
  '''Decides if the stream will be copied or transcoded based on its settings

  This function will check if the stream will be copied or transcoded based on
  its current settings. It will first compare the currently used codec with
  ``name`` and then set the ``codec`` key in ``settings`` to either ``copy``,
  in case the check is ``True`` or ``codec`` in case it is false. Info messages
  will be logged all the way.


  Parameters:

    stream (xml.etree.Element): An XML element corresponding to the stream to
      check

    name (str): The bit of string to check on the currently used codec name.
      For example, this may be ``aac`` or ``264``. It does not need to be the
      full codec name as that is normally changing depending on how you
      compiled ffmpeg.

    codec (str): This is a keyword that will be used later and defines the
      codec we actually want for this stream

    settings (dict): This is the dictionary that determines the fate of this
      stream on the overall transcoding plan.

  '''

  if name not in stream.attrib['codec_name']:
    logger.info('%s stream (index=%s, language=%s) is encoded with ' \
        'codec=%s - transcoding stream to %s',
        stream.attrib['codec_type'].capitalize(),
        stream.attrib['index'],
        _get_stream_language(stream),
        stream.attrib['codec_name'],
        codec)
    settings['codec'] = codec

  else: #copy whatever
    logger.info('%s stream (index=%s, language=%s) is already encoded ' \
        'with codec=%s - copying stream',
        stream.attrib['codec_type'].capitalize(),
        stream.attrib['index'],
        _get_stream_language(stream),
        codec)
    settings['codec'] = 'copy'


def _plan_video(streams, mapping):
  '''Creates a transcoding plan for the (only?) default video stream

  Parameters:

    streams (list): A list of :py:class:`xml.etree.ElementTree` objects
      representing video streams. Most likely, there will be only one

    mapping (dict): Where to place the planning

  '''

  video = _get_default_stream(_get_streams(streams, 'video'), 'video')

  mapping[video]['index'] = 0 #video is always first
  mapping[video]['disposition'] = 'default' #video should be shown by default

  _copy_or_transcode(video, '264', 'h264', mapping[video])


def _get_stream_language(stream):
  '''Returns the language of the stream'''

  tags = stream.findall('tag')
  lang = [t for t in tags if t.attrib['key'] == 'language']
  if lang:
    return lang[0].attrib['value']
  return 'und' #undefined, ffprobe standard


def _get_default_audio_stream(streams, languages):
  '''Tries to get the default audio stream respecting the language setting'''

  assert languages

  for l in languages:
    for s in streams:
      if l == _get_stream_language(s):
        if l != languages[0]:
          logger.warn('Could not find audio stream in ``%s\' - ' \
              'using language `%s\' instead', languages[0], l)
        return s

  # if you get to this point, there is no audio stream that actually statisfies
  # your request. we then consider the "default" audio stream to be the one
  return _get_default_stream(audio_streams, 'audio')


def _plan_audio(streams, languages, ios_audio, mapping):
  '''Creates a transcoding plan for audio streams

  Parameters:

    streams (list): A list of :py:class:`xml.etree.ElementTree` objects
      representing audio streams. There is at least one in every video file,
      but there may be many

    languages (list, tuple): The list of audio streams to retain according to
      language and in order of preference. Languages should be encoded using a
      3-character string (ISO 639 language codes). The audio languages that are
      available on the stream will be selected and organized according to this
      preference. The main audio stream of the file will be considered to be
      the first language and will make up audio[0] (and audio[1] if
      ``ios_audio`` is set to ``True``). The following audio tracks will be
      organized as defined.

    ios_audio (:py:class:`bool`, optional): If set to ``True``, then audio[1]
      will contain a stereo AC3 encoded track which is suitable to play on iOS
      devices

    mapping (dict): Where to place the planning

  Returns:

    str: The default audio language of the original movie file. This is a
    3-character string following the ISO 639 specifications.

  '''

  audio_streams = _get_streams(streams, 'audio')

  # now, let's handle the default audio bands
  default_audio = _get_default_audio_stream(audio_streams, languages)
  default_lang = _get_stream_language(default_audio)
  default_channels = int(default_audio.attrib['channels'])
  mapping[default_audio]['index'] = 1
  mapping[default_audio]['disposition'] = 'default' #audible by default

  # if the default audio is already in AAC, just copy it
  _copy_or_transcode(default_audio, 'aac', 'aac', mapping[default_audio])

  secondary_audio = [s for s in audio_streams if s != default_audio]

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
        mapping[s]['disposition'] = 'none' # not audible by default
        _copy_or_transcode(s, 'aac', 'aac', mapping[s])

    # if, at this point, ios_stream was not found, transcode from the default
    # audio stream
    if ios_stream is None:
      logger.info('iOS audio stream is encoded in %s - transcoding ' \
          'stream to AAC, profile = LC, channels = 2, language = %s',
          default_audio.attrib['codec_name'], default_lang)
      mapping['__ios__'] = {'original': default_audio}
      mapping['__ios__']['index'] = 2
      mapping['__ios__']['codec'] = 'aac'
      mapping['__ios__']['disposition'] = 'none'

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
        mapping[s]['index'] = curr_index
        mapping[s]['disposition'] = 'none' # not audible by default
        curr_index += 1
        _copy_or_transcode(s, 'aac', 'aac', mapping[s])

    # remove any used stream so we don't iterate over it again
    secondary_audio = [s for s in secondary_audio if s != used_stream]

    # remove any other stream that matches the same language
    secondary_audio = [s for s in secondary_audio \
        if _get_stream_language(s) != k]


def _plan_subtitles(streams, filename, languages, mapping, show=None):
  '''Creates a transcoding plan for subtitle streams


  Parameters:

    streams (list): A list of :py:class:`xml.etree.ElementTree` objects
      representing all streams available in the file.

    filename (str): Full path leading to the movie original filename. We use
      this path to potentially discover subtitles we will incorporate in the
      final MP4 file. Subtitles are encoded using ``mov_text``.

    languages (list, tuple): The list of all subtitle streams to retain
      according to language, in order of preference. Languages should be
      encoded using a 3-character string (ISO 639 language codes). For subtitle
      tracks, all tracks will be off by default (unless ``show`` is set). The
      order of tracks is defined by this variable.

    mapping (dict): Where to place the planning

    show (:py:class:`str`, optional): The 3-character ISO 639 specification of
      a subtitle language to show by default. If not set, then don't display
      any subtitle by default.

  '''

  subtitle_streams = _get_streams(streams, 'subtitle')

  # finally, we handle the subtitles, keep language priority and suppress any
  # other languages. there are 2 options here: (1) the stream is encoded within
  # the file. in such a case, we leave it as is if already in mov_text type,
  # otherwise transcode it into this type. (2) there is a subtitle text file of
  # type SRT alongside the original file. in such a case we import it into a
  # mov_text subtitle, setting the language adequately.

  # re-arrange the languages so the input order is preserved. If the ``show``
  # language is not among ``languages``, add it.
  if show is not None:
    if show not in languages:
      languages = _uniq([show] + languages)
  curr_index = len([(k,v) for k,v in mapping.items() if v])

  for k in languages:
    used_stream = None
    for s in subtitle_streams:
      tags = s.findall('tag')
      lang = _get_stream_language(s)
      if lang == k:
        # incorporate stream into the output file
        mapping[s]['index'] = curr_index
        mapping[s]['disposition'] = 'default' if show == k else 'none'
        curr_index += 1
        _copy_or_transcode(s, 'mov_text', 'mov_text', mapping[s])
        break #go to the next language, don't pay attention to SRT files

      # if you get at this point, it is because we never entered the if clause
      # in this case, look for an external subtitle file on the target language
      candidate = os.path.splitext(filename)[0] + '.' + k + '.srt'
      if os.path.exists(candidate):
        mapping[candidate] = {'index': curr_index}
        curr_index += 1
        mapping[candidate]['disposition'] = 'default' if show == k else 'none'
        mapping[candidate]['codec'] = 'mov_text'
        mapping[candidate]['language'] = k

    # remove any used stream so we don't iterate over it again
    subtitle_streams = [s for s in subtitle_streams if s != used_stream]

    # remove any other stream that matches the same language
    subtitle_streams = [s for s in subtitle_streams \
        if _get_stream_language(s) != k]


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


def plan(probe, languages, default_subtitle_language=None, ios_audio=True):
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

    default_subtitle_language (:py:class:`str`, optional): The 3-character ISO
      639 specification of a subtitle language to show by default. If not set,
      then don't display any subtitle by default.

    ios_audio (:py:class:`bool`, optional): If set to ``True``, then audio[1]
      will contain a stereo AC3 encoded track which is suitable to play on iOS
      devices


  Returns:

    dict: A dictionary with the transcoding plan considering all aspects
    related to the movie file and allowing for minimal CPU effort to take
    place. The keys correspond to the stream XML objects. Values are
    dictionaries with properties of the transcoding plan.

  '''

  languages = _uniq(languages)

  mapping = {}
  streams = list(probe.iter('stream'))
  for s in streams: mapping[s] = {}

  _plan_video(streams, mapping)
  _plan_audio(streams, languages, ios_audio, mapping)

  filename = probe.find('format').attrib['filename']
  _plan_subtitles(streams, filename, languages, mapping,
      show=default_subtitle_language)

  # return information only for streams that will be used
  return mapping


def print_plan(plan):
  '''Prints out the transcoding plan


  Parameters:

    plan (dict): A dictionary with the transcoding plan considering all aspects
      related to the movie file and allowing for minimal CPU effort to take
      place. The keys correspond to the stream XML objects. Values are
      dictionaries with properties of the transcoding plan.

  '''

  def _sorter(k):
    if isinstance(k[0], six.string_types):
      return k[1]['index']
    return int(k[0].attrib['index'])

  # print the planning
  for k,v in sorted(plan.items(), key=_sorter):
    if not v: #deleting
      print('  %s stream [%s] lang=%s codec=%s -> [deleted]' % \
          (k.attrib['codec_type'], k.attrib['index'],
            _get_stream_language(k), k.attrib['codec_name']))
      continue

    if isinstance(k, six.string_types):
      # either it is an __ios__ stream or an external sub
      if k == '__ios__':
        print('  %s stream [%s] lang=%s codec=%s -> [%d] codec=%s (iOS)' % \
            (v['original'].attrib['codec_type'],
              v['original'].attrib['index'],
              _get_stream_language(v['original']),
              v['original'].attrib['codec_name'],
              v['index'], v['codec']))
      else: #it is a subtitle
        print('  (%s) lang=%s -> [%d] codec=%s %s' % \
            (os.path.basename(k), v['language'], v['index'], v['codec'],
            '**' if v['disposition'] == 'default' else ''))

    else:
      if k.attrib['codec_type'] in ('video', 'subtitle'):
        print('  %s stream [%s] lang=%s codec=%s -> [%d] codec=%s %s' % \
            (k.attrib['codec_type'], k.attrib['index'],
              _get_stream_language(k), k.attrib['codec_name'],
              v['index'], v['codec'],
              '**' if v['disposition'] == 'default' else ''))
      elif k.attrib['codec_type'] == 'audio':
        print('  %s stream [%s] lang=%s codec=%s channels=%s -> [%d] '\
            'codec=%s %s' % \
            (k.attrib['codec_type'], k.attrib['index'],
              _get_stream_language(k), k.attrib['codec_name'],
              k.attrib['channels'], v['index'], v['codec'],
              '**' if v['disposition'] == 'default' else ''))


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

  def _audio_codec(index, channels):
    '''Chooses fdk-aac if available, otherwise stock aac'''

    caps = ffmpeg_codec_capabilities()
    if 'libfdk_aac' in caps['aac']['description']:
      return ['libfdk_aac', '-vbr', '4']
    else: #use default
      bitrate = channels * 64
      return ['aac', '-b:%d' % index, '%dk' % bitrate]


  # organizes the input stream by index
  keeping = [(k,v) for k,v in planning.items() if v]
  sorted_planning = sorted(keeping, key=lambda k: k[1]['index'])

  mapopt = [] #mapping options
  codopt = [] #codec options
  inopt  = [] #input options
  extsubcnt = 1 #external subtitle stream count
  for k,v in sorted_planning:

    if isinstance(k, six.string_types):

      if k == '__ios__': #secondary iOS stream
        mapopt += ['-map', '0:2']
        codopt += [
            '-disposition:%d' % v['index'],
            v['disposition'],
            '-codec:%d' % v['index'],
            ] + \
            _audio_codec(v['index'], 2) + \
            [
                # converting from surround (5.1) - this formula comes from:
                # http://atsc.org/wp-content/uploads/2015/03/A52-201212-17.pdf
                '-ac', '2', '-af', 'pan=stereo|FL < 1.0*FL + 0.707*FC + ' \
                '0.707*BL|FR < 1.0*FR + 0.707*FC + 0.707*BR',
                '-metadata:s:%d' % v['index'],
                'language=%s' % _get_stream_language(v['original']),
            ]

      else: #subtitle SRT to bring in
        inopt += ['-i', k]
        mapopt += ['-map', str(extsubcnt) + ':0']
        extsubcnt += 1
        codopt += [
            '-disposition:%d' % v['index'], v['disposition'],
            '-codec:%d' % v['index'],
            'mov_text',
            '-metadata:s:%d' % v['index'],
            'language=%s' % v['language'],
            ]

    else: # normal stream to be moved or transcoded

      mapopt += ['-map', '0:%s' % k.attrib['index']]
      codopt += [
          '-disposition:%d' % v['index'], v['disposition'],
          '-codec:%d' % v['index'],
          ]
      kind = k.attrib['codec_type']

      if v['codec'] == 'copy':
        codopt += ['copy']
      else: #some transcoding
        if kind == 'video':
          codopt += ['libx264', '-preset', 'slower', '-crf', '21']
        elif kind == 'audio':
          codopt += _audio_codec(v['index'], int(k.attrib['channels']))
        elif kind == 'subtitle':
          codopt += ['mov_text']

      if kind in ('audio', 'subtitle'): #add language
        codopt += [
            '-metadata:s:%d' % v['index'],
            'language=%s' % _get_stream_language(k),
            ]

  # replaces qtfaststart need
  codopt += ['-movflags', '+faststart']

  fix_sub_duration = ['-fix_sub_duration']

  # now we create the mapping specification
  return ['-threads', str(threads)] + fix_sub_duration + \
      ['-i', infile] + inopt + mapopt + codopt + [outfile]


def run(options, progress=0):
  '''Runs ffmpeg taking into consideration the input options

  Uses ``pexpect`` to capture ffmpeg output and display progress with ``tqdm``.


  Parameters:

    options (list): A list of options for ffmpeg as returned by
      :py:func:`options`

    progress (:py:class:`int`, optional): If set to a value greater than zero,
      then it is considered to correspond to the total number of frames (in the
      main video sequence) to process. A progress bar will then be displayed
      showing the progress with ``tqdm``.


  Returns:

    int: zero, in case of a successful execution. Different than zero otherwise

  '''

  ffmpeg = os.path.join(os.path.dirname(sys.executable), 'ffmpeg')

  # checks ffmpeg is there...
  if not os.path.exists(ffmpeg):
    raise IOError('Cannot find ffmpeg executable at `%s\' - did you ' \
        'install it?' % ffmpeg)

  cmd = [ffmpeg] + options
  logger.info('Executing `%s\'...' % ' '.join(cmd))
  child = pexpect.spawn(' '.join(cmd))

  else_re = re.compile(b'(?P<all>\s*\S+.*)')
  pattern_list = [pexpect.EOF, else_re]

  if progress > 0:
    frame_re = re.compile(b'frame=\s*(?P<frame>\d+)\s+.*\s+speed=\s*(?P<speed>\d+(\.\d+)?)x\s*')
    pattern_list.insert(1, frame_re)

  cpl = child.compile_pattern_list(pattern_list)

  with tqdm.tqdm(total=progress, disable=not progress, unit='frames') as pbar:
    previous_frame = 0
    while True:
      i = child.expect_list(cpl, timeout=None)
      if i == 0: # EOF
        child.close()
        if child.exitstatus != 0:
          logger.error("Command %s" % ' '.join(cmd))
          logger.error("Exited with status %d", child.exitstatus)
        else:
          logger.debug("Process exited with status %d", child.exitstatus)
        return child.exitstatus
      elif i == 1 and progress > 0: #frame_re
        m = child.match.groupdict()
        pbar.set_postfix(speed=m['speed'].decode()+'x')
        pbar.update(int(m['frame'])-previous_frame)
        previous_frame = int(m['frame'])
      elif i == 2 or (i == 1 and progress <= 0): #else_re
        logger.debug("ffmpeg: %s", child.match.string)
