from pycparser import c_parser, c_ast

import os
import pycparser_ext
import rewrite_fun

class LabelizeFuncCall(c_ast.NodeVisitor):
	"""
	Add random label all macro calls.

	Passing macro a random label is required because
	calling a macro twice causes duplication of label
	if the label name is fixed within macro.

	Consider the following code:

	#define f() \
	do { \
	rand_label: \
	; \
	} while (0)
	f();
	f(); // duplication of rand_label

	Instead, we define macros that is passed a label name
	and give it a random label every different call:

	#define f(rand_label) \
	do { \
	rand_label: \
	} while (0)
	f(rand_label_1);
	f(rand_label_2);
	"""
	def __init__(self, env, macro_names):
		self.env = env
		self.macro_names = macro_names
		self.called_in_macro = False

	def visit_FuncDef(self, n):
		if n.decl.name in self.macro_names:
			self.called_in_macro = True
		c_ast.NodeVisitor.generic_visit(self, n)
		self.called_in_macro = False

	class Name(c_ast.NodeVisitor):
		"""
		Get the name of the function called.
		Usage: visit(FuncCall.name)
		"""
		def __init__(self):
			self.result = ""

		def visit_ID(self, n):
			self.result = n.name

	def visit_FuncCall(self, n):
		f = self.Name();
		f.visit(n.name)
		if not f.result in self.macro_names:
			return
		namespace = rewrite_fun.newrandstr(self.env.rand_names, rewrite_fun.N)
		if self.called_in_macro:
			namespace = "namespace ## %s" % namespace
		if n.args == None:
			n.args = c_ast.ExprList([])
		n.args.exprs.insert(0, c_ast.ID(namespace))

class RewriteFile:
	def __init__(self, text):
		self.text = text
		self.env = rewrite_fun.Env()

	def run(self):
		parser = c_parser.CParser()
		ast = parser.parse(self.text)

		macroizables = [] # (i, runner)
		for i, n in enumerate(ast.ext):
			if not isinstance(n, c_ast.FuncDef):
				continue

			# -ansi doesn't allow inline specifier
			if not 'inline' in n.decl.funcspec:
				continue

			runner = rewrite_fun.RewriteFun(self.env, n)
			runner.sanitizeNames()
			if runner.canMacroize():
				macroizables.append((i, runner))

		LabelizeFuncCall(self.env, [runner.func.decl.name for i, runner in macroizables]).visit(ast)

		for i, runner in macroizables:
			runner.insertGotoLabel().rewriteReturnToGoto().appendNamespaceToLabels().macroize()
			ast.ext[i] = runner.returnAST()

		generator = pycparser_ext.CGenerator()
		output = generator.visit(ast)

		# Purge "^;\n" that is not allowed by ISO standard
		return '\n'.join([line for line in output.splitlines() if line != ";"])


testcase = r"""
struct T { int x; };
static int x = 0;
inline void f1(void) { x = 1; }
inline void f2(int
  x) {   }
%s

int f3(void)
{
  x = 3;
  f2(x);
  return x;
}

inline void f4() {}
inline void f5() { f4(); f4(); }
int f6() { f5(); f5(); }

inline void f7(struct T *t, int x)
{
	t->x = x;
}

inline void f8(int x)
{
  int y = (int) x;
}

int main()
{
  int x;
  int y;
  struct T t;
  f1();
  x = f3();
  f5(); f5();
  f6();
  f7(&t, y);
  f8((int) x);
  puts("OK");
  return 0;
}
""" % rewrite_fun.testcase

if __name__ == "__main__":
	output = RewriteFile(testcase).run()

	file_contents = r"""
#include <stdio.h>
%s
""" % output
	fn = "macro-of-inline-test.c"
	f = open(fn, "w")
	f.write(file_contents)
	f.close()
	# TODO Direct from stdio. Use gcc -xs -
	os.system("gcc -ansi -pedantic %s && ./a.out" % fn)
	print(output)
