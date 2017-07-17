#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Utilities for wrapping subliminal in a confortable API'''


import os
import logging
import subliminal
import babelfish
import chardet
import pysrt
import six

from .utils import load_config_section
from .convert import detect_srt_encoding

logger = logging.getLogger(__name__)


def _parse_config_string(s):
  '''Parses the config string to generate a dictionary of key/values'''

  chunks = [k for k in s.split(',') if k]
  return dict([k.split(1) for k in chunks])


def setup_subliminal(user_provided=None):
  '''Sets up subliminal for this session

  This is done by looking to 4 different places in this order of preference:

  1. If the user provided a setup configuration via the command-line, use it
  2. If no key was provided, check the environment variable
     ``SUBTITLES_SETUP``. If that is set, uset it
  3. If 1. and 2. failed and if the user has a file called ``.librarianrc`` on
     the current directory, load a config file from it and use the values set
     on the ``subtitles`` section
  4. If everything else fails and if the user has a file called
     ``.librarianrc`` on ther home directory, load a config file from it and
     use the values set on the ``subtitles`` section

  The following parameters can be provided on the subtitles section:

  .. code-block:: ini

     [subtitles]
     opensubtitles_username = user
     opensubtitles_password = pass
     legendastv_username = user
     legendastv_password = pass
     addic7ed_username = user
     addic7ed_password = pass


  A setup provided by the environment is complex string containing
  ``key=value`` assignments as per above, separated by commas ``,``. For
  example:

  .. code-block:: sh

     $ export SUBTITLES_SETUP='legendastv_username=user,legendastv_password=pass,opensubtitles_username=user,opensubtitles_password=pass'


  .. note::

     In this scheme, your password cannot contain ``=`` (equal) signs.


  Parameters:

    user_provided (:py:class:`str`, optional): If the user provided a setup via
      the application command-line, pass it here. See its description above.


  '''

  config = None
  if user_provided is not None:
    config = _parse_config_string(user_provided)

  envkey = os.environ.get('SUBTITLES_SETUP')
  if config is None and envkey is not None:
    config = _parse_config_string(envkey)

  if config is None and os.path.exists('.librarianrc'):
    config = load_config_section('.librarianrc', 'subtitles')

  home_path = os.path.join(os.environ['HOME'], '.librarianrc')
  if config is None and os.path.exists(home_path):
    config = var_from_config(home_path, 'subtitles')

  def _associate(config):
    '''Associate config parameters with provider names'''
    retval = {}
    for key, val in config.items():
      prov, kw = key.split('_', 1)
      retval.setdefault(prov, {kw: val})[kw] = val
    return retval

  if config:
    # really the worst, since no caching will be performed, but also the easiest
    subliminal.region.configure('dogpile.cache.memory',
        replace_existing_backend=True)
    return _associate(config)

  logger.warn('No subtitle setup was provided - this may limit your search')
  return {}


def _get_video(filename):
  '''Return the subliminal.Video object from the given filename'''

  if os.path.exists(filename):
    logger.info('File `%s\' exists, parsing file contents', filename)
    return subliminal.scan_video(filename)
  else:
    logger.info('File `%s\' does not exist, parsing filename only', filename)
    return subliminal.Video.fromname(filename)


def search(filename, languages, config, providers=None):
  '''Search subtitles for a given filename


  Parameters:

    filename (str): Search subtitles for a given file on the provided languages

    languages (list): Defines the languages of your preference. Each language
      should be an object of type :py:class:`babelfish.Language`. Subtitles for
      these languages will be downloaded and organized following an
      2-character english-based language encoding convention (ISO 639-3),
      possibily with the contry code attached (e.g. "pt-BR", if one is
      available.

    config (dict): A dictionary where the keys represent the various providers
      available and the values correspond to dictionaries with keyword-argument
      parameters that will be used on their constructor

    providers (:py:class:`list`, optional): A list of strings determining
      providers to use for the query. If not set, then use all available
      providers.


  Returns:

    dict: A dictionary mapping the languages asked in the input with subtitles
    found on different providers.

  '''

  video = _get_video(filename)

  # call APIs once
  logger.info('Contacting subtitle providers...')
  subtitles = subliminal.list_subtitles([video], set(languages),
      subliminal.core.ProviderPool, providers=providers,
      provider_configs=config)

  def _score(st):
    try:
      return subliminal.compute_score(st, video)
    except Exception as e:
      logger.warn('subliminal.compute_score() returned an error: %s', e)
      return 0

  def _matches(st):
    try:
      return st.get_matches(video)
    except Exception as e:
      logger.warn('subliminal.get_matches() returned an error: %s', e)
      return ['??']

  # sort by language and then by score
  logger.info('Sorting subtitles by score...')
  retval = {}
  for k in languages:
    tmp = [(_score(l), l, _matches(l)) for l in subtitles[video] \
        if l.language == k]
    retval[k] = sorted(tmp, key=lambda x: x[0], reverse=True)

  return retval


