#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Functionality to deal with TMDB information and API'''

import os
import io
import logging
import tmdbsimple as tmdb
from mutagen.mp4 import MP4, MP4Cover

from .utils import var_from_config

logger = logging.getLogger(__name__)


def setup_apikey(user_provided=None):
  '''Sets up the TMDB API key for this session

  This is done by looking to 4 different places in this order of preference:

  1. If the user provided a key via the command-line, use it
  2. If no key was provided, check the environment variable ``TMDB_APIKEY``. If
     that is set, uset it
  3. If 1. and 2. failed and if the user has a file called ``.librarianrc`` on
     the current directory, load a config file from it and use the values set
     on it
  4. If everything else fails and if the user has a file called
     ``.librarianrc`` on ther home directory, load a config file from it and
     use the values set on it


  Parameters:

    user_provided (:py:class:`str`, optional): If the user provided a key via
      the application command-line, pass it here


  Raises:

    RuntimeError: In case it cannot find a proper API key for TMDB

  '''

  if user_provided is not None:
    tmdb.API_KEY = user_provided
    return

  envkey = os.environ.get('TMDB_APIKEY')
  if envkey is not None:
    tmdb.API_KEY = envkey
    return

  if os.path.exists('.librarianrc'):
    key = var_from_config('.librarianrc', 'apikeys', 'tmdb')
    if key is not None:
      tmdb.API_KEY = key
      return

  home_path = os.path.join(os.environ['HOME'], '.librarianrc')
  if os.path.exists(home_path):
    key = var_from_config(home_path, 'apikeys', 'tmdb')
    if key is not None:
      tmdb.API_KEY = key
      return

  raise RuntimeError('Cannot setup TMDB API key')


def record_from_query(query, year=None):
  '''Retrieves the TMDB record using the provided query string

  This function uses the tmdbsimple package to retrieve information from TMDB.
  You should set the API key adequately module before calling it.


  Parameters:

    query (dict): An arbitrary query string
    year (:py:class:`int`, optional): If set, then filter search results by
      year (this value should correspond to the 4-digit julian year - e.g.
      2012)


  Returns:

    obj: An object representing a movie returned from the tmdbsimple API, if a
    match can be found. Otherwise, ``None``.

  '''

  search = tmdb.Search()
  args = dict(query=query)
  if year is not None: args['year'] = year
  logger.info('Searching TMDB for `%s\'', query)
  response = search.movie(**args)
  if response['total_results'] >= 1:
    logger.info('Retrieving information for movie id=`%d\'',
        response['results'][0]['id'])
    retval = tmdb.Movies(response['results'][0]['id'])

    # trigger downloading of a few resources
    retval.info() #basic movie information
    retval.credits() #cast
    retval.releases() #ratings in US
    return retval

  return None


def record_from_guess(guess):
  '''Retrieves the TMDB record using the provided guess

  This function uses the tmdbsimple package to retrieve information from TMDB.
  You should set the API key adequately before calling it.


  Parameters:

    guess (dict): A dictionary containing the guessed information from the
      movie


  Returns:

    obj: An object representing a movie returned from the tmdbsimple API

  '''

  return record_from_query(guess['title'], guess.get('year'))


