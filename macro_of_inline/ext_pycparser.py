from pycparser import c_ast, c_parser, c_generator

import enum
import re

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
		query = QueryDeclType()
		query.visit(param)

		# f(...(*g)(...))
		if query.result == ArgType.fun:
			return False

		# f(void)
		f = self.VoidParam()
		f.visit(param)
		return f.result

	def hasVarArgs(self):
		if self.voidArgs():
			return False
		for param_decl in self.func.decl.type.args.params:
			if isinstance(param_decl, c_ast.EllipsisParam):
				return True
		return False

	# TODO
	def isRecursive(self):
		return False

	# -ansi doesn't allow inline specifier
	def isInline(self):
		return "inline" in self.func.decl.funcspec

	def isStatic(self):
		return "static" in self.func.decl.storage

class ParamDecl:
	"""
	FuncDef.decl.type..args.params :: [ParamDecl]
	"""
	def __init__(self, node):
		self.node = node

	def queryType(self):
		query = QueryDeclType()
		query.visit(self.node)
		return query.result

	def show(self):
		if not DEBUG:
			return
		print("name %s" % self.node.name)
		self.node.type.show()
		print("type %r" % self.queryType())

class FileAST:
	pass

class FuncCallName(c_ast.NodeVisitor):
	"""
	Usage: visit(FuncCall.name)

	A call might be of form "(*f)(...)"
	The AST is then

	FuncCall
	  UnaryOp
		ID

	While ordinary call is of

	FuncCall
	  ID

	We need to find the ID node recursively.

	Note:
	The AST representation of f->f(hoge) is like this.
	As a result, this function returns 'f' as the name of this call.
	This works because 'f' shadows the non-void functions.
	(We don't expect f->f(hoge) will be written to f->f(&retval, hoge))

        FuncCall:
          StructRef: ->
            ID: f
            ID: f
          ExprList:
            ID: hoge
	"""
	def __init__(self):
		self.found = False

	def visit_ID(self, n):
		if self.found: return
		self.result = n.name
		self.found = True

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
