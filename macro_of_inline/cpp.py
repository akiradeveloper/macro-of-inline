from pycparser import c_ast
import enum
import pycparser_ext

def cpp(filename):
	pass

def analizeInclude(filename, txt):
	"""
	txt -> [(header, txt)]
	"""
	current_result = None
	result = [] # (lineno, [])
	for line in txt.splitlines():
		line = line.strip()
		if not len(line):
			continue

		if line.startswith("#"):
			xs = line.split()
			fn = xs[2].strip('"')
			if fn == filename:
				lineno = int(xs[1])
				current_result = None
			# Ignore # 1 "<command-line>"
			elif current_result == None and len(xs) > 3:
				current_result = []
				result.append((lineno, current_result))
		elif current_result != None:
			current_result.append(line)

DeclType = enum.Enum("DeclType", "typedef funcdef struct decl")
def type_and_name_of(n):
	if isinstance(n, c_ast.Typedef):
		return (DeclType.typedef, n.name)
	elif isinstance(n, c_ast.FuncDef):
		return (DeclType.funcdef, n.decl.name)
	elif isinstance(n, c_ast.Decl):
		if n.name != None:
			return (DeclType.decl, n.name)
		else:
			return (DeclType.struct, n.type.name)

def ast_delete(a, b):
	"""
	AST-level deletion
	a -= b 
	"""
	t = {
		DeclType.typedef : set(),
		DeclType.funcdef : set(),
		DeclType.struct  : set(),
		DeclType.decl    : set(),
	}

	for n in b.ext:
		(type, name) = type_and_name_of(n)
		t[type].add(name)

	delete_indices = []
	for i, n in enumerate(a.ext):
		(type, name) = type_and_name_of(n)
		if name in t[type]:
			delete_indices.append(i)

	for i in reversed(delete_indices):
		del(a.ext[i])

class Apply:
	"""
	(AST -> AST) -> filename -> txt

	The file (of filename) can be before preprocessing.
	It can contains directives.
	"""
	def __init__(self, f):
		self.f = f

	def on(self, filename):
		cpped_txt = cpp(filename)
		includes = analyzeInclude(filename, cpped_txt)

		fp = open(filename)
		orig_txt_lines = fp.read().splitlines()
		fp.close()
		included_headers = []
		included_code = []
		for lineno, code in	includes:
			included_headers.append(orig_txt_lines[lineno - 1])
			included_codes.append(code)

		ast_a = pycparser_ext.ast_of(cpped_txt)
		ast_b = pycparser_ext.ast_of('\n'.join(included_codes))
		ast_delete(ast_a, ast_b)

		ast_a = f(ast_a)

		contents = pycparser_ext.CGenerator().visit(ast_a)
		return """r
%s
%s
""" % ('\n'.join(included_headers), pycparser_ext.CGenerator.cleanUp(contents))

if __name__ == "__main__":
	testcase = r"""
# 1 "main.c"
# 1 "<command-line>"
# 1 "main.c"
# 1 "/usr/lib/gcc/x86_64-linux-gnu/4.7/include/stdarg.h" 1 3 4
# 40 "/usr/lib/gcc/x86_64-linux-gnu/4.7/include/stdarg.h" 3 4
typedef __builtin_va_list __gnuc_va_list;
# 102 "/usr/lib/gcc/x86_64-linux-gnu/4.7/include/stdarg.h" 3 4
typedef __gnuc_va_list va_list;
# 2 "main.c" 2
# 1 "a.h" 1

# 1 "f/g.h" 1
typedef long mylong;
# 3 "a.h" 2
struct T { int x; };

struct U {
 int y;
  int z;
};
# 3 "main.c" 2
# 1 "b.h" 1
# 1 "c.h" 1
# 2 "b.h" 2
# 1 "d.h" 1
# 1 "e.h" 1
# 1 "d.h" 2
# 3 "b.h" 2
# 1 "f/g.h" 1
typedef long mylong;
# 3 "b.h" 2
# 4 "main.c" 2


int main(void) { return 0; }
"""	
	analizeInclude("main.c", testcase)

a = r"""
int x1;
int x2;
struct T1 { int x; };
struct T2 { int x; };
typedef int int1;
typedef int int2;
void f1() {}
void f2() {}

int main()
{
	return 0;
}
"""
ast_a = pycparser_ext.ast_of(a)

b = r"""
int x1;
struct T1 { int x; };
typedef int int1;
void f1() {}
void f2();
typedef struct T3 { int x; } t3;
typedef int int1;
"""
ast_b = pycparser_ext.ast_of(b)

ast_delete(ast_a, ast_b)
