// Copyright (c) 2014-2019, The Monero Project
//
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without modification, are
// permitted provided that the following conditions are met:
//
// 1. Redistributions of source code must retain the above copyright notice, this list of
//    conditions and the following disclaimer.
//
// 2. Redistributions in binary form must reproduce the above copyright notice, this list
//    of conditions and the following disclaimer in the documentation and/or other
//    materials provided with the distribution.
//
// 3. Neither the name of the copyright holder nor the names of its contributors may be
//    used to endorse or promote products derived from this software without specific
//    prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY
// EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF
// MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL
// THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
// SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
// PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
// INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
// STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF
// THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
//
// Parts of this file are originally copyright (c) 2012-2013 The Cryptonote developers

#pragma once

#include <mutex>
#include "p2p/p2p_protocol_defs.h"
#include "cryptonote_basic/cryptonote_basic.h"
#include <boost/date_time/posix_time/posix_time.hpp>
#include "common/command_line.h"
#include <zmq.hpp>
#include <memory>
#include "boost/date_time/posix_time/posix_time.hpp"
#include <chrono>
#include <boost/lockfree/queue.hpp>
#include <thread>
#include <regex>
#include <cstdint>

#include <boost/asio.hpp>
using boost::asio::ip::tcp;
using boost::asio::ip::udp;

namespace monero_mntr {

  const command_line::arg_descriptor<bool, false> arg_monitor_node = {
    "monitor_node"
    , "Instantiate a Monitor Node"
    , false
  };

  const command_line::arg_descriptor<std::string, false> arg_monitor_name = {
    "monitor_name"
    ,"Unique name for Monitor Node to send to Archive Node"
    ,"mon_node"
  };

  const command_line::arg_descriptor<std::string ,false> arg_archive_ip = {
    "archive_ip"
    ,"IP Address and port to connect to Archive Node"
    ,"null"
  };

  enum monitor_req { MON_HANDSHAKE, MON_PEER_TRACKING, MON_BLOCK_TRACKING };
  
  struct mon_peerlist_info {
    uint32_t ip_addr;
    uint8_t  last_seen_days;
    uint8_t  last_seen_hours;
    uint8_t  last_seen_minutes;
    uint8_t  last_seen_seconds;
  };

  struct mon_req {
    uint16_t req_type;
    uint16_t req_len;    
    uint64_t mon_ip_l;
    uint64_t mon_ip_h;    
    uint32_t sender_ip;
    uint64_t cur_time;
    uint8_t block_hash[crypto::HASH_SIZE];
    mon_peerlist_info peerlist_info[250];
  };


  
  class monero_monitor {

  public:    
    static void init_options(boost::program_options::options_description& desc) {
      command_line::add_arg(desc, arg_monitor_node);
      command_line::add_arg(desc, arg_monitor_name);
      command_line::add_arg(desc, arg_archive_ip);
    }
    
    monero_monitor()
      {
	std::unique_ptr<zmq::context_t> tmpCtxt(new zmq::context_t(1));
	m_context = std::move(tmpCtxt);
	std::unique_ptr<zmq::socket_t> tmpSock(new zmq::socket_t(*(m_context.get()), ZMQ_REQ));
	m_socket = std::move(tmpSock);
	m_ip_addr_l = 0x0;
	m_ip_addr_h = 0x0;	
	m_wrap_up = false;
      }

