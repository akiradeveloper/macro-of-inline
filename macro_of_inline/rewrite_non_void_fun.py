from pycparser import c_ast

import copy
import ext_pycparser
import recorder

class Main(ext_pycparser.FuncDef):
	"""
	Rewrite function definitions
	1. Return type T to void: T f(..) -> void f(..)
	2. New argument for returning value: f(..) -> f(.., T *retval)
	3. Return statement to assignment: return x -> *retval = x
	"""

	PHASES = [
		"add_ret_val",
		"void_return_type",
		"return_to_assignment",
	]

	def __init__(self, func):
		self.func = func
		self.phase_no = 0

	def addRetval(self):
		funtype = self.func.decl.type
		rettype = copy.deepcopy(funtype.type)
		ext_pycparser.RewriteTypeDecl("retval").visit(rettype)
		newarg = c_ast.Decl("retval", [], [], [], c_ast.PtrDecl([], rettype), None, None)
		params = []
		if not self.voidArgs():
			params = funtype.args.params
		params.insert(0, newarg)
		if not funtype.args:
			funtype.args = c_ast.ParamList([])
		funtype.args.params = params
		return self

	def voidReturnValue(self):
		self.phase_no += 1
		self.func.decl.type.type = c_ast.TypeDecl(self.name(), [], c_ast.IdentifierType(["void"]))
		return self

	class ReturnToAssignment(ext_pycparser.NodeVisitor):
		def visit_Return(self, n):
			ass = c_ast.Assignment("=",
						c_ast.UnaryOp("*", c_ast.ID("retval")), # lvalue
						n.expr) # rvalue
			ext_pycparser.NodeVisitor.rewrite(self.current_parent, self.current_name, ass)

			compound = self.current_parent

			# We expect that the parent is compound (because we will have at least two lines in there).
			# However, some hacky code omits curly braces (Linux kernel even oblige this).
			if not isinstance(self.current_parent, c_ast.Compound):
				compound = c_ast.Compound([ass])
				ext_pycparser.NodeVisitor.rewrite(self.current_parent, self.current_name, compound)

			# Since we are visiting in depth-first and
			# pycparser's children() method first create nodelist
			# it is safe to add some node as sibling (but it won't be visited)
			compound.block_items.append(c_ast.Return(None))

	def rewriteReturn(self):
		self.phase_no += 1
		self.ReturnToAssignment().visit(self.func)
		return self

	def run(self):		
		return self.addRetval().show().voidReturnValue().show().rewriteReturn().show()

	def returnAST(self):
		return self.func

	def show(self):
		recorder.fun_record(self.PHASES[self.phase_no], self.func)
		return self

test_fun = r"""
inline struct T *f(int n)
{
	struct T *t = init_t();
	t->x = n;
	return g(t);
}
"""

test_fun2 = r"""
inline int f(int x, ...) {
	while (0)
		return 0;
	for (;;)
		return 0;
	while (0) {
		if (0)
			return 0;

		if (1) {
			return 1;
		} else {
			return 0;
		}
	}
} 
"""

if __name__ == "__main__":
	fun = ext_pycparser.ast_of(test_fun2).ext[0]
	fun.show()
	ast = Main(fun).run().returnAST()
	print ext_pycparser.CGenerator().visit(ast)
