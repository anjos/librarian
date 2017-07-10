#!/usr/bin/env python
# vim: set fileencoding=utf-8 :


"""Re-encodes a video file respecting criteria defined by you using ffmpeg

Usage: %(prog)s [-v...] [-language=<lang>...] [-show=<lang>] [--ios-audio]
                [--threads=<N>] [--dry-run] <infile> <outfile>
       %(prog)s --help
       %(prog)s --version


Arguments:
  <infile>    The input filename (any ffmpeg supported extension)
  <outfile>   The output filename (should end in ``.mp4``)


Options:
  -h, --help            Shows this help message and exits
  -V, --version         Prints the version and exits
  -v, --verbose         Increases the output verbosity level. May be used
                        multiple times
  -d, --dry-run         If set, doesn't actually run ffmpeg, but just shows the
                        stream planning for the output video. This is a good
                        debugging resource and can help you understand how the
                        program operates
  -l, --language=<lang> Defines the languages of your preference. Audio and
                        subtitle streams will be organized using this order.
                        The language in front of your list defines the default
                        audio stream. Subtitle streams won't be shown by
                        default, unless you specify it with -s.
  -s, --show=<lang>     If set, then subtitles for the provided language will
                        be shown by default
  -i, --ios-audio       If set and if the first programmed audio stream is not
                        stereo (i.e., has 2-channels), then a second audio
                        stream with 2-channels will be created in AAC format.
                        This stream is selected prioritarily by iOS devices. It
                        is not audible by default otherwise.
  -t, --threads=N       Specify the number of threads ffmpeg is allowed to use
                        from your machine. [default: %(threads)d]


Examples:

  1. Convert mkv file, use english as main language, preserve french and
     italian audio/subtitle streams (if available), display french subtitles by
     default by default, create iOS audio stream:

     $ %(prog)s -vv -l eng -l fre -l ita -s fre -i file.mkv file.mp4

  2. Re-convert mp4 file, use hindi as main language, preserve english
     audio/subtitles. No default subtitles shown:

     $ %(prog)s -vv -l hin -l eng file.mp4 other-file.mp4

"""


import os
import sys
import six


def main(user_input=None):

  if user_input is not None:
    argv = user_input
  else:
    argv = sys.argv[1:]

  import docopt
  import pkg_resources
  import multiprocessing

  completions = dict(
      prog=os.path.basename(sys.argv[0]),
      version=pkg_resources.require('librarian')[0].version,
      threads=multiprocessing.cpu_count(),
      )

  args = docopt.docopt(
      __doc__ % completions,
      argv=argv,
      version=completions['version'],
      )

  from ..utils import setup_logger
  logger = setup_logger('librarian', args['--verbose'])

  from .. import convert

  # planning
  probe = convert.probe(args['<infile>'])
  planning = convert.plan(probe, languages=args['--language'],
      default_subtitle_language=args['--show'],
      ios_audio=bool(args['--ios-audio']))
  options = convert.options(args['<infile>'], args['<outfile>'],
      planning, int(args['--threads']))

  # running
  if not bool(args['--dry-run']):
    streams = list(probe.iter('stream'))
    video = convert._get_default_stream(streams, 'video')
    frames = int(video.attrib['nb_frames'])
    retcode = convert.run(options, frames)
    sys.exit(retcode)

  else:
    print('Stream planning:')
    convert.print_plan(planning)
    print('Options for ffmpeg:')
    print('  %s' % ' '.join(options))
    sys.exit(0)
