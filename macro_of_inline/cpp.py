def cpp(filename):
	pass

def analizeInclude(filename, txt):
	"""
	txt -> [(header, txt)]
	"""
	current_result = None
	result = [] # (lineno, [])
	for line in txt.splitlines():
		line = line.strip()
		if not len(line):
			continue

		if line.startswith("#"):
			xs = line.split()
			fn = xs[2].strip('"')
			if fn == filename:
				lineno = int(xs[1])
				current_result = None
			# Ignore # 1 "<command-line>"
			elif current_result == None and len(xs) > 3:
				current_result = []
				result.append((lineno, current_result))
		elif current_result != None:
			current_result.append(line)

def ast_delete(a, b):
	"""
	AST-level deletion
	a -= b 
	"""

class Apply:
	"""
	(AST -> AST) -> filename -> txt

	The file (of filename) can be before preprocessing.
	It can contains directives.
	"""
	def __init__(self, f):
		self.f = f

	def ast_of(self, txt):
		parser = c_parser.CParser()
		return parser.parse(txt)

	def on(self, filename):
		txt = cpp(filename)

		includes = analyzeInclude(filename, txt)
		included_headers = []
		included_code = ""

		ast_a = ast_of(txt)
		ast_b = ast_of(included_code)
		ast_delete(ast_a, ast_b)

		ast_a = f(ast_a)

		generator = pycparser_ext.CGenerator()
		contents = generator.visit(ast_a)

		return """r
%s
%s
""" % ('\n'.join(included_headers), pycparser_ext.CGenerator.cleanUp(contents))

if __name__ == "__main__":
	testcase = r"""
# 1 "main.c"
# 1 "<command-line>"
# 1 "main.c"
# 1 "/usr/lib/gcc/x86_64-linux-gnu/4.7/include/stdarg.h" 1 3 4
# 40 "/usr/lib/gcc/x86_64-linux-gnu/4.7/include/stdarg.h" 3 4
typedef __builtin_va_list __gnuc_va_list;
# 102 "/usr/lib/gcc/x86_64-linux-gnu/4.7/include/stdarg.h" 3 4
typedef __gnuc_va_list va_list;
# 2 "main.c" 2
# 1 "a.h" 1

# 1 "f/g.h" 1
typedef long mylong;
# 3 "a.h" 2
struct T { int x; };

struct U {
 int y;
  int z;
};
# 3 "main.c" 2
# 1 "b.h" 1
# 1 "c.h" 1
# 2 "b.h" 2
# 1 "d.h" 1
# 1 "e.h" 1
# 1 "d.h" 2
# 3 "b.h" 2
# 1 "f/g.h" 1
typedef long mylong;
# 3 "b.h" 2
# 4 "main.c" 2


int main(void) { return 0; }
"""	
	analizeInclude("main.c", testcase)
