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

def compare_asts(ast1, ast2):
	if type(ast1) != type(ast2):
		return False

	# macro-of-inline add namespace argument if it's calling macro.
	# Thus, pure AST comparator doesn't work as the FuncCalls aren't equal
	# if only one of them is as a result of rewrite.
	if isinstance(ast1, c_ast.FuncCall) and isinstance(ast2, c_ast.FuncCall):
		return True

	if isinstance(ast1, tuple) and isinstance(ast2, tuple):
		if ast1[0] != ast2[0]:
			return False
		ast1 = ast1[1]
		ast2 = ast2[1]
		return compare_asts(ast1, ast2)
	for attr in ast1.attr_names:
		if getattr(ast1, attr) != getattr(ast2, attr):
			return False
	for i, c1 in enumerate(ast1.children()):
		if compare_asts(c1, ast2.children()[i]) == False:
			return False
	return True

class ASTDiff:
	def __init__(self):
		self.asts = [] # [[ast, count]]

	def inc(self, ast):
		for e in self.asts:
			if compare_asts(e[0], ast):
				e[1] += 1
				return
		self.asts.append([ast, 1])

	def dec(self, ast):
		"""
		Return true iff the ast exists (count > 0)
		"""
		for e in self.asts:
			if compare_asts(e[0], ast):
				if (e[1] > 0):
					e[1] -= 1
					return True
				else:
					return False
		return False

def ast_delete(a, b):
	"""
	AST-level deletion
	a -= b 

	Assumes that header directives are listed
	at the head of the target file.
	"""
	diff= ASTDiff()

	for n in b.ext:
		diff.inc(n)

	delete_indices = []
	for i, n in enumerate(a.ext):
		if diff.dec(n):
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
struct f;
void f1();
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