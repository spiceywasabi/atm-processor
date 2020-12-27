#!/usr/bin/env python
import socket
import datetime
import os
import sys
import pyDes
import string
import traceback
import time
import subprocess

from pprint import pprint

OPENWRTMODE=True
SVCTIMEOUT=250

REMOTE_SERVER="127.0.0.1"
REMOTE_PORT=2265 
path = sys.argv[1] 

if not os.path.exists(path):
	print("error path does not exist for serial processor")
	exit(1)


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
                        logs.error("error while reading config",e)
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
                        if int(c) == 1:
                                BCODE="111"
                        else:
                                BCODE="000"
                c = get_setting(check_name)
                if c is not None:
                        BPERSON=c


# Mode to be set
mode = 0o666

# flags
flags = os.O_NOCTTY | os.O_RDWR

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
#       print("%s Binary: %s"%(m,str(b)))


def makeMessage(buf,parity_msg=True,parity_lrc=False):
        parity_end = 7 # 0 is first char
        fin_msg = ""
        for ch in buf:
                och = ord(ch)
                if parity_msg and parityEven(och):
                        och = setBit(och,parity_end)
                fin_msg+=chr(och)
        #checksum = 0
        #for el in buf:
        #        checksum ^= ord(el)
        #print checksum, hex(checksum), chr(checksum)
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

fd = os.open(path, flags, mode)

