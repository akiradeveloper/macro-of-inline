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
$ macro-of-inline foo/bar/hoge.c --with-cpp
```

will write to stdout and you can overwrite the file:


```
$ macro-of-inline foo/bar/hoge.c --with-cpp -o foo/bar/hoge.c
```

To record the tracks of translation, add `--record` flag:

```
$ macro-of-inline foo/bar/hoge.c --with-cpp --record
```

Type '-h' for help:

```
usage: macro-of-inline [-h] [-v] [-o OUTFILE] [--with-cpp [{--,gcc}]]
                       [-X OPTIONS [OPTIONS ...]] [--record [DIR]]
                       [-I PATHS [PATHS ...]] [--macroize-static-funs]
                       INFILE

C Preprocessor to translate inline functions to equivalent macros

positional arguments:
  INFILE                input file. by default, already preprocessed (see
                        --with-cpp)

optional arguments:
  -h, --help            show this help message and exit
  -v, --version         show program's version number and exit
  -o OUTFILE            output (default:-)
  --with-cpp [{--,gcc}]
                        without this flag, the input needs to be explicitly
                        preprocessed. but with this flag, the input file will
                        be implicitly preprocessed within this program. note
                        that, the default mode works tricky thus it's not
                        always work. it depends on how tedious the input file
                        is. gcc mode is experimental and only for testing
  -X OPTIONS [OPTIONS ...], --cpp-args OPTIONS [OPTIONS ...]
                        [--with-cpp] extra options to preprocessor (e.g.
                        _Ipath _DHOGE)
  --record [DIR]        record the tracks of code translation. specify a
                        directory if you don't want to use the default
                        directory (default:record-macro-of-inline)
  -I PATHS [PATHS ...]  [deprecated][--with-cpp] add paths to search
  --macroize-static-funs
                        [deprecated] static functions, no matter they are with
                        inline specifier, are to be macroized
```

## Requirements

- gcc: `gcc -E` preprocessing is used internally.
- [--with-cpp] mcpp: A well-designed preprocessor. In Debian, `aptitude install mcpp`

## Limitation

- [--with-cpp] Dealing with directives: `#define` directives will be purged after preprocessed and will not be recovered as the output of this program
  while `#include` directives will be. Make sure the input code doesn't use `#define` in tricky manner. All `#include`
  directives will be collected at the beginning with the order preserved. The following code will not probably be translated badly because
  the output won't sandwitch `#include "mylib.h"` with the define/undef.

```c
/* NG: Don't do this. MYLIB_SWITCH_A will be purged */
#define MYLIB_SWITCH_A
#include "mylib.h"
```

- GCC-extensions are ignored ([--with-cpp] input file will be preprocessed with -U\_\_GNUC\_\_). This is a limitation of pycparser.

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
