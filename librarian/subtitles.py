#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Utilities for wrapping subliminal in a confortable API'''


import os
import logging
import subliminal
import babelfish

from .utils import load_config_section

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


  Raises:

    RuntimeError: In case it cannot find a proper API key for TMDB

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

  raise RuntimeError('Cannot setup subtitle provider credentials')


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

    languages (list): Defines the languages of your preference. Language
      specification may be provided with 3-character or 2(+2)-character strings
      (e.g.  "fre", "en" or "pt-br"). Subtitles for these languages will be
      downloaded and organized following an english-based 3-character language
      encoding convention (ISO 639-3).

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

  _languages = []
  for k in languages:
    if len(k) == 3: #ISO-639-3
      _languages.append(babelfish.Language.fromalpha3b(k))
    else: #trie IETF conversion
      _languages.append(babelfish.Language.fromietf(k))

  # call APIs once
  logger.info('Contacting subtitle providers...')
  subtitles = subliminal.list_subtitles([video], set(_languages),
      subliminal.core.ProviderPool, providers=providers,
      provider_configs=config)

  def _score(st):
    return subliminal.compute_score(st, video)

  def _matches(st):
    return st.get_matches(video)

  # sort by language and then by score
  logger.info('Sorting subtitles by score...')
  retval = {}
  for k,a in zip(_languages, languages):
    tmp = [(_score(l), l, _matches(l)) for l in subtitles[video] \
        if l.language == k]
    retval[a] = sorted(tmp, key=lambda x: x[0], reverse=True)

  return retval


def print_results(results, languages, limit=None):
  '''Nicely print results from subtitle search in (reversed) scoring order


  Parameters:


    results (dict): A dictionary mapping the languages asked in the input with
      subtitles found on different providers as a result from calling
      :py:func:`search_subtitles`.

    languages (list): Defines the languages of your preference. Language
      specification may be provided with 3-character or 2(+2)-character strings
      (e.g.  "fre", "en" or "pt-br"). Subtitles for these languages will be
      downloaded and organized following an english-based 3-character language
      encoding convention (ISO 639-3).

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

    languages (list): Defines the languages of your preference. Language
      specification may be provided with 3-character or 2(+2)-character strings
      (e.g.  "fre", "en" or "pt-br"). Subtitles for these languages will be
      downloaded and organized following an english-based 3-character language
      encoding convention (ISO 639-3).

    config (dict): A dictionary where the keys represent the various providers
      available and the values correspond to dictionaries with keyword-argument
      parameters that will be used on their constructor

    providers (:py:class:`list`, optional): A list of strings determining
      providers to use for the query. If not set, then use all available
      providers.

  '''

  to_download = []
  for lang in languages:
    if not results[lang]:
      logger.error('Did not find any subtitle for language `%s\'', lang)
      continue
    to_download.append(results[lang][0][1])

  # if you get at this point, we can download the subtitle
  logger.info('Downloading best subtitles...')

  # downloads only the contents of the subtitles
  subliminal.download_subtitles(to_download, subliminal.core.ProviderPool,
      providers=providers, provider_configs=config)

  # stores the subtitles side-by-side with the movie
  logger.info('Saving subtitles in UTF-8 encoding...')
  video = _get_video(filename)
  subliminal.save_subtitles(video, to_download, encoding='UTF-8')
