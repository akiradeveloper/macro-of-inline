# macro-of-inline

C-Preprocessor to translate functions to equivalent macros.

## Motivation

ANSI-C doesn't have inilne specifier in its definition.
So, strict ANSI C compiler doesn't inline functions although
function inlining is often really an effective performance optimization.

People suffer from this restriction
have been rewriting functions in macros **by hand** at the cost of
losing readability.

This **macro-of-inline** provides fully-automated
code-level function inlining as preprocessing.

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
                       [-X OPTION [OPTION ...]] [-O MASK]
                       [--fake-include FILE] [--record [DIR]]
                       INFILE

C Preprocessor to translate functions to equivalent macros

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
  -X OPTION [OPTION ...], --cpp-args OPTION [OPTION ...]
                        [--with-cpp] extra options to preprocessor (e.g.
                        _Ipath _DHOGE)
  -O MASK               mask to determine the chance of inlining. static
                        inline = 1, inline = 2, static = 4 (default:7)
  --fake-include FILE   fake include to deceive pycparser by adding fake
                        typedefs
  --record [DIR]        record the tracks of code translation. specify a
                        directory if you don't want to use the default
                        directory (default:/tmp/record-macro-of-inline)
```

## Requirements

- eliben/pycparser: Installing upstream version is recommended but pypi version is typically OK.
- gcc: `gcc -E` preprocessing is used internally.
- [--with-cpp] mcpp: A well-designed preprocessor.

## Limitations

### [--with-cpp] Directives

`#define` directives will be purged after processing
while `#include` directives won't be. Make sure the input code doesn't use `#define` in unexpected manner.
The following code will probably be badly translated.
How this program preserves `#include` directives can be seen in cppwrap.py.

```c
/* NG: Don't do this. MYLIB_SWITCH_A will be purged after processing */
#define MYLIB_SWITCH_A /* Will be purged */
#include "mylib.h" /* Only this line will remain */
#undef MYLIB_SWITCH_A /* Will be purged */
```

The following code is preferred in style

```c
/* OK */
#include "a.h"
#include "b.h"
...
```

### Other Limitations

- Pycparser can't parse codes with GCC-extensions. Make sure that the input code doesn't have one after preprocessing.

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
