from pycparser import c_ast, c_parser, c_generator

def ast_of(txt):
	parser = c_parser.CParser()
	return parser.parse(txt)

class Any(c_ast.Node):
	"""
	Any node contains any text representation.
	"""
	# FIXME This node is not complete so can't call show() method
	# to an AST that contains Any node.
	def __init__(self, text):
		self.text = text
	attr_names = ('text',)

class CGenerator(c_generator.CGenerator):
	"""
	Since we don't modify the upstream CGenerator
	The text representation of Any node is

	(expected)
	$n.text

	(actual)
	$n.text
	;

	The semicolon (;) appended is not allowed by
	strict ISO standard. '-pedantic' option of gcc compiler
	can worn this.
	"""
	def visit_Any(self, n):
		return n.text

	@classmethod
	def cleanUp(cls, txt):
		"""
		Purge "^;\n" that is not allowed by ISO standard
		"""
		return '\n'.join([line for line in txt.splitlines() if line != ";"])
