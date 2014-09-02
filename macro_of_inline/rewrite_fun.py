from pycparser import c_parser, c_ast

import recorder
import pycparser_ext
import collections
import string
import random
import copy
import enum

Symbol = collections.namedtuple('Symbol', 'alias, overwritable')

DEBUG = False

# False -> $oldname -> $randstr
# True -> ($oldname -> ($oldname_$randstr))
VERBOSE = False

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
		if VERBOSE:
			alias = "%s_%s" % (name, alias)
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
		RewriteTypeDecl(alias).visit(node.type)
		c_ast.NodeVisitor.generic_visit(self, node)

	def visit_StructRef(self, node):
		"""
		StructRef = name.field

		Dive into the "name" node for renaming because
		"field" node will never be renamed.
		"""
		self.visit(node.name)
		c_ast.NodeVisitor.generic_visit(self, node.name)

	def visit_Cast(self, node):
		self.visit(node.expr)
		c_ast.NodeVisitor.generic_visit(self, node.expr)

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
	"rename_function_body",
	"rename_args",
	"insert_decl_lines",
	"insert_goto_label",
	"rewrite_return_to_goto",
	"append_namespace_to_labels",
	"memoize"]

class RewriteFun:
	"""
	AST -> AST
	"""
	def __init__(self, env, func):
		self.phase_no = 0
		self.env = env
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

	def canMacroize(self):
		if self.success != None: # Lazy initialization
			return self.success

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

	def renameDecl(self, node, alias):
		"""
		int var -> int $alias
		"""
		node.name = alias
		RewriteTypeDecl(alias).visit(node)

	def renameArgs(self):
		self.phase_no += 1
		if not self.success:
			return self

		for arg in self.args:
			if not arg.shouldInsertDecl():
				alias  = self.init_table.alias(arg.node.name)
				self.renameDecl(arg.node, alias)
			
		return self

	def insertDeclLines(self):
		"""
		Insert decl lines (see. shouldInsertDecl)
		f(int x, char c)
		{
		  ...
		}

		f(int rand1, char rand2)
		{
		  int rand3 = rand1;
		  int rand4 = rand2;
		}
		"""
		self.phase_no += 1
		if not self.success:
			return self

		block_items = self.func.body.block_items
		if not block_items:
			return self

		for arg in reversed(self.args):
			if arg.shouldInsertDecl():
				newname = newrandstr(self.env.rand_names, N)

				# Insert decl line
				oldname = arg.node.name
				if VERBOSE:
					newname = "%s_%s" % (oldname, newname)

				decl = copy.deepcopy(arg.node)
				alias = self.init_table.alias(oldname)
				self.renameDecl(decl, alias)
				decl.init = c_ast.ID(newname)
				block_items.insert(0, decl)

				# Rename the arg
				self.renameDecl(arg.node, newname)

		return self

	def sanitizeNames(self):
		return self.renameFuncBody().show().renameArgs().show().insertDeclLines().show()

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

	class HasReturn(c_ast.NodeVisitor):
		def __init__(self):
			self.result = False

		def visit_Return(self, n):
			self.result = True

	def insertGotoLabel(self):
		self.phase_no += 1
		if not self.success:
			return self

		f = self.HasReturn()
		f.visit(self.func)
		if f.result:
			self.InsertGotoLabel().visit(self.func)

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
		self.phase_no += 1
		if not self.success:
			return self

		self.RewriteReturnToGoto().visit(self.func)
		return self

	class AppendNamespaceToLables(c_ast.NodeVisitor):
		def visit_Goto(self, n):
			n.name = "namespace ## %s" % n.name

		def visit_Label(self, n):
			n.name = "namespace ## %s" % n.name

	def appendNamespaceToLabels(self):
		self.phase_no += 1
		if not self.success:
			return self

		self.AppendNamespaceToLables().visit(self.func)
		return self

	def macroize(self):
		self.phase_no += 1
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
		return self

	def returnAST(self):
		return self.func

	def show(self): 
		recorder.fun_record(PHASES[self.phase_no], self.func)
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
		goto label1;
	}
	label1:
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

testcase_8 = r"""
inline void fun(int x)
{
  int y = (int) x;
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
	# test(testcase_8)
	# test(testcase_void1)
	# test(testcase_void2)
	# test(testcase_void3)
