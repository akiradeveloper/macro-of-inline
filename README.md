# macro-of-inline

C-Preprocessor to translate inline functions to an equivalent macros.

## Motivation

Though function inlining is really an effective optimization in many cases
but some immature compiler doesn't support it.
They are often out of maintainance and there is no hope
of the functionality available.

This macro-of-inline provides function inlining as preprocessing.

## Limitation

- Only those returns void is supported. Those returns non-void values is Todo.
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

- Translation of functions returns non-void value.
- Mode that doesn't need `cpp -E` preprocessing by text-searching the function definitions in the C-code.
- Automated regressiong tests. 
- More experience with actual projects (hope to hear your reports).

## Fixme

### Guard Clause
If the function has guard clause that quit the function before the
end of the function body
macro-of-inline produces incorrect translation.
We can reproduce this problem with this tiny example:

Input:
```
inline void fun(int x)
{
  if (1)
  {
    return;
  }

}
```

Output:
```
#define fun(x) \
do { \
  int eVdhzUIpUJRQosxr = x; \
  if (1) \
  { \
    return; \
  } \
 \
} while(0)
```

## Developer

Akira Hayakawa (ruby.wktk@gmail.com)
