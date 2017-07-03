#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

"""Re-tag an MP4 video with information from TMDB

Usage: %(prog)s [-v...] [--query=<query>] [--tmdbkey=<key>]
                [--basename-only] <file>
       %(prog)s --help
       %(prog)s --version


Arguments:
  <file>    The input filename (which should end in ".mp4")


Options:
  -h, --help           Shows this help message and exits
  -V, --version        Prints the version and exits
  -v, --verbose        Increases the output verbosity level. May be used
                       multiple times
  -q, --query=<title>  Specifies the title (or query) to search for information
                       on TMDB. This is handy if the movie name can't be
                       guessed from the current filename
  -t, --tmdbkey=<key>  If provided, then use this key instead of searching for
                       one in your home directory or the current directory on
                       the file named ".librarianrc.py"
  -b, --basename-only  If a query is not passed, this app will try to guess the
                       movie title from the filename. If you set this flag,
                       then only the basename of the file will be considered.
                       Otherwise, the full path


Examples:

  1. Guess movie title from filename and re-tag:

     $ %(prog)s -vv movie.mp4

  2. Suggest the movie title instead of guessing:

     $ %(prog)s -vv movie.mp4 --query="The Great Escape (1976)"

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
      version=pkg_resources.require('librarian')[0].version
      )

  args = docopt.docopt(
      __doc__ % completions,
      argv=argv,
      version=completions['version'],
      )

  from ..utils import setup_logger
  logger = setup_logger('librarian', args['--verbose'])

  from ..utils import setup_tmdb_apikey
  setup_tmdb_apikey(args['--tmdbkey'])

  if args['--query'] is None:
    from ..utils import guess, record_from_guess
    logger.debug("Trying to guess name from filename")
    info = guess(args['<file>'], fullpath=not args['--basename-only'])
    if info['type'] == 'episode':
      raise RuntimeError('File %s was guessed as a TV show episode - " \
          "you may pass the --query="title" with the right title to fix it')
    movie = record_from_guess(info)

  else:
    from ..utils import record_from_query
    movie = record_from_query(args['--query'])

  # printout some information about the movie
  logger.info('Title: %s', movie.title)
  logger.info('Release date: %s', movie.release_date)
  logger.info('TMDB id: %d', movie.id)

  from ..utils import retag_movie
  retag_movie(args['<file>'], movie)

  sys.exit(0)
