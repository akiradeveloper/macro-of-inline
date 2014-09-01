import pycparser_ext

import os
import shutil

class Recorder:
	ROOTDIR = "record-macro-of-inline"

	def __init__(self):
		self.file_rewrite_level = 0

		self.current_fun_name = None
		self.fun_write_level = {}

		shutil.rmtree(ROOTDIR)

		if not os.path.exists(ROOTDIR):
			os.makedirs(ROOTDIR)

	def file_record(self, title, contents):
		self.file_rewrite_level += 1
		fn = "%s/%d-%s.txt" % (ROOTDIR, self.file_rewrite_level, title)
		f = open(fn, "w")
		f.write(contents)
		f.close()

	def fun_record(self, title, ast):
		if not isinstance(ast, c_ast.Any)
			self.current_fun_name = ast.decl.name

		fun_name = self.current_fun_name
		
		if not fun_name in self.fun_rewrite_level:
			self.fun_rewrite_level[fun_name] = 0

		dn = "%s/%d-%d/%s" % (ROOTDIR, self.file_rewrite_level, self.file_rewrite_level + 1, fun_name)
		if not os.path.exists(dn):
			os.makedirs(dn)

		self.fun_rewrite_level[fun_name] += 1
		fn = "%s/%d-%s.txt" % (dn, self.fun_rewrite_level[fun_name], title)

		f = open(fn, "w")
		f.write(pycparser_ext.CGenerator().visit(ast))
		f.close()

g_recorder = Recorder()

def file_record(title, contents):
	g_recorder.file_record(title, contents)

def fun_record(title, ast):
	g_recorder.fun_record(title, ast)
