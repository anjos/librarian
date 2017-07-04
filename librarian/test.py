#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Test units'''

import os
import tempfile
import datetime
import pkg_resources
from xml.etree import ElementTree
import nose.tools
from mutagen import mp4

from . import tmdb, tvdb, utils

tmdb.setup_apikey()
tvdb.setup_apikey()


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
  assert len(movie.poster_path) != 0
  nose.tools.eq_(movie.original_language, 'en')


def test_tvdb_from_query():

  episode = tvdb.record_from_query('Friends', 1, 1)

  nose.tools.eq_(episode.FirstAired, datetime.date(1994, 9, 22))
  nose.tools.eq_(episode.EpisodeName, 'The One Where Monica Gets A Roommate')
  assert len(episode.Overview) != 0
  nose.tools.eq_(episode.Language, 'en')

  season = episode.season

  nose.tools.eq_(season.season_number, 1)
  nose.tools.eq_(len(season), 24)

  show = season.show
  nose.tools.eq_(show.SeriesName, 'Friends')
  nose.tools.eq_(show.Network, 'NBC')
  nose.tools.eq_(show.language, 'en')
  nose.tools.eq_(show.Genre, ['Comedy', 'Romance'])
  nose.tools.eq_(show.ContentRating, 'TV-14')
  assert len(show.Overview) != 0
  assert len(show.poster) != 0


def test_tmdb_from_guess():

  info = utils.guess('/Volumes/My Movies/Star Wars: Rogue One (2016).mp4',
      fullpath=False)
  movie = tmdb.record_from_guess(info)

  nose.tools.eq_(movie.title, 'Rogue One: A Star Wars Story')
  nose.tools.eq_(movie.release_date, '2016-12-14')
  assert len(movie.poster_path) != 0
  nose.tools.eq_(movie.original_language, 'en')


def test_tvdb_from_guess():

  info = utils.guess('/Volumes/My TV Shows/friends.s01e01.the_one_where_monica_gets_a_roommate.mkv', fullpath=False)

  episode = tvdb.record_from_guess(info)

  nose.tools.eq_(episode.FirstAired, datetime.date(1994, 9, 22))
  nose.tools.eq_(episode.EpisodeName, 'The One Where Monica Gets A Roommate')
  assert len(episode.Overview) != 0
  nose.tools.eq_(episode.Language, 'en')

  season = episode.season

  nose.tools.eq_(season.season_number, 1)
  nose.tools.eq_(len(season), 24)

  show = season.show
  nose.tools.eq_(show.SeriesName, 'Friends')
  nose.tools.eq_(show.Network, 'NBC')
  nose.tools.eq_(show.language, 'en')
  nose.tools.eq_(show.Genre, ['Comedy', 'Romance'])
  nose.tools.eq_(show.ContentRating, 'TV-14')
  assert len(show.Overview) != 0
  assert len(show.poster) != 0


def test_mp4_movie_tagging():

  movie = tmdb.record_from_query('Star Wars Episode II')
  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'movie.mp4'))
  with tempfile.NamedTemporaryFile() as tmp:
    with open(filename, 'rb') as original: tmp.write(original.read())
    tmp.flush()
    tmp.seek(0)
    tmdb.retag(tmp.name, movie)
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


def test_mp4_episode_tagging():

  episode = tvdb.record_from_query('Friends', 1, 1) #season 1, episode 1
  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'movie.mp4'))
  with tempfile.NamedTemporaryFile() as tmp:
    with open(filename, 'rb') as original: tmp.write(original.read())
    tmp.flush()
    tmp.seek(0)
    tvdb.retag(tmp.name, episode)
    rewritten = mp4.MP4(tmp)

    nose.tools.eq_(rewritten["tvsh"][0], episode.season.show.SeriesName)
    nose.tools.eq_(rewritten["\xa9nam"][0], episode.EpisodeName)
    nose.tools.eq_(rewritten["tven"][0], episode.EpisodeName)
    assert rewritten["desc"][0].startswith(episode.Overview)
    nose.tools.eq_(rewritten["ldes"][0], episode.Overview)
    nose.tools.eq_(rewritten["tvnn"][0], episode.season.show.Network)
    nose.tools.eq_(rewritten["\xa9day"][0],
        episode.FirstAired.strftime('%Y-%m-%d'))
    nose.tools.eq_(rewritten["tvsn"], [episode.season.season_number])
    nose.tools.eq_(rewritten["disk"], [(episode.season.season_number,
      len(episode.season.show))])
    nose.tools.eq_(rewritten["\xa9alb"][0], '%s, Season %d' % \
        (episode.season.show.SeriesName, episode.season.season_number))
    nose.tools.eq_(rewritten["tves"], [episode.EpisodeNumber])
    nose.tools.eq_(rewritten["trkn"], \
        [(episode.EpisodeNumber, len(episode.season))])
    nose.tools.eq_(rewritten["stik"], [10])
    #nose.tools.eq_(rewritten["hdvd"], self.HD)
    nose.tools.eq_(rewritten["\xa9gen"], episode.season.show.Genre)

    us_cert = rewritten.tags["----:com.apple.iTunes:iTunEXTC"][0].decode()
    nose.tools.eq_(us_cert, 'us-tv|TV-14|500|')

    #ensures we can parse the embedded XML document
    plist = rewritten.tags['----:com.apple.iTunes:iTunMOVI'][0]
    xml = ElementTree.fromstring(plist)
    nose.tools.eq_(xml.tag, 'plist')

    #check cover is present
    covr = rewritten['covr']
    nose.tools.eq_(len(covr), 1)
    covr = covr[0]
    assert len(covr) != 0
