#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Test units'''

import os
import sys
import six
import shutil
import tempfile
import datetime
import contextlib
import pkg_resources
from xml.etree import ElementTree
import nose.tools
from mutagen import mp4
import pysrt

from . import tmdb, tvdb, utils, convert, subtitles


def setup_apikeys():
  tmdb.setup_apikey()
  tvdb.setup_apikey()


@contextlib.contextmanager
def diverge_stdout_to_null():
  buf = sys.stdout
  f = open(os.devnull, 'w')
  sys.stdout = f
  yield
  sys.stdout = buf #re-stores stdout


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


@nose.tools.with_setup(setup_apikeys)
def test_tmdb_from_query():

  movie = tmdb.record_from_query('Star Wars Episode II')

  nose.tools.eq_(movie.title, 'Star Wars: Episode II - Attack of the Clones')
  nose.tools.eq_(movie.release_date, '2002-05-15')
  assert len(movie.poster_path) != 0
  nose.tools.eq_(movie.original_language, 'en')


@nose.tools.with_setup(setup_apikeys)
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


@nose.tools.with_setup(setup_apikeys)
def test_tmdb_from_guess():

  info = utils.guess('/Volumes/My Movies/Star Wars: Rogue One (2016).mp4',
      fullpath=False)
  movie = tmdb.record_from_guess(info)

  nose.tools.eq_(movie.title, 'Rogue One: A Star Wars Story')
  nose.tools.eq_(movie.release_date, '2016-12-14')
  assert len(movie.poster_path) != 0
  nose.tools.eq_(movie.original_language, 'en')


@nose.tools.with_setup(setup_apikeys)
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


@nose.tools.with_setup(setup_apikeys)
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


@nose.tools.with_setup(setup_apikeys)
def test_mp4_movie_pretty_printing():

  movie = tmdb.record_from_query('Star Wars Episode II')
  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'movie.mp4'))
  with tempfile.NamedTemporaryFile() as tmp:
    with open(filename, 'rb') as original: tmp.write(original.read())
    tmp.flush()
    tmp.seek(0)
    with diverge_stdout_to_null():
      tmdb.pretty_print(tmp.name, movie)


@nose.tools.with_setup(setup_apikeys)
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


@nose.tools.with_setup(setup_apikeys)
def test_mp4_episode_pretty_printing():

  episode = tvdb.record_from_query('Friends', 1, 1) #season 1, episode 1
  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'movie.mp4'))
  with tempfile.NamedTemporaryFile() as tmp:
    with open(filename, 'rb') as original: tmp.write(original.read())
    tmp.flush()
    tmp.seek(0)
    with diverge_stdout_to_null():
      tvdb.pretty_print(tmp.name, episode)


def test_ffprobe():

  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'movie.mp4'))

  data = convert.probe(filename)

  nose.tools.eq_(data.tag, 'ffprobe')
  stream = list(data.iter('stream'))
  nose.tools.eq_(len(stream), 2)

  video = [s for s in stream if s.attrib['codec_type'] == 'video'][0]
  audio = [s for s in stream if s.attrib['codec_type'] == 'audio'][0]

  # stream zero
  nose.tools.eq_(video.attrib['codec_name'], 'h264')
  nose.tools.eq_(video.attrib['codec_type'], 'video')
  nose.tools.eq_(video.attrib['width'], '560')
  nose.tools.eq_(video.attrib['height'], '320')
  nose.tools.eq_(video.attrib['pix_fmt'], 'yuv420p')
  assert float(video.attrib['duration']) > 5.5 #5.533333
  nose.tools.eq_(video.attrib['bit_rate'], '465641')
  nose.tools.eq_(video.attrib['nb_frames'], '166')
  nose.tools.eq_(video.attrib['nb_frames'], '166')

  video_disp = video.find('disposition')
  nose.tools.eq_(video_disp.attrib['default'], '1')
  video_tags = video.findall('tag')
  video_lang = [t for t in video_tags if t.attrib['key'] == 'language'][0]
  nose.tools.eq_(video_lang.attrib['value'], 'und')

  # stream one
  nose.tools.eq_(audio.attrib['codec_name'], 'aac')
  nose.tools.eq_(audio.attrib['codec_type'], 'audio')
  nose.tools.eq_(audio.attrib['channels'], '1')
  assert float(audio.attrib['duration']) > 5.5 #5.568000
  nose.tools.eq_(audio.attrib['bit_rate'], '83050')
  nose.tools.eq_(audio.attrib['nb_frames'], '261')

  audio_disp = audio.find('disposition')
  nose.tools.eq_(audio_disp.attrib['default'], '1')
  audio_tags = audio.findall('tag')
  audio_lang = [t for t in audio_tags if t.attrib['key'] == 'language'][0]
  nose.tools.eq_(audio_lang.attrib['value'], 'eng')

  # container info
  fmt = data.find('format')
  nose.tools.eq_(fmt.attrib['filename'], filename)
  nose.tools.eq_(fmt.attrib['nb_streams'], '2')
  nose.tools.eq_(fmt.attrib['format_name'], 'mov,mp4,m4a,3gp,3g2,mj2')
  assert float(fmt.attrib['duration']) > 5.5
  nose.tools.eq_(fmt.attrib['bit_rate'], '551193')


