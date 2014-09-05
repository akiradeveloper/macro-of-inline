from pycparser import c_ast, c_generator
import cfg
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

class SymbolTable:
	def __init__(self):
		self.names = set()
		self.prev_table = None

	def register(self, name):
		self.names.add(name)

	def clone(self):
		st = SymbolTable()
		st.names = copy.deepcopy(self.names)
		return st

	def show(self):
		print(self.names)

class RewriteFun:
	"""
	Rewrite all functions
	that may call the rewritten (non-void -> void) functions.
	"""
	def __init__(self, func, non_void_funs):
		self.func = func
		self.non_void_funs = non_void_funs
		self.non_void_names = set([rewrite_fun.Fun(n).name() for _, n in self.non_void_funs])

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


	class PopFuncCall(c_ast.NodeVisitor):
		def __init__(self, context):
			self.context = context
			self.cur_table = SymbolTable()
			self.found = False

			if not self.context.func.decl.type.args:
				return

			for param_decl in self.context.func.decl.type.args.params or []:
				self.cur_table.register(param_decl.name)

		def expandFuncCall(self, exprs, i, retitem):
			"""
			(exprs, i, None)
			@exprs are the parameters of function call and @i is the visiting index.

			(None, None, retitem)
			The @retiem is of c_ast.Return
			As return() is not a function we need this tricky work-around.
			"""
			if self.found:
				return
			expr = exprs[i] if exprs else retitem.expr
			if not isinstance(expr, c_ast.FuncCall):
				return
			unshadowed_names = self.context.non_void_names - self.cur_table.names
			if not expr.name.name in unshadowed_names:
				return

			self.found = True
			randvar = rewrite_fun.newrandstr(cfg.env.rand_names, rewrite_fun.N)
			old_expr = copy.deepcopy(expr)
			if exprs:
				exprs[i] = c_ast.ID(randvar)
			else:
				retitem.expr = c_ast.ID(randvar)

			# randvar = expr;
			self.cur_compound.block_items.insert(self.cur_compound_index,
					c_ast.Assignment("=",
						c_ast.ID(randvar), # lvalue
						old_expr)) # rvalue

			# T randvar;
			func = (m for _, m in self.context.non_void_funs if rewrite_fun.Fun(m).name() == old_expr.name.name).next()
			old_decl = copy.deepcopy(func.decl.type.type)
			rewrite_fun.RewriteTypeDecl(randvar).visit(old_decl)
			self.cur_compound.block_items.insert(0, c_ast.Decl(randvar,
				[], [], [], old_decl, None, None))

		def onFuncCall(self, n):
			if not n.args:
				return
			for i, expr in enumerate(n.args.exprs):
				self.expandFuncCall(n.args.exprs, i, None)
				if self.found:
					return
			c_ast.NodeVisitor.generic_visit(self, n)

		def visit_Compound(self, n):
			self.cur_compound = n
			self.switchTable()
			for i, item in enumerate(n.block_items or []):
				self.cur_compound_index = i
				if isinstance(item, c_ast.Decl):
					self.cur_table.register(item.name)
				elif isinstance(item, c_ast.FuncCall):
					# f();
					self.onFuncCall(item)
				elif isinstance(item, c_ast.Return):
					if not item.expr:
						return
					# return expr;
					self.expandFuncCall(None, None, item)
				else:
					# var = f();
					c_ast.NodeVisitor.generic_visit(self, item)
			self.revertTable()

		def visit_FuncCall(self, n):
			self.onFuncCall(n)

		def switchTable(self):
			new_table = self.cur_table.clone()
			new_table.prev_table = self.cur_table
			self.cur_table = new_table

		def revertTable(self):
			self.cur_table = self.cur_table.prev_table;

	def run(self):
		self.DeclSplit().visit(self.func)

		cont = True
		while cont:
			f = self.PopFuncCall(self)
			f.visit(self.func)
			cont = f.found

		print "--"
		f = self.PopFuncCall(self)
		f.visit(self.func)

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

		old_non_void_funs = copy.deepcopy(self.non_void_funs)

		# Rewrite definitions
		for i, n in self.non_void_funs:
			self.ast.ext[i] = VoidFun(n).run().returnAST()

		# Rewrite all callers
		for i, n in enumerate(self.ast.ext):
			if not isinstance(n, c_ast.FuncDef):
				continue
			self.ast.ext[i] = RewriteFun(n, old_non_void_funs).run().returnAST()

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

void r(int x) {}

int foo()
{
	int x = f();
	r(f());
	x += 1;
	int y = g(z, g(y, f()));
	int z = 2;
	int hR = h1(h1(h2(h3(0))));
	int p;
	return g(x, f());
}


int bar() {}
"""

if __name__ == "__main__":
	ast = pycparser_ext.ast_of(test_file)
	ast.show()
	ast = RewriteFile(ast).run().returnAST()
	# ast.show()
	print c_generator.CGenerator().visit(ast)

	# fun = pycparser_ext.ast_of(test_fun).ext[0]
	# fun.show()
	# ast = VoidFun(fun).run().returnAST()
	# print c_generator.CGenerator().visit(ast)
