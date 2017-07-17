#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

"""Cleans-up a subrip (.srt) file by re-indexing it and re-writing in UTF-8

Usage: %(prog)s [-v...] <file>
       %(prog)s --help
       %(prog)s --version


Arguments:
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

  1. To clean-up an existing SRT file:

     $ %(prog)s -vv rogue-one-2016.srt

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

  from ..subtitles import cleanup_subtitles
  new_subs = cleanup_subtitles(args['<file>'])

  backup = args['<file>'] + '~'
  if os.path.exists(backup): os.unlink(backup)
  shutil.copy(args['<file>'], backup)
  new_subs.save(args['<file>'], encoding='utf-8')
