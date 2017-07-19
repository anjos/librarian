#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

"""Re-tag an MP4 video with information from TMDB

Usage: %(prog)s [-v...] [--name=<name>] [--apikey=<key>] [--dry-run]
                [--basename-only] [--season=<int>] [--episode=<int>] <file>
       %(prog)s --help
       %(prog)s --version


Arguments:
  <file>    The input filename (which should end in ".mp4")


Options:
  -h, --help           Shows this help message and exits
  -V, --version        Prints the version and exits
  -v, --verbose        Increases the output verbosity level. May be used
                       multiple times
  -d, --dry-run        If set, doesn't actually retag, but just shows the
                       episode information retrieved from the remote database.
                       This is a good debugging resource and can help you
                       understanding how the file is going to be re-tagged
  -n, --name=<name>    Specifies the TV show name to search for information
                       on TVDB. This is handy if it can't be guessed from the
                       current filename
  -s, --season=<int>   Get data for a specific season number. This will
                       override any guessing made from the filename
  -e, --episode=<int>  Get data for a specific episode number. This will
                       override any guessing made from the filename
  -b, --basename-only  If neither and IMDB identifier nor a title is passed,
                       this app will try to guess the movie title from the
                       filename. If you set this flag, then only the basename
                       of the file will be considered. Otherwise, the full path
  -a, --apikey=<key>   If provided, then use this key instead of searching for
                       one in the environment (TVDB_APIKEY), your current
                       working directory or your home directory (.librarianrc)


Examples:

  1. Guess TV show title, season and episode from filename and re-tag:

     $ %(prog)s -vv friends-s01e01.mp4

  2. Guess season and episode number from filename, inform show title:

     $ %(prog)s -vv --name="Friends" s01e01.mp4

  3. Suggest the TV show title, episode's season and number instead of
     guessing:

     $ %(prog)s -vv episode.mp4 --name="Friends" --season=1 --episode=1

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

  from ..tvdb import setup_apikey
  setup_apikey(args['--apikey'])

  # we always guess and then complete
  from ..utils import guess
  info = guess(args['<file>'], fullpath=not args['--basename-only'])

  if args['--title'] is None and \
      args['--season'] is None and \
      args['--episode'] is None and info['type'] != 'episode':
    raise RuntimeError('File %s was guessed as a movie - " \
        "you may pass the --name="title" --season=1 --episode=1 " \
        "with the right information to fix this')

  # and we complete if stuff from the cmdline
  if args['--name']: info['title'] = args['--name']
  if args['--season']: info['season'] = int(args['--season'])
  if args['--episode']: info['episode'] = int(args['--episode'])
  info['type'] == 'episode' #force

  from ..tvdb import record_from_guess
  episode = record_from_guess(info)

  if args['--dry-run']:
    from ..tvdb import pretty_print
    pretty_print(args['<file>'], episode)
  else:
    logger.info('TV show name: %s', episode.season.show.SeriesName)
    logger.info('Air date: %s', episode.FirstAired.strftime('%Y-%m-%d'))
    logger.info('TVDB episode id: %d', episode.id)
    from ..tvdb import retag
    retag(args['<file>'], episode)

  sys.exit(0)
