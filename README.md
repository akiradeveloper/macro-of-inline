# macro-of-inline

C-Preprocessor to translate inline functions to an equivalent macros.

## Motivation

Though function inlining is really an effective optimization in many cases
but some immature compiler doesn't support it.
They are often out of maintainance and there is no hope
of the functionality available.

This **macro-of-inline** provides function inlining as preprocessing.

## Usage

```
$ macro-of-inline foo/bar/hoge.c
```

will write to stdout and you can overwrite the file:


```
$ macro-of-inline foo/bar/hoge.c -o foo/bar/hoge.c
```

To record the tracks of translation, add `--record` flag:

```
$ macro-of-inline foo/bar/hoge.c --record
```

Type '-h' for help:

```
$ macro-of-inline -h
usage: macro-of-inline [-h] [-v] [-o OUTFILE] [-I PATHS [PATHS ...]]
                       [--record [DIR]] [--macroize-static-funs]
                       INFILE

C Preprocessor to translate inline functions to equivalent macros

positional arguments:
  INFILE                input filename. It does _not_ need to be preprocessed

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -o OUTFILE            output (default:-)
  -I PATHS [PATHS ...]  add paths to search
  --record [DIR]        record the tracks of code translation. specify a
                        directory if you don't want to use the default
                        directory (default:record-macro-of-inline)
  --macroize-static-funs
                        static functions, no matter they are with inline
                        specifier, are to be macroized
```

## Requirements

- mcpp: A well-designed preprocessor. In Debian, `aptitude install mcpp`

## Limitation

- Include directives will be moved to the head of the file. Make sure this transformation is OK.
- GCC-extensions are ignored (input file will be preprocessed with -U\_\_GNUC\_\_). This is a limitation of pycparser.

## Installation

- To clone source tree, run `git clone https://github.com/akiradeveloper/macro-of-inline`.
- To install, run `python setup.py install`.
- To keep updated, run `git pull`.
- To uninstall, run `sh uninstall.sh`.

## Todo

- fake\_libc\_include should be downloaded from pycparser.
- Automated regressiong tests. 
- More experience with actual projects (hope to hear your reports).

## Known Bugs

## Developer

Akira Hayakawa (ruby.wktk@gmail.com)
