#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

'''Shared utilities'''


import os
import sys
import logging
import babelfish
from six.moves import configparser

import guessit

logger = logging.getLogger(__name__)


# Apple tag translations for various US content ratings
US_CONTENT_RATINGS_APPLE = {
    None: b'mpaa|Not Rated|000|',
    "": b'mpaa|Not Rated|000|',
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


def load_config_section(fname, section):
  '''Loads a whole section from a configuration file'''

  parser = configparser.ConfigParser()
  parser.read(fname)
  if section in parser: return parser[section]
  return None


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


def uniq(seq, idfun=None):
  """Very fast, order preserving uniq function"""

  # order preserving
  if idfun is None:
      def idfun(x): return x
  seen = {}
  result = []
  for item in seq:
      marker = idfun(item)
      # in old Python versions:
      # if seen.has_key(marker)
      # but in new ones:
      if marker in seen: continue
      seen[marker] = 1
      result.append(item)
  return result


def as_language(l):
  '''Converts the language string into a :py:class:`babelfish.Language` object

  This method tries a conversion using the following techniques:

  1. Tries the IETF 3-letter standard
  2. Tries an ISO 639 3-letter B standard
  3. Finally, if everything else fails, tries a simple call to the base class
     with the input string. An exception (from :py:mod:`babelfish`) is raised
     in case of problems.


  Parameters:

    l (str): An ISO 639 3-letter string for the language to convert. This
    method also accepts 2-letter or 2+2-letter identifiers


  Returns:

    babelfish.Language: A language object with the normalize language
    definition


  Raises:

    ValueError: If it cannot convert the language

  '''

  try:
    return babelfish.Language.fromietf(l)
  except Exception:
    pass

  try:
    return babelfish.Language.fromalpha3b(l)
  except Exception:
    return babelfish.Language(l)


def language_acronyms(l):
  '''Defines all possible language acronyms, more specific first


  Parameters:

    babelfish.Language: A language object


  Returns:

    list of str: Strings, in order of preference going from specific to general
    language encodings

  '''

  retval = []
  if l.country is not None:
    a22 = l.alpha2 + '-' + l.country.alpha2
    retval += [
        a22,
        a22.lower(),
        a22.replace('-', ''),
        a22.replace('-', '').lower(),
        ]

  # these are more generic, so go last
  return uniq(retval + [l.alpha2, l.alpha3b, l.alpha3])
