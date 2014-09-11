from pycparser import c_ast

import cfg
import copy
import cppwrap
import ext_pycparser
import rewrite_non_void

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
			if cfg.env.macroize_static_funs:
				r |= self.isStatic()
			return r

class Context:
	def __init__(self):
		self.all_funcs = {} # name -> (i, ast)
		self.macroizables = [] # [name]

	def setup(self, ast):
		for i, n in enumerate(ast.ext):
			if isinstance(n, c_ast.FuncDef):
				self.all_funcs[FuncDef(n).name()] = (i, copy.deepcopy(n))

		for name, (_, n) in self.all_funcs.items():
			if not FuncDef(n).doMacroize():
				continue
			self.macronizables.append(name)

		# TODO reduce macronizes

context = Context()

MACROIZE_NON_VOID = False
class AST:
	"""
	AST -> AST
	"""
	def __init__(self, ast):
		self.ast = ast
		context.setup(ast)

	def run(self):
		if MACROIZE_NON_VOID:
			runner = rewrite_non_void.Main(self.ast)
			runner.run()
			self.ast = runner.returnAST()
			recorder.file_record("convert_non_void_to_void", ext_pycparser.CGenerator().visit(self.ast))

		runner = rewrite_void.Main(self.ast)
		runner.run()
		self.ast = runner.returnAST()

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
