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

def mkDecl(func, newname):
	"""
	int f(...) {}, name -> int name;
	"""
	decl = copy.deepcopy(func.decl.type.type)
	ext_pycparser.RewriteTypeDecl(newname).visit(decl)
	return c_ast.Decl(newname, [], [], [], decl, None, None)

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
			self.cur_table = self.cur_table.revert();

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
			name = rewrite.FuncCallName(n)

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

	class AssignRetVal(ext_pycparser.NodeVisitor):
		"""
		f() -> T t; t = f();
		(void) f() -> T t; t = f();
		return f() -> T t; t = f(); return t;
		"""
		def __init__(self, func, macroizables):
			self.macroizables = macroizables
			self.current_table = compound.SymbolTable()

		def canMacroize(self, name):
			return name in self.macroizables - self.current_table.names

		def visit_Compound(self, n):
			if not n.block_items:
				return

			self.current_table = self.current_table.switch()
			insert_list = []

			def onFuncCall(call):
				if not self.canMacroize(rewrite.FuncCallName(call)):
					return

				randvar = rewrite.newrandstr()
				n.block_items[i] = c_ast.Assignment("=", c_ast.ID(randvar), call)

				_, func = rewrite.t.all_funcs[rewrite.FuncCallName(call)]
				insert_list.append((0, mkDecl(func, randvar)))

			for i, item in enumerate(n.block_items):
				if isinstance(item, c_ast.Decl):
					self.current_table.register(item.name)
				elif isinstance(item, c_ast.FuncCall):
					onFuncCall(item)
				elif isinstance(item, c_ast.Cast):
					if not isinstance(item.expr, c_ast.FuncCall):
						continue
					onFuncCall(item.expr)
				elif isinstance(item, c_ast.Return):
					if not isinstance(item.expr, c_ast.FuncCall):
						continue
					if not self.canMacroize(rewrite.FuncCallName(item.expr)):
						continue

					name = rewrite.FuncCallName(item.expr)

					randvar = rewrite.newrandstr()
					insert_list.append((i, c_ast.Assignment("=", c_ast.ID(randvar), item.expr)))
					item.expr = c_ast.ID(randvar)

					_, func = rewrite.t.all_funcs[name]
					insert_list.append((0, mkDecl(func, randvar)))

			ext_pycparser.NodeVisitor.generic_visit(self, n)

			insert_list.sort(key=lambda x: -x[0])
			for i, m in insert_list:
				n.block_items.insert(i, m)

			self.current_table = self.current_table.revert()

	class PopNested(ext_pycparser.NodeVisitor):
		"""
		r = f(g()) -> U u; u = g(); r = f(u);
		"""
		def __init__(self, func, macroizables):
			self.current_table = compound.SymbolTable()
			self.result = True # FIXME

		def visit_Compound(self, n):
			self.current_table = self.current_table.switch()
			ext_pycparser.NodeVisitor.generic_visit(self, n)
			self.current_table = self.current_table.revert()

		def visit_Decl(self, n):
			self.current_table.register(n.name)

		def visit_Assignment(self, n):
			pass

	class ToVoid(ext_pycparser.NodeVisitor):
		"""
		r = f(...) -> f(&r, ...)
		"""
		def __init__(self, func, macroizables):
			self.current_table = compound.SymbolTable()

		def visit_Compound(self, n):
			self.current_table = self.current_table.switch()
			ext_pycparser.NodeVisitor.generic_visit(self, n)
			self.current_table = self.current_table.revert()

		def visit_Decl(self, n):
			self.current_table.register(n.name)

		def visit_Assignment(self, n):
			pass

	def run(self):
		self.AssignRetVal(self.func, self.macroizables).visit(self.func)
		self.phase_no += 1

		while not ext_pycparser.Result(self.PopNested(self.func, self.macroizables)).visit(self.func):
			pass
		self.phase_no += 1

		self.ToVoid(self.func, self.macroizables).visit(self.func)
		self.phase_no += 1

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
		void_funcs = []
		for name in macroizables:
			i, func = rewrite.t.all_funcs[name]
			void_funcs.append((i, rewrite_non_void_fun.Main(copy.deepcopy(func)).run().returnAST()))
		void_funcs.sort(key=lambda x: -x[0]) # reverse order
		for i, vfunc in void_funcs:
			self.ast.ext.insert(i, vfunc)
		for _, vfunc in void_funcs:
			decl = copy.deepcopy(vfunc.decl)
			self.ast.ext.insert(0, decl)
		recorder.t.file_record("rewrite_func_defines", c_generator.CGenerator().visit(self.ast))

	def run(self):
		macroizables = set()
		for name in rewrite.t.macroizables:
			i, func = rewrite.t.all_funcs[name]
			if not ext_pycparser.FuncDef(func).returnVoid():
				macroizables.add(name)

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
	f();
	(void)f();
	x += 1;
	int y = g(z, g(y, (*f)()));
	int z = 2;
	int hR = h1(h1(h2(h3(0))));
	if (0)
		return h1(h1(0));
	do {
		int hR = h1(h1(h2(h3(0))));
		f();
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
