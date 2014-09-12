from pycparser import c_parser, c_ast

import os

import cfg
import cppwrap
import ext_pycparser
import recorder
import rewrite
import rewrite_void_fun
import utils

NORMALIZE_LABEL = True

# FIXME Only inside compound
class AddNamespaceToFuncCalls(ext_pycparser.NodeVisitor):
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
	def __init__(self, macro_names):
		self.macro_names = macro_names
		self.called_in_macro = False

	def visit_FuncDef(self, n):
		if n.decl.name in self.macro_names:
			self.called_in_macro = True
		ext_pycparser.NodeVisitor.generic_visit(self, n)
		self.called_in_macro = False

	class Name(ext_pycparser.NodeVisitor):
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
		namespace = rewrite.newrandstr()
		if self.called_in_macro:
			namespace = "namespace ## %s" % namespace
		if n.args == None:
			n.args = c_ast.ExprList([])
		n.args.exprs.insert(0, c_ast.ID(namespace))

class Main:
	"""
	AST -> AST
	"""
	def __init__(self, ast):
		rewrite.t.setupAST(ast)
		self.ast = ast

	def applyPreprocess(self):
		fn = "/tmp/%s.c" % utils.randstr(16)
		fp = open(fn, "w")
		fp.write(ext_pycparser.CGenerator().visit(self.ast))
		fp.close()
		# print(cppwrap.cpp(fn))
		self.ast = ext_pycparser.ast_of(cppwrap.cpp(fn))
		os.remove(fn)

	class NormalizeLabels(ext_pycparser.NodeVisitor):
		def __init__(self):
			self.m = {} # string -> int

		def do_visit(self, n):
			if n.name not in self.m:
				self.m[n.name] = rewrite.newrandstr()
			n.name = self.m[n.name]

		def visit_Goto(self, n):
			self.do_visit(n)

		def visit_Label(self, n):
			self.do_visit(n)

	def normalizeLabels(self):
		self.NormalizeLabels().visit(self.ast)

	def run(self):
		macroizables = []
		for name in rewrite.t.macroizables:
			_, func = rewrite.t.all_funcs[name]
			if ext_pycparser.FuncDef(func).returnVoid():
				macroizables.append(name)

		AddNamespaceToFuncCalls(macroizables).visit(self.ast)
		recorder.t.file_record("labelize_func_call", ext_pycparser.CGenerator().visit(self.ast))

		runners = []
		for name in macroizables:
			i, func = rewrite.t.all_funcs[name]
			runner = rewrite_void_fun.Main(func)
			runners.append((i, runner))

		for i, runner in runners:
			runner.sanitizeNames()
		recorder.t.file_record("sanitize_names", ext_pycparser.CGenerator().visit(self.ast))

		for i, runner in runners:
			runner.insertGotoLabel().show().rewriteReturnToGoto().show().appendNamespaceToLabels().show().macroize().show()
			self.ast.ext[i] = runner.returnAST()
		recorder.t.file_record("macroize", ext_pycparser.CGenerator().visit(self.ast))

		# Apply preprocessor and normalize labels to fixed length
		# Some compiler won't allow too-long lables.
		if NORMALIZE_LABEL:
			self.applyPreprocess()
			self.normalizeLabels()
		recorder.t.file_record("normalize_labels", ext_pycparser.CGenerator().visit(self.ast))

		return self

	def returnAST(self):
		return self.ast

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

inline int f9(int x) { return x; }

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
""" % rewrite_void_fun.testcase

if __name__ == "__main__":
	parser = c_parser.CParser()
	ast = parser.parse(testcase)

	output = Main(ast).run().returnAST()

	generator = ext_pycparser.CGenerator()
	output = generator.visit(output)
	file_contents = """
#include <stdio.h>
%s
""" % ext_pycparser.CGenerator.cleanUp(output)

	fn = "/tmp/%s.c" % utils.randstr(16)
	f = open(fn, "w")
	f.write(file_contents)
	f.close()
	# TODO Direct from stdio. Use gcc -xs -
	os.system("gcc -ansi -pedantic %s && ./a.out" % fn)
	os.remove(fn)
	print(output)