def test_language_conversion():

  def _check(lang, a3, a3b, a2, name, country):
    l = utils.as_language(lang)
    nose.tools.eq_(l.alpha3, a3) #language specific name
    nose.tools.eq_(l.alpha3b, a3b) #international name (english)
    nose.tools.eq_(l.alpha2, a2) #2-letter code
    nose.tools.eq_(l.name, name) #2-letter code
    nose.tools.eq_(l.country, country) #abbreviation of country name

  _check('por',   'por', 'por', 'pt', 'Portuguese', None)
  _check('pt-br', 'por', 'por', 'pt', 'Portuguese', 'BR')
  _check('deu',   'deu', 'ger', 'de', 'German',     None)
  _check('ger',   'deu', 'ger', 'de', 'German',     None)
  _check('fre',   'fra', 'fre', 'fr', 'French',     None)
  _check('fra',   'fra', 'fre', 'fr', 'French',     None)
  _check('eng',   'eng', 'eng', 'en', 'English',    None)
  _check('en-us', 'eng', 'eng', 'en', 'English',    'US')
  _check('en',    'eng', 'eng', 'en', 'English',    None)
  _check('en-gb', 'eng', 'eng', 'en', 'English',    'GB')
  _check('spa',   'spa', 'spa', 'es', 'Spanish',    None)
  _check('es-es', 'spa', 'spa', 'es', 'Spanish',    'ES')

  # special case for an undetermined language
  l = utils.as_language('und')
  nose.tools.eq_(l.alpha3, 'und') #language specific name
  nose.tools.eq_(l.alpha3b, 'und') #international name (english)
  nose.tools.eq_(l.name, 'Undetermined') #2-letter code
  nose.tools.eq_(l.country, None)


def test_language_acronyms():

  def _check(lang, acronyms):
    l = utils.as_language(lang)
    nose.tools.eq_(utils.language_acronyms(l), acronyms)

  _check('por',   ['pt', 'por'])
  _check('pt-br', ['pt-BR', 'pt-br', 'ptBR', 'ptbr', 'pt', 'por'])
  _check('eng',   ['en', 'eng'])
  _check('en-us', ['en-US', 'en-us', 'enUS', 'enus', 'en', 'eng'])
  _check('en-gb', ['en-GB', 'en-gb', 'enGB', 'engb', 'en', 'eng'])
  _check('fr-CA', ['fr-CA', 'fr-ca', 'frCA', 'frca', 'fr', 'fre', 'fra'])
  _check('deu', ['de', 'ger', 'deu'])


