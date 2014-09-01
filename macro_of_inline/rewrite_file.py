from pycparser import c_parser, c_ast

import os
import pycparser_ext
import cpp_ext
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

# Buggy thus disabled
SERIALIZE_LABEL = False

class RewriteFile:
	"""
	AST -> AST
	"""
	def __init__(self, ast):
		self.ast = ast
		self.env = rewrite_fun.Env()

	class SerializeLabels(c_ast.NodeVisitor):
		def __init__(self):
			self.m = {} # string -> int

		def do_visit(self, n):
			if n.name not in self.m:
				self.m[n.name] = len(self.m)
			n.name = "label%d" % self.m[n.name]

		def visit_Goto(self, n):
			self.do_visit(n)

		def visit_Label(self, n):
			self.do_visit(n)

	def run(self):
		macroizables = [] # (i, runner)
		for i, n in enumerate(self.ast.ext):
			if not isinstance(n, c_ast.FuncDef):
				continue

			# -ansi doesn't allow inline specifier
			if not 'inline' in n.decl.funcspec:
				continue

			runner = rewrite_fun.RewriteFun(self.env, n)
			runner.sanitizeNames()
			if runner.canMacroize():
				macroizables.append((i, runner))

		LabelizeFuncCall(self.env, [runner.func.decl.name for i, runner in macroizables]).visit(self.ast)

		for i, runner in macroizables:
			runner.insertGotoLabel().rewriteReturnToGoto().appendNamespaceToLabels().macroize()
			self.ast.ext[i] = runner.returnAST()

		# TODO Apply preprocessor and shrink labels to fixed length
		# Some compiler won't allow too-long lables.
		if SERIALIZE_LABEL:
			fn = "%s.c" % rewrite_fun.randstr(16)
			fp = open(fn, "w")
			fp.write(pycparser_ext.CGenerator().visit(self.ast))
			fp.close()
			# print(cpp_ext.cpp(fn))
			self.ast = pycparser_ext.ast_of(cpp_ext.cpp(fn))
			self.SerializeLabels().visit(self.ast)
			os.remove(fn)

		return self.ast

class RewriteFileContents:
	"""
	File -> Text
	"""
	def __init__(self, filename):
		self.filename = filename

	def run(self):
		f = lambda ast: RewriteFile(ast).run()
		output = cpp_ext.Apply(f).on(self.filename)
		return pycparser_ext.CGenerator.cleanUp(output)

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

inline void f4() { return; }
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
	parser = c_parser.CParser()
	output = RewriteFile(parser.parse(testcase)).run()

	generator = pycparser_ext.CGenerator()
	output = generator.visit(output)
	file_contents = """
#include <stdio.h>
%s
""" % pycparser_ext.CGenerator.cleanUp(output)

	fn = "macro-of-inline-test.c"
	f = open(fn, "w")
	f.write(file_contents)
	f.close()
	# TODO Direct from stdio. Use gcc -xs -
	os.system("gcc -ansi -pedantic %s && ./a.out" % fn)
	print(output)

	output = RewriteFileContents("tests/proj/main.c").run()
	print(output)
