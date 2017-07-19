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
import chardet
from xml.etree import ElementTree

import logging
logger = logging.getLogger(__name__)

from .utils import as_language, language_acronyms, uniq
UNDETERMINED_LANGUAGE = as_language('und')


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

  r = [s for s in streams if s.attrib['codec_type'] == ctype and \
      s.find('disposition').attrib['default'] == '1']

  if len(r) == 0:
    logger.warn('No %s streams tagged with "default" - returning first' % ctype)
    return streams[0]

  if len(r) > 1:
    logger.warn('More than one %s stream found - keeping first only' % ctype)
    # we're only interested in the "default" <ctype> stream

  return r[0]


def _copy_or_transcode(stream, names, codec, settings):
  '''Decides if the stream will be copied or transcoded based on its settings

  This function will check if the stream will be copied or transcoded based on
  its current settings. It will first compare the currently used codec with
  ``name`` and then set the ``codec`` key in ``settings`` to either ``copy``,
  in case the check is ``True`` or ``codec`` in case it is false. Info messages
  will be logged all the way.


  Parameters:

    stream (xml.etree.Element): An XML element corresponding to the stream to
      check

    names (list of str): The bit of string to check on the currently used codec
      name.  For example, this may be ``aac`` or ``264``. It does not need to
      be the full codec name as that is normally changing depending on how you
      compiled ffmpeg. You may pass multiple strings to check for. If you pass
      a single string, still wrap it in a list.

    codec (str): This is a keyword that will be used later and defines the
      codec we actually want for this stream

    settings (dict): This is the dictionary that determines the fate of this
      stream on the overall transcoding plan.

  '''

  if not any(s in stream.attrib['codec_name'] for s in names):
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
        stream.attrib['codec_name'])
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

  _copy_or_transcode(video, ['264'], 'h264', mapping[video])


def _get_stream_language(stream):
  '''Returns the language of the stream'''

  tags = stream.findall('tag')
  lang = [t for t in tags if t.attrib['key'] == 'language']
  if lang:
    return as_language(lang[0].attrib['value'])
  return UNDETERMINED_LANGUAGE


def _get_default_audio_stream(streams, languages):
  '''Tries to get the default audio stream respecting the language setting'''

  assert languages

  for l in languages:
    for s in streams:
      if l == _get_stream_language(s):
        if l != languages[0]:
          logger.warn('Could not find audio stream in ``%s\' - ' \
              'using language `%s\' instead', languages[0].alpha3b, l.alpha3b)
        return s

  # if you get to this point, there is no audio stream that actually statisfies
  # your request. we then consider the "default" audio stream to be the one
  return _get_default_stream(streams, 'audio')


