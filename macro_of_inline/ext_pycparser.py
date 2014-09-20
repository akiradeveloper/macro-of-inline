from pycparser import c_ast, c_parser, c_generator

import enum
import re

class Result:
	def __init__(self, visitor):
		self.visitor = visitor

	def visit(self, n):
		self.visitor.visit(n)
		return self.visitor.result

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

class CommaOp(c_ast.Node):
	def __init__(self, exprs, coord=None):
		self.exprs = exprs
		self.coord = coord

	def children(self):
		nodelist = []
		return tuple(nodelist)

	attr_names = ('exprs',)

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

	def visit_CommaOp(self, n):
		return "(" + self.visit(n.exprs) + ")"

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

	@classmethod
	def rewrite(cls, o, name, value):
		r = re.compile("(\w+)(\[(\d+)\])?")
		m = r.search(name)
		assert(m.group(1))
		attrname = m.group(1)
		if m.group(2): # o.attr[i]
			index = int(m.group(3))
			getattr(o, attrname)[index] = value
		else: # o.attr
			setattr(o, attrname, value)


class RewriteTypeDecl(NodeVisitor):
	def __init__(self, alias):
		self.alias = alias

	def visit_TypeDecl(self, node):
		node.declname = self.alias

ArgType = enum.Enum("ArgType", "other fun array")
class QueryDeclType(NodeVisitor):
	def __init__(self):
		self.result = ArgType.other

	def visit_FuncDecl(self, node):
		self.result = ArgType.fun

	def visit_ArrayDecl(self, node):
		self.result = ArgType.array

class FuncType:
	def __init__(self, decl):
		"""
		@decl FuncDef.decl (:: Decl)
		"""
		self.decl = decl

	# -ansi doesn't allow inline specifier
	def isInline(self):
		return "inline" in self.decl.funcspec

	def isStatic(self):
		return "static" in self.decl.storage

class FuncDef:
	def __init__(self, func):
		self.func = func

	def name(self):
		return self.func.decl.name

	class ReturnVoid(NodeVisitor):
		def __init__(self):
			self.result = False

		def visit_ParamList(self, n):
			pass

		def visit_TypeDecl(self, n):
			# n.type can be Struct.
			# What we concerns is that the return type is void or not
			if isinstance(n.type, c_ast.IdentifierType):
				self.result = "void" in n.type.names

	def returnVoid(self):
		# void f(...)
		f = self.ReturnVoid()
		f.visit(self.func.decl)
		return f.result

	class VoidParam(NodeVisitor):
		def __init__(self):
			self.result = False

		def visit_PtrDecl(self, n):
			"""
			Avoid f(void *)
			"""
			pass

		def visit_TypeDecl(self, n):
			# Same as ReturnVoid
			# We don't concern types other than IdentifierType
			if isinstance(n.type, c_ast.IdentifierType):
				self.result = "void" in n.type.names

	def voidArgs(self):
		args = self.func.decl.type.args

		# f()
		if args == None:
			return True

		# f(a, b, ...)
		if len(args.params) > 1:
			return False

		param = args.params[0]

		# f(...(*g)(...))
		if Result(QueryDeclType()).visit(param) == ArgType.fun:
			return False

		# f(void)
		return Result(self.VoidParam()).visit(param)

	def hasVarArgs(self):
		if self.voidArgs():
			return False
		for param_decl in self.func.decl.type.args.params:
			if isinstance(param_decl, c_ast.EllipsisParam):
				return True
		return False

	def isInline(self):
		return FuncType(self.func.decl).isInline()

	def isStatic(self):
		return FuncType(self.func.decl).isStatic()

class ParamDecl:
	"""
	FuncDef.decl.type..args.params :: [ParamDecl]
	"""
	def __init__(self, node):
		self.node = node

	def queryType(self):
		return Result(QueryDeclType()).visit(self.node)

	def show(self):
		if not DEBUG:
			return
		print("name %s" % self.node.name)
		self.node.type.show()
		print("type %r" % self.queryType())

class FileAST:
	pass

class AllFuncCalls(NodeVisitor):
	def __init__(self):
		self.result = []

	def visit_FuncCall(self, n):
		self.result.append(n)

class FuncCall:
	pass

class T:
	def __init__(self):
		self.xs = [1, 2, 3]
		self.y = 10

if __name__ == "__main__":
	t = T()
	NodeVisitor.rewrite(t, "xs[1]", 4)
	assert(t.xs[1] == 4)
	NodeVisitor.rewrite(t, "y", 20)
	assert(t.y == 20)
