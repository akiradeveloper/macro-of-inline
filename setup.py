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
		url = 'https://github.com/akiradeveloper/macro-of-inline',
		platforms = ['Cross Platform'],
		scripts= ['bin/macro-of-inline'],
		packages = ['macro_of_inline'],
		package_data = {'macro_of_inline' : ['fake_libc_include/*.h']},
		include_package_data = True,
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