def _plan_audio(streams, languages, ios_audio, preserve_all, mapping):
  '''Creates a transcoding plan for audio streams

  Parameters:

    streams (list): A list of :py:class:`xml.etree.ElementTree` objects
      representing audio streams. There is at least one in every video file,
      but there may be many

    languages (list, tuple): The list of audio streams to retain according to
      language and in order of preference. Languages are objects of type
      :py:class:`babelfish.Language`. The audio languages that are available on
      the stream will be selected and organized according to this preference.
      The main audio stream of the file will be considered to be the first
      language and will make up audio[0] (and audio[1] if ``ios_audio`` is set
      to ``True``). The following audio tracks will be organized as defined.

    ios_audio (bool): If set to ``True``, then audio[1] will contain a stereo
      AAC (or AC3) encoded track which is suitable to play on iOS devices

    preserve_all (bool): If set, preserve all audio streams available in the
      selected languages on the output file. If this is not set and we have
      found audio streams matching each of the selected languages, then,
      exceeding audio streams will be dropped (e.g. a director's commentary
      stream). If you want to preserve those, set this flag

    mapping (dict): Where to place the planning

  Returns:

    babelfish.Language: The default audio language of the original movie file.

  '''

  audio_streams = _get_streams(streams, 'audio')

  # creates a list of languages w/o country codes
  languages = [as_language(l.alpha3b) for l in languages]

  # now, let's handle the default audio bands
  default_audio = _get_default_audio_stream(audio_streams, languages)
  default_lang = _get_stream_language(default_audio)
  default_channels = int(default_audio.attrib['channels'])
  mapping[default_audio]['index'] = 1
  mapping[default_audio]['disposition'] = 'default' #audible by default

  # if the default audio is already in AAC, just copy it
  _copy_or_transcode(default_audio, ['aac'], 'aac', mapping[default_audio])

  secondary_audio = [s for s in audio_streams if s != default_audio]

  ios_stream = None

  if ios_audio and default_channels > 2:

    # tries to find a stream, with the same language as the default audio
    # stream, but with only 2 audio channels (stereo), that is still encoded as
    # AAC or AC3. copy that prioritarily if available
    for s in secondary_audio:
      if ios_stream is not None: break
      if default_lang == _get_stream_language(s) and \
          int(s.attrib['channels']) == 2:
        ios_stream = s #found it
        mapping[s]['index'] = 2
        mapping[s]['disposition'] = 'none' # not audible by default
        _copy_or_transcode(s, ['ac3', 'aac'], 'aac', mapping[s])

    # if, at this point, ios_stream was not found, transcode from the default
    # audio stream
    if ios_stream is None:
      logger.info('iOS audio stream is encoded in %s (channels = %s) - ' \
          'transcoding to aac, profile = LC, channels = 2, language = %s',
          default_audio.attrib['codec_name'], default_audio.attrib['channels'],
          default_lang.alpha3b)
      mapping['__ios__'] = {'original': default_audio}
      mapping['__ios__']['index'] = 2
      mapping['__ios__']['codec'] = 'aac'
      mapping['__ios__']['disposition'] = 'none'

  else:
    logger.info('Skipping creation of optimized iOS audio track')

  # Secondary audio streams

  # Exclude used iOS audio stream
  secondary_audio = [s for s in secondary_audio if s != ios_stream]

  if not preserve_all:
    # remove anything that is in the main language
    secondary_audio = [s for s in secondary_audio \
        if _get_stream_language(s) not in (UNDETERMINED_LANGUAGE, default_lang)]

    # re-organize the input languages to that the default language, which
    # already has 1 or 2 streams guaranteed, does not reappear
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
        _copy_or_transcode(s, ['ac3', 'aac'], 'aac', mapping[s])

    # remove any used stream so we don't iterate over it again
    secondary_audio = [s for s in secondary_audio if s != used_stream]

    # remove any other stream that matches the same language
    secondary_audio = [s for s in secondary_audio \
        if _get_stream_language(s) != k]


def detect_srt_encoding(fname):
  '''Tries to detect the most pertinent encoding for the input SRT file'''

  translator_matrix = {
      'UTF-8-SIG': 'UTF-8',
      }

  with open(fname, 'rb') as f:
    ret = chardet.detect(f.read())
    if ret['encoding'] is not None:
      ret = ret['encoding'].upper()
      return translator_matrix.get(ret, ret)

  return None


def _plan_subtitles(streams, filename, languages, mapping, show,
    ignore_internal):
  '''Creates a transcoding plan for subtitle streams


  Parameters:

    streams (list): A list of :py:class:`xml.etree.ElementTree` objects
      representing all streams available in the file.

    filename (str): Full path leading to the movie original filename. We use
      this path to potentially discover subtitles we will incorporate in the
      final MP4 file. Subtitles are encoded using ``mov_text``.

    languages (list, tuple): The list of all subtitle streams to retain
      according to language, in order of preference. Languages are objects of
      type :py:class:`babefish.Language`. For subtitle tracks, all tracks will
      be off by default (unless ``show`` is set). The order of tracks is
      defined by this variable.

    mapping (dict): Where to place the planning

    show (babelfish.Language): The language of subtitles to display by default.

    ignore_internal (bool): If set to ``True``, then all internal subtitle
      tracks will **not** be considered when looking for language-specific
      subtitles, only external ones, if available.

  '''

  if not ignore_internal:
    subtitle_streams = _get_streams(streams, 'subtitle')
  else:
    subtitle_streams = []

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
      languages = uniq([show] + languages)
  curr_index = len([(k,v) for k,v in mapping.items() if v])

  for k in languages:
    used_stream = None
    for s in subtitle_streams:
      tags = s.findall('tag')
      lang = _get_stream_language(s)
      if lang.alpha3b == k.alpha3b: #ignore country codes as per mp4 standards
        # incorporate stream into the output file
        mapping[s]['index'] = curr_index
        mapping[s]['disposition'] = 'default' if show == k else 'none'
        mapping[s]['language'] = k
        curr_index += 1
        _copy_or_transcode(s, ['mov_text'], 'mov_text', mapping[s])
        used_stream = s
        break #go to the next language, don't pay attention to SRT files

    # already found a stream, continue to the next language
    if used_stream is not None: continue

    # if you get at this point, it is because we never entered the if clause
    # in this case, look for an external subtitle file on the target language
    for var in language_acronyms(k):
      candidate = os.path.splitext(filename)[0] + '.' + var + '.srt'
      if os.path.exists(candidate):
        logger.info('Using external SRT file `%s\' as `%s\' subtitle input',
            candidate, k.alpha3b)
        mapping[candidate] = {'index': curr_index}
        curr_index += 1
        mapping[candidate]['disposition'] = 'default' if show == k else 'none'
        mapping[candidate]['codec'] = 'mov_text'
        mapping[candidate]['language'] = k
        mapping[candidate]['encoding'] = detect_srt_encoding(candidate)
        break

    # remove any used stream so we don't iterate over it again
    subtitle_streams = [s for s in subtitle_streams if s != used_stream]

    # remove any other stream that matches the same language
    subtitle_streams = [s for s in subtitle_streams \
        if _get_stream_language(s) != k]


