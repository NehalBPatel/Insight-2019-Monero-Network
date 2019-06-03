#!/usr/bin/python3
from struct import *
from collections import namedtuple

class peerlist_info:
    def __init__(self, ipAddr = 0x0, lsd = 0xff, lsh = 0xff, lsm = 0xff, lss = 0xff):
        self.ip_addr = ipAddr
        self.last_seen_days = lsd
        self.last_seen_hours = lsh
        self.last_seen_minutes = lsm
        self.last_seen_seconds = lss

class monitor_req:
    block_hash = []
    peerlist = []
    def __init__(self, message):
        msg_offset = 0

        # Unpack the header
        hdrTpl = namedtuple('MonReqHdr', ['req_type', 'req_len', 'mon_ip_l', 'mon_ip_h', 'sender_ip', 'cur_time'])
        hdrFormat = "HHQQIQ"
        hdr = hdrTpl._make(unpack_from(hdrFormat, message, msg_offset))
#        hdr = hdrTpl._make(unpack(hdrFormat, message))
        self.req_type =  hdr.req_type
        self.req_len = hdr.req_len
        self.mon_ip_l = hdr.mon_ip_l
        self.mon_ip_h = hdr.mon_ip_h
        self.sender_ip = hdr.sender_ip
        self.cur_time = hdr.cur_time

        if( self.req_len > 256 ):
            print("\nERROR.  Len > 256: {}".format(self.req_len))
            return
        
                
        # Set offset to after header
        #  msg_offset = req_type + req_len + mon_ip_l + mon_ip_h + sender_ip + cur_time
        msg_offset = 2 + 2 + 8 + 8 + 4 + 8
        # For some reason, the offset seems to be 40 bytes, not 32 as it should be.
        msg_offset = msg_offset + 8
        
        # Now unpack the Block hash
        # This is the block hash where HASH_SIZE is 32
        # B*32 - uint8_t block_hash[HASH_SIZE]
        blHashFormat = ("B" * 32)
        blHashArrName = []
        for cntr in range(32) :
            blHashArrName.append('block_hash_' + str(cntr))

        blHashTpl = namedtuple('blHash', blHashArrName)
        blHash = blHashTpl._make(unpack_from(blHashFormat, message, msg_offset))
        msg_offset = msg_offset + 32

        # Only unpack Block Hash if Request is of type Block Tracking
        if( self.req_type == 2 ) :
            for cntr in range(32):
                self.block_hash.append( getattr(blHash, ('block_hash_' + str(cntr)) ) )

            for cntr in range(32):
                print("Received Hash[{}]: {}".format(cntr, self.block_hash[cntr]))
            

        # Now unpack the Peerlist
        # Only unpack Peer List if Request is of type Peer List Tracking
        if( self.req_type == 1 ) :
            plFormat = 'IBBBB'
            plTpl = namedtuple('peerlist_entry', ['ip_addr', 'last_seen_days', 'last_seen_hours', 'last_seen_minutes', 'last_seen_seconds'])

            for cntr in range(self.req_len):
                pl = plTpl._make(unpack_from(plFormat, message, msg_offset))
                msg_offset = msg_offset + 8
                self.peerlist.append(peerlist_info(pl.ip_addr, pl.last_seen_days, pl.last_seen_hours, pl.last_seen_minutes, pl.last_seen_seconds))

            
    
