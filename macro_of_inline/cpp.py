def cpp(filename):
	pass

def analizeInclude(txt):
	"""
	txt -> [(header, txt)]
	"""
	pass

def ast_delete(a, b):
	"""
	AST-level deletion
	a -= b 
	"""

class Apply:
	"""
	(AST -> AST) -> filename -> txt

	The file (of filename) can be before preprocessing.
	It can contains directives.
	"""
	def __init__(self, f):
		self.f = f

	def ast_of(self, txt):
		parser = c_parser.CParser()
		return parser.parse(txt)

	def on(self, filename):
		txt = cpp(filename)

		includes = analyzeInclude(txt)
		included_headers = []
		included_code = ""

		ast_a = ast_of(txt)
		ast_b = ast_of(included_code)
		ast_delete(ast_a, ast_b)

		ast_a = f(ast_a)

		generator = pycparser_ext.CGenerator()
		contents = generator.visit(ast_a)

		return """r
%s
%s
""" % ('\n'.join(included_headers), pycparser_ext.CGenerator.cleanUp(contents))

if __name__ == "__main__":
	pass
