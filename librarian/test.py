#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Test units'''

import os
import six
import tempfile
import datetime
import pkg_resources
from xml.etree import ElementTree
import nose.tools
from mutagen import mp4

from . import tmdb, tvdb, utils, convert

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

  planning = convert.plan(probe, languages=['eng', 'fre'], ios_audio=True,
      default_subtitle_language='eng')
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

  # this should be the 2-channel audio stream, not in AAC format
  # even if ios_audio is ``True``, we should not have a second stream because
  # the first audio stream is already good enough for iOS compatibility
  audio, opts = sorted_planning[1]
  assert 'aac' not in audio.attrib['codec_name']
  nose.tools.eq_(audio.attrib['codec_type'], 'audio')
  nose.tools.eq_(audio.attrib['channels'], '2')
  nose.tools.eq_(opts['index'], 1)
  nose.tools.eq_(opts['codec'], 'aac')
  nose.tools.eq_(opts['disposition'], 'default')

  # the 3rd stream should be the english dubbed version, it is AAC encoded
  audio, opts = sorted_planning[2]
  nose.tools.eq_(audio.attrib['codec_type'], 'audio')
  nose.tools.eq_(opts['index'], 2)
  nose.tools.eq_(opts['codec'], 'copy')
  nose.tools.eq_(opts['disposition'], 'none')

  # the 4th stream should be an external SRT subtitle in english
  subt, opts = sorted_planning[3]
  assert isinstance(subt, six.string_types)
  nose.tools.eq_(opts['index'], 3)
  nose.tools.eq_(opts['codec'], 'mov_text')
  nose.tools.eq_(opts['language'], 'eng')
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

  planning = convert.plan(probe, languages=['eng', 'fre'], ios_audio=True)
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
  nose.tools.eq_(opts['index'], 1)
  nose.tools.eq_(opts['codec'], 'copy')
  nose.tools.eq_(opts['disposition'], 'default')

  # the 3rd stream should be iOS stream, which will be moved from 4rd position
  audio, opts = sorted_planning[2]
  nose.tools.eq_(audio.attrib['codec_type'], 'audio')
  assert 'aac' in audio.attrib['codec_name']
  nose.tools.eq_(audio.attrib['index'], '3')
  nose.tools.eq_(opts['index'], 2)
  nose.tools.eq_(opts['codec'], 'copy')
  nose.tools.eq_(opts['disposition'], 'none')

  # the 4th stream should be audio in french
  audio, opts = sorted_planning[3]
  nose.tools.eq_(audio.attrib['codec_type'], 'audio')
  nose.tools.eq_(audio.attrib['index'], '2')
  nose.tools.eq_(opts['index'], 3)
  nose.tools.eq_(opts['codec'], 'copy')
  nose.tools.eq_(opts['disposition'], 'none')

  # the 5th stream should be an external SRT subtitle in english
  subt, opts = sorted_planning[4]
  assert isinstance(subt, six.string_types)
  nose.tools.eq_(opts['index'], 4)
  nose.tools.eq_(opts['codec'], 'mov_text')
  nose.tools.eq_(opts['language'], 'eng')
  nose.tools.eq_(opts['disposition'], 'none')

  # the 6th stream should be an internal SRT subtitle in french
  subt, opts = sorted_planning[5]
  nose.tools.eq_(opts['index'], 5)
  nose.tools.eq_(opts['codec'], 'mov_text')
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

  planning = convert.plan(probe, languages=['eng', 'fre'], ios_audio=True,
      default_subtitle_language='eng')

  output = os.path.splitext(moviefile)[0] + '.mp4'
  options = convert.options(moviefile, output, planning, threads=2)

  expected = [
      '-threads', '2',
      '-fix_sub_duration',
      '-i', moviefile,
      '-i', os.path.splitext(moviefile)[0] + '.eng.srt',
      '-map', '0:0',
      '-map', '0:1',
      '-map', '0:2',
      '-map', '1:3',
      '-disposition:0', 'default',
      '-codec:0', 'copy',
      '-disposition:1', 'default',
      '-codec:1', 'aac', '-vbr', '4',
      '-disposition:2', 'none',
      '-codec:2', 'copy',
      '-disposition:3', 'default',
      '-codec:3', 'mov_text',
      '-metadata:s:3', 'language=eng',
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

  planning = convert.plan(probe, languages=['eng', 'fre'], ios_audio=True)

  output = os.path.splitext(moviefile)[0] + '.mp4'
  options = convert.options(moviefile, output, planning, threads=3)

  expected = [
      '-threads', '3',
      '-fix_sub_duration',
      '-i', moviefile,
      '-i', os.path.splitext(moviefile)[0] + '.eng.srt',
      '-map', '0:0',
      '-map', '0:1',
      '-map', '0:2',
      '-map', '0:3',
      '-map', '1:4',
      '-map', '0:5',
      '-disposition:0', 'default',
      '-codec:0', 'copy',
      '-disposition:1', 'default',
      '-codec:1', 'copy',
      '-disposition:2', 'none',
      '-codec:2', 'copy',
      '-disposition:3', 'none',
      '-codec:3', 'copy',
      '-disposition:4', 'none',
      '-codec:4', 'mov_text',
      '-metadata:s:4', 'language=eng',
      '-disposition:5', 'none',
      '-codec:5', 'mov_text',
      '-metadata:s:5', 'language=fre',
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