    virtual bool init(const boost::program_options::variables_map& vm)
    {

      try {
	boost::asio::io_service netService;
	udp::resolver   resolver(netService);
	udp::resolver::query query(udp::v4(), "google.com", "");
	udp::resolver::iterator endpoints = resolver.resolve(query);
	udp::endpoint ep = *endpoints;
	udp::socket socket(netService);
	socket.connect(ep);
	boost::asio::ip::address addr = socket.local_endpoint().address();
	if( addr.is_v4() ) {
	  m_ip_addr_l = addr.to_v4().to_ulong();
	}
	else {
	  boost::asio::ip::address_v6::bytes_type addr_bytes = addr.to_v6().to_bytes();
	  m_ip_addr_l = 0;
	  for(int cntr{3}; cntr>=0; --cntr) {
	    m_ip_addr_l <<= 8;
	    m_ip_addr_l |= (addr_bytes[cntr] & 0xff);
	  }

	  m_ip_addr_h = 0;
	  for(int cntr{7}; cntr>=4; --cntr) {
	    m_ip_addr_h <<= 8;
	    m_ip_addr_h |= (addr_bytes[cntr] & 0xff);
	  }
	  
	}
      } catch (std::exception& e){
	std::cerr << "Could not deal with socket. Exception: " << e.what() << std::endl;
	
      }
      
      m_monitor_en = command_line::get_arg(vm, arg_monitor_node);
      if( m_monitor_en ) {
	m_monitor_name = command_line::get_arg(vm, arg_monitor_name);
	m_archive_ip = command_line::get_arg(vm, arg_archive_ip);
	if( m_archive_ip == "null") {
	  MGINFO("ERROR.  Monitor En is set, but archive Ip is not Set.  Set via command line option --archive_ip <ip_addr:port>");
	  m_monitor_en = false;
	  return false;
	}
	MGINFO("Insight 2019-dc::Monitor Mode is set  ...");
	MGINFO("Insight 2019-dc::Monitor Name is " << m_monitor_name);
	MGINFO("Insight 2019-dc::Archive Ip is " << m_archive_ip);

	m_archive_ip = "tcp://" + m_archive_ip;
	
	// Fix me
	//m_socket->connect ("tcp://localhost:5555");
	m_socket->connect (m_archive_ip.c_str());      	

	mon_req hs_req;
	hs_req.req_type = monitor_req::MON_HANDSHAKE;
	hs_req.mon_ip_l = m_ip_addr_l;
	hs_req.mon_ip_h = m_ip_addr_h;
	hs_req.req_len = 0;

	send_msg(hs_req);


	// Fork off thread
	std::unique_ptr<std::thread> tmpTxThr(new std::thread(&monero_monitor::send_data, this));
	txThr = std::move(tmpTxThr);
	
	
      }

      return true;
    }

    virtual bool deinit()
    {
      if( m_monitor_en ) {
	m_wrap_up = true;
	if( txThr ) {
	  txThr->join();
	}
	// join threads
      }
      return true;
    }    
    
    virtual void track_peer( const time_t lcl_time, const epee::net_utils::connection_context_base& context, const std::vector<nodetool::peerlist_entry>& peerlist) {
      if( m_monitor_en ) {
	mon_req tp_req;
	uint8_t days, hours, minutes, seconds;
	
	tp_req.req_type = monitor_req::MON_PEER_TRACKING;
	tp_req.mon_ip_l = m_ip_addr_l;
	tp_req.mon_ip_h = m_ip_addr_h;	
	tp_req.cur_time = lcl_time;
	std::string ipAddr = regex_replace(context.m_remote_address.str(), std::regex(":\\d+"), std::string(""));
	if( !epee::string_tools::get_ip_int32_from_string( tp_req.sender_ip, ipAddr) ) {
	  std::cout << "Track Peer Received Error from get_ip_int32_from_string **" << context.m_remote_address.str() << "**" << std::endl;
	  return;
	}

	tp_req.req_len = (peerlist.size() > 250) ? 250 : peerlist.size();

	time_t now_time = 0;
	time(&now_time);
	
	for(int cntr{0}; cntr<tp_req.req_len; ++cntr) {
	  std::string ipAddr = regex_replace(peerlist[cntr].adr.str(), std::regex(":\\d+"), std::string(""));
	  
	  if( !epee::string_tools::get_ip_int32_from_string( tp_req.peerlist_info[cntr].ip_addr, ipAddr ) ) {
	    std::cout << "track Peer 2 Received Error from get_ip_int32_from_string " << std::endl;
	    return;
	  }
	  set_last_seen_time(  (now_time - peerlist[cntr].last_seen)
			     , tp_req.peerlist_info[cntr].last_seen_days
			     , tp_req.peerlist_info[cntr].last_seen_hours
			     , tp_req.peerlist_info[cntr].last_seen_minutes
			     , tp_req.peerlist_info[cntr].last_seen_seconds);

	}

	m_tx_q.push(tp_req);
      }      
    }
    
    
    virtual void track_block( const epee::net_utils::connection_context_base&  context, cryptonote::block bl) {
      if( m_monitor_en ) {
	mon_req bl_req;

	bl_req.req_type = monitor_req::MON_BLOCK_TRACKING;
	bl_req.mon_ip_l = m_ip_addr_l;
	bl_req.mon_ip_h = m_ip_addr_h;
	bl_req.req_len = 0;
	
	std::string ipAddr = regex_replace(context.m_remote_address.str(), std::regex(":\\d+"), std::string(""));
	if( !epee::string_tools::get_ip_int32_from_string(bl_req.sender_ip, ipAddr ) ) {
	  std::cout << "Track_block  Received Error from get_ip_int32_from_string" << std::endl;
	  return;
	}
	bl_req.cur_time = ( boost::posix_time::microsec_clock::universal_time() - boost::posix_time::from_time_t(0) ).total_microseconds();
	for(int cntr{0}; cntr<crypto::HASH_SIZE; ++cntr) {
	  bl_req.block_hash[cntr] = (uint8_t)(bl.hash.data[cntr]);
	}

	m_tx_q.push(bl_req);
      }
    }

