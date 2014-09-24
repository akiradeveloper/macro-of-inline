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

class RewriteCaller(compound.NodeVisitor, compound.SymbolTableMixin):
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
		compound.SymbolTableMixin.__init__(self, func, macroizables)
		name = ext_pycparser.FuncDef(func).name()
		self.called_in_macro = True if name in macroizables else False

	def visit_Compound(self, n):
		self.switch()
		ext_pycparser.NodeVisitor.generic_visit(self, n)
		self.revert()

	def visit_Decl(self, n):
		self.register(n)

	def visit_FuncCall(self, n):
		name = rewrite.FuncCallName(n)

		if not self.canMacroize(name):
			return

		# Assignment to n.name.name always work because we only consider
		# basic function call f(...).
		n.name.name = "macro_%s" % name # macro_f(...)

		namespace = rewrite.newrandstr()
		if self.called_in_macro:
			namespace = "namespace ## %s" % namespace

		if n.args == None:
			n.args = c_ast.ExprList([])
		n.args.exprs.insert(0, c_ast.ID(namespace)) # macro_f(namespace, ...)


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
			ext_pycparser.NodeVisitor.generic_visit(self, n)

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

	class PurgeInlines(ext_pycparser.NodeVisitor):
		"""
		Purge all "inline" specifiers in the source code.
		"inline" specifier is possibly rejected by the compiler but the input file
		may include it to ask macroizing the specified functions.

		E.g.

		static inline f();
		static inline g() {}

		=>

		static f();
		static g() {}
		"""
		def visit_Decl(self, n):
			if "inline" in n.funcspec:
				n.funcspec.remove("inline")

	class AllIDs(c_ast.NodeVisitor, compound.SymbolTableMixin):
		def __init__(self, func, allDeclNames):
			compound.SymbolTableMixin.__init__(self, func, allDeclNames)
			self.result = set()

		def visit_Compound(self, n):
			self.switch()
			c_ast.NodeVisitor.generic_visit(self, n)
			self.revert()

		def visit_Decl(self, n):
			self.register(n)

		def visit_ID(self, n):
			name = n.name
			if self.canMacroize(name):
				self.result.add(name)
			c_ast.NodeVisitor.generic_visit(self, n)

	def prependDecls(self):
		"""
		Move declarations before its first caller.

		Note:
		Anonymous struct/union like
		struct { int x; } t;
		can't appear twice because it leads to compilation error.
		So, unlike prependFuncDecls(), we just move the declaration.
		"""
		all_decls = {}
		for i, n in enumerate(self.ast.ext):
			if isinstance(n, c_ast.Decl):
				all_decls[n.name] = (i, n)

		declLocs = {} # name => i
		for i, n in enumerate(self.ast.ext):
			if isinstance(n, c_ast.FuncDef):
				names = ext_pycparser.Result(self.AllIDs(n, set(all_decls.keys()))).visit(n)
				for name in names:
					if not name in declLocs:
						declLocs[name] = i

		for name, i in sorted(declLocs.items(), key=lambda x: -x[1]):
			j, decl = all_decls[name]
			self.ast.ext.insert(i, decl) # Move the declaration before its first caller.
			self.ast.ext[j] = None # And remove the declaration

		# TODO Sweep None ext nodes

	# FIXME Only inside compound?
	class AllFuncCalls(compound.NodeVisitor, compound.SymbolTableMixin):
		"""
		Find out all the function calls in a function.
		"""
		def __init__(self, func, allFuncNames):
			compound.SymbolTableMixin.__init__(self, func, allFuncNames)
			self.result = set()

		def visit_Compound(self, n):
			self.switch()
			compound.NodeVisitor.generic_visit(self, n)
			self.revert()

		def visit_Decl(self, n):
			self.register(n)

		def visit_FuncCall(self, n):
			callName = rewrite.FuncCallName(n)
			if self.canMacroize(callName):
				self.result.add(callName)
			compound.NodeVisitor.generic_visit(self, n)

	def prependFuncDecls(self):
		"""
		Prepend declarations of functions that are used in the function so the function
		can find the declarations.

		E.g.
		void f() { g(); h(0); }

		=>

		void g();
		void h(int);
		void f() { g(); h(0); }
		"""
		# NOTE We can't sweep the old prototypes because they may be used as pointer reference
		all_funcs = {} # name -> (i, ast)
		for i, n in enumerate(self.ast.ext):
			if isinstance(n, c_ast.FuncDef):
				all_funcs[ext_pycparser.FuncDef(n).name()] = (i, n)

		declLocs = {}
		for i, n in enumerate(self.ast.ext):
			if isinstance(n, c_ast.FuncDef):
				callNames = ext_pycparser.Result(self.AllFuncCalls(n, set(all_funcs.keys()))).visit(n)
				for callName in callNames:
					if not callName in declLocs:
						declLocs[callName] = i

		for callName, i in sorted(declLocs.items(), key=lambda x: -x[1]):
			func = all_funcs[callName][1]
			decl = copy.deepcopy(func.decl)
			self.ast.ext.insert(i, decl)

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

		self.PurgeInlines().visit(self.ast)

		for i, mfunc in macro_funcs:
			self.ast.ext.insert(0, mfunc)
		# print ext_pycparser.CGenerator().visit(self.ast)

		self.applyPreprocess() # Apply cpp is necessary for the later stages.

		if NORMALIZE_LABEL:
			# Normalize labels to fixed length. Some compilers won't allow labels too long.
			self.normalizeLabels()
		recorder.t.file_record("normalize_labels", ext_pycparser.CGenerator().visit(self.ast))

		# FIXME
		self.prependDecls()
		self.prependFuncDecls()

		return self

	def returnAST(self):
		return self.ast

testcase = r"""
struct T { int x; };
struct U { int x; };
struct V { int x; };
static int x = 0;
static inline void f4();
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

static inline void f4() { return; }
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

inline void f_rec() { f_rec(); }

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
