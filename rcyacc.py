import ply.yacc as yacc
from rclex import tokens, passOnTotalTemporaryRelations
import sys
import os

precedence = (
	('left', 'COMP', 'UNION', 'INTERSECT', 'DIFFERENCE'),
)

varNumber = 0
tempRels  = 0
doPrint   = False
errored   = False
transed   = {}

class Query:
	withs = ""
	match = ""
	where = ""
	retX  = ""
	retY  = ""
	num = -1
	asWith = False
	enforceDistinct = False
	parenthable = True
	expr = ""

	def initVars(self):
		self.retX = self.getQueryVarX()
		self.retY = self.getQueryVarY()		

	def initMatch(self):
		self.initVars()
		self.match = "(" + self.retX + "), (" + self.retY + ")"

	def combineWheres(self, where1, where2):
		self.where = where1
		self.addToWhere(where2)

	def addToWhere(self, newwhere):
		if self.where != "" and newwhere != "":
			self.where += " AND "
		self.where += newwhere

	def addEquality(self, src, dst):
		self.addToWhere(src + " = " + dst)

	def combineWiths(self, with1, with2):
		self.addWith(with1)
		self.addWith(with2)

	def addWith(self, newWith):
		if self.withs == "":
			self.withs = newWith
		else:
			self.withs += "\n" + newWith

	def toStr(self):
		s = ""
		if self.withs != "":
			s += self.withs + "\n"
		s += "// " + self.expr + "\n"
		s += "MATCH " + self.match
		if self.where != "":
			s += "\nWHERE " + self.where + ""
		if self.asWith:
			s += "\nWITH "
		else:
			if self.enforceDistinct:
				s += "\nRETURN DISTINCT "
			else:
				s += "\nRETURN " 
		s += self.retX + ", " + self.retY
		return s

	def replaceInWhere(self, src, dst):
		while src in self.where:
			self.where = self.where.replace(src, dst)

	def toCreate(self):
		self.asWith = True
		global tempRels
		tempRels += 1
		temprel = "temporary" + str(tempRels)
		self.where += "\nCREATE (" + self.retX + ")-[:" + temprel + "{_temporary:true}]->(" + self.retY + ")"


	def finalize(self):
		# this is just to take care of the case where retX = retY on the final return
		if self.retX == self.retY:
			self.retY = self.retY + " AS y_"
		# clean up the cluttering temporary relationships
		global tempRels
		if tempRels > 0:
			# add a pre-with that gives every existing relationship the attribute non-temporary
			self.withs = "MATCH (x)-[r]->(y) SET r._temporary = false WITH x,y\n" + self.withs
			# the x and y from the above with can just be discarded, really; they don't influence anything.

			self.where += "\n\n// cleanup"
			for i in range(0, tempRels):
				qvar = self.getNewVarNumber()
				qx = "x" + str(qvar)
				qy = "y" + str(qvar)
				q  = "\nWITH " + self.retX + ", " + self.retY
				q += "\nMATCH (" + qx + ")-[rel:temporary" + str(i+1) + "]->(" + qy + ")"
				q += "\nDELETE rel"
				# add to current query
				self.where += q

			self.where += "\nWITH " + self.retX + "," + self.retY
			self.where += "\nMATCH ()-[r{_temporary:false}]->() REMOVE r._temporary"

		tempRels = 0
		self.enforceDistinct = True

	def getNewVarNumber(self):
		global varNumber
		varNumber += 1
		return varNumber - 1

	def generateQueryVarNumber(self):
		self.num = self.getNewVarNumber()

	def getQueryVarX(self):
		if self.num == -1:
			self.generateQueryVarNumber()
		return "x" + str(self.num)

	def getQueryVarY(self):
		if self.num == -1:
			self.generateQueryVarNumber()
		return "y" + str(self.num)

def p_expression_R(p):
	'expression : RELATION'
	q = Query()
	q.retX = q.getQueryVarX()
	q.retY = q.getQueryVarY()
	q.match = "(" + q.retX + "), (" + q.retY + ")"
	q.where = "(" + q.retX + ")-[:" + p[1] + "]->(" + q.retY + ")"
	q.expr = "R"
	p[0] = q

