#!/usr/bin/env python
# vim: set fileencoding=utf-8 :

from setuptools import setup, find_packages

setup(

    name='librarian',
    version='0.0.1',
    description="Utilities for organizing Movie/TV show libraries",
    url='https://github.com/anjos/librarian',
    license="GPLv3",
    author='Andre Anjos',
    author_email='andre.dos.anjos@gmail.com',
    long_description=open('README.rst').read(),

    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,

    install_requires=[
      'setuptools',
      'six',
      'docopt',
      'guessit',
      'subliminal',
      'mutagen',
      'tmdbsimple',
      'pytvdbapi',
      'pexpect',
      'tqdm',
      'chardet',
      'babelfish',
      'pysrt',
      ],

    entry_points = {
      'console_scripts': [
        'retag_movie.py = librarian.scripts.retag_movie:main',
        'retag_tvshow.py = librarian.scripts.retag_tvshow:main',
        'tomp4.py = librarian.scripts.tomp4:main',
        'getsubs.py = librarian.scripts.getsubs:main',
        'resync_subs.py = librarian.scripts.resync_subs:main',
        'cleanup_subs.py = librarian.scripts.cleanup_subs:main',
      ],
    },

    classifiers = [
      'Development Status :: 4 - Beta',
      'Intended Audience :: Developers',
      'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
      'Natural Language :: English',
      'Programming Language :: Python',
      'Programming Language :: Python :: 3',
    ],

)
