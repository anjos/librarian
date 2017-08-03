#!/usr/bin/env python
# vim: set fileencoding=utf-8 :


"""Re-encodes a video file respecting criteria defined by you using ffmpeg

Usage: %(prog)s [-v...] [--show=<lang>] [--ios-audio] [--threads=<N>]
                [--dry-run] [--ignore-sstreams] [--preserve-astreams]
                <infile> <outfile> <lang> [<lang>...]
       %(prog)s --help
       %(prog)s --version


Arguments:
  <infile>    The input filename (any ffmpeg supported extension)
  <outfile>   The output filename (should end in ``.mp4``)
  <lang>      Defines the languages of your preference. May be used multiple
              times. You may use the ISO-639 3-letter standard, e.g. "deu" or
              "ger" for german, a 2-letter standard, e.g. "es" for spain, or a
              2-letter + country code, e.g. "pt-BR" for brazilian portuguese.
              Audio and subtitle streams will be organized using this order.
              The first language of your list defines the default audio stream.
              Subtitle streams won't be shown by default, unless you specify it
              with "--show=<lang>"


Options:
  -h, --help               Shows this help message and exits
  -V, --version            Prints the version and exits
  -v, --verbose            Increases the output verbosity level. May be used
                           multiple times
  -d, --dry-run            If set, doesn't actually run ffmpeg, but just shows
                           the stream planning for the output video. This is a
                           good debugging resource and can help you understand
                           how the program operates
  -g, --ignore-sstreams    If set, ignore all internal subtitle streams. It may
                           be necessary if internal subtitle streams are not
                           character-based and cannot be easily converted to
                           "mov_text" or in case you wish to re-encode external
                           subtitles once more
  -a, --preserve-astreams  If set, preserve all audio streams available in the
                           selected languages on the output file. If this is
                           not set and we have found audio streams matching
                           each of the selected languages, then, exceeding
                           audio streams will be dropped (e.g. a director's
                           commentary stream). If you want to preserve those,
                           set this flag
  -s, --show=<lang>        If set, then subtitles for the provided language
                           will be shown by default. The encoding should be the
                           same as for "<lang>"
  -i, --ios-audio          If set and if the first programmed audio stream is
                           not stereo (i.e., has 2-channels), then a second
                           audio stream with 2-channels will be created in AAC
                           format. This stream is selected prioritarily by iOS
                           devices. It is not audible by default otherwise.
  -t, --threads=N          Specify the number of threads ffmpeg is allowed to
                           use from your machine. If you set this number to
                           zero, then ffmpeg will decide on the "optimal"
                           number of threads to use for transcoding.
                           [default: 0]


Examples:

  1. Convert mkv file, use english as main language, preserve french and
     italian audio/subtitle streams (if available), display french subtitles by
     default by default, create iOS audio stream:

     $ %(prog)s -vv -l eng -l fre -l pt-br -s fre -i file.mkv file.mp4

  2. Re-convert mp4 file, use (canadian) french as main language, preserve
     english audio/subtitles. No default subtitles shown:

     $ %(prog)s -vv -l fr-ca -l eng file.mp4 other-file.mp4

"""


import os
import sys


def main(user_input=None):

  if user_input is not None:
    argv = user_input
  else:
    argv = sys.argv[1:]

  import docopt
  import pkg_resources

  completions = dict(
      prog=os.path.basename(sys.argv[0]),
      version=pkg_resources.require('librarian')[0].version,
      )

  args = docopt.docopt(
      __doc__ % completions,
      argv=argv,
      version=completions['version'],
      )

  from ..utils import setup_logger, as_language
  logger = setup_logger('librarian', args['--verbose'])

  # normalize languages
  args['<lang>'] = [as_language(k) for k in args['<lang>']]
  args['--show'] = args['--show'] if args['--show'] is None else \
      as_language(args['--show'])

  from .. import convert

  # planning
  probe = convert.probe(args['<infile>'])
  planning = convert.plan(probe, languages=args['<lang>'],
      default_subtitle_language=args['--show'],
      ios_audio=bool(args['--ios-audio']),
      preserve_audio_streams=bool(args['--preserve-astreams']),
      ignore_subtitle_streams=bool(args['--ignore-sstreams']))
  options = convert.options(args['<infile>'], args['<outfile>'],
      planning, int(args['--threads']))

  # running
  if not bool(args['--dry-run']):
    streams = list(probe.iter('stream'))
    video = convert._get_default_stream(streams, 'video')

    # handle backup
    if os.path.exists(args['<outfile>']):
      logger.warn('Renaming %s to %s~', args['<outfile>'], args['<outfile>'])
      backup = args['<outfile>'] + '~'
      if os.path.exists(backup): os.unlink(backup)
      os.rename(args['<outfile>'], backup)

    if 'nb_frames' in video.attrib:
      frames = int(video.attrib['nb_frames'])
    else:
      logger.info('Number of frames not available - using stream duration')
      frames = float(probe.find('format').attrib['duration'])
    retcode = convert.run(options, frames)
    sys.exit(retcode)

  else:
    print('Stream planning:')
    convert.print_plan(planning)
    print('Options for ffmpeg:')
    print('  %s' % ' '.join(options))
    sys.exit(0)
