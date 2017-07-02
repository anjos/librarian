#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

"""Re-tag an MP4 video with information from TMDB

Usage: %(prog)s [-v...] [--title=<title>|--imdbid=<id>] [--tmdbkey=<key>]
                [--tvdbkey=<key>] [--tvdbuser=<usr>] [--tvdbpass=<pwd>]
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
  -i, --imdbid=<id>    Specifies the IMDB identifier (starting with "tt"). This
                       is handy if you want to skip searching and download
  -t, --tmdbkey=<key>  If provided, then use this key instead of searching for
                       one in your home directory or the current directory on
                       the file named ".librarianrc.py"
  -b, --basename-only  If neither and IMDB identifier nor a title is passed,
                       this app will try to guess the movie title from the
                       filename. If you set this flag, then only the basename
                       of the file will be considered. Otherwise, the full path
  -d, --tvdbkey=<key>  If provided, then use this key instead of searching for
                       one in your home directory or the current directory on
                       the file named ".librarianrc.py"
  -u, --tvdbuser=<usr> If provided, then use this username instead of searching
                       for one in your home directory or the current directory
                       on the file named ".librarianrc.py"
  -u, --tvdbpass=<pwd> If provided, then use this user password instead of
                       searching for one in your home directory or the current
                       directory on the file named ".librarianrc.py"


Examples:

  1. Guess movie title from filename and re-tag:

     $ %(prog)s -vv movie.mp4

  2. Suggest the movie title instead of guessing:

     $ %(prog)s -vv movie.mp4 --title="The Great Escape (1976)"

  3. Pass a precise IMDB id for the tags you want to retrieve:

     $ %(prog)s -vv movie.mp4 --imdbid=tt1234567

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
      version=pkg_resources.require('popster')[0].version
      )

  args = docopt.docopt(
      __doc__ % completions,
      argv=argv,
      version=completions['version'],
      )

  from ..utils import setup_logger
  logger = setup_logger('popster', args['--verbose'])

  from ..utils import setup_tmdb_apikey
  setup_tmdb_apikey(args['--tmdbkey'])

  from ..utils import setup_tvdb_apikey
  tvdb_client = setup_tmdb_apikey(args['--tvdbkey'], args['--tvdbuser'],
      args['--tvdbpass'])

  if args['--query'] is None:
    from ..utils import guess, record_from_guess
    logger.debug("Trying to guess name from filename")
    info = guess(args['<file>'], fullpath=not args['--basename-only'])
    movie = record_from_guess(info)

  else:
    from ..utils import record_from_query
    movie = record_from_query(args['--query'])

  # printout some information about the movie
  logger.info('Type: %s', info['type'])
  logger.info('Title: %s', info['title'])
  if 'year' in info:
    logger.info('Year: %s', info['year'])
  if info['type'] == 'episode':
    logger.info('Season: %d', info['season'])
    logger.info('Episode: %d', info['season'])
  else:
    logger.info('TMDB id: %d', info['id'])

  logger.info("Re-tagging file %s", args['<file>'])


import os
import sys
try:
    from urllib.request import urlretrieve
except ImportError:
    from urllib import urlretrieve
try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import tempfile
import time
import logging
from tmdb_api import tmdb
from mutagen.mp4 import MP4, MP4Cover
from extensions import valid_output_extensions, valid_poster_extensions, tmdb_api_key


class tmdb_mp4:
    def __init__(self, title, original=None, language='en', logger=None):

        if logger:
            self.log = logger
        else:
            self.log = logging.getLogger(__name__)

        self.original = original

        for i in range(3):
            try:
                tmdb.configure(tmdb_api_key, language=language)

                movies = tmdb.Movies(title.encode('ascii', errors='ignore'), limit=1)
                movies = list(movies.iter_results())
                if not movies:
                  self.log.warn("Could not match any movie")
                  sys.exit(1)
                movie = movies[0]
                self.log.info('Id: %s' % movie['id'])
                self.log.info('Title: %s %s' % (movie['title'], movie['release_date']))

                self.movie = tmdb.Movie(movie['id'])

                self.HD = None

                self.title = self.movie.get_title()
                self.genre = self.movie.get_genres()

                self.shortdescription = self.movie.get_tagline()
                self.description = self.movie.get_overview()

                self.date = self.movie.get_release_date()

                # Generate XML tags for Actors/Writers/Directors/Producers
                self.xml = self.xmlTags()
                break
            except Exception as e:
                self.log.exception("Failed to connect to tMDB, trying again in 20 seconds.")
                time.sleep(20)

    def writeTags(self, mp4Path, artwork=True, thumbnail=False):
        self.log.info("Tagging file: %s." % mp4Path)
        ext = os.path.splitext(mp4Path)[1][1:]
        if ext not in valid_output_extensions:
            self.log.error("File is not the correct format.")
            sys.exit()

        video = MP4(mp4Path)
        try:
            video.delete()
        except IOError:
            self.log.debug("Unable to clear original tags, attempting to proceed.")

        video["\xa9nam"] = self.title  # Movie title
        video["desc"] = self.shortdescription  # Short description
        video["ldes"] = self.description  # Long description
        video["\xa9day"] = self.date  # Year
        video["stik"] = [9]  # Movie iTunes category
        if self.HD is not None:
            video["hdvd"] = self.HD
        if self.genre is not None:
            genre = None
            for g in self.genre:
                if genre is None:
                    genre = g['name']
                    break
                # else:
                    # genre += ", " + g['name']
            video["\xa9gen"] = genre  # Genre(s)
        video["----:com.apple.iTunes:iTunMOVI"] = self.xml  # XML - see xmlTags method
        rating = self.rating()
        if rating is not None:
            video["----:com.apple.iTunes:iTunEXTC"] = rating

        if artwork:
            path = self.getArtwork(mp4Path)
            if path is not None:
                cover = open(path, 'rb').read()
                if path.endswith('png'):
                    video["covr"] = [MP4Cover(cover, MP4Cover.FORMAT_PNG)]  # png poster
                else:
                    video["covr"] = [MP4Cover(cover, MP4Cover.FORMAT_JPEG)]  # jpeg poster
        if self.original:
            video["\xa9too"] = "MDH:" + os.path.basename(self.original)
        else:
            video["\xa9too"] = "MDH:" + os.path.basename(mp4Path)

        for i in range(3):
            try:
                self.log.info("Trying to write tags.")
                video.save()
                self.log.info("Tags written successfully.")
                break
            except IOError as e:
                self.log.info("Exception: %s" % e)
                self.log.exception("There was a problem writing the tags. Retrying.")
                time.sleep(5)

    def rating(self):
        ratings = {'G': '100',
                        'PG': '200',
                        'PG-13': '300',
                        'R': '400',
                        'NC-17': '500'}
        output = None
        mpaa = self.movie.get_mpaa_rating()
        if mpaa in ratings:
            numerical = ratings[mpaa]
            output = 'mpaa|' + mpaa.capitalize() + '|' + numerical + '|'
        return str(output)

    def setHD(self, width, height):
        if width >= 1900 or height >= 1060:
            self.HD = [2]
        elif width >= 1260 or height >= 700:
            self.HD = [1]
        else:
            self.HD = [0]

    def xmlTags(self):
        # constants
        header = "<?xml version=\"1.0\" encoding=\"UTF-8\"?><!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" \"http://www.apple.com/DTDs/PropertyList-1.0.dtd\"><plist version=\"1.0\"><dict>\n"
        castheader = "<key>cast</key><array>\n"
        writerheader = "<key>screenwriters</key><array>\n"
        directorheader = "<key>directors</key><array>\n"
        producerheader = "<key>producers</key><array>\n"
        subfooter = "</array>\n"
        footer = "</dict></plist>\n"

        output = StringIO()
        output.write(header)

        # Write actors
        output.write(castheader)
        for a in self.movie.get_cast()[:5]:
            if a is not None:
                output.write("<dict><key>name</key><string>%s</string></dict>\n" % a['name'].encode('ascii', 'ignore'))
        output.write(subfooter)
        # Write screenwriters
        output.write(writerheader)
        for w in self.movie.get_writers()[:5]:
            if w is not None:
                output.write("<dict><key>name</key><string>%s</string></dict>\n" % w['name'].encode('ascii', 'ignore'))
        output.write(subfooter)
        # Write directors
        output.write(directorheader)
        for d in self.movie.get_directors()[:5]:
            if d is not None:
                output.write("<dict><key>name</key><string>%s</string></dict>\n" % d['name'].encode('ascii', 'ignore'))
        output.write(subfooter)
        # Write producers
        output.write(producerheader)
        for p in self.movie.get_producers()[:5]:
            if p is not None:
                output.write("<dict><key>name</key><string>%s</string></dict>\n" % p['name'].encode('ascii', 'ignore'))
        output.write(subfooter)

        # Write final footer
        output.write(footer)
        return output.getvalue()
        output.close()
    # end xmlTags

    def getArtwork(self, mp4Path, filename='cover'):
        # Check for local artwork in the same directory as the mp4
        extensions = valid_poster_extensions
        poster = None
        for e in extensions:
            head, tail = os.path.split(os.path.abspath(mp4Path))
            path = os.path.join(head, filename + os.extsep + e)
            if (os.path.exists(path)):
                poster = path
                self.log.info("Local artwork detected, using %s." % path)
                break
        # Pulls down all the poster metadata for the correct season and sorts them into the Poster object
        if poster is None:
            try:
                poster = urlretrieve(self.movie.get_poster("l"), os.path.join(tempfile.gettempdir(), "poster-tmdb.jpg"))[0]
            except Exception as e:
                self.log.error("Exception while retrieving poster %s.", str(e))
                poster = None
        return poster


def main():
    console = logging.StreamHandler()
    console.setLevel(logging.DEBUG)
    logger = logging.getLogger(__name__)
    logger.addHandler(console)
    logger.setLevel(logging.DEBUG)
    if len(sys.argv) > 2:
        mp4 = str(sys.argv[1]).replace("\\", "\\\\").replace("\\\\\\\\", "\\\\")
        imdb_id = str(sys.argv[2])
        tmdb_mp4_instance = tmdb_mp4(imdb_id)
        if os.path.splitext(mp4)[1][1:] in valid_output_extensions:
            tmdb_mp4_instance.writeTags(mp4)
        else:
            print("Wrong file type")


if __name__ == '__main__':
    main()
