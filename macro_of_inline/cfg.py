class Env:
	def __init__(self):
		self.rand_names = set()
		self.record_enabled = False
		self.record_dir = "/tmp/record-macro-of-inline" # Stub
		self.macroize_static_funs = False
		self.additional_search_paths = []

env = Env()
