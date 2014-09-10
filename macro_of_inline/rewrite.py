from pycparser import c_ast
from singleton.singleton import Singleton

import cfg
import cppwrap
import ext_pycparser
import rewrite_non_void

def prepare_rewrite(ast):
	self.all_funcs = []
	for i, n in enumerate(ast.ext):
		if isinstance(n, c_ast.FuncDef):
			self.all_funcs.append((i, n))
		
	self.macronizables = []
	for _, func in all_funcs:
		if not Fun(func).doMacroize():
			continue
		self.macronizables.append(func)

	print(self.all_funcs)
	# TODO filter out unsafe macroizables

class Fun(ext_pycparser.FuncDef):
	def __init__(self, func):
		ext_pycparser.FuncDef.__init__(self, func)

	def doMacroize(self):
			if self.hasVarArgs():
				return False
			# Recursive call can't be macroized in any safe ways.
			if self.isRecursive():
				return False
			r = self.isInline()
			if cfg.env.macroize_static_funs:
				r |= self.isStatic()
			return r

@Singleton
class Env:
	def __init__(self, ast):
		pass

MACROIZE_NON_VOID = False
class AST:
	def __init__(self, ast):
		self.ast = ast
		AST.prepare_rewrite(ast)

	def run(self):
		if MACROIZE_NON_VOID:
			void_runner = void_fun.Main(self.ast)
			void_runner.run()
			recorder.file_record("convert_non_void_to_void", ext_pycparser.CGenerator().visit(self.ast))

		pass

	def returnAST(self):
		return self.ast

class Main:
	"""
	File -> Text
	"""
	def __init__(self, filename):
		self.filename = filename

	def run(self):
		f = lambda ast: AST(ast).run().returnAST()
		output = cppwrap.Apply(f).on(self.filename)
		return ext_pycparser.CGenerator.cleanUp(output)

if __name__ == "__main__":
	output = Main("tests/proj/main.c").run()
	print(output)