def p_expression_comp(p):
	'expression : expression COMP expression'
	q = Query()
	q1 = p[1]
	q2 = p[3]
	q.match = q1.match + ", " + q2.match
	q.combineWiths(q1.withs, q2.withs)
	q.combineWheres(q1.where, q2.where)
	q.addEquality(q1.retY, q2.retX)
	q.retX = q1.retX
	q.retY = q2.retY
	q.expr = "(" + q1.expr + " COMP " + q2.expr + ")"
	p[0] = q

def p_expression_ID(p):
	'expression : ID'
	q = Query()
	q.retX = q.getQueryVarX()
	q.match = "(" + q.retX + ")"
	q.retY = q.retX
	q.expr = "ID"
	p[0] = q

def p_expression_DI(p):
	'expression : DI'
	q = Query()
	q.initMatch()
	q.where = q.retX + " <> " + q.retY
	q.expr = "DI"
	p[0] = q

def p_expression_proj(p):
	'expression : PROJ NUMBER LPAREN expression RPAREN'
	q = p[4]
	if p[2] == 1:
		q.retY = q.retX
	if p[2] == 2:
		q.retX = q.retY
	#no need to adjust the WITHs
	q.expr = "P" + str(p[2]) + " (" + q.expr + ")"
	p[0] = q

def p_expression_inv(p):
	'expression : INV LPAREN expression RPAREN'
	q = p[3]
	q.retX, q.retY = q.retY, q.retX
	# no need to adjust the WITHs
	q.expr = "INV (" + q.expr + ")"
	p[0] = q

def p_expression_intersect(p):
	'expression : expression INTERSECT expression'
	q = Query()
	q1 = p[1]
	q2 = p[3]
	q.match = q1.match + "," + q2.match
	#okay, so, intersect: combine the wheres
	q.combineWiths(q1.withs, q2.withs)
	q.combineWheres(q1.where, q2.where)
	q.addEquality(q1.retX, q2.retX)
	q.addEquality(q1.retY, q2.retY)
	q.retX = q1.retX
	q.retY = q1.retY
	q.expr = "(" + q1.expr + " INTERSECT " + q2.expr + ")"
	p[0] = q

def p_expression_union(p):
	'expression : expression UNION expression'
	q = Query()
	q1 = p[1]
	q2 = p[3]
	q.combineWiths(q1.withs, q2.withs)
	q.initMatch()
	chained = False
	if q1.parenthable and q2.parenthable:
		q.match += ", " + q1.match + ", " + q2.match
		#UNION: WHERE (q1) or (q2)
		q1.where += " AND " + q.retX + ' = ' + q1.retX + ' AND ' + q.retY + ' = ' + q1.retY
		q2.where += " AND " + q.retX + ' = ' + q2.retX + ' AND ' + q.retY + ' = ' + q2.retY
		q.where = "(" + q1.where + ") OR (" + q2.where + ")"
		q.where = "(" + q.where + ")"
	if (q1.parenthable == False) and q2.parenthable:
		#UNION: with (q1), MATCH q2
		q1.asWith = True
		q.withs += q1.toStr()
		q.match += "," + q2.match
		q.where = "(" + q1.retX + " = " + q.retX + " AND " + q1.retY + " = " + q.retY + ")"
		q2.where += " AND " + q.retX + ' = ' + q2.retX + ' AND ' + q.retY + ' = ' + q2.retY
		q.where += " OR (" + q2.where + ")"	
	if q1.parenthable and (q2.parenthable == False):
		#UNION: with (q2), MATCH q1
		q2.asWith = True
		q.withs += q2.toStr()
		q.match += "," + q1.match
		q.where = "(" + q2.retX + " = " + q.retX + " AND " + q2.retY + " = " + q.retY + ")"
		q1.where += " AND " + q.retX + ' = ' + q1.retX + ' AND ' + q.retY + ' = ' + q1.retY
		q.where += " OR (" + q1.where + ")"
	if not (q1.parenthable or q2.parenthable):
		q1.asWith = True
		q.withs += q1.toStr()
		q2.asWith = True
		q.withs += q2.toStr()
		#modify the second WITH to also pass on the variables of the first WITH
		q.withs += "," + q1.retX + "," + q1.retY
		#apply UNION-ing of two conditions
		q.where =  "(" + q1.retX + " = " + q.retX + " AND " + q1.retY + " = " + q.retY + ")"
		q.where += " OR "
		q.where += "(" + q2.retX + " = " + q.retX + " AND " + q.retY + " = " + q2.retY + ")"

	q.expr = "(" + q1.expr + " UNION " + q2.expr + ")"
	p[0] = q

