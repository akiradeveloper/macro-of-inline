from pycparser import c_ast

import os
import enum
import pycparser
import pycparser_ext

def cpp(filename):
	"""
	File -> txt
	"""
	# TODO Use pkg_resources or something that fits more.
	p = os.path.join(os.path.dirname(__file__), 'fake_libc_include')
	return pycparser.preprocess_file(filename, cpp_path='gcc', cpp_args=['-E', '-U__GNUC__', r'-I%s' % p])

def analyzeInclude(filename, txt):
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
	return result

DeclType = enum.Enum("DeclType", "typedef funcdef struct decl any")
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
	elif isinstance(n, pycparser_ext.Any):
		return (DeclType.any, n.text)

def ast_delete(a, b):
	"""
	AST-level deletion
	a -= b 
	"""
	diff_table = {
		DeclType.typedef : set(),
		DeclType.funcdef : set(),
		DeclType.struct  : set(),
		DeclType.decl    : set(),
		DeclType.any     : set(),
	}

	for n in b.ext:
		(type, name) = type_and_name_of(n)
		diff_table[type].add(name)

	delete_indices = []
	for i, n in enumerate(a.ext):
		(type, name) = type_and_name_of(n)
		if name in diff_table[type]:
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
		# print(cpped_txt)

		includes = analyzeInclude(filename, cpped_txt)

		# print(includes)

		fp = open(filename)
		orig_txt_lines = fp.read().splitlines()
		fp.close()
		included_headers = []
		included_codes = []
		for lineno, code in	includes:
			included_headers.append(orig_txt_lines[lineno - 1])
			included_codes.append('\n'.join(code))
		# print(included_codes)
		# print(included_headers)	

		ast_a = pycparser_ext.ast_of(cpped_txt)
		ast_a = self.f(ast_a)
		# TODO Preprocess to remove macros that might be generated
		# by the functor 'f'. But mostly, OK.

		ast_b = pycparser_ext.ast_of('\n'.join(included_codes))
		ast_delete(ast_a, ast_b)

		contents = pycparser_ext.CGenerator().visit(ast_a)
		return """
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
	analyzeInclude("main.c", testcase)

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
