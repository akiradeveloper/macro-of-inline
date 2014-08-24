from pycparser import c_ast, c_generator

class Any(c_ast.Node):
	def __init__(self, text):
		self.text = text

class CGenerator(c_generator.CGenerator):
	def visit_Any(self, n):
		return n.text