def test_planning_mkv_1():

  # organization of the test file (french original movie with default english
  # subtitles):
  # Stream[0] - video, h.264 codec, default
  # Stream[1] - audio, mp3 codec, 2 channels, language = fre, default
  # Stream[2] - audio, aac codec, 2 channels, language = eng
  # Stream[3] - subtitle, subrip codec, language = und, default
  # External: movie.eng.srt alongside

  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'mkv_1', 'probe.xml'))

  # given an input file in MKV format and external SRT files, plans for MP4
  # transcoding
  with open(filename, 'rt') as f:
    probe = ElementTree.fromstring(f.read())

  # adjust filename as we don't know where we're installed
  moviefile = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'mkv_1', 'movie.mkv'))
  probe.find('format').attrib['filename'] = moviefile

  languages = [utils.as_language(k) for k in ['en-gb', 'fra']]
  planning = convert.plan(probe, languages=languages, ios_audio=True,
      default_subtitle_language=languages[0])
  keeping = [(k,v) for k,v in planning.items() if v]
  deleting = [(k,v) for k,v in planning.items() if not v]
  sorted_planning = sorted(keeping, key=lambda k: k[1]['index'])

  # we should be throwing away 1 single stream which is an untitled subtitle
  nose.tools.eq_(len(deleting), 1)
  nose.tools.eq_(deleting[0][0].attrib['codec_type'], 'subtitle')
  nose.tools.eq_(len(deleting[0][1]), 0)

  # this should be the video stream
  video, opts = sorted_planning[0]
  nose.tools.eq_(video.attrib['codec_type'], 'video')
  nose.tools.eq_(opts['index'], 0)
  nose.tools.eq_(opts['codec'], 'copy')
  nose.tools.eq_(opts['disposition'], 'default')

  # this should be the 2-channel audio stream, english, in AAC format
  audio, opts = sorted_planning[1]
  assert 'aac' in audio.attrib['codec_name']
  nose.tools.eq_(audio.attrib['codec_type'], 'audio')
  nose.tools.eq_(audio.attrib['channels'], '2')
  nose.tools.eq_(audio.attrib['index'], '2')
  nose.tools.eq_(opts['index'], 1)
  nose.tools.eq_(opts['codec'], 'copy')
  nose.tools.eq_(convert._get_stream_language(audio).alpha3b,
      languages[0].alpha3b)
  nose.tools.eq_(opts['disposition'], 'default')

  # the 3rd stream should be the french dubbed version, not in AAC encoded
  audio, opts = sorted_planning[2]
  assert 'aac' not in audio.attrib['codec_name']
  nose.tools.eq_(audio.attrib['codec_type'], 'audio')
  nose.tools.eq_(audio.attrib['channels'], '2')
  nose.tools.eq_(audio.attrib['index'], '1')
  nose.tools.eq_(opts['index'], 2)
  nose.tools.eq_(opts['codec'], 'aac')
  nose.tools.eq_(convert._get_stream_language(audio).alpha3b,
      languages[1].alpha3b)
  nose.tools.eq_(opts['disposition'], 'none')

  # the 4th stream should be an external SRT subtitle in english
  subt, opts = sorted_planning[3]
  assert isinstance(subt, six.string_types)
  assert subt.endswith('en-GB.srt')
  nose.tools.eq_(opts['index'], 3)
  nose.tools.eq_(opts['codec'], 'mov_text')
  nose.tools.eq_(opts['language'], languages[0])
  nose.tools.eq_(opts['disposition'], 'default')


def test_planning_mkv_2():

  # organization of the test file (french original movie with default english
  # subtitles):
  # Stream[0] - video, h.264 codec, default
  # Stream[1] - audio, aac codec, 6 channels, language = eng, default
  # Stream[2] - audio, aac codec, 2 channels, language = fre
  # Stream[3] - audio, aac codec, 2 channels, language = eng
  # Stream[4] - subtitle, subrip codec, language = fre, default
  # External: movie.eng.srt alongside
  # External: movie.fre.srt alongside

  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'mkv_2', 'probe.xml'))

  # given an input file in MKV format and external SRT files, plans for MP4
  # transcoding
  with open(filename, 'rt') as f:
    probe = ElementTree.fromstring(f.read())

  # adjust filename as we don't know where we're installed
  moviefile = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'mkv_2', 'movie.mkv'))
  probe.find('format').attrib['filename'] = moviefile

  languages = [utils.as_language(k) for k in ['eng', 'fra']]
  planning = convert.plan(probe, languages=languages, ios_audio=True)
  keeping = [(k,v) for k,v in planning.items() if v]
  deleting = [(k,v) for k,v in planning.items() if not v]
  sorted_planning = sorted(keeping, key=lambda k: k[1]['index'])

  # we should not be throwing away anything
  nose.tools.eq_(len(deleting), 0)

  # this should be the video stream
  video, opts = sorted_planning[0]
  nose.tools.eq_(video.attrib['codec_type'], 'video')
  nose.tools.eq_(opts['index'], 0)
  nose.tools.eq_(opts['codec'], 'copy')
  nose.tools.eq_(opts['disposition'], 'default')

  # this should be the 6-channel audio stream, in AAC
  audio, opts = sorted_planning[1]
  nose.tools.eq_(audio.attrib['codec_type'], 'audio')
  assert 'aac' in audio.attrib['codec_name']
  nose.tools.eq_(audio.attrib['channels'], '6')
  nose.tools.eq_(convert._get_stream_language(audio), languages[0])
  nose.tools.eq_(opts['index'], 1)
  nose.tools.eq_(opts['codec'], 'copy')
  nose.tools.eq_(opts['disposition'], 'default')

  # the 3rd stream should be iOS stream, which will be moved from 4rd position
  audio, opts = sorted_planning[2]
  nose.tools.eq_(audio.attrib['codec_type'], 'audio')
  assert 'aac' in audio.attrib['codec_name']
  nose.tools.eq_(audio.attrib['index'], '3')
  nose.tools.eq_(convert._get_stream_language(audio), languages[0])
  nose.tools.eq_(opts['index'], 2)
  nose.tools.eq_(opts['codec'], 'copy')
  nose.tools.eq_(opts['disposition'], 'none')

  # the 4th stream should be audio in french
  audio, opts = sorted_planning[3]
  nose.tools.eq_(audio.attrib['codec_type'], 'audio')
  nose.tools.eq_(audio.attrib['index'], '2')
  nose.tools.eq_(opts['index'], 3)
  nose.tools.eq_(opts['codec'], 'copy')
  nose.tools.eq_(convert._get_stream_language(audio), languages[1])
  nose.tools.eq_(opts['disposition'], 'none')

  # the 5th stream should be an external SRT subtitle in english
  subt, opts = sorted_planning[4]
  assert isinstance(subt, six.string_types)
  nose.tools.eq_(opts['index'], 4)
  nose.tools.eq_(opts['codec'], 'mov_text')
  nose.tools.eq_(opts['language'], languages[0])
  nose.tools.eq_(opts['disposition'], 'none')

  # the 6th stream should be an internal SRT subtitle in french
  subt, opts = sorted_planning[5]
  nose.tools.eq_(opts['index'], 5)
  nose.tools.eq_(opts['codec'], 'mov_text')
  nose.tools.eq_(opts['language'], languages[1])
  nose.tools.eq_(opts['disposition'], 'none')


