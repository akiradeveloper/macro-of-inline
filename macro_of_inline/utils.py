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
