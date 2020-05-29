import requests
from requests.auth import HTTPBasicAuth
import json
import sys

def replaceAll(s, src, dst):
	while src in s:
		s = s.replace(src,dst)
	return s

def sendReq(stm):
	stm = replaceAll(stm,"\{","{")
	stm = replaceAll(stm,"\}","}")
	payload = {"statements": [{
		"statement": stm
	}] }
	req = requests.post("http://localhost:7474/db/data/transaction/commit", auth=HTTPBasicAuth("neo4j","simplegraph"),json=payload)
	return req.json()

def convertResp(resp):
	#{'results': [{'columns': ['x', 'y'], 'data': [{'row': [{'name': '1'}, {'name': '2'}], 'meta': [{'id': 6, 'type': 'node', 'deleted': False}, {'id': 7, 'type': 'node', 'deleted': False}]}, {'row': [{'name': '1'}, {'name': '1'}], 'meta': [{'id': 6, 'type': 'node', 'deleted': False}, {'id': 6, 'type': 'node', 'deleted': False}]}, {'row': [{'name': '2'}, {'name': '3'}], 'meta': [{'id': 7, 'type': 'node', 'deleted': False}, {'id': 0, 'type': 'node', 'deleted': False}]}]}], 'errors': []}

	# handle the errors column first
	errors = resp['errors']
	if len(errors) != 0:
		for err in errors:
			print(err['code'] + ": " + err['message'])
		return

	#{'results': [{'columns': ['x', 'y'], 'data': [{'row': [{'name': '1'}, {'name': '2'}], 'meta': [{'id': 6, 'type': 'node', 'deleted': False}, {'id': 7, 'type': 'node', 'deleted': False}]}, {'row': [{'name': '1'}, {'name': '1'}], 'meta': [{'id': 6, 'type': 'node', 'deleted': False}, {'id': 6, 'type': 'node', 'deleted': False}]}, {'row': [{'name': '2'}, {'name': '3'}], 'meta': [{'id': 7, 'type': 'node', 'deleted': False}, {'id': 0, 'type': 'node', 'deleted': False}]}]}], 'errors': []}
	# always one query
	formatted = []
	for result in resp['results'][0]['data']:
		#{'row': [{'name': '1'}, {'name': '2'}], 'meta': [{'id': 6, 'type': 'node', 'deleted': False}, {'id': 7, 'type': 'node', 'deleted': False}]
		# discard meta-info for now
		curr = result['row']
		# always two columns at the end
		tmparr = [curr[0]['name'], curr[1]['name']]
		formatted.append(tmparr)
	return formatted

def executeQuery(stm, printQuery):
	if stm == "":
		return []
	if printQuery:
		print("Executing query\n" + stm + "\n...")
	resp = sendReq(stm)
	form = convertResp(resp)
	return form


if __name__ == "__main__":
	# get the query from a file
	if len(sys.argv) > 1:
		with open(sys.argv[1], 'r') as data:
			executed = executeQuery(data.read(), True)
			print(executed)
	else:
		print("Invalid argument: no data given to querier.")