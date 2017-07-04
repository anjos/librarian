.. image:: https://travis-ci.org/anjos/librarian.svg?branch=master
   :target: https://travis-ci.org/anjos/librarian

--------------------------------------------------------
 The Librarian - Utilities for Organizing MP4 Libraries
--------------------------------------------------------

A bunch of utilities to organize libraries of movies and TV shows. Some bits,
pieces and ideas were taken from `Sickbeard's mp4 automator`_.


Install
=======

I advise you to install a Conda_-based environment for deployment with this
command line::

  $ conda env create --force -f dev.yml
  $ source activate librarian-dev
  $ buildout

After running ``buildout``, you should have all executables inside the ``bin/``
directory.


API Keys
--------

For some of the functionality, you'll need to setup API keys that will be used
to contact the movie/TV show database. You may pass the keys everytime you use
one of the applications bundled or permanently set it up on your account and
let the apps find it. The search order is the following:

0. If you pass the API key through the command line, then they take precedence
1. If a file named ``.librarianrc`` exists on the current directory, then it is
   loaded and it should contain a variable named ``tmdb`` (or ``tvdb``) inside
   a section named ``apikeys``, with the value of your API key
2. If a file named ``.librarianrc`` exists on your home directory and none exist
   on your current directory, than that one is use instead.
3. If none of the above exist and you don't pass an API key via command-line
   parameters, then an error is produced and the application will stop.

The syntax of the ``.librarianrc`` file is simple, following a Windows
INI-style syntax::

  [apikeys]
  tmdb = 1234567890abcdef123456
  tvdb = 1234567890abc


Usage
=====

There are various utilities you may use for organizing a video library.


Downloading Subtitles
---------------------

To download subtitles for movies and TV shows, we use `subliminal`_::

  $ ./bin/subliminal download -l en titled-movie-year.mp4


Converting to MP4
-----------------

This is done through ffmpeg-python, with parameters optimized for better
cross-device compatibility::

  $ ./bin/tomp4.py


Re-tagging a Movie
------------------

To re-tag an MP4 file with a movie, do the following::

  $ ./bin/retag_movie.py <file>.mp4

This command will attempt to guess the movie title (and date) from the input
file name using `guessit`_. The program will then probe the TMDB database using
`tmdbsimple`_.

You can specify a friendly search string (e.g. movie title and year) to
optimize the search and avoid guessing::

  $ ./bin/retag_movie.py <file>.mp4 --query="<query-matching-movie>"

Once information is retrieved from TMDB, it is recorded on the MP4 file using
mutagen_.


Re-tagging a TV show Episode
----------------------------

To re-tag an MP4 file with a movie, do the following::

  $ ./bin/retag_tvshow.py <file>.mp4

This command will attempt to guess the TV show title season and episode from
the input file name using `guessit`_. The program will then probe the TVDB
database using `tvdbapi-client`_.

You can specify a friendly search string (e.g. series name, season and episode
number ) to optimize the search and avoid guessing::

  $ ./bin/retag.py <file>.mp4 --query="<query-matching-movie>"

Once information is retrieved from TVDB, it is recorded on the MP4 file using
mutagen_, similar to movies.


Development
===========


Build
-----

To build the project and make it ready to run, do::

  $ conda env create --force -f dev.yml
  $ source activate librarian-dev
  $ buildout

This command should leave you with a functional environment.


Testing
-------

To test the package, run the following::

  $ ./bin/nosetests -sv --with-coverage --cover-package=librarian


Conda Builds
============

Building dependencies requires you install ``conda-build``. Do the following to
prepare::

  $ conda install -n root conda-build anaconda-client

Then, you can build dependencies one by one, in order::

  $ for p in deps/rebulk deps/babelfish deps/guessit deps/zc.buildout deps/ipdb deps/ffmpeg-python deps/mutagen deps/qtfaststart deps/args deps/clint deps/pbr deps/requests-toolbelt deps/tqdm deps/twine deps/tvdbapi-client deps/stevedore deps/rarfile deps/pysrt deps/enzyme deps/dogpile.cache deps/subliminal; do conda build $p; done
  $ TMDB_APIKEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx conda build deps/tmdbsimple

To build some of the packages, you'll need to setup environment variables with
API keys, usernames and passwords.

.. note::

   As of today, subliminal_ is still installed as a PIP package.


Anaconda Uploads
================

To upload all built dependencies (so you don't have to re-build them
everytime), do::

  $ anaconda login
  # enter credentials
  $ anaconda upload <conda-bld>/noarch/{rebulk,babelfish,guessit,zc.buildout,ipdb,ffmpeg-python,mutagen,qtfaststart,args,clint,pbr,requests-toolbelt,tqdm,twine,tmdbsimple,tvdbapi-client,stevedore,rarfile,pysrt,enzyme,dogpile.cache,subliminal}-*.tar.bz2


.. Place your references after this line
.. _conda: http://conda.pydata.org/miniconda.html
.. _guessit: https://pypi.python.org/pypi/guessit
.. _subliminal: https://pypi.python.org/pypi/subliminal
.. _tmdbsimple: https://pypi.python.org/pypi/tmdbsimple
.. _mutagen: https://mutagen.readthedocs.io/en/latest/
.. _qtfaststart: https://github.com/danielgtaylor/qtfaststart
.. _pytvdbapi: https://github.com/fuzzycode/pytvdbapi
.. _sickbeard's mp4 automator: https://github.com/mdhiggins/sickbeard_mp4_automator
.. _ffmpeg-python: https://github.com/kkroening/ffmpeg-python
