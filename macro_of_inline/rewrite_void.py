from pycparser import c_parser, c_ast

import os

import cfg
import compound
import copy
import cppwrap
import ext_pycparser
import recorder
import rewrite
import rewrite_void_fun
import utils

NORMALIZE_LABEL = True

# FIXME care for scope
class AddNamespaceToFuncCalls(compound.CompoundVisitor):
	"""
	Add random namespace macro calls.

	To allow multiple returns in a function we need exit label
	at the end of the definition.
	However, giving a function a label without care for how it
	is called causes label duplication when it's macroized and
	then expanded.

	#define f() \
	do { \
	rand_label: \
	; \
	} while (0)
	f();
	f(); // duplication of rand_label

	Instead, we introduce a notion of namespace.

	#define f(namespace) \
	do { \
	namespace ## exit: \
	} while (0)
	f(rand_label_1);
	f(rand_label_2); // won't conflict
	"""
	def __init__(self, macroizables):
		self.macroizables = macroizables
		self.called_in_macro = False

	def visit_FuncDef(self, n):
		if n.decl.name in self.macroizables:
			self.called_in_macro = True
		ext_pycparser.NodeVisitor.generic_visit(self, n)
		self.called_in_macro = False

	def visit_FuncCall(self, n):
		name = ext_pycparser.Result(ext_pycparser.FuncCallName()).visit(n.name)
		if not name in self.macroizables:
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

	def rewriteCallers(self, macroizables):
		AddNamespaceToFuncCalls(macroizables).visit(self.ast)
		recorder.t.file_record("labelize_func_call", ext_pycparser.CGenerator().visit(self.ast))

	def rewriteDefs(self, macroizables):
		runners = []
		for name in macroizables:
			i, func = rewrite.t.all_funcs[name]
			runner = rewrite_void_fun.Main(copy.deepcopy(func))
			runners.append((i, runner))

		for i, runner in runners:
			runner.sanitizeNames()
		recorder.t.file_record("sanitize_names", ext_pycparser.CGenerator().visit(self.ast))

		for i, runner in reversed(runners):
			runner.insertGotoLabel().show().rewriteReturnToGoto().show().appendNamespaceToLabels().show().macroize().show()
			self.ast.ext.insert(i, runner.returnAST())

		recorder.t.file_record("macroize", ext_pycparser.CGenerator().visit(self.ast))

	def run(self):
		macroizables = []
		for name in rewrite.t.macroizables:
			_, func = rewrite.t.all_funcs[name]
			if ext_pycparser.FuncDef(func).returnVoid():
				macroizables.append(name)

		self.rewriteCallers(macroizables)

		# After macroize() calls within macroized functions are expanded.
		# We need to rewrite callers before that.
		self.rewriteDefs(macroizables)

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
