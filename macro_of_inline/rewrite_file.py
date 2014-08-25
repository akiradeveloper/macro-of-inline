from pycparser import c_parser, c_ast

import pycparser_ext
import rewrite_fun

class LabelizeFuncCall(c_ast.NodeVisitor):
	def __init__(self, env, macro_names):
		self.env = env
		self.macro_names = macro_names

	def visit_FuncCall(self, n):
		if not n.name.name in self.macro_names: # function pointer
			return
		exit_label = rewrite_fun.newrandstr(self.env.rand_names, rewrite_fun.N)
		if n.args == None:
			n.args = c_ast.ExprList([])
		n.args.exprs.insert(0, c_ast.ID(exit_label))

class RewriteFile:
	def __init__(self, text):
		self.text = text
		self.env = rewrite_fun.Env()

	def run(self):
		parser = c_parser.CParser()
		ast = parser.parse(self.text)

		macroizables = [] # (i, runner)
		for i, n in enumerate(ast.ext):
			if isinstance(n, c_ast.FuncDef):
				if 'inline' in n.decl.funcspec:
					runner = rewrite_fun.RewriteFun(self.env, n)
					runner.sanitizeNames()
					macroizables.append((i, runner))

		LabelizeFuncCall(self.env, [runner.func.decl.name for i, runner in macroizables]).visit(ast)

		for i, runner in macroizables:
			runner.insertGotoLabel().rewriteReturnToGoto().macroize()
			ast.ext[i] = runner.returnAST()

		generator = pycparser_ext.CGenerator()
		return generator.visit(ast)

testcase = r"""
struct T { int x; };
static int x = 0;
inline void f1(void) { x = 1; }
inline void f2(int
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
