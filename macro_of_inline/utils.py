import cfg
import pycparser
import random
import string

DEBUG = False

def P(s):
	if not DEBUG:
		return
	print(s)

N = 16
def randstr(n):
	return ''.join(random.choice(string.letters) for i in xrange(n))

def newrandstr(names, n):
	while True:
		alias = randstr(n)
		if alias in names:
			continue
		else:
			names.add(alias)
			break
	return alias

def countMap(xs):
	m = {}
	for x in xs:
		if not x in m:
			m[x] = 0
		m[x] += 1
	return m

def countMapDiff(m1, m2):
	"""
	m1 -= m2
	"""
	assert(set(m1.keys()).issuperset(set(m2.keys())))
	for k in m2.keys():
		m1[k] -= m2[k]

def to_option(x):
	"""
	_o -> -o
	__option -> --option
	"""
	l = list(x)
	i = 0
	while (l[i] == '_'):
		l[i] = '-'
		i += 1
	return ''.join(l)

def cpp(filename):
	"""
	File -> Text

	__builtin_va_list is really built-in and we can't access the
	definition in header file. We redefine this for parsing.
	"""
	cpp_args = ['-E', '-U__GNUC__']
	cpp_args.extend([r'%s' % to_option(option) for option in cfg.t.extra_options])
	return pycparser.preprocess_file(filename, cpp_path='gcc', cpp_args=cpp_args)

if __name__ == "__main__":
	a = countMap([2,1,1,2,3])
	b = countMap([3,1,2,2,2])
	countMapDiff(a, b)
	print(a)

	print cpp("tests/proj/main.c")
