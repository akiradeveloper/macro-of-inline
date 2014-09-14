class Env:
	def __init__(self):
		self.record_enabled = False
		self.record_dir = "/tmp/record-macro-of-inline" # Stub
		self.cross_build = False
		self.macroize_static_funs = False
		self.additional_search_paths = []

t = Env()
