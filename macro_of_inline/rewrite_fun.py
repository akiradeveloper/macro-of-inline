from pycparser import c_parser, c_ast

import pycparser_ext
import collections
import string
import random
import copy
import enum

Symbol = collections.namedtuple('Symbol', 'alias, overwritable')

DEBUG = False
def P(s):
	if not DEBUG:
		return
	print(s)

def randstr(n):
	return ''.join(random.choice(string.letters) for i in xrange(n))

def newrandstr(names, n):
	while True:
		alias = randstr(n)
		if alias in names:
			continue
		else:
			names.add(alias)
			break
	return alias

class Env:
	def __init__(self):
		self.rand_names = set()

N = 16
class NameTable:
	def __init__(self, env):
		self.table = {}
		self.prev_table = None
		self.env = env

	def register(self, name):
		alias = newrandstr(self.env.rand_names, N)
		self.table[name] = Symbol(alias, overwritable=False)

	def declare(self, name):
		if name in self.table:
			if self.table[name].overwritable:
				self.register(name)
		else:
			self.register(name)

	def alias(self, name):
		if name in self.table:
			return self.table[name].alias
		else:
			return name	

	def clone(self):
		new = {}
		for name in self.table:
			new[name] = Symbol(self.table[name].alias, overwritable=True)
		nt = NameTable(self.env)
		nt.table = new
		return nt
	
	def show(self):
		if not DEBUG:
			return
		print("NameTable")
		for name in self.table:
			tup = self.table[name]
			print("  %s -> (alias:%s, overwritable:%r)" % (name, tup.alias, tup.overwritable))

ArgType = enum.Enum("ArgType", "other fun array")
class QueryDeclType(c_ast.NodeVisitor):
	def __init__(self):
		self.result = ArgType.other

	def visit_FuncDecl(self, node):
		self.result = ArgType.fun

	def visit_ArrayDecl(self, node):
		self.result = ArgType.array

class Arg:
	def __init__(self, node):
		self.node = node

	def queryType(self):
		query = QueryDeclType() 	
		query.visit(self.node)
		return query.result

	def shouldInsertDecl(self):
		"""
		Need to insert decl lines.
		except func decl (function pointer) and array decl (e.g. int xs[])
		which are immutable through the function body.
		"""
		t = self.queryType()
		return not (t == ArgType.fun or t == ArgType.array)

	def show(self):
		if not DEBUG:
			return
		print("name %s" % self.node.name)
		self.node.type.show()
		print("type %r" % self.queryType())

class RewriteTypeDecl(c_ast.NodeVisitor):
	def __init__(self, alias):
		self.alias = alias

	def visit_TypeDecl(self, node):
		node.declname = self.alias

class RenameVars(c_ast.NodeVisitor):
	def __init__(self, init_table):
		self.cur_table = init_table

	def visit_Compound(self, node):
		self.switchTable()
		c_ast.NodeVisitor.generic_visit(self, node)
		self.revertTable()

	def visit_Decl(self, node):
		self.cur_table.register(node.name)
		alias = self.cur_table.alias(node.name)
		P("Decl: %s -> %s" % (node.name, alias))
		node.name = alias
		RewriteTypeDecl(alias).visit(node)
		c_ast.NodeVisitor.generic_visit(self, node)

	def visit_StructRef(self, node):
		"""
		StructRef = name.field

		Dive into the "name" node for renaming because
		"field" node will never be renamed.
		"""
		self.visit(node.name)
		c_ast.NodeVisitor.generic_visit(self, node.name)

	def visit_ID(self, node):
		alias = self.cur_table.alias(node.name)
		P("ID: %s -> %s" % (node.name, alias))
		node.name = alias

	def switchTable(self):
		P("switch table")
		self.cur_table.show()
		new_table = self.cur_table.clone()
		new_table.prev_table = self.cur_table
		self.cur_table = new_table

	def revertTable(self):
		P("revert table")
		self.cur_table = self.cur_table.prev_table


GOTO_LABEL = "exit"

PHASES = [
	"rename function body",
	"rename args",
	"insert decl lines",
	"insert goto label",
	"rewrite return to goto",
	"append namespace to labels",
	"memoize"]