###########################################################################################
try:
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
				'11': self.pgen,
				'12': self.pgen,
				'15': self.pgen,
				'21': self.pgen,
				'22': self.pgen,
				'25': self.pgen,
				'29': self.pgen,
				'31': self.pgen,
				'32': self.pgen,
				'35': self.pgen,
				'41': self.pgen,
				'42': self.pgen,
				'43': self.pgen,
				'44': self.pgen,
				'45': self.pgen,
				'46': self.pgen,
				'47': self.pgen,
				'48': self.pgen,
				'49': self.pgen,
				'50': self.process_host_totals,
				'51': self.process_host_totals,
				'52': self.pgen,
				'53': self.pgen,
				'60': self.process_download_request,
				'61': self.pgen,
				'62': self.pgen
			}

		def parseHeader(self,buf):
			field = {}
			offset=1
			if len(buf)>(101):
				print(">> DEBUG MODE DETECTED FROM ATM")
				field['communications_identifier'] = getChunk(buf,8,offset)
				offset+=8
				field['terminal_identifier'] = getChunk(buf,2,offset)
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
				field['transaction_code'] = getChunk(buf,2,offset)
				offset+=2
			offset+=1 # FS
			field['msg'] = buf[(offset):]
			field['body_offset']=offset
			return field

		def send_to_processor(self,termid,msg,action):
			global REMOTE_SERVER,REMOTE_PORT
			sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			sock.settimeout(15)
			server_address = (REMOTE_SERVER,REMOTE_PORT)
			data = None
			message = msg
			try:
				print >>sys.stderr, 'sending "%s"' % message
				sent = sock.sendto(message, server_address)
				print >>sys.stderr, 'waiting to receive'
				data, server = sock.recvfrom(4096)
				print >>sys.stderr, 'received "%s"' % data
			finally:
				print >>sys.stderr, 'closing socket'
				sock.close()
			return data

		# encryption key should be changed at some point i think !!!!!!!
		def process_download_request(self,termid,msg,action,enc_id="~"):
			tdes = pyDes.des(('\00'*8), pyDes.ECB)
			encrypted_key = tdes.encrypt('\00'*8)
			#int(str(encrypted_key),"ENCRYPTED ATM")
			msg = termid  + '\x1c' + action + '\x1c' + enc_id + encrypted_key.encode('hex') + '\x1c' + '\x03'
			return makeMessage(msg,True,True)

		def pgen(self,termid,msg,action):
			return self.send_to_processor(termid,msg,action)

		def process_host_totals(self,termid,msg,tcode='50'):
			# encryption key should be changed at some point i think !!!!!!!
			bus_date = time.strftime('%m%d%y')
			#msg = termid  + '\x1c' + "50" + '\x1c' + time.strftime('%m%d%y')  + '\x1c' + "0000 0000 0000 0000 0000" + '\x1c' + '\x03'
			msg = termid + '\x1c' + str(tcode) + '\x1c' + bus_date + '\x1c' + '0'*4 + '0'*4 +'0'*4 + "00000005" + '\x1c' + '\x03'
			nicePrint(msg,"Sending Host Total:")
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
			if 'amount1' in body_elements.keys():
				body_elements['amount1'] = int(body_elements['amount1'])/100
			if 'amount2' in body_elements.keys():
				body_elements['amount2'] = int(body_elements['amount2'])/100
			if 'amount3' in body_elements.keys():
				body_elements['amount3'] = int(body_elements['amount3'])/100
			amount = body_elements['amount1']-(body_elements['amount2']+body_elements['amount3'])
			body_elements['amount']=amount
			#action = hdr['transaction_code']
			response_code = "000" # 000 = approved, 111 = declined
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
		
		def processMessage(self,action,termid,buf):
			action_str = action
			action_int = int(action)
			if action_str in self.transaction_table_calls:
				if self.transaction_table_calls[action_str] is not None:
					print(">> Reached: %s: Attempting to call handler..."%str(self.transaction_table_messages[action_str]))
					# we are in good state
					return self.transaction_table_calls[action_str](termid,buf,action)
			print(">> Unknown Message ABORT! %s"%(str(action_str)))
			nicePrint(buf,"Unkown Message Packet: ")
			return None

	t = Transactions()

	# Open the specified file path
	# using os.open() method
	# and get the file descriptor for
	# opened file path

	print("File path opened successfully.")
	message=""
	allbytes=""
	handshake=False

	message_start = False
	message_end = False
	message_lrc = False

	prev_action = ""
	curr_action = ""

	message_retries_remaining = 100

	# todo: auto detect
	hasDebugEnabled = False
	# lol
	os.read(fd,1)
	os.write(fd,"\r\nATS0=4\r\n\r\nATS0=2\r\n")
	# lol
	start = time.time()
	while True:
			readbit = os.read(fd, 1)
			print readbit.encode("hex") + " ",
			if readbit == "" :
					continue
			char = fixParity(readbit)
			if char == "" :
					continue
			#print(char.encode('hex') + " " + char)
			if (time.time() - start)>float(SVCTIMEOUT):
				# we are done
				os.write(fd,"\r\nATS0=4\r\n\r\nATS0=2\r\n")
				sys.exit(1)
			if char.encode("hex") == "7f" :
					os.write(fd,"\x05\x05\x05")
					handshake=True
			if handshake:
					allbytes+=char
					print("all: %s"%allbytes.encode('hex'))
					if len(allbytes)>(256*2):
						message_start, message_end = False,False
						os.write(fd,"\r\n+++\r\nATH\r\n")
						allbytes=""
						# resetting
						continue
					if char.encode("hex") == "02":
							message_start = True
							message="\x02"
							while True:
									mchar = fixParity(os.read(fd,1))
									message+=mchar
									allbytes+=mchar
									if mchar.encode("hex") == "03":
											# found end message
											mchar+= fixParity(os.read(fd,1))
											allbytes+=mchar
											message_end = True
											break
							if message_start and message_end:
									#process message here
									curr_msg = message
									message = ""
									if hasDebugEnabled:
											terminalID = getChunk(curr_msg,15,22)
											action = getChunk(curr_msg,2,38)
									else:
											terminalID = getChunk(curr_msg,15,1)
											action = getChunk(curr_msg,2,17)
									print(">CURR MESSAGE> ",curr_msg.encode('hex'))
									openwrt_updates()
									m = t.processMessage(action,terminalID,curr_msg)
									if m is not None:
										os.write(fd,m)
										message_start, message_end = False,False
										curr_action = action
					elif '\x05' in char or '\x06' in char:
							print("> WE GOT A %s POSITIVE  MESSAGE FROM ACTION %s"%(convertCtrlChar(char),curr_action))
							os.write(fd,"\x84"*2)
					elif '\x15' in char:
							print("> WE GOT A %s NEGATIVE MESSAGE FROM ACTION %s"%(convertCtrlChar(char),curr_action))
							os.write(fd,"\x06"*2)
							os.write(fd,"\r\n\r\n+++\r\nATH0\r\n  \r\nATS0=4\r\n\r\nATS0=2\r\n")
							os.close(fd)
							print("Error Processing, Shutting down Program")
							sys.exit(1)
							# end close shit
					elif '\x04' in char:
							print("> WE GOT A %s - WE SHOULD REPLY WITH AN END MESSAGE FROM ACTION %s"%(convertCtrlChar(char),curr_action))
							os.write(fd,chr(setBit(ord("\x04"),7)))
							# start close shit
							os.write(fd,"\r\n\r\n+++\r\nATH0\r\n  \r\nATS0=4\r\n\r\nATS0=2\r\n")
							allbytes=""
							curr_action=""
							handshake=False
							curr_msg=""
							char = ""
							os.close(fd)
							fd = os.open(path, flags, mode)
							os.write(fd,"\r\nATS0=4\r\n\r\nATS0=2\r\n")
							print("> END OF MESSAGE????")
							message_start, message_end = False,False
							# end close shit
							sys.exit(1)
					else:
							print("> WE GOT A %s STRANGE MESSAGE FROM ACTION %s"%(convertCtrlChar(char),curr_action))
							os.write(fd,"\x84\x06")
							if (curr_action == prev_action) and (message_retries_remaining == 0):
							# start close shit
								os.write(fd,"\r\n\r\n+++\r\nATH0\r\n") #  \r\nATS0=4\r\n\r\nATS0=2\r\n")
								handshake=False
								print("> RESET SYSTEM... ATTEMPT AGAIN")
								message_start, message_end = False,False
								message_retries_remaining=100
								prev_action=""
								curr_action=""
								char=""
								continue
								#sys.exit(1)
							else:
								message_retries_remaining-=1 
					prev_action = curr_action
							# skip
					# repeat
	# Close the file descriptor
	os.close(fd)
	print("\nFile descriptor closed successfully.")
except Exception as e:
	os.write(fd,"\r\n\r\n+++\r\nATH0\r\n")
	traceback.print_exc()
	if e is KeyboardInterrupt:
		sys.exit(1)

