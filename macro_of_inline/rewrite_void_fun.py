from pycparser import c_parser, c_ast

import collections
import copy
import enum

import cfg
import ext_pycparser
import recorder
import rewrite
import utils

Symbol = collections.namedtuple('Symbol', 'alias, overwritable')

# False -> ($oldname -> $randstr)
# True  -> ($oldname -> ($oldname_$randstr))
VERBOSE = False

class NameTable:
	def __init__(self):
		self.table = {}
		self.prev_table = None

	def register(self, name):
		alias = rewrite.newrandstr()
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
		nt = NameTable()
		nt.table = new
		return nt
	
	def show(self):
		if not utils.DEBUG:
			return
		print("NameTable")
		for name in self.table:
			tup = self.table[name]
			print("  %s -> (alias:%s, overwritable:%r)" % (name, tup.alias, tup.overwritable))

class RenameVars(ext_pycparser.NodeVisitor):
	def __init__(self, init_table):
		self.cur_table = init_table

	def visit_Compound(self, node):
		self.switchTable()
		ext_pycparser.NodeVisitor.generic_visit(self, node)
		self.revertTable()

	def visit_Decl(self, node):
		self.cur_table.register(node.name)
		alias = self.cur_table.alias(node.name)
		utils.P("Decl: %s -> %s" % (node.name, alias))
		node.name = alias
		ext_pycparser.RewriteTypeDecl(alias).visit(node.type)
		ext_pycparser.NodeVisitor.generic_visit(self, node)

	def visit_StructRef(self, node):
		"""
		StructRef = name.field

		Dive into the "name" node for renaming because
		"field" node will never be renamed.
		"""
		self.visit(node.name)
		ext_pycparser.NodeVisitor.generic_visit(self, node.name)

	def visit_Cast(self, node):
		self.visit(node.expr)
		ext_pycparser.NodeVisitor.generic_visit(self, node.expr)

	def visit_ID(self, node):
		alias = self.cur_table.alias(node.name)
		utils.P("ID: %s -> %s" % (node.name, alias))
		node.name = alias

	def switchTable(self):
		utils.P("switch table")
		self.cur_table.show()
		new_table = self.cur_table.clone()
		new_table.prev_table = self.cur_table
		self.cur_table = new_table

	def revertTable(self):
		utils.P("revert table")
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

class Main(ext_pycparser.FuncDef):
	"""
	AST -> AST
	"""
	class Arg(ext_pycparser.ParamDecl):
		def __init__(self, param):	
			ext_pycparser.ParamDecl.__init__(self, param)

		def shouldInsertDecl(self):
			"""
			Need to insert decl lines.
			except func decl (function pointer) and array decl (e.g. int xs[])
			which are immutable through the function body.
			"""
			t = self.queryType()
			return not (t == ext_pycparser.ArgType.fun or t == ext_pycparser.ArgType.array)

	def __init__(self, func):
		self.phase_no = 0
		self.func = func

		# Like Maybe monad, we will keep the state if once failed.
		self.ok = True

		if utils.DEBUG:
			self.func.show()

		self.args = []
		self.init_table = NameTable()

		# We consider f(void) as f() that truly doesn't have arguments as AST-level.
		if self.voidArgs():
			return

		for param_decl in func.decl.type.args.params:
			arg = self.Arg(param_decl)
			self.args.append(arg)

		for arg in self.args:
			name = arg.node.name
			self.init_table.declare(name)

	def renameFuncBody(self):
		if not self.ok: return self

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
		ext_pycparser.RewriteTypeDecl(alias).visit(node)

	def renameArgs(self):
		self.phase_no += 1
		if not self.ok: return self

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
		if not self.ok: return self

		block_items = self.func.body.block_items
		if not block_items:
			return self

		for arg in reversed(self.args):
			if arg.shouldInsertDecl():
				newname = rewrite.newrandstr()

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

	class InsertGotoLabel(ext_pycparser.NodeVisitor):
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
			# We don't need recursive generic_visit() because we only want to
			# insert goto at the top level.

	class HasReturn(ext_pycparser.NodeVisitor):
		def __init__(self):
			self.result = False

		def visit_Return(self, n):
			self.result = True

	def insertGotoLabel(self):
		self.phase_no += 1
		if not self.ok: return self

		f = self.HasReturn()
		f.visit(self.func)
		if f.result:
			self.InsertGotoLabel().visit(self.func)
		return self

	class RewriteReturnToGoto(ext_pycparser.NodeVisitor):
		"""
		Visit a compound and rewrite "return" to "goto GOTO_LABEL".
		We assume at most only one "return" exists in a compound.
		"""
		def visit_Return(self, n):
			ext_pycparser.NodeVisitor.rewrite(self.current_parent, self.current_name, c_ast.Goto(GOTO_LABEL))

	def rewriteReturnToGoto(self):
		self.phase_no += 1
		if not self.ok: return self

		self.RewriteReturnToGoto().visit(self.func)
		return self

	class AppendNamespaceToLables(ext_pycparser.NodeVisitor):
		def visit_Goto(self, n):
			n.name = "namespace ## %s" % n.name

		def visit_Label(self, n):
			n.name = "namespace ## %s" % n.name

	def appendNamespaceToLabels(self):
		self.phase_no += 1
		if not self.ok: return self

		self.AppendNamespaceToLables().visit(self.func)
		return self

	def macroize(self):
		self.phase_no += 1
		if not self.ok: return self

		fun_name = "macro_%s" % self.name()
		args = ', '.join(["namespace"] + map(lambda arg: arg.node.name, self.args))
		generator = ext_pycparser.CGenerator()
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
		self.func = ext_pycparser.Any(macro)
		return self

	def returnAST(self):
		return self.func

	def show(self): 
		recorder.t.fun_record(PHASES[self.phase_no], self.func)
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

testcase_9 = r"""
inline struct T **fun(struct T *t) {}
"""

testcase_10 = r"""
inline void fun(int x, ...) {}
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
	# ast.show()
	rewrite_fun = Main(ast.ext[0])
	# print rewrite_fun.returnVoid()
	# print rewrite_fun.voidArgs()
	rewrite_fun.renameFuncBody().show().renameArgs().show().insertDeclLines().show().insertGotoLabel().show().rewriteReturnToGoto().show().appendNamespaceToLabels().show().macroize().show().returnAST().show()

if __name__ == "__main__":
	test(testcase)
	# test(testcase_2)
	# test(testcase_3)
	# test(testcase_4)
	# test(testcase_5)
	# test(testcase_6)
	# test(testcase_7)
	# test(testcase_8)
	# test(testcase_9)
	# test(testcase_10)
	# test(testcase_void1)
	# test(testcase_void2)
	# test(testcase_void3)