def test_planning_mkv_3():

  # organization of the test file (french original movie with default english
  # subtitles):
  # Stream[0] - video, h.264 codec, default
  # Stream[1] - audio, dts codec, 6 channels, language = eng, default
  # Stream[2] - audio, ac3 codec, 2 channels, language = eng
  # Stream[3] - audio, ac3 codec, 2 channels, language = eng
  # Stream[4] - subtitle, hdmv_pgs_subtitle codec, language = eng
  # Stream[5] - subtitle, hdmv_pgs_subtitle codec, language = por
  # Stream[6] - subtitle, hdmv_pgs_subtitle codec, language = dan
  # Stream[7] - subtitle, hdmv_pgs_subtitle codec, language = fin
  # Stream[8] - subtitle, hdmv_pgs_subtitle codec, language = fre
  # Stream[9] - subtitle, hdmv_pgs_subtitle codec, language = ger
  # Stream[10] - subtitle, hdmv_pgs_subtitle codec, language  = spa
  # Stream[11] - subtitle, hdmv_pgs_subtitle codec, language  = dut
  # Stream[12] - subtitle, hdmv_pgs_subtitle codec, language  = nor
  # Stream[13] - subtitle, hdmv_pgs_subtitle codec, language  = swe
  # Stream[14] - subtitle, hdmv_pgs_subtitle codec, language  = eng
  # Stream[15] - subtitle, hdmv_pgs_subtitle codec, language  = dan
  # Stream[16] - subtitle, hdmv_pgs_subtitle codec, language  = fin
  # Stream[17] - subtitle, hdmv_pgs_subtitle codec, language  = fre
  # Stream[18] - subtitle, hdmv_pgs_subtitle codec, language  = ger
  # Stream[19] - subtitle, hdmv_pgs_subtitle codec, language  = dut
  # Stream[20] - subtitle, hdmv_pgs_subtitle codec, language  = nor
  # Stream[21] - subtitle, hdmv_pgs_subtitle codec, language  = swe
  # Stream[22] - subtitle, hdmv_pgs_subtitle codec, language  = eng
  # Stream[23] - subtitle, hdmv_pgs_subtitle codec, language  = dan
  # Stream[24] - subtitle, hdmv_pgs_subtitle codec, language  = fin
  # Stream[25] - subtitle, hdmv_pgs_subtitle codec, language  = fre
  # Stream[26] - subtitle, hdmv_pgs_subtitle codec, language  = ger
  # Stream[27] - subtitle, hdmv_pgs_subtitle codec, language  = dut
  # Stream[28] - subtitle, hdmv_pgs_subtitle codec, language  = nor
  # Stream[29] - subtitle, hdmv_pgs_subtitle codec, language  = swe

  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'mkv_3', 'probe.xml'))

  # given an input file in MKV format and external SRT files, plans for MP4
  # transcoding
  with open(filename, 'rt') as f:
    probe = ElementTree.fromstring(f.read())

  # adjust filename as we don't know where we're installed
  moviefile = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'mkv_3', 'movie.mkv'))
  probe.find('format').attrib['filename'] = moviefile

  languages = [utils.as_language(k) for k in ['eng', 'por', 'fre']]
  planning = convert.plan(probe, languages=languages, ios_audio=True,
      preserve_audio_streams=False, ignore_subtitle_streams=True)
  keeping = [(k,v) for k,v in planning.items() if v]
  deleting = [(k,v) for k,v in planning.items() if not v]
  sorted_planning = sorted(keeping, key=lambda k: k[1]['index'])

  # we should be throwing away all subtitles plus the 3rd audio track (eng)
  nose.tools.eq_(len(deleting), 27)

  # this should be the video stream
  video, opts = sorted_planning[0]
  nose.tools.eq_(video.attrib['codec_type'], 'video')
  nose.tools.eq_(opts['index'], 0)
  nose.tools.eq_(opts['codec'], 'copy')
  nose.tools.eq_(opts['disposition'], 'default')

  # this should be the 6-channel audio stream, in DTS
  audio, opts = sorted_planning[1]
  nose.tools.eq_(audio.attrib['codec_type'], 'audio')
  assert 'dts' in audio.attrib['codec_name']
  nose.tools.eq_(audio.attrib['channels'], '6')
  nose.tools.eq_(convert._get_stream_language(audio), languages[0])
  nose.tools.eq_(opts['index'], 1)
  nose.tools.eq_(opts['codec'], 'aac')
  nose.tools.eq_(opts['disposition'], 'default')

  # the 3rd stream should be iOS stream, which will be copied as well
  audio, opts = sorted_planning[2]
  nose.tools.eq_(audio.attrib['codec_type'], 'audio')
  assert 'ac3' in audio.attrib['codec_name']
  nose.tools.eq_(audio.attrib['index'], '2')
  nose.tools.eq_(convert._get_stream_language(audio), languages[0])
  nose.tools.eq_(opts['index'], 2)
  nose.tools.eq_(opts['codec'], 'aac')
  nose.tools.eq_(opts['disposition'], 'none')


