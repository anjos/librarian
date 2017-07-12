#!/usr/bin/env python
# vim: set fileencoding=utf-8 :


"""Downloads the subtitles for a particular movie file

Usage: %(prog)s [-v...] [--dry-run] [-l N] <file> <language> [<language>...]
       %(prog)s --help
       %(prog)s --version


Arguments:
  <file>      Name of the file you'll be downloading subtitles for
  <language>  Defines the languages of your preference. May be used multiple
              times. You may use the ISO-639 3-letter standard, e.g. "deu" or
              "ger" for german, a 2-letter standard, e.g. "es" for spain, or a
              2-letter + country code, e.g. "pt-BR" for brazilian portuguese.


Options:
  -h, --help       Shows this help message and exits
  -V, --version    Prints the version and exits
  -v, --verbose    Increases the output verbosity level. May be used multiple
                   times
  -d, --dry-run    Hits subtitle providers and shows list of subtitles that
                   will be downloaded
  -l N, --limit=N  If set, limit the number of displayed subtitles to the top
                   N. A value of 0 removes any limitation and makes the program
                   print all subtitles found [default: 5]


Examples:

  1. Check potential subtitles in french for a movie:

     $ %(prog)s -vv file.mp4 fre
     # files saved, if we succeed, will use 2-character code:
     # - file.fr.srt

  2. Download top-hits for subtitles in brazilian portuguese and german using a
     2(+2)-character language definition:

     $ %(prog)s -vv file.mp4 pt-br de
     # files saved, if we succeed, will use 2-character code (+country)
     # - file.pt-BR.srt
     # - file.de.srt

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
  #logger = setup_logger('subliminal', args['--verbose'])

  # normalize languages
  args['<language>'] = [as_language(k) for k in args['<language>']]

  from .. import subtitles
  config = subtitles.setup_subliminal()
  results = subtitles.search(args['<file>'], args['<language>'], config)

  if bool(args['--dry-run']):
    print("Subtitles for `%s'" % args['<file>'])
    limit = int(args['--limit'])
    subtitles.print_results(results, args['<language>'], limit=limit)

  else:
    subtitles.download(args['<file>'], results, args['<language>'], config)
