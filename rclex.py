import ply.lex as lex
import sys

# reserved words
reserved = {
  'proj'       : 'PROJ',
  'comp'       : 'COMP',
  'coproj'     : 'COPROJ',
  'id'         : 'ID',
  'di'         : 'DI',
  'inv'        : 'INV',
  'trans'      : 'TRANS',
  'union'      : 'UNION',
  'difference' : 'DIFFERENCE',
  'intersect'  : 'INTERSECT',
}
# List of token names.   This is always required
tokens = ['NUMBER','LPAREN','RPAREN','RELATION'] + list(reserved.values())

totalTemps = 0

# Regular expression rules for simple tokens
t_LPAREN   = r'\('
t_RPAREN   = r'\)'

def t_WORD(t):
    r'[a-zA-Z_]+'
    t.type = reserved.get(t.value.lower(),'RELATION') #check for reserved words
    tempPlus = ["trans"]
    if t.value.lower() in tempPlus:
      global totalTemps
      totalTemps += 1
    return t

# A regular expression rule with some action code
def t_NUMBER(t):
    r'[12]'
    t.value = int(t.value)    
    return t

# Define a rule so we can track line numbers
def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

# A string containing ignored characters (spaces and tabs)
t_ignore  = ' \t'

# Error handling rule
def t_error(t):
    print("Illegal character '%s'" % t.value[0])
    t.lexer.skip(1)

# Build the lexer
lexer = lex.lex()
if __name__ == "__main__":
  if len(sys.argv) > 1:
    with open(sys.argv[1], 'r') as data:
      lexer.input(data.read())

      while True:
        tok = lexer.token()
        if not tok:
          break
        print(tok)
  else:
    print("Invalid argument: no data given to tokenizer.")

# type = NUMBER/PLUS/etc
# value = 1/2/'555'/etc

def passOnTotalTemporaryRelations():
  global totalTemps
  return totalTemps