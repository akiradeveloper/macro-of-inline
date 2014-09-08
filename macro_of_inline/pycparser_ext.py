from pycparser import c_ast, c_parser, c_generator

def ast_of(txt):
	parser = c_parser.CParser()
	return parser.parse(txt)

class Any(c_ast.Node):
	"""
	Any node contains any text representation.
	"""
	def __init__(self, text, coord=None):
		self.text = text
		self.coord = coord

	def children(self):
		nodelist = []
		return tuple(nodelist)

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
	can warn this.
	"""
	def visit_Any(self, n):
		return n.text

	@classmethod
	def cleanUp(cls, txt):
		"""
		Purge "^;\n" that is not allowed by ISO standard
		"""
		return '\n'.join([line for line in txt.splitlines() if line != ";"])

class NodeVisitor(c_ast.NodeVisitor):

	def visit(self, node):
		if not hasattr(self, "current_parent"):
			self.current_parent = node
		c_ast.NodeVisitor.visit(self, node)

	def generic_visit(self, node):
		oldparent = self.current_parent
		self.current_parent = node
		for c_name, c in node.children():
			self.current_name = c_name
			# print("%s.%s = %s" % (self.current_parent, self.current_name, type(c)))
			self.visit(c)
		self.current_parent = oldparent
