class Env:
	def __init__(self):
		self.rand_names = set()
		self.record_enabled = False
		self.record_dir = "/tmp/record-macro-of-inline" # Stub
		self.macroize_static = False

env = Env()
