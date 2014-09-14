import os
import shutil

import cfg
import ext_pycparser

class Recorder:

	def __init__(self):
		self.rec_dir = cfg.t.record_dir
		self.file_rewrite_level = 0

		self.current_fun_name = None
		self.fun_rewrite_level = {}

		if os.path.exists(self.rec_dir):
			shutil.rmtree(self.rec_dir)

		if not os.path.exists(self.rec_dir):
			os.makedirs(self.rec_dir)

	def file_record(self, title, contents):
		if not cfg.t.record_enabled:
			return

		self.file_rewrite_level += 1
		fn = "%s/%d-%s.txt" % (self.rec_dir, self.file_rewrite_level, title)
		f = open(fn, "w")
		f.write(contents)
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

		f = open(fn, "w")
		f.write(ext_pycparser.CGenerator().visit(ast))
		f.close()

t = Recorder()
