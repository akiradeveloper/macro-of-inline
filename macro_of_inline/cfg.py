class Env:
	def __init__(self):
		self.record_enabled = False
		self.record_dir = "/tmp/record-macro-of-inline"
		self.with_cpp = False
		self.cpp_mode = None
		self.extra_options = []
		self.inline_mask = 7
		self.fake_include = None

t = Env()