def test_planning_mkv_3b():

  # organization of the test file (french original movie with default english
  # subtitles):
  # Stream[0] - video, h.264 codec, default
  # Stream[1] - audio, dts codec, 6 channels, language = eng, default
  # Stream[2] - audio, ac3 codec, 2 channels, language = eng
  # Stream[3] - audio, ac3 codec, 2 channels, language = eng
  # Stream[4] - subtitle, hdmv_pgs_subtitle codec, language = eng
  # Stream[5] - subtitle, hdmv_pgs_subtitle codec, language = por
  # Stream[6] - subtitle, hdmv_pgs_subtitle codec, language = dan
  # Stream[7] - subtitle, hdmv_pgs_subtitle codec, language = fin
  # Stream[8] - subtitle, hdmv_pgs_subtitle codec, language = fre
  # Stream[9] - subtitle, hdmv_pgs_subtitle codec, language = ger
  # Stream[10] - subtitle, hdmv_pgs_subtitle codec, language  = spa
  # Stream[11] - subtitle, hdmv_pgs_subtitle codec, language  = dut
  # Stream[12] - subtitle, hdmv_pgs_subtitle codec, language  = nor
  # Stream[13] - subtitle, hdmv_pgs_subtitle codec, language  = swe
  # Stream[14] - subtitle, hdmv_pgs_subtitle codec, language  = eng
  # Stream[15] - subtitle, hdmv_pgs_subtitle codec, language  = dan
  # Stream[16] - subtitle, hdmv_pgs_subtitle codec, language  = fin
  # Stream[17] - subtitle, hdmv_pgs_subtitle codec, language  = fre
  # Stream[18] - subtitle, hdmv_pgs_subtitle codec, language  = ger
  # Stream[19] - subtitle, hdmv_pgs_subtitle codec, language  = dut
  # Stream[20] - subtitle, hdmv_pgs_subtitle codec, language  = nor
  # Stream[21] - subtitle, hdmv_pgs_subtitle codec, language  = swe
  # Stream[22] - subtitle, hdmv_pgs_subtitle codec, language  = eng
  # Stream[23] - subtitle, hdmv_pgs_subtitle codec, language  = dan
  # Stream[24] - subtitle, hdmv_pgs_subtitle codec, language  = fin
  # Stream[25] - subtitle, hdmv_pgs_subtitle codec, language  = fre
  # Stream[26] - subtitle, hdmv_pgs_subtitle codec, language  = ger
  # Stream[27] - subtitle, hdmv_pgs_subtitle codec, language  = dut
  # Stream[28] - subtitle, hdmv_pgs_subtitle codec, language  = nor
  # Stream[29] - subtitle, hdmv_pgs_subtitle codec, language  = swe

  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'mkv_3', 'probe.xml'))

  # given an input file in MKV format and external SRT files, plans for MP4
  # transcoding
  with open(filename, 'rt') as f:
    probe = ElementTree.fromstring(f.read())

  # adjust filename as we don't know where we're installed
  moviefile = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'mkv_3', 'movie.mkv'))
  probe.find('format').attrib['filename'] = moviefile

  languages = [utils.as_language(k) for k in ['eng', 'por', 'fre']]
  planning = convert.plan(probe, languages=languages, ios_audio=True,
      preserve_audio_streams=True, ignore_subtitle_streams=True)
  keeping = [(k,v) for k,v in planning.items() if v]
  deleting = [(k,v) for k,v in planning.items() if not v]
  sorted_planning = sorted(keeping, key=lambda k: k[1]['index'])

  # we should be throwing away all subtitles (only)
  nose.tools.eq_(len(deleting), 26)

  # this should be the video stream
  video, opts = sorted_planning[0]
  nose.tools.eq_(video.attrib['codec_type'], 'video')
  nose.tools.eq_(opts['index'], 0)
  nose.tools.eq_(opts['codec'], 'copy')
  nose.tools.eq_(opts['disposition'], 'default')

  # this should be the 6-channel audio stream, in DTS
  audio, opts = sorted_planning[1]
  nose.tools.eq_(audio.attrib['codec_type'], 'audio')
  assert 'dts' in audio.attrib['codec_name']
  nose.tools.eq_(audio.attrib['channels'], '6')
  nose.tools.eq_(convert._get_stream_language(audio), languages[0])
  nose.tools.eq_(opts['index'], 1)
  nose.tools.eq_(opts['codec'], 'aac')
  nose.tools.eq_(opts['disposition'], 'default')

  # the 3rd stream should be iOS stream, which will be copied as well
  audio, opts = sorted_planning[2]
  nose.tools.eq_(audio.attrib['codec_type'], 'audio')
  assert 'ac3' in audio.attrib['codec_name']
  nose.tools.eq_(audio.attrib['index'], '2')
  nose.tools.eq_(convert._get_stream_language(audio), languages[0])
  nose.tools.eq_(opts['index'], 2)
  nose.tools.eq_(opts['codec'], 'aac')
  nose.tools.eq_(opts['disposition'], 'none')

  # the 4th stream should be an auxiliary english audio stream
  audio, opts = sorted_planning[3]
  nose.tools.eq_(audio.attrib['codec_type'], 'audio')
  assert 'ac3' in audio.attrib['codec_name']
  nose.tools.eq_(audio.attrib['index'], '3')
  nose.tools.eq_(convert._get_stream_language(audio), languages[0])
  nose.tools.eq_(opts['index'], 3)
  nose.tools.eq_(opts['codec'], 'aac')
  nose.tools.eq_(opts['disposition'], 'none')


