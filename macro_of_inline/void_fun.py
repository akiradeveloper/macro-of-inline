from pycparser import c_ast, c_generator
import copy
import inspect
import rewrite_fun
import pycparser_ext

class VoidFun(rewrite_fun.Fun):
	"""
	Rewrite function definitions
	1. Return type T to void: T f(..) -> void f(..)
	2. New argument for returning value: f(..) -> f(.., T *retval)
	3. Return statement to assignment: return x -> *retval = x
	"""
	def __init__(self, func):
		self.func = func

	def addRetval(self):
		rettype = copy.deepcopy(self.func.decl.type.type)
		rewrite_fun.RewriteTypeDecl("retval").visit(rettype)
		newarg = c_ast.Decl("retval", [], [], [], c_ast.PtrDecl([], rettype), None, None)
		params = []
		if not self.voidArgs():
			params = self.func.decl.type.args.params
		params.append(newarg)
		self.func.decl.type.args.params = params
		return self

	def voidReturnValue(self):
		self.func.decl.type.type = c_ast.TypeDecl(self.name(), [], c_ast.IdentifierType(["void"]))
		return self

	class ReturnToAssignment(c_ast.NodeVisitor):
		def visit_Compound(self, n):
			if not n.block_items:
				return

			return_item = None
			for i, item in enumerate(n.block_items):
				if isinstance(item, c_ast.Return):
					return_item = (i, item)
			if return_item != None:
				i, item = return_item
				n.block_items[i] = c_ast.Assignment("=",
						c_ast.UnaryOp("*", c_ast.ID("retval")), # lvalue
						item.expr)
				n.block_items.append(c_ast.Return(None))

	def rewriteReturn(self):
		self.ReturnToAssignment().visit(self.func)
		return self

	def run(self):		
		return self.addRetval().show().voidReturnValue().show().rewriteReturn().show()

	def returnAST(self):
		return self.func

	def show(self):
		self.func.show()
		return self

class RewriteFun:
	"""
	Rewrite all functions
	that may call the rewritten (non-void -> void) functions.
	"""
	def __init__(self, func, names):
		self.func = func

class File:
	def __init__(self, ast):
		self.ast = ast

	def run(self):

		non_void_funs = []
		for i, n in enumerate(self.ast.ext):
			if not isinstance(n, c_ast.FuncDef):
				continue
			
			if not rewrite_fun.Fun(n).isInline():
				continue

			if not rewrite_fun.Fun(n).returnVoid():
				non_void_funs.append((i, n))

		# rewrite definitions
		for i, n in non_void_funs:
			self.ast.ext[i] = VoidFun(n).run().returnAST()

		# rewrite all functions
		for i, n in enumerate(self.ast.ext):
			if not isinstance(n, c_ast.FuncDef):
				continue

			self.ast.ext[i] = RewriteFun(n, [rewrite_fun.Fun(n).name() for n in non_void_funs]).run()

test_fun = r"""
inline struct T *f(int n)
{
	struct T *t = init_t();
	t->x = n;
	return g(t);
}
"""

if __name__ == "__main__":
	fun = pycparser_ext.ast_of(test_fun).ext[0]
	fun.show()
	ast = VoidFun(fun).run().returnAST()
	print c_generator.CGenerator().visit(ast)
