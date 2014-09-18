from pycparser import c_parser, c_ast

import os

import cfg
import compound
import copy
import cppwrap
import ext_pycparser
import pycparser
import recorder
import rewrite
import rewrite_void_fun
import sys
import utils

NORMALIZE_LABEL = True

class RewriteCaller(compound.CompoundVisitor):
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
	def __init__(self, func, macroizables):
		self.current_table = compound.SymbolTable()
		self.current_table.register_args(func)
		self.macroizables = macroizables
		name = ext_pycparser.FuncDef(func).name()
		self.called_in_macro = True if name in macroizables else False

	def visit_Compound(self, n):
		self.current_table = self.current_table.switch()
		ext_pycparser.NodeVisitor.generic_visit(self, n)
		self.current_table = self.current_table.revert()

	def visit_Decl(self, n):
		self.current_table.register(n.name)

	def visit_FuncCall(self, n):
		name = rewrite.FuncCallName(n)
		if not name in self.macroizables - self.current_table.names:
			return

		# Assignment to n.name.name always work because we only consider
		# basic function call f(...).
		n.name.name = "macro_%s" % rewrite.FuncCallName(n) # macro_f(...)

		namespace = rewrite.newrandstr()
		if self.called_in_macro:
			namespace = "namespace ## %s" % namespace

		if n.args == None:
			n.args = c_ast.ExprList([])
		n.args.exprs.insert(0, c_ast.ID(namespace)) # macro_f(namespace, ...)

def purge_inlines(ast):
	l = []
	for i, n in enumerate(ast.ext):
		if isinstance(n, c_ast.FuncDef) and ext_pycparser.FuncDef(n).isInline():
			l.append(i)
		if isinstance(n, c_ast.Decl) and isinstance(n.type, c_ast.FuncDecl) and ext_pycparser.FuncType(n).isInline():
			l.append(i)
	for i in reversed(sorted(l)):
		del ast.ext[i]

class Main:
	"""
	AST -> AST
	"""
	def __init__(self, ast):
		rewrite.t.setupAST(ast)
		self.ast = ast

	def applyPreprocess(self):
		fn = "/tmp/%s.c" % utils.randstr(16)
		with open(fn, "w") as fp:
			txt = ext_pycparser.CGenerator().visit(self.ast)
			fp.write(ext_pycparser.CGenerator.cleanUp(txt))
		try:
			self.ast = ext_pycparser.ast_of(pycparser.preprocess_file(fn, cpp_path='gcc', cpp_args=['-E']))
		except Exception as e:
			sys.stderr.write(e.message)
			sys.exit(1)
		finally:
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
		for (_, func) in rewrite.t.all_funcs.values():
			RewriteCaller(func, macroizables).visit(func)
		recorder.t.file_record("rewrite_func_call", ext_pycparser.CGenerator().visit(self.ast))

	def rewriteDefs(self, macroizables):
		runners = []
		for name in macroizables:
			i, func = rewrite.t.all_funcs[name]
			runner = rewrite_void_fun.Main(func)
			runners.append((i, runner))

		for i, runner in runners:
			runner.sanitizeNames()
		recorder.t.file_record("sanitize_names", ext_pycparser.CGenerator().visit(self.ast))

		for i, runner in reversed(runners):
			runner.insertGotoLabel().show().rewriteReturnToGoto().show().appendNamespaceToLabels().show().macroize().show()
			self.ast.ext[i] = runner.returnAST()
		recorder.t.file_record("macroize", ext_pycparser.CGenerator().visit(self.ast))

	def run(self):
		macroizables = set()

		for name in rewrite.t.macroizables:
			_, func = rewrite.t.all_funcs[name]
			if ext_pycparser.FuncDef(func).returnVoid():
				macroizables.add(name)

		# We keep the original FuncDefs and revive them after the
		# corresponding functions and their callers are transformed.
		orig_funcs = []
		for name in macroizables:
			i, func = rewrite.t.all_funcs[name]
			orig_funcs.append((i, copy.deepcopy(func)))
		orig_funcs.sort(key=lambda x: -x[0]) # reversed order by lineno

		self.rewriteCallers(macroizables)

		# After macroize() calls within macroized functions are expanded.
		# We need to rewrite callers before that.
		self.rewriteDefs(macroizables)

		macro_funcs = []
		for i, _ in orig_funcs:
			macro_funcs.append((i, self.ast.ext[i])) # reversed order

		for i, func in orig_funcs:
			self.ast.ext[i] = func

		if cfg.t.purge_inlines:
			purge_inlines(self.ast)

		for i, mfunc in macro_funcs:
			self.ast.ext.insert(0, mfunc)
		# print ext_pycparser.CGenerator().visit(self.ast)

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
struct U { int x; };
struct V { int x; };
static int x = 0;
inline void f4();
inline void f1(void) { x = 1; f4(); }
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
	# os.system("gcc -ansi -pedantic %s && ./a.out" % fn)
	os.system("gcc -pedantic %s && ./a.out" % fn)
	os.remove(fn)
	print(output)
