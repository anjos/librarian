#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Shared utilities'''


import os
import io
import sys
import shutil
import logging
import tempfile
import configparser

import guessit
import tmdbsimple as tmdb
import tvdbapi_client
from mutagen.mp4 import MP4, MP4Cover

logger = logging.getLogger(__name__)


def tmdb_key_from_config(fname):
  '''Loads the TMDB API key from configuration file'''

  parser = configparser.ConfigParser()
  parser.read(fname)
  if 'apis' in parser and 'tmdbkey' in parser['apis']:
    return parser['apis']['tmdbkey']
  return None


def setup_tmdb_apikey(user_provided=None):
  '''Sets up the TMDB API key for this session

  This is done by looking to 3 different places in this order of preference:

  1. If the user provided a key via the command-line, use it
  2. If the user has a file called ``.librarianrc`` on the current
     directory, load a config file from it and use the values set on it
  3. If the user has a file called ``.librarianrc`` on ther home
     directory, load a config file from it and use the values set on it

  If no key is found, a :py:exc:`RuntimeError` is raised


  Parameters:

    user_provided (:py:class:`str`, optional): If the user provided a key via
      the application command-line, pass it here


  Raises:

    RuntimeError: In case it cannot find a proper API key for TMDB

  '''

  if user_provided is not None:
    tmdb.API_KEY = user_provided
    return

  if os.path.exists('.librarianrc'):
    key = tmdb_key_from_config('.librarianrc')
    if key is not None:
      tmdb.API_KEY = key
      return

  home_path = os.path.join(os.environ['HOME'], '.librarianrc')
  if os.path.exists(home_path):
    key = tmdb_key_from_config(home_path)
    if key is not None:
      tmdb.API_KEY = key
      return

  raise RuntimeError('Cannot setup TMDB API key')


def tvdb_info_from_config(fname):
  '''Loads the TVDB API key, username and passwd from configuration file'''

  key, user, pwd = None, None, None

  parser = configparser.ConfigParser()
  parser.read(fname)
  if 'apis' in parser:
    if 'tvdbkey' in parser['apis']:
      key = parser['apis']['tvdbkey']
    if 'tvdbuser' in parser['apis']:
      user = parser['apis']['tvdbuser']
    if 'tvdbpass' in parser['apis']:
      pwd = parser['apis']['tvdbpass']
  return key, user, pwd


def setup_tvdb_apikey(key=None, username=None, passwd=None):
  '''Sets up the TVDB API key for this session

  This is done by looking to 3 different places in this order of preference:

  1. If the user provided a username, password and key via the command-line,
     use them
  2. If the user has a file called ``.librarianrc`` on the current
     directory, load a config file from it and use the values set on it
  3. If the user has a file called ``.librarianrc`` on ther home
     directory, load a config file from it and use the values set on it

  If no key is found, a :py:exc:`RuntimeError` is raised


  Parameters:

    key (:py:class:`str`, optional): If the user provided a key via the
      application command-line, pass it here

    username (:py:class:`str`, optional): The user name on TVDB to setup the
      client for

    passwd (:py:class:`str`, optional): The user password on TVDB to setup the
      client for


  Raises:

    RuntimeError: In case it cannot find a proper API key for TMDB

  '''

  if username is None or passwd is None or key is None:
    # try to fetch information from config file
    if os.path.exists('.librarianrc'):
      _apikey, _username, _userpass = tvdb_info_from_config('.librarianrc')
      apikey = apikey or _apikey
      username = username or _username
      passwd = passwd or _userpass
    elif os.path.exists(os.path.join(os.environ['HOME'], '.librarianrc')):
      _apikey, _username, _userpass = \
          tvdb_info_from_config(os.path.join(os.environ['HOME'],
            '.librarianrc'))
      apikey = apikey or _apikey
      username = username or _username
      passwd = passwd or _userpass

  if username is not None and passwd is not None and key is not None:
    return tvdbapi_client.getclient(apikey=key, username=username,
      userpass=passwd)

  raise RuntimeError('Cannot setup TVDB API key/user/pass - missing info')


def setup_logger(name, verbosity):
  '''Sets up the logging of a script


  Parameters:

    name (str): The name of the logger to setup

    verbosity (int): The verbosity level to operate with. A value of ``0``
      (zero) means only errors, ``1``, errors and warnings; ``2``, errors,
      warnings and informational messages and, finally, ``3``, all types of
      messages including debugging ones.

  '''

  logger = logging.getLogger(name)
  formatter = logging.Formatter("%(name)s@%(asctime)s -- %(levelname)s: " \
      "%(message)s")

  _warn_err = logging.StreamHandler(sys.stderr)
  _warn_err.setFormatter(formatter)
  _warn_err.setLevel(logging.WARNING)

  class _InfoFilter:
    def filter(self, record): return record.levelno <= logging.INFO
  _debug_info = logging.StreamHandler(sys.stdout)
  _debug_info.setFormatter(formatter)
  _debug_info.setLevel(logging.DEBUG)
  _debug_info.addFilter(_InfoFilter())

  logger.addHandler(_debug_info)
  logger.addHandler(_warn_err)


  logger.setLevel(logging.ERROR)
  if verbosity == 1: logger.setLevel(logging.WARNING)
  elif verbosity == 2: logger.setLevel(logging.INFO)
  elif verbosity >= 3: logger.setLevel(logging.DEBUG)

  return logger


def guess(filename, fullpath=True):
  '''From a given filename try to guess movie TV show information

  This function will try to guess movie title, TV show episode number, etc


  Parameters:

    filename (str): The name of the file being guessed, including, possibly,
      its fullpath

    fullpath (:py:obj:`bool`, optional): If set, the movie name will be guessed
      using the full path leading to the movie file


  Returns:

    dict: A dictionary containing the parts of the movie or TV show
    filename/path that was parsed

  '''

  if not fullpath:
    filename = os.path.basename(filename)

  return guessit.guessit(filename)


