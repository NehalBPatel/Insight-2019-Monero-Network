#!/usr/bin/python3
import re

peer_tr_st = re.compile("^START_PEER_TRACKING")
peer_bl_tr_sendr = re.compile("^Sender: (\d+\.\d+\.\d+\.\d+)");
peer_tr_list = re.compile("rpc port")
peer_tr_end = re.compile("^END_PEER_TRACKING")
block_tr_st = re.compile("^START_BLOCK_TRACKING")
block_tr_end = re.compile("^END_BLOCK_TRACKING")
block_tr_hash = re.compile("^Block Hash:")
peer_bl_tr_time = re.compile("^Time:")

def parse_peer_tr( inFile ):
  peerIpAddr = ""
  peerSenderIpAddr = ""

  for pt_myline in inFile:
      if( peer_bl_tr_sendr.search(pt_myline) != None):
          print (pt_myline)
          peerIpAddrObj = re.search( r"Sender: (\d+\.\d+\.\d+\.\d+):", pt_myline, re.M|re.I)
          if( peerIpAddrObj ):
              peerSenderIpAddr = peerIpAddrObj.group(1)
              print("IpAddr : ",peerSenderIpAddr)

      elif( peer_bl_tr_time.search(pt_myline) != None):

        peerTimeObj = re.search( r"Time: (\d+)", pt_myline, re.M|re.I)
        
        if( peerTimeObj ) :
          timeVal = peerTimeObj.group(1)

            
      elif( peer_tr_list.search(pt_myline) != None):
          peerIpObj = re.search(r"^\w+\W+(\d+\.\d+\.\d+\.\d+):", pt_myline, re.M|re.I)
          peerLastSeenObj = re.search(r"last_seen: (.*)", pt_myline, re.M|re.I)
          
          peerIpAddr = ""
          lastSeen = ""
          if( peerIpObj ) :
              peerIpAddr = peerIpObj.group(1)

          if( peerLastSeenObj ):
              lastSeen = peerLastSeenObj.group(1)

          print("Peer Ip:{}\tLastSeen: {} " .format(peerIpAddr, lastSeen))
      elif( peer_tr_end.search(pt_myline) != None):
          return

def parse_block_tr( inFile ):
  blSenderIpAddr = ""
  blHash = ""
  blTime = ""

  for bt_myline in inFile:
    
    if( peer_bl_tr_sendr.search(bt_myline) != None) :
      blIpaddrObj = re.search(r"Sender: (\d+\.\d+\.\d+\.\d+):", bt_myline, re.M|re.I)
      if( blIpaddrObj ) :
        blockSenderIpAddr = blIpaddrObj.group(1)
    elif( block_tr_hash.search(bt_myline) != None) :
      blHashObj = re.search(r"^Block Hash: <(\w+)>", bt_myline, re.M|re.I)

      if( blHashObj ) :
        blHash = blHashObj.group(1)
          
    elif( peer_bl_tr_time.search(bt_myline) != None) :
      blTimeObj = re.search(r"^Time: (\d+)", bt_myline, re.M|re.I)

      if( blTimeObj ) :
        blTime = blTimeObj.group(1)

    elif( block_tr_end.search(bt_myline) != None):
      print("\nFound Block Sent by: {}" .format(blockSenderIpAddr))
      return


with open("test.txt", "rt") as myfile:
    for myline in myfile:
        if( peer_tr_st.search(myline) != None):
            print("Found Start of Peer Tracking")
            parse_peer_tr(myfile)
        elif( block_tr_st.search(myline) != None):
            print("Found Start of Block Tracking")
            parse_block_tr(myfile)






