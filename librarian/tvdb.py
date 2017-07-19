#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Functionality to deal with TVDB information and API'''

import os
import io
import logging
import pytvdbapi.api as tvdb
from mutagen.mp4 import MP4, MP4Cover

from .utils import var_from_config

logger = logging.getLogger(__name__)
server = None


def setup_apikey(user_provided=None):
  '''Sets up the TVDB API key for this session

  This is done by looking to 4 different places in this order of preference:

  1. If the user provided a key via the command-line, use it
  2. If no key was provided, check the environment variable ``TVDB_APIKEY``. If
     that is set, uset it
  3. If 1. and 2. failed and if the user has a file called ``.librarianrc`` on
     the current directory, load a config file from it and use the values set
     on it
  4. If everything else fails and if the user has a file called
     ``.librarianrc`` on ther home directory, load a config file from it and
     use the values set on it

  If no key is found, a :py:exc:`RuntimeError` is raised


  Parameters:

    user_provided (:py:class:`str`, optional): If the user provided a key via
      the application command-line, pass it here


  Raises:

    RuntimeError: In case it cannot find a proper API key for TVDB

  '''

  global server

  if user_provided is not None:
    server = tvdb.TVDB(user_provided)
    return

  envkey = os.environ.get('TVDB_APIKEY')
  if envkey is not None:
    server = tvdb.TVDB(envkey)
    return

  if os.path.exists('.librarianrc'):
    key = var_from_config('.librarianrc', 'apikeys', 'tvdb')
    if key is not None:
      server = tvdb.TVDB(key)
      return

  home_path = os.path.join(os.environ['HOME'], '.librarianrc')
  if os.path.exists(home_path):
    key = var_from_config(home_path, 'apikeys', 'tvdb')
    if key is not None:
      server = tvdb.TVDB(key)
      return

  raise RuntimeError('Cannot setup TVDB API key')


def record_from_query(query, season=1, episode=1, language='en'):
  '''Retrieves the TVDB record for a TV show using the provided query string

  This function uses the pytvdbapi package to retrieve information from TVDB.
  You should set the API key adequately before calling it.


  Parameters:

    query (dict): An arbitrary query string for a TV show name
    season (:py:class:`int`, optional): The number of the season to retrieve
    episode (:py:class:`int`, optional): The number of the episode to retrieve
    language (:py:class:`str`, optional): If set, then filter for TV shows only
      in a particular (original) language. Defaults to ``en`` (english). If
      set, should be the 2-character language specification (ISO 639-1 code).
      Examples are ``pt`` for Portuguese, ``fr`` for French or ``es`` for
      Spanish. A complete list can be found on wikipedia
      (https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)


  Returns:

    obj: An object representing a TV show returned from the pytvdbapi API

  '''

  logger.info('Searching TVDB for `%s\', Season %d, Episode %d ' \
      '(language=`%s\')', query, season, episode, language)
  search = server.search(query, language=language)
  return search[0][season][episode]


def record_from_guess(guess, language='en'):
  '''Retrieves the TVDB record using the provided guess

  This function uses the ``pytvdbapi`` package to retrieve information from
  TVDB. You should set the API key adequately before calling it.


  Parameters:

    guess (dict): A dictionary containing the guessed information from the
      TV show episode
    language (:py:class:`str`, optional): If set, then filter for TV shows only
      in a particular (original) language. Defaults to ``en`` (english). If
      set, should be the 2-character language specification (ISO 639-1 code).
      Examples are ``pt`` for Portuguese, ``fr`` for French or ``es`` for
      Spanish. A complete list can be found on wikipedia
      (https://en.wikipedia.org/wiki/List_of_ISO_639-1_codes)


  Returns:

    obj: An object representing an episode returned from the pytvdbapi API

  '''

  return record_from_query(guess['title'], guess['season'], guess['episode'],
      language)


def _make_apple_plist(episode):
  '''Builds an XML string with episode information

  Returns a string containing a XML document which can be parsed by Apple
  movie players. It contains information about the cast and crew of the TV show
  episode.

  The XML document is written in a single string with now new-lines. If it
  would be indented, it could look like this:

  .. code-block:: xml

     <?xml version="1.0" encoding="UTF-8"?>
     <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
     <plist version="1.0">
       <dict>
         <key>cast</key>
         <array>
           <dict><key>name</key><string>Lisa Kudrow</string></dict>
           <dict><key>name</key><string>Matt LeBlanc</string></dict>
           <dict><key>name</key><string>Matthew Perry</string></dict>
           <dict><key>name</key><string>Courteney Cox</string></dict>
           <dict><key>name</key><string>David Schwimmer</string></dict>
         </array>
         <key>screenwriters</key>
         <array>
           <dict><key>name</key><string>David Crane</string></dict>
           <dict><key>name</key><string>Marta Kauffman</string></dict>
         </array>
         <key>directors</key>
         <array>
           <dict><key>name</key><string>James Burrows</string></dict>
         </array>
       </dict>
     </plist>

  '''

  logger.debug('Building XML info tree...')

  from xml.etree import ElementTree

  header = b'<?xml version="1.0" encoding="UTF-8"?>' \
      b'<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" ' \
      b'"http://www.apple.com/DTDs/PropertyList-1.0.dtd">'

  output = io.BytesIO()
  output.write(header)

  # creates root elements
  plist  = ElementTree.Element('plist', {'version': '1.0'})
  keyval = ElementTree.SubElement(plist, 'dict')

  # inserts a section of
  def _insert_section(name, entries):
    ElementTree.SubElement(keyval, 'key').text = name
    array = ElementTree.SubElement(keyval, 'array')
    for k in entries:
      kv = ElementTree.SubElement(array, 'dict')
      ElementTree.SubElement(kv, 'key').text = 'name'
      ElementTree.SubElement(kv, 'string').text = k

  _insert_section('cast', episode.season.show.Actors[:5])
  _insert_section('screenwriters', episode.Writer)
  _insert_section('directors', [episode.Director])

  et = ElementTree.ElementTree(plist)
  et.write(output, encoding='utf-8')

  return output.getvalue()