def _make_apple_plist(movie):
  '''Builds an XML string with movie information

  Returns a string containing a XML document which can be parsed by Apple
  movie players. It contains information about the cast and crew of the movie.

  The XML document is written in a single string with now new-lines. If it
  would be indented, it could look like this:

  .. code-block:: xml

     <?xml version="1.0" encoding="UTF-8"?>
     <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
     <plist version="1.0">
       <dict>
         <key>cast</key>
         <array>
           <dict><key>name</key><string>Ewan McGregor</string></dict>
           <dict><key>name</key><string>Natalie Portman</string></dict>
           <dict><key>name</key><string>Hayden Christensen</string></dict>
           <dict><key>name</key><string>Ian McDiarmid</string></dict>
           <dict><key>name</key><string>Samuel L. Jackson</string></dict>
         </array>
         <key>screenwriters</key>
         <array>
           <dict><key>name</key><string>Jonathan Hales</string></dict>
           <dict><key>name</key><string>George Lucas</string></dict>
         </array>
         <key>directors</key>
         <array>
           <dict><key>name</key><string>George Lucas</string></dict>
           <dict><key>name</key><string>James McTeigue</string></dict>
         </array>
         <key>producers</key>
         <array>
           <dict><key>name</key><string>George Lucas</string></dict>
           <dict><key>name</key><string>Rick McCallum</string></dict>
           <dict><key>name</key><string>Robin Gurland</string></dict>
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
      ElementTree.SubElement(kv, 'string').text = k['name']

  _insert_section('cast', movie.cast[:5])
  all_writers = [k for k in movie.crew if k['department'] == 'Writing']
  _insert_section('screenwriters', all_writers[:5])
  all_directors = [k for k in movie.crew if k['department'] == 'Directing']
  _insert_section('directors', all_directors[:5])
  all_producers = [k for k in movie.crew if k['department'] == 'Production']
  _insert_section('producers', all_producers[:5])

  et = ElementTree.ElementTree(plist)
  et.write(output, encoding='utf-8')

  return output.getvalue()


def _image_url(movie, width=500):
  '''Returns the URL of a movie poster'''

  return ('http://image.tmdb.org/t/p/w%d' + movie.poster_path) % width


def _get_image(movie):
  '''Downloads an image associated to a movie into a pre-opened file'''

  from six.moves import urllib

  url = _image_url(movie)
  logger.debug('Trying to retrieve image at %s', url)
  return urllib.request.urlopen(url).read()


def _us_certification(movie):
  '''Outputs the string for MPAA certification, if available'''

  from .utils import US_CONTENT_RATINGS_APPLE
  ratings_us = [k for k in movie.countries if k['iso_3166_1'] == 'US']
  if ratings_us:
    return US_CONTENT_RATINGS_APPLE[ratings_us[0].get('certification')]
  else:
    return US_CONTENT_RATINGS_APPLE[None]


def _hd_tag(filename):
  '''Calculates the proper HD tag to use given a movie file'''

  from .convert import probe, _get_streams, _get_default_stream
  data = probe(filename)
  streams = list(data.iter('stream'))
  video = _get_default_stream(_get_streams(streams, 'video'), 'video')
  width = int(video.attrib['width'])
  height = int(video.attrib['height'])

  if width >= 1900 or height >= 1060: return '2'
  elif width >= 1260 or height >= 700: return '1'
  return '0'


def pretty_print(filename, movie):
  '''Prints how the movie file is going to be retagged


  Parameters:

    filename (str): The full path to the movie file to be re-tagged

    movie (obj): An object returned by the TMDB API implementation containing
      all fields required to retag the movie

  '''

  hd_tag = _hd_tag(filename)

  print("Filename = %s" % filename)
  print("\xa9nam = %s" % movie.title)
  print("desc = %s" % movie.tagline)
  print("ldes = %s" % movie.overview)
  print("\xa9day = %s" % movie.release_date)
  print("stik = [9] # Movie iTunes category")
  print("hdvd = %s # 0: low res; 1: 720p; 2: 1080p or superior" % hd_tag)
  print("\xa9gen = %s" % ([k['name'] for k in movie.genres],))
  print("covr = %s" % _image_url(movie) if hasattr(movie, 'poster_path') \
      else None)
  print("----:com.apple.iTunes:iTunEXTC = %s" % _us_certification(movie))
  print("----:com.apple.iTunes:iTunMOVI = %s" % _make_apple_plist(movie))


def retag(filename, movie):
  '''Re-tags an MP4 file with information from the movie record


  Parameters:

    filename (str): The full path to the movie file to be re-tagged

    movie (obj): An object returned by the TMDB API implementation containing
      all fields required to retag the movie

  '''

  logger.info("Tagging file: %s" % filename)
  hd_tag = _hd_tag(filename)
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
  video["hdvd"] = [hd_tag]
  video["\xa9gen"] = [k['name'] for k in movie.genres]
  video["----:com.apple.iTunes:iTunMOVI"] = _make_apple_plist(movie)
  video["----:com.apple.iTunes:iTunEXTC"] = _us_certification(movie)

  if hasattr(movie, 'poster_path'):
    bindata = _get_image(movie)
    if movie.poster_path.endswith('.png'):
      video["covr"] = [MP4Cover(bindata, MP4Cover.FORMAT_PNG)]
    else:
      video["covr"] = [MP4Cover(bindata, MP4Cover.FORMAT_JPEG)]
    logger.info('Finally saving tags to file...')

  video.save()

  logger.info("Tags written successfully")
