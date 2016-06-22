raw_server_messages = True
raw_client_messages = True

actions_char = '~'
actions_usenotice = True
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#from machine import Pin
#import onewire
#from time import sleep_ms
#ow = onewire.OneWire(Pin(2))
#ds = onewire.DS18B20(ow)
#roms = ds.scan()
#
#def temperature(x):
#  global roms, ds
#  ds.convert_temp()
#  sleep_ms(750)
#  return ds.read_temp(roms[0])
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
#from gc import mem_free
#from esp import flash_id
#from machine import unique_id
#actions = {
#           "free":(lambda user: mem_free()),
#           "tempC":(lambda user:"%.1f" % temperature(user)),
#           "tempF":(lambda user:"%.1f" % (32+(temperature(user)*(9./5.)))),
 #          "flash_id":(lambda user: flash_id()),
 #          "unique_id":(lambda user: unique_id()),
#          }
#
#responses = {#"[Hh][Ii] "+nick+".*":(lambda n: "Hi %s!" % n),
#             "^[pP]ing.*":(lambda n: "ack"),
#             nick+".*:(.*)":(lambda n: ""),
#            }
# ----------------------------------------------------------------------------
#TODO Improve/unify repl reporting/debugging code
import socket
import ure
from gc import collect

collect()

sock=None
channels=[]
nick=""
current_nick=nick
suffixes=[]
actions={}
responses={}

actions["src"]="TBC" # XXX TODO
action_help=""

def join_with_nick_to_channels(n,c):
  global sock # FIXME?
  sock.send(b"NICK %s\r\n" % n)
  sock.send(b"USER %s 8 * :%s\r\n" % (n,n))
  for ch in c:
    sock.send(b"JOIN %s\r\n" % ch)

def send_msg_to_channel(chan, msg, use_notice):
  global sock # FIXME?
  tosend = b"%s %s :%s\r\n" % ("NOTICE" if use_notice else "PRIVMSG",chan,msg)
  sock.send(tosend)
  if raw_client_messages: print("Client sent: [%s]" % tosend)

user_match=":(\S+)!~?(\S+)@(\S+)\s"
def do_server():
  collect()
  line = sock.readline()
  if len(line) < 3: print("Unexpected short line length (%d characters)" % len(line))
  if not (line[-2]==13 and line[-1]==10): # Assume all IRC messages should end in \r\n 
    print("Invalid message from server; ignoring message"); return
  if raw_server_messages and len(line)>1: print("Server sent: [%s]" % line)
  if line.find(b"PING :") == 0:
    _ = sock.send(b"PONG :%s" % line[6:])
    if raw_client_messages: print("Client sent: [%s]" % (b"PONG :%s" % line[6:]))
  elif line.find(b":Nickname is already in use") != -1:
      print("Nickname '%s' is already in use" % nick)
      if len(suffixes) > 0:
        print("Trying an alternative nick suffix")
        if   current_nick == nick             : current_nick = nick+suffixes[0]
        elif current_nick == nick+suffixes[-1]: current_nick = nick
        else:
          current_suffix = current_nick[len(nick):]
          found = False
          for suffix in suffixes:
            if found == True: break
            if suffix == current_suffix: found = True
          current_nick = nick+suffix
        print("New nickname is '%s'" % current_nick)
        join_with_nick_to_channels(current_nick, channels)
  elif line.find(b" PRIVMSG ") != -1:
    u=ure.match(user_match+"PRIVMSG\s(\S+)\s:(.+)\r\n",line)
    user,name,location,channel,message = u.group(1),u.group(2),u.group(3),u.group(4),u.group(5)
    print("User [%s] (%s) at [%s] on channel %s said [%s]" %\
          (user,name,location,channel,message))
    if channel == nick: channel = user # return message goes back to user (not bot or channel)
#    if message.find(1) != -1: # FIXME Add code for emote extensions etc like /me (escape char)
    if message[0] == actions_char or message[:len(current_nick)+1]==current_nick+":":
      command = message[1:] if message[0]==actions_char else message[len(current_nick)+1:]
      # FIXME Add check for zero size actions?
      command = command.strip() # Remove leading spaces in command
      usenotice = actions_usenotice if channel != user else False
      if len(command)==0 or command == "help": # assumed not in actions dict so check first
        send_msg_to_channel(channel, action_help, usenotice)
      elif command not in actions.keys():
        send_msg_to_channel(channel, "No command '%s'; %s" % (command,action_help), usenotice)
      else:
        if isinstance(actions[command],str): send_msg_to_channel(channel,actions[command],usenotice)
        else: send_msg_to_channel(channel,actions[command](user),usenotice)
    elif len(responses) >0 and user != current_nick: # have some responses and message not from bot
      print("Checking responses")
      for k,v in responses.items():
        print("Checking for [%s] in [%s]" % (k,message))
        u=ure.match(k,message)
        if u != None: # Found a match
          send_msg_to_channel(channel,v(user),False)
  elif line.find(b" JOIN ") != -1:
    u=ure.match(user_match+"JOIN (\S+)",line)
    user,name,location,channel=u.group(1),u.group(2),u.group(3),u.group(4)
    print("%s (%s) joined channel %s" % (user,name,channel))
  elif line.find(b" QUIT ") != -1:
    u=ure.match(user_match+"QUIT (\S+)",line)
    user,name,location,reason=u.group(1),u.group(2),u.group(3),u.group(4)
    print("%s (%s) quit due to %s" % (user,name,reason))
  elif line.find(b" PART ") != -1:
    u=ure.match(user_match+"PART\s(\S+)\s(\S+)",line)
    user,name,location,channel,reason=u.group(1),u.group(2),u.group(3),u.group(4),u.group(5)
    print("%s (%s) left %s due to %s" %(user,name,channel,reason))
  elif line.find(b" NICK ") != -1:
    u=ure.match(user_match+"NICK\s:(\S+)",line)
    user,name,location,newuser=u.group(1),u.group(2),u.group(3),u.group(4)
    print("%s changed nick from '%s' to '%s'" % (name,user,newuser))
  elif line.find(b" KICK ") != -1:
    print("KICK") # XXX MORE info?
  elif line.find(b" ERROR ") != -1:
    print("ERROR") # XXX MORE info?
  elif line.find(b" NOTICE ") != -1:
    u=ure.match(":(\S+)\sNOTICE\s(.+)\r\n",line)
    server,message = u.group(1),u.group(2)
    print("NOTICE: %s says: '%s'" % (server,message))
  else: pass # Other

def connect(server,port,channels_,nick_,suffixes_,actions_,responses_):
  global sock,channels,nick,suffixes,current_nick,actions,responses,action_help
  channels=channels_
  nick=nick_
  current_nick=nick
  suffixes=suffixes_
  actions=actions_
  responses=responses_

  action_help = "Commands: help src "+" ".join(actions.keys())+" (prefix with "+actions_char+" or nick:)"
  sock = socket.socket()
  addr = socket.getaddrinfo(server, port)
  sock.connect(addr[0][-1])
  join_with_nick_to_channels(current_nick, channels)
  while True: do_server()