def _image_url(episode):
  '''Returns the poster URL for this episode'''

  episode.season.show.load_banners()

  # tries to get the most adequate banner for the season
  season_banners = [k for k in episode.season.show.banner_objects if \
      k.BannerType == 'season' and k.Season == episode.season.season_number]

  if not season_banners:
    return None

  return season_banners[0].banner_url


def _get_image(episode):
  '''Downloads an image associated to a TV show into a pre-opened file'''

  from six.moves import urllib

  url = _image_url(episode)

  if url is None:
    logger.warn('Did not find season cover art for %s, Season %d',
        episode.season.show.SeriesName, episode.season.season_number)
    return None, None

  logger.debug('Trying to retrieve image at %s', url)
  return urllib.request.urlopen(url).read(), url[-4:]


def _us_certification(episode):
  '''Outputs the string for MPAA certification, if available'''

  from .utils import US_CONTENT_RATINGS_APPLE
  return US_CONTENT_RATINGS_APPLE[episode.season.show.ContentRating]


def _make_short_description(overview):
  '''Make a shorter description of the episode overview'''

  max_size = 256

  if overview is None: return ''
  if len(overview) < max_size: return overview

  # get the first few phrases so that the total size is still < 256
  return '.'.join(overview[:max_size].split('.')[:-1]) + '.'


def pretty_print(filename, episode):
  '''Prints how the episode file is going to be retagged


  Parameters:

    filename (str): The full path to the movie file to be re-tagged

    episode (obj): An object returned by the TVDB API implementation containing
      all fields required to retag the TV show episode

  '''

  from .tmdb import _hd_tag
  hd_tag = _hd_tag(filename)

  print("tvsh = %s" % episode.season.show.SeriesName)
  print("\xa9nam = %s" % episode.EpisodeName)
  print("tven = %s" % episode.EpisodeName)
  print("desc = %s" % _make_short_description(episode.Overview))
  print("ldes = %s" % episode.Overview)
  print("tvnn = %s" % episode.season.show.Network)
  print("\xa9day = %s" % episode.FirstAired.strftime('%Y-%m-%d'))
  print("tvsn = %s" % episode.season.season_number)
  print("disk = %s" % [(episode.season.season_number,
    len(episode.season.show))])
  print("\xa9alb = %s" % '%s, Season %d' % (episode.season.show.SeriesName,
      episode.season.season_number))
  print("tves = %s" % [episode.EpisodeNumber])
  print("trkn = %s" % [(episode.EpisodeNumber, len(episode.season))])
  print("stik = %s # TV show iTunes category" % 10)
  print("hdvd = %s" % hd_tag)
  print("\xa9gen = %s" % episode.season.show.Genre)
  print("covr = %s" % _image_url(episode))
  print("----:com.apple.iTunes:iTunEXTC = %s" % _us_certification(episode))
  print("----:com.apple.iTunes:iTunMOVI = %s" % _make_apple_plist(episode))


def retag(filename, episode):
  '''Re-tags an MP4 file with information from the episode record


  Parameters:

    filename (str): The full path to the TV show episode file to be re-tagged

    episode (obj): An object returned by the TVDB API implementation containing
      all fields required to retag the TV show episode

  '''
  from .tmdb import _hd_tag

  logger.info("Tagging file: %s" % filename)
  hd_tag = _hd_tag(filename)
  video = MP4(filename)

  try:
    video.delete()
    logger.debug("Successfuly deleted currently existing tags on file")
  except IOError:
    logger.warn("Unable to clear original tags, attempting to proceed...")

  video["tvsh"] = episode.season.show.SeriesName
  video["\xa9nam"] = episode.EpisodeName
  video["tven"] = episode.EpisodeName
  video["desc"] = _make_short_description(episode.Overview)
  video["ldes"] = episode.Overview
  video["tvnn"] = episode.season.show.Network
  video["\xa9day"] = episode.FirstAired.strftime('%Y-%m-%d')
  video["tvsn"] = [episode.season.season_number]
  video["disk"] = [(episode.season.season_number, len(episode.season.show))]
  video["\xa9alb"] = '%s, Season %d' % (episode.season.show.SeriesName,
      episode.season.season_number)
  video["tves"] = [episode.EpisodeNumber]
  video["trkn"] = [(episode.EpisodeNumber, len(episode.season))]
  video["stik"] = [10]  # TV show iTunes category
  video["hdvd"] = [hd_tag]
  video["\xa9gen"] = episode.season.show.Genre
  video["----:com.apple.iTunes:iTunMOVI"] = _make_apple_plist(episode)
  video["----:com.apple.iTunes:iTunEXTC"] = _us_certification(episode)

  bindata, imtype = _get_image(episode)
  if bindata is not None:
    if imtype == '.png':
      video["covr"] = [MP4Cover(bindata, MP4Cover.FORMAT_PNG)]
    else:
      video["covr"] = [MP4Cover(bindata, MP4Cover.FORMAT_JPEG)]

  logger.info('Finally saving tags to file...')
  video.save()
  logger.info("Tags written successfully")