def test_options_mkv_1():

  # organization of the test file (french original movie with default english
  # subtitles):
  # Stream[0] - video, h.264 codec, default
  # Stream[1] - audio, mp3 codec, 2 channels, language = fre, default
  # Stream[2] - audio, aac codec, 2 channels, language = eng
  # Stream[3] - subtitle, subrip codec, language = und, default
  # External: movie.eng.srt alongside

  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'mkv_1', 'probe.xml'))

  # given an input file in MKV format and external SRT files, plans for MP4
  # transcoding
  with open(filename, 'rt') as f:
    probe = ElementTree.fromstring(f.read())

  # adjust filename as we don't know where we're installed
  moviefile = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'mkv_1', 'movie.mkv'))
  probe.find('format').attrib['filename'] = moviefile

  languages = [utils.as_language(k) for k in ['en-GB', 'fra']]
  planning = convert.plan(probe, languages=languages, ios_audio=True,
      default_subtitle_language=languages[0])

  #convert.print_plan(planning)

  output = os.path.splitext(moviefile)[0] + '.mp4'
  options = convert.options(moviefile, output, planning, threads=2)

  has_libfdk_aac = 'libfdk_aac' in \
      convert.ffmpeg_codec_capabilities()['aac']['description']
  aac_encoder = ['-codec:2', 'libfdk_aac', '-vbr', '4'] if has_libfdk_aac \
      else ['-codec:2', 'aac', '-b:2', '128k']

  expected = [
      '-threads', '2',
      '-fix_sub_duration',
      '-i', moviefile,
      '-i', os.path.splitext(moviefile)[0] + '.en-GB.srt',
      '-map', '0:0',
      '-map', '0:2',
      '-map', '0:1',
      '-map', '1:0',
      '-disposition:0', 'default',
      '-codec:0', 'copy',
      '-disposition:1', 'default',
      '-codec:1', 'copy',
      '-metadata:s:1', 'language=%s' % languages[0].alpha3b,
      '-disposition:2', 'none',
      ] + aac_encoder + [
      '-metadata:s:2', 'language=%s' % languages[1].alpha3b,
      '-disposition:3', 'default',
      '-codec:3', 'mov_text',
      '-metadata:s:3', 'language=%s' % languages[0].alpha3b,
      '-movflags', '+faststart',
      os.path.splitext(moviefile)[0] + '.mp4',
      ]

  nose.tools.eq_(options, expected)