class RewriteFun:
	def __init__(self, env, func):
		self.phase_no = 0
		self.func = func

		if DEBUG:
			self.func.show()

		self.success = None
		self.success = self.canMacroize()

		self.args = []
		self.init_table = NameTable(env)

		params = []
		if not self.voidArgs():
			params = func.decl.type.args.params	

		for param_decl in params:
			arg = Arg(param_decl)
			self.args.append(arg)

		for arg in self.args:
			name = arg.node.name
			self.init_table.declare(name)

	class ReturnVoid(c_ast.NodeVisitor):
		def __init__(self):
			self.result = False

		def visit_ParamList(self, n):
			pass

		def visit_TypeDecl(self, n):
			self.result = "void" in n.type.names

	def returnVoid(self):
		# void f(...)
		f = self.ReturnVoid()
		f.visit(self.func.decl)
		return f.result

	class VoidParam(c_ast.NodeVisitor):
		def __init__(self):
			self.result = False

		def visit_TypeDecl(self, n):
			self.result = "void" in n.type.names

	def voidArgs(self):
		args = self.func.decl.type.args

		# f()
		if args == None:
			return True

		# f(a, b, ...)
		if len(args.params) > 1:
			return False

		param = args.params[0]
		query = QueryDeclType()
		query.visit(param)

		# f(...(*g)(...))
		if query.result == ArgType.fun:
			return False

		# f(void)
		f = self.VoidParam()
		f.visit(param)
		return f.result

	class HasJump(c_ast.NodeVisitor):
		def __init__(self):
			self.result = False

		def visit_Goto(self, n):
			self.result = True

		def visit_Label(self, n):
			self.result = True

	def canMacroize(self):
		if self.success != None: # Lazy initialization
			return self.success

		has_jump = self.HasJump()
		has_jump.visit(self.func)
		if has_jump.result:
			return False

		if not self.returnVoid():
			return False

		return True

	def renameFuncBody(self):
		if not self.success:
			return self

		block_items = self.func.body.block_items
		if not block_items:
			return self

		visitor = RenameVars(self.init_table)
		for x in block_items:
			visitor.visit(x)

		return self

	def renameArgs(self):
		if not self.success:
			return self

		for arg in self.args:
			if not arg.shouldInsertDecl():
				alias  = self.init_table.alias(arg.node.name)
				arg.node.name = alias
				f = RewriteTypeDecl(alias)
				f.visit(arg.node)
			
		self.phase_no += 1
		return self

	def insertDeclLines(self):
		"""
		Insert decl lines (see. shouldInsertDecl)
		{
		  int randname1 = x;
		  char randname2 = c;
		  ...
		}
		"""
		if not self.success:
			return self

		block_items = self.func.body.block_items
		if not block_items:
			return self

		for arg in reversed(self.args):
			if arg.shouldInsertDecl():
				decl = copy.deepcopy(arg.node)
				alias = self.init_table.alias(arg.node.name)
				decl.name = alias
				RewriteTypeDecl(alias).visit(decl)
				decl.init = c_ast.ID(arg.node.name)
				block_items.insert(0, decl)
		self.phase_no += 1
		return self

	def sanitizeNames(self):
		return self.renameFuncBody().renameArgs().insertDeclLines()

	class InsertGotoLabel(c_ast.NodeVisitor):
		"""
		Renames the identifiers by random sequence so that they never conflicts others.

		{
		  ...
		  GOTO_LABEL:
		  ;
		}
		"""
		def visit_Compound(self, n):
			if not n.block_items:
				n.block_items = []
			n.block_items.append(c_ast.Label(GOTO_LABEL, c_ast.EmptyStatement()))

	def insertGotoLabel(self):
		if not self.success:
			return self

		self.InsertGotoLabel().visit(self.func)
		self.phase_no += 1
		return self

	class RewriteReturnToGoto(c_ast.NodeVisitor):
		"""
		Visit a compound and rewrite "return" to "goto GOTO_LABEL".
		We assume at most only one "return" exists in a compound.
		"""
		def visit_Compound(self, n):
			if not n.block_items:
				n.block_items = []

			return_index = None
			for (i, item) in enumerate(n.block_items):
				if isinstance(item, c_ast.Return):
					return_index = i
			if return_index != None:
				n.block_items[return_index] = c_ast.Goto(GOTO_LABEL)
			c_ast.NodeVisitor.generic_visit(self, n)

	def rewriteReturnToGoto(self):
		if not self.success:
			return self

		self.RewriteReturnToGoto().visit(self.func)
		self.phase_no += 1
		return self

	class AppendNamespaceToLables(c_ast.NodeVisitor):
		def visit_Goto(self, n):
			n.name = "namespace ## %s" % n.name

		def visit_Label(self, n):
			n.name = "namespace ## %s" % n.name

	def appendNamespaceToLabels(self):
		if not self.success:
			return self

		self.AppendNamespaceToLables().visit(self.func)
		self.phase_no += 1
		return self

	def macroize(self):
		if not self.success:
			return self

		fun_name = self.func.decl.name
		args = ', '.join(["namespace"] + map(lambda arg: arg.node.name, self.args))
		generator = pycparser_ext.CGenerator()
		body_contents = generator.visit(self.func.body).splitlines()[1:-1]
		if not len(body_contents):
			body_contents = [""]
		body = '\n'.join(map(lambda x: "%s \\" % x, body_contents))
		macro = r"""
#define %s(%s) \
do { \
%s
} while(0)
""" % (fun_name, args, body)
		self.func = pycparser_ext.Any(macro)
		self.phase_no += 1
		return self

	def returnAST(self):
		return self.func

	def show(self): 
		P("\nafter phase: %s" % PHASES[self.phase_no])
		generator = pycparser_ext.CGenerator()
		print(generator.visit(self.func))
		return self

