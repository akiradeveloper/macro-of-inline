from pycparser import c_ast, c_generator

import recorder
import cfg
import copy
import inspect
import rewrite_fun
import ext_pycparser

class VoidFun(ext_pycparser.FuncDef):
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

class SymbolTable:
	def __init__(self, func):
		self.names = set()
		self.prev_table = None

	def register(self, name):
		self.names.add(name)

	def register_args(self, func):
		if not func.decl.type.args:
			return

		# Because recursive function will not be macroized
		# we don't need care shadowing by it's own function name.
		for param_decl in func.decl.type.args.params or []:
			if isinstance(param_decl, c_ast.EllipsisParam): # ... (Ellipsisparam)
				continue
			self.register(param_decl.name)

	def clone(self):
		st = SymbolTable()
		st.names = copy.deepcopy(self.names)
		return st

	def switch(self):
		new_table = self.clone()
		new_table.prev_table = self.cur_table
		return new_table

	def show(self):
		print(self.names)

class RewriteFun:
	"""
	Rewrite all functions
	that may call the rewritten (non-void -> void) functions.
	"""
	PHASES = [
		"split_decls",
		"pop_fun_calls",
		"rewrite_calls",
	]

	def __init__(self, func, non_void_funs):
		self.func = func
		self.phase_no = 0
		self.non_void_funs = non_void_funs
		self.non_void_names = set([rewrite_fun.Fun(n).name() for _, n in self.non_void_funs])

	class DeclSplit(c_ast.NodeVisitor):
		"""
		int x = v;

		=>

		int x; (lining this part at the beginning of the function block)
		x = v;
		"""
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
				# TODO Don't split int x = <not func>.
				# E.g. int r = 0;
				decl_var.init = None
				n.block_items.insert(0, decl_var)

			c_ast.NodeVisitor.generic_visit(self, n)

	class RewriteToCommaOp(ext_pycparser.NodeVisitor):
		def __init__(self, context):
			self.cur_table = SymbolTable()
			self.context = context
			self.cur_table.register_args(self.context.func)

		def switchTable(self):
			self.cur_table = self.cur_table.switch()

		def revertTable(self):
			self.cur_table = self.cur_table.prev_table;

		def visit_Compound(self, n):
			self.cur_table = self.cur_table.switch()
			ext_pycparser.NodeVisitor.generic_visit(self, n)
			self.cur_table = self.cur_table.prev_table;

		def mkCommaOp(self, var, f):
			proc = f
			if not proc.args:
				proc.args = c_ast.ExprList([])
			proc.args.exprs.insert(0, c_ast.UnaryOp("&", var))
			return ext_pycparser.CommaOp(c_ast.ExprList([proc, var]))

		def visit_FuncCall(self, n):
			"""
			var = f() => var = (f(&var), var)
			f()       => (f(&randvar), randvar)
			"""
			funcname = ext_pycparser.FuncCallName()
			funcname.visit(n)
			funcname = funcname.result

			unshadowed_names = self.context.non_void_names - self.cur_table.names
			if funcname in unshadowed_names:

				if (isinstance(self.current_parent, c_ast.Assignment)):
					comma = self.mkCommaOp(self.current_parent.lvalue, n)
				else:
					randvar = rewrite_fun.newrandstr(cfg.env.rand_names, rewrite_fun.N)

					# Generate "T var" from the function definition "T f(...)"
					func = (m for _, m in self.context.non_void_funs if rewrite_fun.Fun(m).name() == funcname).next()
					old_decl = copy.deepcopy(func.decl.type.type)
					rewrite_fun.RewriteTypeDecl(randvar).visit(old_decl)
					self.context.func.body.block_items.insert(0, c_ast.Decl(randvar, [], [], [], old_decl, None, None))

					comma = self.mkCommaOp(c_ast.ID(randvar), n)

				ext_pycparser.NodeVisitor.rewrite(self.current_parent, self.current_name, comma)

			ext_pycparser.NodeVisitor.generic_visit(self, n)

	def run(self):
		self.DeclSplit().visit(self.func)
		self.show()

		self.phase_no += 1
		self.RewriteToCommaOp(self).visit(self.func)
		self.show()

		return self

	def returnAST(self):
		return self.func

	def show(self):
		recorder.fun_record(self.PHASES[self.phase_no], self.func)
		return self

class RewriteFile:
	"""
	AST -> AST
	"""
	def __init__(self, ast):
		self.ast = ast
		self.non_void_funs = []

	def run(self):
		for i, n in enumerate(self.ast.ext):
			if not isinstance(n, c_ast.FuncDef):
				continue
			
			if not rewrite_fun.Fun(n).doMacroize():
				continue

			if not rewrite_fun.Fun(n).returnVoid():
				self.non_void_funs.append((i, n))

		old_non_void_funs = copy.deepcopy(self.non_void_funs)

		# Rewrite definitions
		for i, n in self.non_void_funs:
			self.ast.ext[i] = VoidFun(n).run().returnAST()
		recorder.file_record("rewrite_func_defines", c_generator.CGenerator().visit(self.ast))

		# Rewrite all callers
		for i, n in enumerate(self.ast.ext):
			if not isinstance(n, c_ast.FuncDef):
				continue
			self.ast.ext[i] = RewriteFun(n, old_non_void_funs).run().returnAST()
		recorder.file_record("rewrite_all_callers", c_generator.CGenerator().visit(self.ast))

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

test_file = r"""
inline int f(void) { return 0; }
inline int g(int a, int b) { return a * b; }

inline int h1(int x) { return x; }
int h2(int x) { return x; }
inline int h3(int x) { return x; }

void r(int x) {}

int foo(int x, ...)
{
	int x = f();
	r(f());
	x += 1;
	int y = g(z, g(y, (*f)()));
	int z = 2;
	int hR = h1(h1(h2(h3(0))));
	if (0)
		return h1(h1(0));
	do {
		int hR = h1(h1(h2(h3(0))));
		if (0)
			return h1(h1(0));
	} while(0);
	int p;
	int q = 3;
	int hRR = t->h1(h1(h2(h3(0))));
	return g(x, f());
}

int bar() {}
"""

if __name__ == "__main__":
	# ast = ext_pycparser.ast_of(test_file)
	# ast.show()
	# ast = RewriteFile(ast).run().returnAST()
	# ast.show()
	# print ext_pycparser.CGenerator().visit(ast)

	fun = ext_pycparser.ast_of(test_fun2).ext[0]
	fun.show()
	ast = VoidFun(fun).run().returnAST()
	print ext_pycparser.CGenerator().visit(ast)
