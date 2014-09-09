from pycparser import c_ast, c_parser, c_generator

class Brace(c_ast.NodeVisitor):

	def visit_If(self, n):
		if not isinstance(n.iftrue, c_ast.Compound):
			comp = c_ast.Compound([n.iftrue])
			n.iftrue = comp
		if not isinstance(n.iffalse, c_ast.Compound):
			comp = c_ast.Compound([n.iffalse])
			n.iffalse = comp
		c_ast.NodeVisitor.generic_visit(self, n)

	def visit_Case(self, n):
		if not isinstance(n.stmts, c_ast.Compound):
			comp = c_ast.Compound(n.stmts)
			n.stmts = [comp]
		c_ast.NodeVisitor.generic_visit(self, n)

	def visit_Default(self, n):
		if not isinstance(n.stmts, c_ast.Compound):
			comp = c_ast.Compound(n.stmts)
			n.stmts = [comp]
		c_ast.NodeVisitor.generic_visit(self, n)

	def visit_Switch(self, n):
		if not isinstance(n.stmt, c_ast.Compound):
			comp = c_ast.Compound([n.stmt])
			n.stmt = comp
		c_ast.NodeVisitor.generic_visit(self, n)

	def visit_For(self, n):
		if not isinstance(n.stmt, c_ast.Compound):
			comp = c_ast.Compound([n.stmt])
			n.stmt = comp
		c_ast.NodeVisitor.generic_visit(self, n)

	def visit_While(self, n):
		if not isinstance(n.stmt, c_ast.Compound):
			comp = c_ast.Compound([n.stmt])
			n.stmt = comp
		c_ast.NodeVisitor.generic_visit(self, n)

	def visit_DoWhile(self, n):
		if not isinstance(n.stmt, c_ast.Compound):
			comp = c_ast.Compound([n.stmt])
			n.stmt = comp
		c_ast.NodeVisitor.generic_visit(self, n)


t1 = r"""
void f()
{
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
"""

p = c_parser.CParser()
ast = p.parse(t1)
ast.show()

Brace().visit(ast)
print c_generator.CGenerator().visit(ast)