def record_from_query(query, year=None):
  '''Retrieves the TMDB or TVDB record using the provided query string

  This function uses the tmdbsimple package to retrieve information from TMDB.
  You should set the API key adequately on that module before calling it.


  Parameters:

    query (dict): An arbitrary query string
    year (:py:class:`int`, optional): If set, then


  Returns:

    dict: A complete record from TMDB or TVDB, depending if the guess pointed
    to a movie or TV show episode

  '''

  search = tmdb.Search()
  args = dict(query=query)
  if year is not None: args['year'] = year
  logger.info('Searching TMDB for `%s\'', query)
  response = search.movie(**args)
  logger.info('Retrieving information for movie id=`%d\'',
      response['results'][0]['id'])
  retval = tmdb.Movies(response['results'][0]['id'])

  # trigger downloading of a few resources
  retval.info() #basic movie information
  retval.credits() #cast
  retval.releases() #ratings in US

  return retval


def record_from_guess(guess):
  '''Retrieves the TMDB or TVDB record using the provided guess

  This function uses the tmdbsimple package to retrieve information from TMDB.
  You should set the API key adequately on that module before calling it.


  Parameters:

    guess (dict): A dictionary containing the guessed information from the
      movie or TV show episode


  Returns:

    dict: A complete record from TMDB or TVDB, depending if the guess pointed
    to a movie or TV show episode

  '''

  return record_from_query(guess['title'], guess.get('year'))


def _make_xml(movie):
  '''Builds an XML string with movie information'''

  logger.debug('Building XML info tree...')

  header = b"<?xml version=\"1.0\" encoding=\"UTF-8\"?><!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\"><plist version=\"1.0\"><dict>\n"

  output = io.BytesIO()
  output.write(header)

  # Write actors
  output.write(b"<key>cast</key><array>\n")
  for a in movie.cast[:5]:
    output.write(b"<dict><key>name</key><string>%s</string></dict>\n" % a['name'].encode('ascii', 'ignore'))
  output.write(b'</array>')

  # Write screenwriters
  output.write(b"<key>screenwriters</key><array>\n")
  for w in [k for k in movie.crew if k['department'] == 'Writing']:
    output.write(b"<dict><key>name</key><string>%s</string></dict>\n" % w['name'].encode('ascii', 'ignore'))
  output.write(b'</array>')

  # Write directors
  output.write(b"<key>directors</key><array>\n")
  for d in [k for k in movie.crew if k['department'] == 'Directing']:
    output.write(b"<dict><key>name</key><string>%s</string></dict>\n" % d['name'].encode('ascii', 'ignore'))
  output.write(b'</array>')

  # Write producers
  output.write(b"<key>producers</key><array>\n")
  for p in [k for k in movie.crew if k['department'] == 'Production']:
    output.write(b"<dict><key>name</key><string>%s</string></dict>\n" % p['name'].encode('ascii', 'ignore'))
  output.write(b'</array>')

  output.write(b"</dict></plist>\n")

  return output.getvalue()


def _get_image(movie):
  '''Downloads an image associated to a movie into a pre-opened file'''

  import urllib.request

  url = 'http://image.tmdb.org/t/p/w500' + movie.poster_path
  logger.debug('Trying to retrieve image at %s', url)
  return urllib.request.urlopen(url).read()


def _us_certification(movie):
  '''Outputs the string for MPAA certification, if available'''

  ratings_us = [k for k in movie.countries if k['iso_3166_1'] == 'US']
  if ratings_us and ratings_us[0].get('certification') is not None and \
      ratings_us[0].get('certification') in ('G','PG','PG-13','R''NC-17'):
    value = ratings_us[0].get('certification')
    numerical = {
        'G': '100',
        'PG': '200',
        'PG-13': '300',
        'R': '400',
        'NC-17': '500',
        }[value]
    return 'mpaa|' + value.capitalize() + '|' + numerical + '|'


def retag_movie(filename, movie):
  '''Re-tags an MP4 file with information from the movie record


  Parameters:

    filename (str): The full path to the movie file to be re-tagged

    movie (obj): An object returned by the TMDB API implementation containing
      all fields required to retag the movie

  '''

  logger.info("Tagging file: %s" % filename)
  video = MP4(filename)

  try:
    video.delete()
    logger.debug("Successfuly deleted currently existing tags on file")
  except IOError:
    logger.warn("Unable to clear original tags, attempting to proceed...")

  video["\xa9nam"] = movie.title
  video["desc"] = movie.tagline
  video["ldes"] = movie.overview
  video["\xa9day"] = movie.release_date
  video["stik"] = [9]  # Movie iTunes category
  #video["hdvd"] = self.HD
  video["\xa9gen"] = movie.genres[0]['name']
  video["----:com.apple.iTunes:iTunMOVI"] = _make_xml(movie)

  # tries to add US certification to the movie
  us_cert = _us_certification(movie)
  if us_cert is not None:
    video["----:com.apple.iTunes:iTunEXTC"] = us_cert.encode('ascii', 'ignore')

  if hasattr(movie, 'poster_path'):
    bindata = _get_image(movie)
    if movie.poster_path.endswith('.png'):
      video["covr"] = [MP4Cover(bindata, MP4Cover.FORMAT_PNG)]
    else:
      video["covr"] = [MP4Cover(bindata, MP4Cover.FORMAT_JPEG)]
    logger.info('Finally saving tags to file...')

  video.save()

  logger.info("Tags written successfully")