def plan(probe, languages, default_subtitle_language=None, ios_audio=True,
    preserve_audio_streams=False, ignore_subtitle_streams=False):
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
      to retain, in order of preference. Languages are objects of type
      :py:class:`babelfish.Language`. The audio languages that are available on
      the stream will be selected and organized according to this preference.
      The main audio stream of the file will be kept and will make up audio[0]
      and audio[1] (if ``ios_audio`` is set to ``True``). The following audio
      tracks will be organized as defined. For subtitle tracks, all tracks will
      be off by default. The order of tracks is defined by this variable.

    default_subtitle_language (:py:class:`babelfish.Language`, optional):
      Language of subtitles to show by default. If not set, then don't display
      any subtitle by default.

    ios_audio (:py:class:`bool`, optional): If set to ``True``, then audio[1]
      will contain a stereo AC3 encoded track which is suitable to play on iOS
      devices

    preserve_audio_streams (bool): If set, preserve all audio streams available
      in the selected languages on the output file. If this is not set and we
      have found audio streams matching each of the selected languages, then,
      exceeding audio streams will be dropped (e.g. a director's commentary
      stream). If you want to preserve those, set this flag

    ignore_subtitle_streams (:py:class:`bool`, optional): If set to
      ``True``, then all internal subtitle tracks will **not** be considered
      when looking for language-specific subtitles, only external ones, if
      available.


  Returns:

    dict: A dictionary with the transcoding plan considering all aspects
    related to the movie file and allowing for minimal CPU effort to take
    place. The keys correspond to the stream XML objects. Values are
    dictionaries with properties of the transcoding plan.

  '''

  languages = uniq(languages)

  mapping = {}
  streams = list(probe.iter('stream'))
  for s in streams: mapping[s] = {}

  _plan_video(streams, mapping)
  _plan_audio(streams, languages, ios_audio, preserve_audio_streams, mapping)

  filename = probe.find('format').attrib['filename']
  _plan_subtitles(streams, filename, languages, mapping,
      default_subtitle_language, ignore_subtitle_streams)

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
            _get_stream_language(k).alpha3b, k.attrib['codec_name']))
      continue

    if isinstance(k, six.string_types):
      # either it is an __ios__ stream or an external sub
      if k == '__ios__':
        print('  %s stream [%s] lang=%s codec=%s -> [%d] codec=%s (iOS)' % \
            (v['original'].attrib['codec_type'],
              v['original'].attrib['index'],
              _get_stream_language(v['original'].alpha3b),
              v['original'].attrib['codec_name'],
              v['index'], v['codec']))
      else: #it is a subtitle in srt format
        print('  (%s) lang=%s encoding=%s -> [%d] codec=%s %s' % \
            (os.path.basename(k), v['language'].alpha3b,
              v['encoding'] if v['encoding'] is not None else '??',
              v['index'], v['codec'],
            '**' if v['disposition'] == 'default' else ''))

    else:
      if k.attrib['codec_type'] in ('video', 'subtitle'):
        print('  %s stream [%s] lang=%s codec=%s -> [%d] codec=%s %s' % \
            (k.attrib['codec_type'], k.attrib['index'],
              _get_stream_language(k).alpha3b, k.attrib['codec_name'],
              v['index'], v['codec'],
              '**' if v['disposition'] == 'default' else ''))
      elif k.attrib['codec_type'] == 'audio':
        print('  %s stream [%s] lang=%s codec=%s channels=%s -> [%d] '\
            'codec=%s %s' % \
            (k.attrib['codec_type'], k.attrib['index'],
              _get_stream_language(k).alpha3b, k.attrib['codec_name'],
              k.attrib['channels'], v['index'], v['codec'],
              '**' if v['disposition'] == 'default' else ''))


def options(infile, outfile, planning, threads=0):
  '''Define ffmpeg options to convert the input file into an output file


  Parameters:

    infile (str): The full path leading to the input file to be transcoded

    outfile (str): The full path leading to the output file, where the results
      are going to be stored

    planning (dict): A transcode planning, as defined by by :py:func:`plan`.

    threads (:py:class:`int`, optional): The number of threads for ffmpeg to
      use while transcoding the file. If you set this number to zero (default
      default), then let ffmpeg decide on how many threads to use.

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

      if k == '__ios__': #secondary iOS stream, converted from another one
        mapopt += ['-map', '[iOS]']
        codopt += [
            '-disposition:%d' % v['index'],
            v['disposition'],
            '-codec:%d' % v['index'],
            ] + \
            _audio_codec(v['index'], 2) + \
            [
                # converting from surround (5.1) - this formula comes from:
                # http://atsc.org/wp-content/uploads/2015/03/A52-201212-17.pdf
                '-filter_complex', '[0:%s]pan=stereo|FL<1.0*FL+0.707*FC+' \
                '0.707*BL|FR<1.0*FR+0.707*FC+0.707*BR[iOS]' % \
                v['original'].attrib['index'],
                '-metadata:s:%d' % v['index'],
                'language=%s' % _get_stream_language(v['original']).alpha3b,
            ]

      else: #subtitle SRT to bring in
        if v['encoding'] is not None:
          inopt += ['-sub_charenc', v['encoding']]
        inopt += ['-i', k]
        mapopt += ['-map', str(extsubcnt) + ':0']
        extsubcnt += 1
        codopt += [
            '-disposition:%d' % v['index'], v['disposition'],
            '-codec:%d' % v['index'],
            'mov_text',
            '-metadata:s:%d' % v['index'],
            'language=%s' % v['language'].alpha3b,
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
            'language=%s' % _get_stream_language(k).alpha3b,
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

  def _to_time(ss):
    '''converts a string in the format hh:mm:ss.MM) to time in seconds'''
    h, m, s = ss.split(b':')
    h = int(h) * 60 # in minutes
    m = (h + int(m)) * 60 # in seconds
    return m + float(s)

  ffmpeg = os.path.join(os.path.dirname(sys.executable), 'ffmpeg')

  # checks ffmpeg is there...
  if not os.path.exists(ffmpeg):
    raise IOError('Cannot find ffmpeg executable at `%s\' - did you ' \
        'install it?' % ffmpeg)

  cmd = [ffmpeg] + options
  for k, c in enumerate(cmd):
    if ' ' in c: cmd[k] = "'%s'" % c
  logger.info('Executing `%s\'...' % ' '.join(cmd))
  child = pexpect.spawn(' '.join(cmd))

  else_re = re.compile(b'(?P<all>\s*\S+.*)')
  pattern_list = [pexpect.EOF, else_re]

  if progress > 0:
    frame_re = re.compile(b'frame=\s*(?P<frame>\d+)\s+.*time=\s*(?P<time>[\d\.:]+).*\s+speed=\s*(?P<speed>\d+(\.\d+)?)x\s*')
    pattern_list.insert(1, frame_re)

  cpl = child.compile_pattern_list(pattern_list)

  unit = 'frames' if isinstance(progress, int) else 'secs'
  with tqdm.tqdm(total=progress, disable=not progress, unit=unit) as pbar:
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
        if isinstance(progress, int):
          pbar.update(int(m['frame'])-previous_frame)
          previous_frame = int(m['frame'])
        else:
          secs = _to_time(m['time'])
          pbar.update(secs-previous_frame)
          previous_frame = secs
      elif i == 2 or (i == 1 and progress <= 0): #else_re
        logger.debug("ffmpeg: %s", child.match.string)
