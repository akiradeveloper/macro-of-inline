import cfg
import ext_pycparser
import os
import shutil
import StringIO
import time

class Recorder:

	def __init__(self):
		self.rec_dir = cfg.t.record_dir
		self.file_rewrite_level = 0

		self.current_fun_name = None
		self.fun_rewrite_level = {}

		self.last_time = time.clock()

		if os.path.exists(self.rec_dir):
			shutil.rmtree(self.rec_dir)

		if not os.path.exists(self.rec_dir):
			os.makedirs(self.rec_dir)

	def elapsedTime(self):
		cur = time.clock()
		ela = cur - self.last_time
		self.last_time = cur
		return str(ela * 1000) + "[ms]"

	def file_record(self, title, contents):
		if not cfg.t.record_enabled:
			return

		self.file_rewrite_level += 1
		fn = "%s/%d-%s.c" % (self.rec_dir, self.file_rewrite_level, title)
		f = open(fn, "w")
		f.write("/* %s */\n\n%s" % (self.elapsedTime(), contents))
		f.close()

	def fun_record(self, title, ast):
		if not cfg.t.record_enabled:
			return

		if not isinstance(ast, ext_pycparser.Any):
			self.current_fun_name = ast.decl.name

		fun_name = self.current_fun_name
		
		if not fun_name in self.fun_rewrite_level:
			self.fun_rewrite_level[fun_name] = 0

		dn = "%s/%d-%d/%s" % (self.rec_dir, self.file_rewrite_level, self.file_rewrite_level + 1, fun_name)
		if not os.path.exists(dn):
			os.makedirs(dn)

		self.fun_rewrite_level[fun_name] += 1
		fn = "%s/%d-%s.txt" % (dn, self.fun_rewrite_level[fun_name], title)

		ast_txt = StringIO.StringIO()
		ast.show(buf=ast_txt)
		ast_txt = ast_txt.getvalue()

		f = open(fn, "w")
		f.write("%s\n\n%s%s" % (self.elapsedTime(), ext_pycparser.CGenerator().visit(ast), ast_txt))
		f.close()

t = Recorder()
