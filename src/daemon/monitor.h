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

#pragma once
#include "monitor/monero_monitor.h"

namespace daemonize
{

  class t_mon final
  {
  public:
    static void init_options(boost::program_options::options_description & option_spec)
    {
      monero_mntr::monero_monitor::init_options(option_spec);
    }

  private:
    std::shared_ptr<monero_mntr::monero_monitor> m_mon;

  public:
    t_mon( boost::program_options::variables_map const & vm )
      {
	m_mon = std::make_shared<monero_mntr::monero_monitor>();
	MGINFO("Initializing p2p server...");
	if( !m_mon->init(vm))
	{
	  throw std::runtime_error("Failed to initialize Monitor.");
	}
	MGINFO("p2p server initialized OK");
      }

    std::shared_ptr<monero_mntr::monero_monitor>& get()
      {
	return m_mon;
      }

    ~t_mon()
      {
	MGINFO("Deinitializing p2p...");
	try {
	  m_mon->deinit();
	} catch (...) {
	  MERROR("Failed to deinitialize p2p...");
	}
	
      }
  };
}
