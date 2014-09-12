from pycparser import c_ast, c_generator

import cfg
import compound
import copy
import ext_pycparser
import inspect
import recorder
import rewrite
import rewrite_void_fun
import rewrite_non_void_fun
import utils

class RewriteCaller:
	"""
	Rewrite all functions
	that may call the rewritten (non-void -> void) functions.
	"""
	PHASES = [
		"split_decls",
		"pop_fun_calls",
		"rewrite_calls",
	]

	def __init__(self, func, macroizables):
		self.func = func
		self.phase_no = 0
		self.macroizables = macroizables

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
		def __init__(self, func):
			self.func = func
			self.cur_table = compound.SymbolTable()
			self.cur_table.register_args(func)

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
			name = ext_pycparser.Result(ext_pycparser.FuncCallName()).visit(n)

			# FIXME ONLY non-void funcs
			unshadowed_names = rewrite.t.macroizables - self.cur_table.names
			if name in unshadowed_names:
				if (isinstance(self.current_parent, c_ast.Assignment)):
					comma = self.mkCommaOp(self.current_parent.lvalue, n)
				else:
					randvar = rewrite.newrandstr()

					# Generate "T var" from the function definition "T f(...)"
					_, func = rewrite.t.all_funcs[name]
					old_decl = copy.deepcopy(func.decl.type.type)
					ext_pycparser.RewriteTypeDecl(randvar).visit(old_decl)
					self.func.body.block_items.insert(0, c_ast.Decl(randvar, [], [], [], old_decl, None, None))

					comma = self.mkCommaOp(c_ast.ID(randvar), n)

				ext_pycparser.NodeVisitor.rewrite(self.current_parent, self.current_name, comma)

			ext_pycparser.NodeVisitor.generic_visit(self, n)

	def run(self):
		self.DeclSplit().visit(self.func)
		self.show()

		self.phase_no += 1
		self.RewriteToCommaOp(self.func).visit(self.func)
		self.show()

		return self

	def returnAST(self):
		return self.func

	def show(self):
		recorder.t.fun_record(self.PHASES[self.phase_no], self.func)
		return self

class Main:
	"""
	AST -> AST
	"""
	def __init__(self, ast):
		rewrite.t.setupAST(ast)
		self.ast = ast

	def rewriteCallers(self, macroizables):
		for i, func in rewrite.t.all_funcs.values():
			self.ast.ext[i] = RewriteCaller(func, macroizables).run().returnAST()
		recorder.t.file_record("rewrite_all_callers", c_generator.CGenerator().visit(self.ast))

	def rewriteDefs(self, macroizables):
		for name in macroizables:
			i, func = rewrite.t.all_funcs[name]
			self.ast.ext[i] = rewrite_non_void_fun.Main(func).run().returnAST()
		recorder.t.file_record("rewrite_func_defines", c_generator.CGenerator().visit(self.ast))

	def run(self):
		macroizables = []
		for name in rewrite.t.macroizables:
			i, func = rewrite.t.all_funcs[name]
			if not ext_pycparser.FuncDef(func).returnVoid():
				macroizables.append(name)

		self.rewriteCallers(macroizables)

		self.rewriteDefs(macroizables)

		return self

	def returnAST(self):
		return self.ast

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
	ast = ext_pycparser.ast_of(test_file)
	ast.show()
	ast = Main(ast).run().returnAST()
	ast.show()
	print ext_pycparser.CGenerator().visit(ast)
