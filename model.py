#!/usr/local/bin/python3.2
#
# A list-based language to model instructions.
#
# Values are a tuple of (width, value) where value can be None if
# it is unknown, and False if it is unused.
#
# Syntax:
#	( Verb, arg, ...)
#	"#0b..."	binary constant, number of bits given sets width
#	"#0x..."	hex constant, number of nybbles given sets width
#	"/..."		register

import random

class ModelError(Exception):
        def __init__(self, reason):
                self.reason = reason
                self.value = str(self.reason)
        def __str__(self):
                return repr(self.value)


class model(object):
	def __init__(self):
		self.verbs = {
		"SEQ":	(self.verb_seq, "..."),
		">>":	(self.verb_right_shift, "val", "bits"),
		"<<":	(self.verb_left_shift, "val", "bits" "[bi]" "[bo]"),
		"+":	(self.verb_add, "val", "val" "[ci]" "[co]"),
		"-":	(self.verb_sub, "val", "val" "[bi]" "[bo]"),
		"=":	(self.verb_assign, "dest", "val"),
		"AND":	(self.verb_and, "val1", "val2"),
		"OR":	(self.verb_or, "val1", "val2"),
		"RND":	(self.verb_rnd, None),
		"XOR":	(self.verb_xor, "val1", "val2"),
		"INC":	(self.verb_increment, "val", "[bits]"),
		"DEC":	(self.verb_decrement, "val", "[bits]"),
		"TRIM":	(self.verb_trim, "val", "bits"),
		"ZERO?": (self.verb_zero, "val", "cond1", "cond2"),
		}

	def setreg(self, p, state, reg, val):
		if not reg in state:
			raise ModelError("Set: register %s not in state" % reg)
		if state[reg][0] != val[0]:
			raise ModelError("Setting wrong width %d should be %d"
			    % (val[0], state[reg][0]))
		state[reg] = val

	def getreg(self, p, state, reg):
		if not reg in state:
			raise ModelError("Get: register %s not in state" % reg)
		return state[reg]

	def getint(self, p, state, val):
		assert type(val) == str
		w = 0
		v = 0
		if val[:3] == "#0b":
			for i in val[3:]:
				v <<= 1
				w += 1
				if i >= '0' and i <= '1':
					v |= int(i)
				else:
					raise ModelError(
					    "Int: Illegal binary: %s" % val)
		elif val[:3] == "#0x":
			for i in val[3:]:
				v <<= 4
				w += 4
				try:
					v |= int(i, 16)
				except:
					raise ModelError(
					    "Int: Illegal octal: %s" %  val)
		else:
			raise ModelError("Int: Illegal integer: %s" % val)
		return (w,v)

	def eval(self, p, state, expr):
		#print("Eval:", expr)
		#print("  State:", state)
		if state == None:
			return None

		if type(expr) == str and expr[0] == "/":
			retval = self.getreg(p, state, expr);
		elif type(expr) == str and expr[0] == "#":
			retval = self.getint(p, state, expr);
		elif type(expr) == tuple and expr[0] in self.verbs:
			x = self.verbs[expr[0]]
			if x[1] == None:
				retval = x[0](p, state, expr)
			elif len(x) == len(expr):
				retval = x[0](p, state, expr)
			elif len(x) <= len(expr) and x[-1] == "...":
				retval = x[0](p, state, expr)
			else:
				for i in range(1,len(x)):
					if x[i][0] == "[":
						break;
					if len(expr) < i + 1:
						raise ModelError("Syntax: arg_count:" + str(expr))
				retval = x[0](p, state, expr)
		elif type(expr) == tuple and not expr[0] in self.verbs:
			raise ModelError("Unknown verb" + str(expr[0]))
		else:
			raise ModelError("Unknown expression" + str(expr))

		#print("  Return(", expr, "):", retval)
		return retval

	def verb_seq(self, p, state, expr):
		for i in expr[1:]:
			self.eval(p, state, i)

	def verb_right_shift(self, p, state, expr):
		v1 = self.eval(p, state, expr[1])
		if v1[1] == None:
			return v1
		if len(expr) > 2:
			v2 = self.eval(p, state, expr[2])
		else:
			v2 = (8, 1)
		if v2[1] == None:
			raise ModelError("Verb: >> BITS unknown")
		return (v1[0], v1[1] >> v2[1])

	def verb_left_shift(self, p, state, expr):
		v1 = self.eval(p, state, expr[1])
		if v1[1] == None:
			return v1

		if len(expr) > 2:
			v2 = self.eval(p, state, expr[2])
		else:
			v2 = (8, 1)
		if v2[1] == None:
			raise ModelError("Verb: << BITS unknown")

		return (v1[0], v1[1] << v2[1])

	def verb_assign(self, p, state, expr):
		v2 = self.eval(p, state, expr[2])
		self.setreg(p, state, expr[1], v2)

	def verb_increment(self, p, state, expr):
		if len(expr) > 2:
			v2 = self.eval(p, state, expr[2])
		else:
			v2 = (8, 1)
		v1 = self.getreg(p, state, expr[1])
		if v1[1] != None and v2[1] != None:
			vn = (v1[0], (v1[1] + v2[1]) & ((1 << v1[0]) - 1))
		else:
			vn = (v1[0], None)
		self.setreg(p, state, expr[1], vn)
		return vn

	def verb_decrement(self, p, state, expr):
		if len(expr) > 2:
			v2 = self.eval(p, state, expr[2])
		else:
			v2 = (8, 1)
		v1 = self.getreg(p, state, expr[1])
		if v1[1] != None and v2[1] != None:
			vn = (v1[0], (v1[1] - v2[1]) & ((1 << v1[0]) - 1))
		else:
			vn = (v1[0], None)
		self.setreg(p, state, expr[1], vn)
		return vn

	def verb_or(self, p, state, expr):
		v1 = self.eval(p, state, expr[1])
		v2 = self.eval(p, state, expr[2])
		assert v1[0] == v2[0]
		if v1[1] == None or v2[1] == None:
			return (v1[0], None)
		return (v1[0], v1[1] | v2[1])

	def verb_xor(self, p, state, expr):
		v1 = self.eval(p, state, expr[1])
		v2 = self.eval(p, state, expr[2])
		assert v1[0] == v2[0]
		if v1[1] == None or v2[1] == None:
			return (v1[0], None)
		return (v1[0], v1[1] ^ v2[1])

	def verb_and(self, p, state, expr):
		v1 = self.eval(p, state, expr[1])
		v2 = self.eval(p, state, expr[2])
		assert v1[0] == v2[0]
		if v1[1] == None or v2[1] == None:
			return (v1[0], None)
		return (v1[0], v1[1] & v2[1])

	def verb_add(self, p, state, expr):
		v1 = self.eval(p, state, expr[1])
		v2 = self.eval(p, state, expr[2])
		assert v1[0] == v2[0]

		if len(expr) > 3:
			ci = self.eval(p, state, expr[3])
		else:
			ci = (1,0)

		if v1[1] == None or v2[1] == None or ci[1] == None:
			if len(expr) > 4:
				self.setreg(p, state, expr[4], (1, None))
			return (v1[0], None)

		s = v1[1] + v2[1] + ci[1]

		if len(expr) > 4:
			self.setreg(p, state, expr[4], (1, s >> v1[0]))

		return (v1[0], s & ((1 << v1[0]) - 1))

	def verb_sub(self, p, state, expr):
		v1 = self.eval(p, state, expr[1])
		v2 = self.eval(p, state, expr[2])
		assert v1[0] == v2[0]

		if len(expr) > 3:
			bi = self.eval(p, state, expr[3])
		else:
			bi = (1,0)

		if v1[1] == None or v2[1] == None or bi[1] == None:
			if len(expr) > 4:
				self.setreg(p, state, expr[4], (1, None))
			return (v1[0], None)

		s = v1[1] - (v2[1] + bi)

		if len(expr) > 4:
			self.setreg(p, state, expr[4], (1, s >> v1[0]))

		return (v1[0], s & ((1 << v1[0]) - 1))

	def verb_trim(self, p, state, expr):
		v1 = self.eval(p, state, expr[1])
		v2 = self.eval(p, state, expr[2])
		return(v2[1], v1[1] & ((1 << v2[1]) - 1))

	def verb_zero(self, p, state, expr):
		v1 = self.eval(p, state, expr[1])
		if v1[1] == 0:
			self.eval(p, state, expr[2])
		elif v1[1] != None:
			self.eval(p, state, expr[3])
		else:
			# XXX: what ?
			self.eval(p, state, expr[3])

	def verb_rnd(self, p, state, expr):
		return (1, 1)
		if random.random() >= .5:
			return (1, 1)
		else:
			return (1, 0)

if __name__ == "__main__":

	m = model()

	si = {
		"/R1": (16,0),
	}

	m.eval(None, si, "/R1")
	m.eval(None, si, ("SEQ", "#0b001", "#0x001"))
	m.eval(None, si, (">>", "#0b101", "#0x001"))
	m.eval(None, si, ("=", "/R1", "#0x0001"))
	print(si)
	m.eval(None, si, ("INC", "/R1"))
	print(si)
	m.eval(None, si, ("DEC", "/R1", "#0x3"))
	print(si)
	try:
		m.eval(None, si, ("DEC", "/R2", "#0x3"))
		assert(False)
	except:
		pass
	m.eval(None, si, ("DEC",))
