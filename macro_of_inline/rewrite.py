from pycparser import c_ast

import cfg
import copy
import compound
import cppwrap
import ext_pycparser
import os
import recorder
import rewrite_void
import rewrite_non_void
import sys
import utils

class DeclSplit(c_ast.NodeVisitor):
	"""
	int x = v;

	=>

	int x; (lining this part at the beginning of the function block)
	x = v;
	"""
	def visit_Compound(self, n):
		decls = []
		for i, item in enumerate(n.block_items or []):
			if not isinstance(item, c_ast.Decl):
				continue
			# if item.init:
			if isinstance(item.init, c_ast.FuncCall):
				decls.append((i, item))

		for i, decl in reversed(decls):
			if decl.init:
				n.block_items[i] = c_ast.Assignment("=",
						c_ast.ID(decl.name), # lvalue
						decl.init) # rvalue
			else:
				del n.block_items[i]

		for i, decl in reversed(decls):
			decl_var = copy.deepcopy(decl)
			# TODO Don't split int x = <not func>.
			# E.g. int r = 0;
			decl_var.init = None
			n.block_items.insert(i, decl_var)

		c_ast.NodeVisitor.generic_visit(self, n)

class FuncDef(ext_pycparser.FuncDef):
	def __init__(self, func):
		ext_pycparser.FuncDef.__init__(self, func)

	def doMacroize(self):
		if self.hasVarArgs():
			return False
		# Recursive call can't be macroized in any safe ways.
		if self.isRecursive():
			return False
		r = self.isInline()
		if cfg.t.macroize_static_funs:
			r |= self.isStatic()
		return r

class Context:
	def __init__(self):
		self.rand_names = set()

		self.ast = None
		self.all_funcs = {} # name -> (i, ast)
		self.macroizables = set() # set(name)

	def blacklist(self):
		f = lambda n: ext_pycparser.Result(ext_pycparser.FuncCallName()).visit(n)
		all_calls = utils.countMap(map(f, ext_pycparser.Result(ext_pycparser.AllFuncCall()).visit(self.ast)))
		# print all_calls
		incomp_calls = utils.countMap(map(f, ext_pycparser.Result(compound.AllFuncCall()).visit(self.ast)))
		# print incomp_calls
		utils.countMapDiff(all_calls, incomp_calls)
		return set([k for k, v in all_calls.items() if v > 0])

	def setupAST(self, ast):
		if self.ast == ast:
			return
		self.ast = ast

		compound.Brace().visit(self.ast) # The statements always be surrounded by { and }
		DeclSplit().visit(self.ast)	# Declarations and assignments be split.

		for i, n in enumerate(ast.ext):
			if isinstance(n, c_ast.FuncDef):
				self.all_funcs[FuncDef(n).name()] = (i, n)

		for name, (_, n) in self.all_funcs.items():
			if not FuncDef(n).doMacroize():
				continue
			self.macroizables.add(name)

		# Exclude functions calls inside expressions
		blacklist = self.blacklist()
		# print blacklist
		self.macroizables -= blacklist

t = Context()

def newrandstr():
	return utils.newrandstr(t.rand_names, utils.N)

MACROIZE_NON_VOID = False
class AST:
	"""
	AST -> AST
	"""
	def __init__(self, ast):
		t.setupAST(ast)
		self.ast = ast

	def run(self):
		if MACROIZE_NON_VOID:
			runner = rewrite_non_void.Main(self.ast)
			runner.run()
			self.ast = runner.returnAST()
			recorder.t.file_record("convert_non_void_to_void", ext_pycparser.CGenerator().visit(self.ast))

		runner = rewrite_void.Main(self.ast)
		runner.run()
		self.ast = runner.returnAST()
		return self

	def returnAST(self):
		return self.ast

class Main:
	"""
	File -> Text
	"""
	def __init__(self, filename):
		self.filename = filename

	def run(self):
		f = lambda ast: AST(ast).run().returnAST() # AST -> AST
		if cfg.t.with_cpp:
			if cfg.t.cpp_mode == 'gcc':
				cpped_txt = utils.cpp(self.filename)
				output = ext_pycparser.CGenerator().visit(f(ext_pycparser.ast_of(cpped_txt)))
			else:
				output = cppwrap.Apply(f).on(self.filename)
		else:
			with open(self.filename, "r") as fp:
				cpped_txt = fp.read()
			try:
				output = ext_pycparser.CGenerator().visit(f(ext_pycparser.ast_of(cpped_txt)))
			except:
				sys.stderr.write("[ERROR] %s failed to parse. Is this file preprocessed? Do you forget --with-cpp?\n" % self.filename)
				sys.exit(1)
		return ext_pycparser.CGenerator.cleanUp(output)

if __name__ == "__main__":
	fn = "/tmp/%s.c" % utils.randstr(16)
	with open(fn, "w") as fp:
		fp.write(utils.cpp("tests/proj/main.c"))
	output = Main(fn).run()
	os.remove(fn)