    virtual void send_mon_peerlist( const std::vector<nodetool::peerlist_entry>& peerlist) {
      if( m_monitor_en ) {
	mon_req tp_req;
	uint8_t days, hours, minutes, seconds;
	
	tp_req.req_type = monitor_req::MON_PEER_TRACKING;
	tp_req.mon_ip_l = m_ip_addr_l;
	tp_req.mon_ip_h = m_ip_addr_h;	
	tp_req.cur_time = ( boost::posix_time::microsec_clock::universal_time() - boost::posix_time::from_time_t(0) ).total_microseconds();
	tp_req.sender_ip = m_ip_addr_l;
	
	tp_req.req_len = (peerlist.size() > 250) ? 250 : peerlist.size();

	time_t now_time = 0;
	time(&now_time);
	
	for(int cntr{0}; cntr<tp_req.req_len; ++cntr) {
	  std::string ipAddr = regex_replace(peerlist[cntr].adr.str(), std::regex(":\\d+"), std::string(""));
	  if( !epee::string_tools::get_ip_int32_from_string( tp_req.peerlist_info[cntr].ip_addr, ipAddr ) ) {
	    std::cout << "Track Mon Peerlist  Received Error from get_ip_int32_from_string " << std::endl;
	    return;
	  }
	  
	  set_last_seen_time(  (now_time - peerlist[cntr].last_seen)
			     , tp_req.peerlist_info[cntr].last_seen_days
			     , tp_req.peerlist_info[cntr].last_seen_hours
			     , tp_req.peerlist_info[cntr].last_seen_minutes
			     , tp_req.peerlist_info[cntr].last_seen_seconds);
	}

	m_tx_q.push(tp_req);
      }
    }

    
    virtual void send_msg( mon_req &req) {
      std::lock_guard<std::mutex> tp_lg(m_monitor_mtx);
      zmq::message_t request(sizeof(req));

      memcpy(request.data(), &req, sizeof(req));
      m_socket->send(request);
      zmq::message_t reply;
      m_socket->recv(&reply);
    }
    
  private:
    std::mutex m_monitor_mtx;
    bool m_monitor_en;
    bool m_wrap_up;
    std::string m_monitor_name;
    std::string m_archive_ip;
    uint64_t  m_ip_addr_l;
    uint64_t  m_ip_addr_h;    
    std::stringstream m_blStr;
    // np debug
    boost::lockfree::queue<mon_req> m_tx_q;
    static constexpr int MAX_MON_MSG_SIZE = 32*1024;

    std::unique_ptr<std::thread> txThr;
    std::unique_ptr<std::thread> rxThr;
    
    std::unique_ptr<zmq::context_t> m_context;
    std::unique_ptr<zmq::socket_t> m_socket;

    virtual void send_data(){
      mon_req cur_req;
      
      while( ! m_wrap_up ) {
	// If something in queue
	while( m_tx_q.pop(cur_req) ) {
	  send_msg(cur_req);
	}

	std::this_thread::sleep_for(std::chrono::seconds(1));
      }
    }

    inline virtual void set_last_seen_time( const time_t& ls_time,
					    uint8_t& ls_days,
					    uint8_t& ls_hours,
					    uint8_t& ls_mins,
					    uint8_t& ls_secs ) {

      time_t tail = ls_time;
      int days = tail/(60*60*24);
      tail = tail%(60*60*24);
      int hours = tail/(60*60);
      tail = tail%(60*60);
      int minutes = tail/(60);
      tail = tail%(60);
      int seconds = tail;

      ls_days = (days > UINT8_MAX) ? UINT8_MAX : (uint8_t)days;
      // Should never happen.  But if it does, set it to max value
      ls_hours = (hours > UINT8_MAX) ? UINT8_MAX : (uint8_t)hours;
      ls_mins = (minutes > UINT8_MAX) ? UINT8_MAX : (uint8_t)minutes;
      ls_secs = (seconds > UINT8_MAX) ? UINT8_MAX : (uint8_t)seconds;
    }

 };

}
