from pycparser import c_ast, c_parser, c_generator

import ext_pycparser

def mk(xs):
	return c_ast.Compound([c_ast.Compound(xs)])

class Brace(ext_pycparser.NodeVisitor):

	def visit_If(self, n):
		if not isinstance(n.iftrue, c_ast.Compound):
			comp = mk([n.iftrue])
			n.iftrue = comp
		if not isinstance(n.iffalse, c_ast.Compound):
			comp = mk([n.iffalse])
			n.iffalse = comp
		c_ast.NodeVisitor.generic_visit(self, n)

	def visit_Case(self, n):
		if not isinstance(n.stmts, c_ast.Compound):
			comp = mk(n.stmts)
			n.stmts = [comp]
		c_ast.NodeVisitor.generic_visit(self, n)

	def visit_Default(self, n):
		if not isinstance(n.stmts, c_ast.Compound):
			comp = mk(n.stmts)
			n.stmts = [comp]
		c_ast.NodeVisitor.generic_visit(self, n)

	def visit_Switch(self, n):
		if not isinstance(n.stmt, c_ast.Compound):
			comp = mk([n.stmt])
			n.stmt = comp
		c_ast.NodeVisitor.generic_visit(self, n)

	def visit_For(self, n):
		if not isinstance(n.stmt, c_ast.Compound):
			comp = mk([n.stmt])
			n.stmt = comp
		c_ast.NodeVisitor.generic_visit(self, n)

	def visit_While(self, n):
		if not isinstance(n.stmt, c_ast.Compound):
			comp = mk([n.stmt])
			n.stmt = comp
		c_ast.NodeVisitor.generic_visit(self, n)

	def visit_DoWhile(self, n):
		if not isinstance(n.stmt, c_ast.Compound):
			comp = mk([n.stmt])
			n.stmt = comp
		c_ast.NodeVisitor.generic_visit(self, n)

class CompoundVisitor(ext_pycparser.NodeVisitor):

	def visit_If(self, n):
		# print(type(n))
		c_ast.NodeVisitor.generic_visit(self, n.iftrue)
		c_ast.NodeVisitor.generic_visit(self, n.iffalse)

	def visit_Case(self, n):
		# print(type(n))
		c_ast.NodeVisitor.generic_visit(self, n.stmts[0])

	def visit_Default(self, n):
		# print(type(n))
		c_ast.NodeVisitor.generic_visit(self, n.stmts[0])

	def visit_Switch(self, n):
		# print(type(n))
		c_ast.NodeVisitor.generic_visit(self, n.stmt)

	def visit_For(self, n):
		# print(type(n))
		c_ast.NodeVisitor.generic_visit(self, n.stmt)

	def visit_While(self, n):
		# print(type(n))
		c_ast.NodeVisitor.generic_visit(self, n.stmt)

	def visit_DoWhile(self, n):
		# print(type(n))
		c_ast.NodeVisitor.generic_visit(self, n.stmt)

class PrintCompound(CompoundVisitor):
	"""
	Test
	"""
	def visit_Compound(self, n):
		print("compound")
		c_ast.NodeVisitor.generic_visit(self, n)

t1 = r"""
void f(int a, int b)
int a;
int b;
{
	{
		int x;
		switch (x)
			case 1:
				break;
			default:
				break;
		if (0)
			return;
		else return;

		for (;;)
			return;

		while (0)
			return;

		do return; while(0);
	}
}
"""


if __name__ == "__main__":
	p = c_parser.CParser()
	ast = p.parse(t1)
	ast.show()

	Brace().visit(ast.ext[0])
	print ast.ext[0].param_decls
	print ast.ext[0].decl.type.args.params
	# print c_generator.CGenerator().visit(ast.ext[0])

	PrintCompound().visit(ast.ext[0])
