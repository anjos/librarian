#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Shared utilities'''


import os
import sys
import logging
from six.moves import configparser

import guessit

logger = logging.getLogger(__name__)


# Apple tag translations for various US content ratings
US_CONTENT_RATINGS_APPLE = {
    None: b'mpaa|Not Rated|000|',
    "TV-Y": b'us-tv|TV-Y|100|',
    "TV-Y7": b'us-tv|TV-Y7|200|',
    "TV-G": b'us-tv|TV-G|300|',
    "TV-PG": b'us-tv|TV-PG|400|',
    "TV-14": b'us-tv|TV-14|500|',
    "TV-MA": b'us-tv|TV-MA|600|',
    "G": b'mpaa|G|100|',
    "PG": b'mpaa|PG|200|',
    "PG-13": b'mpaa|PG-13|300|',
    "R": b'mpaa|R|400|',
    "NC-17": b'mpaa|NC-17|500|',
    }


def var_from_config(fname, section, name):
  '''Loads information from a INI-style configuration file'''

  parser = configparser.ConfigParser()
  parser.read(fname)
  if section in parser:
    return parser[section].get(name)
  return None


def setup_logger(name, verbosity):
  '''Sets up the logging of a script


  Parameters:

    name (str): The name of the logger to setup

    verbosity (int): The verbosity level to operate with. A value of ``0``
      (zero) means only errors, ``1``, errors and warnings; ``2``, errors,
      warnings and informational messages and, finally, ``3``, all types of
      messages including debugging ones.

  '''

  logger = logging.getLogger(name)
  formatter = logging.Formatter("%(name)s@%(asctime)s -- %(levelname)s: " \
      "%(message)s")

  _warn_err = logging.StreamHandler(sys.stderr)
  _warn_err.setFormatter(formatter)
  _warn_err.setLevel(logging.WARNING)

  class _InfoFilter:
    def filter(self, record): return record.levelno <= logging.INFO
  _debug_info = logging.StreamHandler(sys.stdout)
  _debug_info.setFormatter(formatter)
  _debug_info.setLevel(logging.DEBUG)
  _debug_info.addFilter(_InfoFilter())

  logger.addHandler(_debug_info)
  logger.addHandler(_warn_err)


  logger.setLevel(logging.ERROR)
  if verbosity == 1: logger.setLevel(logging.WARNING)
  elif verbosity == 2: logger.setLevel(logging.INFO)
  elif verbosity >= 3: logger.setLevel(logging.DEBUG)

  return logger


def guess(filename, fullpath=True):
  '''From a given filename try to guess movie TV show information

  This function will try to guess movie title, TV show episode number, etc


  Parameters:

    filename (str): The name of the file being guessed, including, possibly,
      its fullpath

    fullpath (:py:obj:`bool`, optional): If set, the movie name will be guessed
      using the full path leading to the movie file


  Returns:

    dict: A dictionary containing the parts of the movie or TV show
    filename/path that was parsed

  '''

  if not fullpath:
    filename = os.path.basename(filename)

  return guessit.guessit(filename)