testcase = r"""
inline void fun(int x, char *y, int (*f)(int), void (*g)(char c), struct T *t, int ys[3])  
{
	int z = *y;
	int *pz = &z;
	int xs[3];
	x = z;
	while (x) {
		int x;
		x = 0;
		x = 0;
		do {
			int x = 0;
			x += x;
		} while (x);
		x += x;
	}
	int alpha;
	if (*y) {
		t->x = f(*y);
	} else {
		g(t->x);
	}
	do {
		struct T t;
		t.x = 1;
	} while (0);
}
"""

testcase_2 = r"""
inline void fun(int x) {}
"""

testcase_3 = r"""
inline int fun(int x) { return x; }
"""

testcase_4 = r"""
inline void fun(int x)
{
	struct T *t = tt + 0;
	if (t->x) {
		return;
	} else {
	}
	while (1) {
		struct T *t;
		y = t->x;
		return;
	}
	return;
}
"""

testcase_5 = r"""
inline void fun_1(int *x) {}
inline void fun_2(int **x) {}
"""

testcase_6 = r"""
inline int * fun_1(void) {}
inline int ** fun_2(void) {}
"""

testcase_7 = r"""
inline void fun(void)
{
	int a[3];
	int xx[10];
	x = a[0];
	x = *(b + 0);
	x = (&xx[0])->x;
}
"""

testcase_void1 = r"""
inline void fun(void)
{
	x = 1;
	goto exit;
exit:
	;
}
"""

testcase_void2 = r"""
inline void fun()
{
	x = 1;
	do {} while (0);
}
"""

testcase_void3 = r"""
inline void fun(void (*f)(void))
{
	f();
	x = 1;
}
"""

def test(testcase):
	parser = c_parser.CParser()
	ast = parser.parse(testcase)
	rewrite_fun = RewriteFun(Env(), ast.ext[0])
	rewrite_fun.renameFuncBody().show().renameArgs().show().insertDeclLines().show().insertGotoLabel().show().rewriteReturnToGoto().show().appendNamespaceToLabels().show().macroize().show()

if __name__ == "__main__":
	# test(testcase)
	# test(testcase_2)
	# test(testcase_3)
	test(testcase_4)
	# test(testcase_5)
	# test(testcase_6)
	# test(testcase_7)
	# test(testcase_void1)
	# test(testcase_void2)
	# test(testcase_void3)
