class Env:
	def __init__(self):
		self.record_enabled = False
		self.record_dir = "/tmp/record-macro-of-inline" # Stub
		self.with_cpp = False
		self.cpp_mode = None
		self.extra_options = []
		self.additional_search_paths = []
		self.macroize_static_funs = False

t = Env()