def test_options_mkv_2():

  # organization of the test file (french original movie with default english
  # subtitles):
  # Stream[0] - video, h.264 codec, default
  # Stream[1] - audio, aac codec, 6 channels, language = eng, default
  # Stream[2] - audio, aac codec, 2 channels, language = fre
  # Stream[3] - audio, aac codec, 2 channels, language = eng
  # Stream[4] - subtitle, subrip codec, language = fre, default
  # External: movie.eng.srt alongside
  # External: movie.fre.srt alongside

  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'mkv_2', 'probe.xml'))

  # given an input file in MKV format and external SRT files, plans for MP4
  # transcoding
  with open(filename, 'rt') as f:
    probe = ElementTree.fromstring(f.read())

  # adjust filename as we don't know where we're installed
  moviefile = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'mkv_2', 'movie.mkv'))
  probe.find('format').attrib['filename'] = moviefile

  languages = [utils.as_language(k) for k in ['eng', 'fra']]
  planning = convert.plan(probe, languages=languages, ios_audio=True)

  output = os.path.splitext(moviefile)[0] + '.mp4'
  options = convert.options(moviefile, output, planning, threads=3)

  #convert.print_plan(planning)

  expected = [
      '-threads', '3',
      '-fix_sub_duration',
      '-i', moviefile,
      '-i', os.path.splitext(moviefile)[0] + '.en.srt',
      '-map', '0:0', #video - copy
      '-map', '0:1', #eng audio - copy (6 chan)
      '-map', '0:3', #ios audio - copy
      '-map', '0:2', #fre audio - copy
      '-map', '1:0', #eng subtitles - encode as mov_text
      '-map', '0:4', #fre subtitles - copy
      '-disposition:0', 'default',
      '-codec:0', 'copy',
      '-disposition:1', 'default', #main english 5.1 DTS
      '-codec:1', 'copy',
      '-metadata:s:1', 'language=%s' % languages[0].alpha3b,
      '-disposition:2', 'none', #iOS english, stereo
      '-codec:2', 'copy',
      '-metadata:s:2', 'language=%s' % languages[0].alpha3b,
      '-disposition:3', 'none', #french dubbed
      '-codec:3', 'copy',
      '-metadata:s:3', 'language=%s' % languages[1].alpha3b,
      '-disposition:4', 'none', #subtitles in english
      '-codec:4', 'mov_text',
      '-metadata:s:4', 'language=%s' % languages[0].alpha3b,
      '-disposition:5', 'none', #subtitles in french
      '-codec:5', 'mov_text',
      '-metadata:s:5', 'language=%s' % languages[1].alpha3b,
      '-movflags', '+faststart',
      os.path.splitext(moviefile)[0] + '.mp4',
      ]

  nose.tools.eq_(options, expected)


def test_run_progress():

  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'movie.mp4'))
  #filename = '/Users/andre/Downloads/SampleVideo_1280x720_30mb.mp4'

  probe = convert.probe(filename)
  streams = list(probe.iter('stream'))
  from .convert import _get_default_stream
  video = _get_default_stream(streams, 'video')

  # creates a temporary filename
  tmpout = tempfile.NamedTemporaryFile(suffix='.mkv')
  tmpname = tmpout.name
  del tmpout
  if os.path.exists(tmpname): os.unlink(tmpname)

  # tests we can run our process spawner and track progress
  options = ['-i', filename, '-acodec', 'copy', '-vcodec', 'ffv1', tmpname]

  try:
    retcode = convert.run(options, int(video.attrib['nb_frames']))
    nose.tools.eq_(retcode, 0)
    assert os.path.exists(tmpname)
  finally:
    # always delete temporary file in the end
    if os.path.exists(tmpname): os.unlink(tmpname)


