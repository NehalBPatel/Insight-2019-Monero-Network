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
	m_ip_addr = "0.0.0.0";
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
	m_ip_addr = addr.to_string();
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

	std::stringstream mnStr;
	mnStr << "START_MONITOR_HANDSHAKE"
	      << "\nName: " << m_monitor_name
	      << "\nIP: " << m_ip_addr
	      << "\nEND_MONITOR_HANDSHAKE"
	      << std::endl;
	send_msg(mnStr.str());
	
      }
      
      return true;
    }

    virtual bool deinit()
    {
      if( m_monitor_en ) {
	// NP DEBUG
	//Close Socket
      }
      return true;
    }    
    
    virtual void track_peer( const time_t lcl_time, const epee::net_utils::connection_context_base& context, const std::vector<nodetool::peerlist_entry>& peerlist) {
      if( m_monitor_en ) {
	m_tpStr << "START_PEER_TRACKING"
	      << "\nSender: " << context.m_remote_address.str()
	      << "\nTime: "<< lcl_time
	      << "\n" << nodetool::print_peerlist_to_string(peerlist)
	      << "END_PEER_TRACKING"
	      << std::endl;
	send_msg(m_tpStr.str());
	m_tpStr.str("");
	m_tpStr.clear();
      }      
    }
    
    
    virtual void track_block( const epee::net_utils::connection_context_base&  context, cryptonote::block bl) {
      if( m_monitor_en ) {
	m_blStr << "START_BLOCK_TRACKING"
		<< "\nSender: " << context.m_remote_address.str()
		<< "\nBlock Hash: " << bl.hash
		<< "\nTime: " << ( boost::posix_time::microsec_clock::universal_time() - boost::posix_time::from_time_t(0) ).total_microseconds()
		<< "\nEND_BLOCK_TRACKING"
		<< std::endl;
	send_msg(m_blStr.str());
	m_blStr.str("");
	m_blStr.clear();
      }
    }

    virtual void send_mon_peerlist( const std::vector<nodetool::peerlist_entry>& peerlist) {
      if( m_monitor_en ) {
	m_mpStr << "START_PEER_TRACKING"
	      << "\nSender: " << m_ip_addr
		<< "\nTime: 00"    // This is a don't care value. 
	      << "\n" << nodetool::print_peerlist_to_string(peerlist)
	      << "END_PEER_TRACKING"
	      << std::endl;
	send_msg(m_mpStr.str());
	m_mpStr.str("");
	m_mpStr.clear();
      }
    }

    
    virtual void send_msg( std::string&& str) {
      auto start = std::chrono::high_resolution_clock::now();
      std::lock_guard<std::mutex> tp_lg(m_monitor_mtx);
      zmq::message_t request(str.size());

      memcpy(request.data(), str.c_str(), str.size());
      m_socket->send(request);
      zmq::message_t reply;
      m_socket->recv(&reply);
      auto end = std::chrono::high_resolution_clock::now();
      auto dur = std::chrono::duration_cast<std::chrono::microseconds>(end - start);
      //std::cout << "Duration: " << dur.count() << "us\n" << std::endl;
      
    }
    
  private:
    std::mutex m_monitor_mtx;
    bool m_monitor_en;
    std::string m_monitor_name;
    std::string m_archive_ip;
    std::string m_ip_addr;
    std::stringstream m_tpStr;
    std::stringstream m_mpStr;    
    std::stringstream m_blStr;

    std::unique_ptr<zmq::context_t> m_context;
    std::unique_ptr<zmq::socket_t> m_socket;
    
 };

}