def print_results(results, languages, limit=None):
  '''Nicely print results from subtitle search in (reversed) scoring order


  Parameters:


    results (dict): A dictionary mapping the languages asked in the input with
      subtitles found on different providers as a result from calling
      :py:func:`search_subtitles`.

    languages (list): Defines the languages of your preference. Each language
      should be an object of type :py:class:`babelfish.Language`. Subtitles for
      these languages will be downloaded and organized following an
      2-character english-based language encoding convention (ISO 639-3),
      possibily with the contry code attached (e.g. "pt-BR", if one is
      available.

    limit (:py:class:`int`, optional): Define the maximum number of entries to
      output. If not defined or set to ``None``, then prints all entries.

  '''

  for lang in languages:
    print("  Language `%s':" % lang)
    iterator = results[lang]
    if bool(limit): iterator = iterator[:limit]
    for score, subtitle, matches in iterator:
      print("    [%d] @%s: %s" % (score, subtitle.provider_name,
        ', '.join(matches)))


def download(filename, results, languages, config, providers=None):
  '''Downloads the best matches for each of the input languages found


  Parameters:

    filename (str): Search subtitles for a given file on the provided languages

    results (dict): A dictionary mapping the languages asked in the input with
      subtitles found on different providers as a result from calling
      :py:func:`search_subtitles`.

    languages (list): Defines the languages of your preference. Each language
      should be an object of type :py:class:`babelfish.Language`. Subtitles for
      these languages will be downloaded and organized following an
      2-character english-based language encoding convention (ISO 639-3),
      possibily with the contry code attached (e.g. "pt-BR", if one is
      available.

    config (dict): A dictionary where the keys represent the various providers
      available and the values correspond to dictionaries with keyword-argument
      parameters that will be used on their constructor

    providers (:py:class:`list`, optional): A list of strings determining
      providers to use for the query. If not set, then use all available
      providers.

  '''

  def _check_or_reset(s):
    '''Checks if a subtitle is of type SRT, otherwise, resets it'''

    try:
      if s.content is None: return

      # get a string representation of subtitles
      srt = None
      r = chardet.detect(s.content)
      enc = r['encoding']
      if enc is not None:
        logger.info('Decoding subtitles from `%s\'', enc)
        content = s.content.decode(encoding=enc)
      else:
        logger.warn('Cannot detect subtitle encoding - ignoring errors')
        content = s.content.decode(errors='ignore')

      # checks decoding
      srt = pysrt.SubRipFile.from_string(content)
      if not srt:
        logger.warn('Discarding contents of subtitle: not parseable')
        s.content = None
        return

      # if everything checks, re-write subtitles in utf-8
      srt.clean_indexes()
      buf = six.StringIO()
      srt.write_into(buf)
      s.content = buf.getvalue().encode(encoding='UTF-8')
      s.encoding = 'utf-8'

    except Exception as e:
      logger.warn('Discarding contents of subtitle: %s', e)
      s.content = None


  to_download = []
  lang_download = []
  for lang in languages:
    if not results[lang]:
      logger.error('Did not find any subtitle for language `%s\'', lang)
      continue
    lang_download.append(lang)
    logger.info('Scheduling download subtitle for language `%s%s\' ' \
        'from `%s\' (score: %d)', lang.alpha2,
        '-%s' % lang.country.alpha2.lower() if lang.country else '',
        results[lang][0][1].provider_name, results[lang][0][0])
    to_download.append(results[lang].pop(0)[1])

  # if you get at this point, we can download the subtitle
  logger.info('Downloading subtitles...')

  # checks if the download was successful, otherwise, tries the next sub
  while not all([z.content for z in to_download]):

    subliminal.download_subtitles(to_download, subliminal.core.ProviderPool,
              providers=providers, provider_configs=config)

    # checks the subtitle is in SRT format
    for k in to_download: _check_or_reset(k)

    for k, (lang, dl) in enumerate(zip(lang_download, to_download)):
      if not dl.content:
        logger.warn('Contents for subtitle for language `%s%s\' where not ' \
            'downloaded from `%s\'', lang.alpha2,
          '-%s' % lang.country.alpha2.lower() if lang.country else '',
          dl.provider_name)
        if results[lang]: #there are still some to consider
          to_try = results[lang].pop(0)
          logger.info('Trying next subtitle in list, with score=%d', to_try[0])
          to_download[k] = to_try[1]

  # stores the subtitles side-by-side with the movie
  logger.info('Saving subtitles in UTF-8 encoding...')
  video = _get_video(filename)
  subliminal.save_subtitles(video, to_download, encoding='UTF-8')


