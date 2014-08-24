import os, sys

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup (
		name = 'macro-of-inline',
		description = 'C preprocessor to translate inline functions to equivalent macros',
		license = 'BSD',
		version = '0.9',
		author = 'Akira Hayakawa',
		maintainer = 'Akira Hayakawa',
		author_email = 'ruby.wktk@gmail.com',
		platforms = ['Cross Platform'],
		scripts= ['bin/macro-of-inline'],
		packages = ['macro_of_inline'],
		install_requires = [
			"pycparser",
			"enum34",
		],
		classifiers = [
			"Development Status :: 4 - Beta",
			"Environment :: Console",
			"Topic :: Software Development :: Code Generators"
		]
)
