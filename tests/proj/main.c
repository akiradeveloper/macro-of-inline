# include "a.h"
#include <stdarg.h>
# include    "b.h"

#include "f/g.h"

#define HAVE_LOCALE_H
#ifdef HAVE_LOCALE_H
#include <locale.h>
#endif
#ifdef RUBY_DEBUG_ENV
#include <stdlib.h>
#endif

#include <ucontext.h>

inline void f_guard(int x)
{
	int x = x;
	if (!x)
		return;
}

inline void ff(void)
{
	f_guard();
	f_guard();
}

inline void fff(void)
{
	ff();
	ff();
}

inline int ffff(void)
{
	if (0) {
		fff();
		fff();
		return 1;
	} else if (0) {
		return 0;
	} else {
		return 0;
	}
}

int g_var = 0;

typedef struct S {
	int x;
	int y;
	int z;
} S_t;

struct V { int x; };

inline void inf_2() {}

int main(void) { return 0; }