def p_expression_difference(p):
	'expression : expression DIFFERENCE expression'
	q = Query()
	q1 = p[1]
	q2 = p[3]
	q.combineWiths(q1.withs, q2.withs)
	q.match = q1.match
	q.where = q1.where
	q.where += " AND NOT EXISTS { MATCH " + q2.match + " WHERE " + q2.where
	q.where += " AND " + q1.retX + " = " + q2.retX
	q.where += " AND " + q1.retY + " = " + q2.retY
	q.where += "}"
	q.retX = q1.retX
	q.retY = q1.retY	
	q.expr = "(" + q1.expr + " DIFFERENCE " + q2.expr + ")"
	q.parenthable = False
	p[0] = q

def p_expression_coproj(p):
	'expression : COPROJ NUMBER LPAREN expression RPAREN'
	q = Query()
	qA = p[4]
	q.addWith(qA.withs)
	tempvar = "t" + str(q.getNewVarNumber())
	q.match = "(" + tempvar + ")"
	if p[2] == 1:
		qA.addEquality(qA.retX, tempvar)
	else:
		qA.addEquality(qA.retY, tempvar)
	q.where = "NOT EXISTS { MATCH " + qA.match + " WHERE " + qA.where + " }"
	q.retX = tempvar
	q.retY = tempvar
	q.expr = "CP" + str(p[2]) + " (" + q.expr + ")"
	q.parenthable = False
	p[0] = q

def p_expression_trans(p):
	'expression : TRANS LPAREN expression RPAREN'
	global tempRels, transed
	q = Query()	
	q1 = p[3]

	transno = -1
	if q1.expr in transed:
		# re-use previous transitive closure temprelation
		transno = transed[q1.expr]
	else:
		# create new transitive closure temprelation
		# chain the previous query as a WITH
		q1.toCreate()
		q.withs = q1.toStr()
		transno = tempRels		
		transed[q1.expr] = tempRels
	
	q.initMatch()
	q.where = "(" + q.retX + ")-[:temporary" + str(transno) + "*..]->(" + q.retY + ")"

	q.expr = "TRANS (" + q1.expr + ")"
	p[0] = q

def p_expression_parenth(p):
	'expression : LPAREN expression RPAREN'
	p[2].expr = "(" + p[2].expr + ")"
	p[0] = p[2]

def p_error(p):
	global doPrint
	global errored
	errored = True
	return None

def translate(orig, printAllowed = False):
	global doPrint
	global errored
	doPrint = printAllowed
	parser = yacc.yacc()
	r = parser.parse(orig)
	if r != None and not errored:
		r.finalize()
		s = r.toStr()
		return s
	else:
		if printAllowed:
			print("No valid query formed.")
		errored = False
		return ""

def isfile(filename):
	# test by trying to open the file
	if os.path.isfile(filename):
		return True
	# not a binary check on os.path.isfile just in case
	return False

if __name__ == "__main__":
	if len(sys.argv) > 1:
		print("> python rcyacc.py \"" + sys.argv[1] + "\"")
		if isfile(sys.argv[1]):
			print("Interpreting argument as file...")
			with open(sys.argv[1],'r') as data:
				for item in data:
					tl = translate(item, True)
					print(tl)
		else:
			print("Interpreting argument as query string...")
			# handle it as a query string
			tl = translate(sys.argv[1], True)
			print(tl)
	else:
		print("Invalid argument: no data given to yacc.")