def resync_subtitles(fname, start_frame, start_time, end_frame, end_time):
  '''Edits an SRT file to time shift subtitles

  This function will time shift and compress/expand all subtitles timings in an
  SRT file so that the subtitle with the given start frame starts on the
  predefined time. Subsequent subtitles will be re-distributed proportionally
  until the end frame, which will start on ``end_time``.

  In order to implement that, we first calculate the compression/expansion
  factor ratio "R" that will adjust the subtitles frequency. Then, at the new
  compressed/expanded framework, we calculate the time shift "S" required to
  put the start subtitle at the desired time. We then re-adjust all subtitles
  respecting both the ratio "R" and the shift "S". In pseudo-code:

  .. code-block:: python

     R = (end_time - start_time) / (subs[end].start - subs[start].start)
     S = start_time - (subs[start].start * R)
     f = pysrt.SubRipFile(fname)
     f.shift(R, S)

  Once this operation is carried out, we resync subtitles so that frame numbers
  in the file are consecutive and starting at one.


  Parameters:

    fname (str): Full path to the SRT file to edit

    start_index (int): The number of the index (subtitle) to affect for the
      ``start_time``. Notice this is **not** the relative position of the
      subtitle within the SRT file, but rather the index assigned by the
      original author. If a file starts with subtitle #1, then position ``[0]``
      of the file will have ``.index == 1`` and that is the expected number
      here.

    start_time (str): The start time, expressed as a string in the format
      "hh:mm:ss,MMM", from the start of the movie. Values after the comma
      express milliseconds.

    end_frame (int): The number of the frame (subtitle) to affect for the
      ``end_time``. Notice this is **not** the relative position of the
      subtitle within the SRT file, but rather the index assigned by the
      original author. If a file ends with subtitle #1000, then position
      ``[-1]`` of the file will have ``.index == 1000`` and that is the
      expected number here, even if the overall number of entries in the file
      is smaller than 1000.

    end_time (str): The end time, expressed as a string in the format
      "hh:mm:ss,MMM", from the start of the movie. Values after the comma
      express milliseconds.


  Returns:

    pysrt.SubRipFile: Edited subrip file instance you can call ``save()`` on to
    overwrite or export edited timings.


  Raises:

    AssertionError: in case the timings and frame numbers don't respect order
    (i.e.: ``start_frame < end_frame && start_time < end_time``)

  '''

  assert start_frame < end_frame
  start_time = pysrt.SubRipTime.coerce(start_time)
  end_time   = pysrt.SubRipTime.coerce(end_time)
  assert start_time < end_time

  f = pysrt.open(fname, encoding=detect_srt_encoding(fname))

  # organize subtitles by index
  indexed = dict([(k.index, k) for k in f])

  # get the actual indexes of the target frames, coerce time stamps
  start_sub  = indexed[start_frame]
  end_sub    = indexed[end_frame]
  assert start_sub.end < end_sub.start

  logger.info('Start frame #%d [pos=%d] %s --> %s (%s)', start_sub.index,
      f.index(start_sub), start_sub.start, start_time, repr(start_sub.text))
  logger.info('End frame #%d [pos=%d] %s --> %s (%s)', end_sub.index,
      f.index(end_sub), end_sub.start, end_time, repr(end_sub.text))

  # calculates the ratio factor "R"
  new_window = (end_time - start_time).ordinal #in milliseconds
  old_window = (end_sub.start - start_sub.start).ordinal #in milliseconds
  R = float(new_window) / old_window
  logger.info('Compression factor is %s', R)

  # calculates the shift "S" using the "compressed"/"expanded" space
  S = start_time - (start_sub.start * R)
  logger.info('"Compressed/Expanded" time shift is %s', S)

  # applies shift and expansion to all subtitles
  f.shift(hours=S.hours, minutes=S.minutes, seconds=S.seconds,
      milliseconds=S.milliseconds, ratio=R)

  # re-adjusts indexes so f[0].index == 1 and f[-1].index == len(f)
  f.clean_indexes()

  return f


def cleanup_subtitles(fname):
  '''Edits an SRT file to re-index it, write in UTF-8 and clean it up

  In this function, we resync subtitles so that frame numbers in the file are
  consecutive and starting at one. The output file is always saved in UTF-8.


  Parameters:

    fname (str): Full path to the SRT file to edit


  Returns:

    pysrt.SubRipFile: Edited subrip file instance you can call ``save()`` on to
    overwrite or export edited timings.


  '''

  f = pysrt.open(fname, encoding=detect_srt_encoding(fname))
  f.clean_indexes()
  return f
