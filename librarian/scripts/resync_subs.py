#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

"""Re-syncs a subrip (.srt) file using newly provided start/end timings

Usage: %(prog)s [-v...] <start_index> <start_time> <end_index> <end_time> <file>
       %(prog)s --help
       %(prog)s --version


Arguments:
  <start_index>  The number of the frame index (subtitle) to affect for the
                 `start_time`. Notice this is **not** the relative position of
                 the subtitle within the SRT file, but rather the index
                 assigned by the original author. If a file starts with
                 subtitle #1, then position ``[0]`` of the file will have
                 `index = 1` and that is the expected number here.
  <start_time>   The start time, expressed as a string in the format
                 "hh:mm:ss,MMM", from the start of the movie. Values after the
                 comma express milliseconds.
  <end_index>    The number of the frame index (subtitle) to affect for the
                 `end_time`. Notice this is **not** the relative position of
                 the subtitle within the SRT file, but rather the index
                 assigned by the original author.
  <end_time>     The end time, expressed as a string in the format
                 "hh:mm:ss,MMM", from the start of the movie. Values after the
                 comma express milliseconds.
  <file>         The input filename (which should end in ".srt"). This file
                 will be overwritten with the new timings and re-indexed (so
                 subtitle indexes start from 1 and are a non-interrupted
                 sequence). A back-up is saved by the side of it.


Options:
  -h, --help           Shows this help message and exits
  -V, --version        Prints the version and exits
  -v, --verbose        Increases the output verbosity level. May be used
                       multiple times


Examples:

  1. To resync subtitles with index 1 and 1348 to new start times use the
     following command:

     $ %(prog)s -vv 1 00:00:10,300 1348 02:05:27,200 rogue-one-2016.srt

"""


import os
import sys
import shutil


def main(user_input=None):

  if user_input is not None:
    argv = user_input
  else:
    argv = sys.argv[1:]

  import docopt
  import pkg_resources

  completions = dict(
      prog=os.path.basename(sys.argv[0]),
      version=pkg_resources.require('librarian')[0].version
      )

  args = docopt.docopt(
      __doc__ % completions,
      argv=argv,
      version=completions['version'],
      )

  from ..utils import setup_logger
  logger = setup_logger('librarian', args['--verbose'])

  start_index = int(args['<start_index>'])
  end_index = int(args['<end_index>'])

  from ..subtitles import resync_subtitles
  new_subs = resync_subtitles(args['<file>'], start_index,
      args['<start_time>'], end_index, args['<end_time>'])

  backup = args['<file>'] + '~'
  if os.path.exists(backup): os.unlink(backup)
  shutil.copy(args['<file>'], backup)
  new_subs.save(args['<file>'], encoding='utf-8')
