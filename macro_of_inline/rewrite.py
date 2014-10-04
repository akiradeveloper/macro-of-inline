from pycparser import c_ast

import cfg
import copy
import compound
import cppwrap
import ext_pycparser
import os
import pycparser
import recorder
import rewrite_void
import rewrite_non_void
import sys
import utils

class FuncDef(ext_pycparser.FuncDef):
	def __init__(self, func):
		ext_pycparser.FuncDef.__init__(self, func)

	def inline_bit(self):
		if self.isStatic() and self.isInline():
			return 1
		if self.isInline():
			return 2
		if self.isStatic():
			return 4
		return 0

	class IsRecursive(c_ast.NodeVisitor, compound.SymbolTableMixin):
		def __init__(self, func):
			compound.SymbolTableMixin.__init__(self, func, set())
			self.result = False

		def visit_Decl(self, n):
			self.register(n)

		def visit_Compound(self, n):
			self.switch()
			c_ast.NodeVisitor.generic_visit(self, n)
			self.revert()

		def visit_FuncCall(self, n):
			if self.result:
				return

			funcName = FuncDef(self.func).name()
			callName = FuncCallName(n)
			if (not callName in self.currentSymbols()) and (callName == funcName):
				self.result = True

	def isRecursive(self):
		return ext_pycparser.Result(self.IsRecursive(self.func)).visit(self.func)

	def doMacroize(self):
		if self.hasVarArgs():
			return False
		# Recursive call can't be macroized in any safe ways.
		if self.isRecursive():
			return False

		if self.inline_bit() & cfg.t.inline_mask:
			return True

		return False

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

		self.all_funcs = {} # name -> (i, ast)
		self.macroizables = set() # set(name)
		self.typedefs = {} # name -> ast

	def blacklist(self, ast):
		f = lambda n: FuncCallName(n)
		all_calls = utils.countMap(map(f, ext_pycparser.Result(ext_pycparser.AllFuncCalls()).visit(ast)))
		# print all_calls
		incomp_calls = utils.countMap(map(f, ext_pycparser.Result(compound.AllFuncCalls()).visit(ast)))
		# print incomp_calls
		utils.countMapDiff(all_calls, incomp_calls)
		return set([k for k, v in all_calls.items() if v > 0])

	def setupAST(self, ast):
		compound.Brace().visit(ast) # The statements always be surrounded by { and }

		for i, n in enumerate(ast.ext):
			if isinstance(n, c_ast.FuncDef):
				self.all_funcs[FuncDef(n).name()] = (i, n)
			if isinstance(n, c_ast.Typedef):
				self.typedefs[n.name] = n

		for name, (_, n) in self.all_funcs.items():
			if not FuncDef(n).doMacroize():
				continue
			self.macroizables.add(name)

		# Exclude functions calls inside expressions
		blacklist = self.blacklist(ast)
		# print blacklist
		self.macroizables -= blacklist

t = Context()

def newrandstr():
	return utils.newrandstr(t.rand_names, utils.N)
BLACKNAME = newrandstr()

MACROIZE_NON_VOID = True
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

class Wrap:
	"""
	Text -> AST
	"""
	def __init__(self, txt):
		self.txt = txt

	def run(self):
		fake_include = cfg.t.fake_include

		if fake_include:
			fn = "/tmp/%s.c" % utils.randstr(16)
			with open(fn, "w") as fp:
				fp.write(self.txt)

			# TODO Ugly. Loan pattern
			try:
				cpp_args = ['-E', r'-include%s' % fake_include]
				cpped_txt = utils.preprocess_file(fn, cpp_path='gcc', cpp_args=cpp_args)
			except Exception as e:
				sys.stderr.write(e.message)
				sys.exit(1)
			finally:
				os.remove(fn)
		else:
			cpped_txt = self.txt

		ast = AST(ext_pycparser.ast_of(cpped_txt)).run().returnAST()

		if fake_include:
			with open(fake_include) as fp:
				ast_b = ext_pycparser.ast_of(fp.read())
			cppwrap.ast_delete(ast, ast_b)

		return ast

class Main:
	"""
	File -> Text
	"""
	def __init__(self, filename):
		self.filename = filename

	def run(self):
		f = lambda text: Wrap(text).run() # Text -> AST
		if cfg.t.with_cpp:
			if cfg.t.cpp_mode == 'gcc':
				cpped_txt = utils.cpp(self.filename)
				output = ext_pycparser.CGenerator().visit(f(cpped_txt))
			else:
				output = cppwrap.Apply(f).on(self.filename)
		else:
			with open(self.filename, "r") as fp:
				cpped_txt = fp.read()
			try:
				output = ext_pycparser.CGenerator().visit(f(cpped_txt))
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
