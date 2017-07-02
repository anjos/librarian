------------------------------------
 Utilities for Re-tagging MP4 files
------------------------------------

A bunch of utilities to organize my movies and TV shows. Bits, pieces and ideas
were taken from `Sickbeard's mp4 automator`_.


Install
=======

I advise you to install a Conda_-based environment for deployment with this
command line::

  $ conda env create -f env.yml


API Keys
--------

For some of the functionality, you'll need to setup API keys that will be used
to contact the movie/TV show database. You may pass the keys everytime you use
one of the applications bundled or permanently set it up on your account and
let the apps find it. The search order is the following:

1. If a file named ``.librarianrc`` exists on the current directory, then it is
   loaded and it should contain a variable named ``tmdbkey`` with the value of
   your API key
2. If a file named ``.librarianrc`` exists on your home directory and none exist
   on your current directory, than that one is use instead.
3. If none of the above exist and you don't pass an API key via command-line
   parameters, then an error is produced and the application will stop.

The syntax of the ``.librarianrc`` file is simple, following a Windows
INI-style syntax::

  [apis]
  tmdbkey = 1234567890abcdef123456
  tvdbkey = 1234567890abcdef123456


Usage
=====

There are various utilities you may use for organizing a video library.


Re-tagging
----------

To re-tag an MP4 file, do the following::

  $ ./bin/retag_movie.py <file>.mp4

This command will attempt to guess the movie title (and date) from the input
file name using `guessit`_. The program will then probe the TMDB database using
`tmdbsimple`_.

You can specify the movie title and year to optimize the search and avoid
guessing::

  $ ./bin/retag.py <file>.mp4 --title="<movie title> (<year>)"

Optionally, you may also specify the IMDB identifier (starting with ``tt``) and
that will skip searching altogether and proceed into re-tagging::

  $ ./bin/retag.py <file>.mp4 --imdbid="tt<id>"

Once information is retrieved from IMDB (or TMDB), it is recorded on the MP4
file using mutagen_ and qtfaststart_.


Downloading Subtitles
---------------------

To download subtitles for movies and TV shows, we use `subliminal`_::

  $ ./bin/subliminal download -l en titled-movie-year.mp4


.. Place your references after this line
.. _conda: http://conda.pydata.org/miniconda.html
.. _guessit: https://pypi.python.org/pypi/guessit
.. _subliminal: https://pypi.python.org/pypi/subliminal
.. _tmdbsimple: https://pypi.python.org/pypi/tmdbsimple
.. _mutagen: https://mutagen.readthedocs.io/en/latest/
.. _qtfaststart: https://github.com/danielgtaylor/qtfaststart
.. _sickbeard's mp4 automator: https://github.com/mdhiggins/sickbeard_mp4_automator