def test_run_no_progress():

  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'movie.mp4'))
  #filename = '/Users/andre/Downloads/SampleVideo_1280x720_30mb.mp4'

  probe = convert.probe(filename)
  streams = list(probe.iter('stream'))
  from .convert import _get_default_stream
  video = _get_default_stream(streams, 'video')

  # creates a temporary filename
  tmpout = tempfile.NamedTemporaryFile(suffix='.mkv')
  tmpname = tmpout.name
  del tmpout
  if os.path.exists(tmpname): os.unlink(tmpname)

  # tests we can run our process spawner and track progress
  options = ['-i', filename, '-acodec', 'copy', '-vcodec', 'ffv1', tmpname]

  try:
    retcode = convert.run(options)
    nose.tools.eq_(retcode, 0)
    assert os.path.exists(tmpname)
  finally:
    # always delete temporary file in the end
    if os.path.exists(tmpname): os.unlink(tmpname)


def check_codec(all_caps, name, ctype):

  assert name in all_caps
  caps = all_caps[name]
  nose.tools.eq_(caps['decode'], True)
  nose.tools.eq_(caps['encode'], True)
  nose.tools.eq_(caps['type'], ctype)


def test_ffmpeg_codecs():

  all_caps = convert.ffmpeg_codec_capabilities()

  check_codec(all_caps, 'ac3', 'audio')
  check_codec(all_caps, 'aac', 'audio')
  check_codec(all_caps, 'h264', 'video')
  check_codec(all_caps, 'mov_text', 'subtitle')
  check_codec(all_caps, 'subrip', 'subtitle')


def test_subtitle_search():

  p = '/path/to/file/Alien.1979.Directors.Cut.Bluray.1080p.DTS-HD.x264-Grym.mkv'
  providers = ['podnapisi']
  languages = [utils.as_language(k) for k in ['en', 'fre']]
  config = subtitles.setup_subliminal()
  results = subtitles.search(p, languages, config, providers=providers)
  assert len(results[languages[0]]) > 0
  assert len(results[languages[1]]) > 0


def test_subtitle_download():

  tempdir = tempfile.mkdtemp()
  providers = ['podnapisi'] #does not need password setup
  languages = [utils.as_language(k) for k in ['en', 'fre']]

  try:
    n = 'Alien.1979.Directors.Cut.Bluray.1080p.DTS-HD.x264-Grym.mkv'
    fn = os.path.join(tempdir, n)
    config = subtitles.setup_subliminal()
    results = subtitles.search(fn, languages, config, providers=providers)
    subtitles.download(fn, results, languages, config, providers=providers)
    en_sub = os.path.join(tempdir, os.path.splitext(n)[0] + '.en.srt')
    assert os.path.exists(en_sub)
    fr_sub = os.path.join(tempdir, os.path.splitext(n)[0] + '.fr.srt')
    assert os.path.exists(fr_sub)

  finally:
    if os.path.exists(tempdir): shutil.rmtree(tempdir)


def _compare_srt_times(t1, t2, diff=1):
  '''Compares times up to a certain amount of milliseconds'''

  assert abs((t1-t2).ordinal) < diff, '%s <> %s (>%d ms)' % (t1, t2, diff)


def test_srt_resync_utf8():

  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'srt', 'utf-8.srt'))

  new_start = '00:00:45,367'
  new_end = '01:36:57,900'
  result = subtitles.resync_subtitles(filename, 3, new_start, 1327, new_end)

  nose.tools.eq_(result[3].index, 4) #notice: index clearing worked
  _compare_srt_times(result[3].start, new_start)
  nose.tools.eq_(result[1327].index, 1328) #notice: index clearing worked
  _compare_srt_times(result[1327].start, new_end)


def test_srt_resync_bom_utf8():

  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'srt', 'bom-utf-8.srt'))

  new_start = '00:00:13,200'
  new_end = '00:00:38,351'
  result = subtitles.resync_subtitles(filename, 2, new_start, 6, new_end)

  nose.tools.eq_(result[1].index, 2)
  _compare_srt_times(result[1].start, new_start)
  nose.tools.eq_(result[5].index, 6)
  _compare_srt_times(result[5].start, new_end)


def test_srt_resync_windows_1252():

  filename = pkg_resources.resource_filename(__name__,
      os.path.join('data', 'srt', 'windows-1252.srt'))

  new_start = '00:00:45,367'
  new_end = '01:36:57,900'
  result = subtitles.resync_subtitles(filename, 3, new_start, 1327, new_end)

  nose.tools.eq_(result[3].index, 4) #notice: index clearing worked
  _compare_srt_times(result[3].start, new_start)
  nose.tools.eq_(result[1327].index, 1328) #notice: index clearing worked
  _compare_srt_times(result[1327].start, new_end)
