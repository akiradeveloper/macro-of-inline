# macro-of-inline

C-Preprocessor to translate inline functions to an equivalent macros.

## Motivation

Though function inlining is really an effective optimization in many cases
but some immature compiler doesn't support it.
They are often out of maintainance and there is no hope
of the functionality available.

This macro-of-inline provides function inlining as preprocessing.

## Limitation

- Only those returns void is supported. Those returns non-void values can't be translated correctly.
- The input source file must be preprocessed earlier. `cpp -E source.c | macro-of-inline` is a usage example.
  This limiation is inherited from pycparser that macro-of-inline uses to talk with AST.
  Please read the below from pycparser README

```
In order to be compilable, C code must be preprocessed by the C preprocessor -
``cpp``. ``cpp`` handles preprocessing directives like ``#include`` and
``#define``, removes comments, and does other minor tasks that prepare the C
code for compilation.
```

## Installation

- `python setup.py install` for the latest version or
- `pip install macro-of-inline` for the pip-registered version.

## Todo

- fake\_lib\_include should be downloaded from pycparser.
- Enhance fake\_lib\_include to pass including context.h.
- Automated regressiong tests. 
- More experience with actual projects (hope to hear your reports).

## Known Bugs

## Developer

Akira Hayakawa (ruby.wktk@gmail.com)
