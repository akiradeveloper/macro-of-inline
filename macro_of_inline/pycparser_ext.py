from pycparser import c_ast, c_generator

class Any(c_ast.Node):
	def __init__(self, text):
		self.text = text
	# attr_names = ('text',)

# Since we don't modify the upstream CGenerator
# The text representation of Any node is
#
# (expected)
# $n.text
#
# (actual)
# $n.text
# ;
#
# The semicolon (;) appended is not allowed by
# strict ISO standard. '-pedantic' option of gcc compiler
# can worn this.
class CGenerator(c_generator.CGenerator):
	def visit_Any(self, n):
		return n.text
