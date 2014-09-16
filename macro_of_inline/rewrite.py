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

def FuncCallName(n):
	"""
	We only macroize basic function calls of pattern f(...)
	where the direct decendant of FuncCall node is ID.
	If we consider other patterns of calls like (*f)(...) or t->f(...)
	we need to track all the renamings to know from where the f came from.
	Theoritically it is possible (although the implementation is really really hard),
	but in pratice it is useless because most of the function calls are
	in basic pattern (use the name as it defines).

	We give random BLACKNAME that doesn't appear as function name
	to exclude the complex call patterns.
	"""
	if isinstance(n.name, c_ast.ID):
		return n.name.name
	else:
		return BLACKNAME

class Context:
	def __init__(self):
		self.rand_names = set()

		self.ast = None
		self.all_funcs = {} # name -> (i, ast)
		self.macroizables = set() # set(name)

	def blacklist(self):
		f = lambda n: FuncCallName(n)
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
BLACKNAME = newrandstr()

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
	print output
	os.remove(fn)
