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

namespace monero_mntr {
  // np debug
  const command_line::arg_descriptor<bool, false> arg_monitor_node = {
    "monitor_node"
    , "Instantiate a Monitor Node"
    , false
  };

  // end np debug


  class monero_monitor {

  public:    
    static void init_options(boost::program_options::options_description& desc) {
      // np debug Options
      std::cout << "\n\nNP DEBUG init_options Entered\n";
      command_line::add_arg(desc, arg_monitor_node);
    }
    

    virtual bool init(const boost::program_options::variables_map& vm)
    {
      MGINFO("NP DEBUG.  Before checking Monitor Mode  ...");
    
      m_monitor_en = command_line::get_arg(vm, arg_monitor_node);
      if( m_monitor_en ) {
	MGINFO("Insight 2019-dc::Monitor Mode is set  ...");
      }

      m_monitor_file.open("xmr_monitor.txt");
      
      return true;
    }

    virtual bool deinit()
    {
      // Close File
      m_monitor_file.close();
      return true;
    }    
    
    virtual void track_peer( const time_t lcl_time, const epee::net_utils::connection_context_base& context, const std::vector<nodetool::peerlist_entry>& peerlist) {
      if( m_monitor_en ) {
	std::lock_guard<std::mutex> tp_lg(m_monitor_mtx);
	m_monitor_file << "\nSTART_PEER_TRACKING"
		       << "\nSender: " << context.m_remote_address.str()
		       << "\nTime: "<< lcl_time
		       << "\n" << nodetool::print_peerlist_to_string(peerlist)
		       << "END_PEER_TRACKING"
		       << std::endl;
      }      
    }
    
    
    virtual void track_block( const epee::net_utils::connection_context_base&  context, cryptonote::block bl) {
      if( m_monitor_en ) {
	std::lock_guard<std::mutex> tp_lg(m_monitor_mtx);
	m_monitor_file << "\nSTART_BLOCK_TRACKING"
		       << "\nSender: " << context.m_remote_address.str()
		       << "\nBlock Hash: " << bl.hash
		       << "\nTime: " << time(nullptr)
		       << "\nEND_BLOCK_TRACKING"
		       << std::endl;
      }
    }
    

  private:
    std::mutex m_monitor_mtx;
    bool m_monitor_en;
    std::ofstream m_monitor_file;
    
 };

}
