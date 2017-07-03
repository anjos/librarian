#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Test units'''

import os
import tempfile
import pkg_resources
from xml.etree import ElementTree
import nose.tools
from mutagen import mp4

from . import tmdb, utils

tmdb.setup_apikey()


def test_guess_movie_onlyname():

  info = utils.guess('/Volumes/My Movies/Star Wars: Rogue One (2016).mp4',
      fullpath=False)

  nose.tools.eq_(info['title'], 'Star Wars: Rogue One')
  nose.tools.eq_(info['year'] , 2016)
  nose.tools.eq_(info['type'] , 'movie')
  nose.tools.eq_(info['container'], 'mp4')


def test_guess_movie_fullpath():

  info = utils.guess('/Volumes/Volume Name/Star Wars Revenge of the Sith 2005/movie.mp4', fullpath=True)

  nose.tools.eq_(info['title'], 'Star Wars Revenge of the Sith')
  nose.tools.eq_(info['year'], 2005)
  nose.tools.eq_(info['type'] , 'movie')
  nose.tools.eq_(info['container'], 'mp4')


def test_guess_tv_show_onlyname():

  info = utils.guess('/Volumes/TV Shows/Friends/Season 1/friends.s01e01.720p.Blu-Ray.DD5.1.x264-BS.mkv', fullpath=False)

  nose.tools.eq_(info['title'], 'friends')
  nose.tools.eq_(info['season'], 1)
  nose.tools.eq_(info['episode'], 1)
  nose.tools.eq_(info['container'], 'mkv')
  nose.tools.eq_(info['type'], 'episode')


def test_guess_tv_show_fullpath():

  info = utils.guess('/Volumes/Friends/Season 1/episode-01.mkv', fullpath=True)

  nose.tools.eq_(info['title'], 'Friends')
  nose.tools.eq_(info['season'], 1)
  nose.tools.eq_(info['episode'], 1)
  nose.tools.eq_(info['container'], 'mkv')
  nose.tools.eq_(info['type'], 'episode')


def test_tmdb_from_query():

  movie = tmdb.record_from_query('Star Wars Episode II')

  nose.tools.eq_(movie.title, 'Star Wars: Episode II - Attack of the Clones')
  nose.tools.eq_(movie.release_date, '2002-05-15')
  assert hasattr(movie, 'poster_path')
  nose.tools.eq_(movie.original_language, 'en')


def test_tvdb_from_query():

  movie = tmdb.record_from_query('Star Wars Episode II')

  nose.tools.eq_(movie.title, 'Star Wars: Episode II - Attack of the Clones')
  nose.tools.eq_(movie.release_date, '2002-05-15')
  assert hasattr(movie, 'poster_path')
  nose.tools.eq_(movie.original_language, 'en')


def test_tmdb_from_guess():

  info = utils.guess('/Volumes/My Movies/Star Wars: Rogue One (2016).mp4',
      fullpath=False)
  movie = tmdb.record_from_guess(info)

  nose.tools.eq_(movie.title, 'Rogue One: A Star Wars Story')
  nose.tools.eq_(movie.release_date, '2016-12-14')
  assert hasattr(movie, 'poster_path')
  nose.tools.eq_(movie.original_language, 'en')


def test_mp4_tagging():

  movie = tmdb.record_from_query('Star Wars Episode II')
  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'movie.mp4'))
  with tempfile.NamedTemporaryFile() as tmp:
    with open(filename, 'rb') as original: tmp.write(original.read())
    tmp.flush()
    tmp.seek(0)
    tmdb.retag_movie(tmp.name, movie)
    rewritten = mp4.MP4(tmp)
    nose.tools.eq_(rewritten.tags['\xa9nam'][0], movie.title)
    nose.tools.eq_(rewritten.tags['desc'][0], movie.tagline)
    nose.tools.eq_(rewritten.tags['ldes'][0], movie.overview)
    nose.tools.eq_(rewritten.tags['\xa9day'][0], movie.release_date)
    nose.tools.eq_(rewritten.tags['stik'], [9])
    #nose.tools.eq_(rewritten.tags['hdvd"] = self.HD
    nose.tools.eq_(sorted(rewritten.tags['\xa9gen']),
                   sorted([k['name'] for k in movie.genres]))
    us_cert = rewritten.tags["----:com.apple.iTunes:iTunEXTC"][0].decode()
    nose.tools.eq_(us_cert, 'mpaa|PG|200|')

    #ensures we can parse the embedded XML document
    plist = rewritten.tags['----:com.apple.iTunes:iTunMOVI'][0]
    xml = ElementTree.fromstring(plist)
    nose.tools.eq_(xml.tag, 'plist')

    #check cover is present
    covr = rewritten['covr']
    nose.tools.eq_(len(covr), 1)
    covr = covr[0]
    assert len(covr) != 0
