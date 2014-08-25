from pycparser import c_parser, c_ast

import pycparser_ext
import rewrite_fun

ASTMODE=True # temporary

class LabelizeFuncCall(c_ast.NodeVisitor):
	def visit_FuncCall(self, n):
		n.show()
		pass

class RewriteFile:
	def __init__(self, text):
		self.text = text

	# First rewrite the FuncDef AST nodes
	# and generate the C-code
	def byAST(self):
		parser = c_parser.CParser()
		ast = parser.parse(self.text)

		LabelizeFuncCall().visit(ast)

		for i, n in enumerate(ast.ext):
			if isinstance(n, c_ast.FuncDef):
				if 'inline' in n.decl.funcspec:
					runner = rewrite_fun.RewriteFun(n)
					runner.run()
					ast.ext[i] = runner.returnAST()

		generator = pycparser_ext.CGenerator()
		return generator.visit(ast)

	# (abondoned)
	# Find the function definitions by text searching (e.g. regex)
	# and replace the found by the translated function.
	def byText(self):
		return self.text

	def run(self):
		if ASTMODE:
			return self.byAST()
		else:
			return self.byText()

testcase = r"""
struct T { int x; };
static int x = 0;
inline void f1(void) { x = 1; }
void f2(int
  x) {   }
%s


inline int f3(void)
{
  x = 3;
  f2(x);
}

int main()
{
  f1();
  return 0;
}
""" % rewrite_fun.testcase

if __name__ == "__main__":
	print RewriteFile(testcase).run()
