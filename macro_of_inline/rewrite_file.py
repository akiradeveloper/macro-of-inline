from pycparser import c_parser, c_ast

import pycparser_ext
import rewrite_fun

class RewriteFile:
	def __init__(self, text):
		self.text = text

	def run(self):
		parser = c_parser.CParser()
		ast = parser.parse(self.text)

		for i, n in enumerate(ast.ext):
			if isinstance(n, c_ast.FuncDef):
				if 'inline' in n.decl.funcspec:
					runner = rewrite_fun.RewriteFun(n)
					runner.run()
					ast.ext[i] = runner.returnAST()

		generator = pycparser_ext.CGenerator()
		return generator.visit(ast)

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
}
""" % rewrite_fun.testcase

if __name__ == "__main__":
	print RewriteFile(testcase).run()
