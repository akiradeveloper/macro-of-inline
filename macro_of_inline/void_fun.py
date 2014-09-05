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
						item.expr) # rvalue
				n.block_items.append(c_ast.Return(None))
			# FIXME ? call generic_visit()

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

	class DeclSplit(c_ast.NodeVisitor):
		def visit_Compound(self, n):
			decls = []
			for i, item in enumerate(n.block_items or []):
				if isinstance(item, c_ast.Decl):
					decls.append((i, item))

			for i, decl in reversed(decls):
				if decl.init:
					n.block_items[i] = c_ast.Assignment("=",
							c_ast.ID(decl.name), # lvalue
							decl.init) # rvalue
				else:
					del n.block_items[i]

			for _, decl in reversed(decls):
				decl_var = copy.deepcopy(decl)
				decl_var.init = None
				n.block_items.insert(0, decl_var)

	# class CollectFuncCallArgs(c_ast.NodeVisitor):
	# 	def __init__(self):
	# 		self.result = []
    #
	# class PopFuncCall(c_ast.NodeVisitor):
	# 	def visit_Compound(self, n):
	# 		func_call_args = []
	# 		for i, item in enumerate(n.block_items) or []:
	# 			f = CollectFuncCallArgs()
	# 			f.visit(item)
	# 			if len(f.result) > 0:
	# 				func_call_args.append((i, f.result))
	# 		for i, result in reversed(func_call_args):
	# 			for fun in result:
	# 				n.block_items.insert(i, Assignment("=",
	# 					varname,

	def run(self):
		self.DeclSplit().visit(self.func)
		return self

	def returnAST(self):
		return self.func

class RewriteFile:
	def __init__(self, ast):
		self.ast = ast
		self.non_void_funs = []

	def run(self):
		for i, n in enumerate(self.ast.ext):
			if not isinstance(n, c_ast.FuncDef):
				continue
			
			if not rewrite_fun.Fun(n).isInline():
				continue

			if not rewrite_fun.Fun(n).returnVoid():
				self.non_void_funs.append((i, n))

		# rewrite definitions
		for i, n in self.non_void_funs:
			self.ast.ext[i] = VoidFun(n).run().returnAST()

		# rewrite all functions
		for i, n in enumerate(self.ast.ext):
			if not isinstance(n, c_ast.FuncDef):
				continue
			self.ast.ext[i] = RewriteFun(n, [rewrite_fun.Fun(n).name() for _, n in self.non_void_funs]).run().returnAST()

		return self

	def returnAST(self):
		return self.ast

test_fun = r"""
inline struct T *f(int n)
{
	struct T *t = init_t();
	t->x = n;
	return g(t);
}
"""

test_file = r"""
inline int f(void) { return 0; }
inline int g(int a, int b) { return a * b; }

inline int h1(int x) { return x; }
int h2(int x) { return x; }
inline int h3(int x) { return x; }

int foo()
{
	int x = f();
	x += 1;
	int y = g(z, g(y, f()));
	int z = 2;
	int hR = h1(h2(h3(0)));
	int p;
	return g(x, f());
}


int bar() {}
"""

if __name__ == "__main__":
	ast = pycparser_ext.ast_of(test_file)
	ast = RewriteFile(ast).run().returnAST()
	ast.show()
	print c_generator.CGenerator().visit(ast)

	# fun = pycparser_ext.ast_of(test_fun).ext[0]
	# fun.show()
	# ast = VoidFun(fun).run().returnAST()
	# print c_generator.CGenerator().visit(ast)
