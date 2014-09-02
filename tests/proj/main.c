# include "a.h"
#include <stdarg.h>
# include    "b.h"
#include "f/g.h"
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

int g_var = 0;

typedef struct S {
	int x;
	int y;
	int z;
} S_t;

struct V { int x; };

inline void inf_2() {}

int main(void) { return 0; }
