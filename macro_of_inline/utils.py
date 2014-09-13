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

if __name__ == "__main__":
	a = countMap([2,1,1,2,3])
	b = countMap([3,1,2,2,2])
	countMapDiff(a, b)
	print(a)
