#!/usr/bin/python3
import sys
import re
import threading 
import os
import queue
import datetime

from monero_archive_data import monitor_req

import platform
print(f'Python version: {platform.python_version()}')
import plotly
print(f"Plotly version: {plotly.__version__}")

import networkx as nx
print (nx.__version__)

from plotly.offline import download_plotlyjs, plot
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import zmq


fig = dict()
data_q = queue.Queue()
context = zmq.Context()
socket = context.socket(zmq.REP)

nodeId = 0                  # Unique Id for each IP Address
edgeCntr = 0                # Counter for number of edges

blockLat = []         # Array of Hashes.  Each hash will contain information about
                            # each block

nodeLat  = dict(dict())     # Hash of hash.  Key is the Ip Address.  Hash is the
                            # block latency information for all blocks sent by that
                            # IP Address

latDataStr_mtx = threading.Lock()     # Mutex for accessing blockLat & nodeLat                            
averageLat = 0
minLat = 0
maxLat = 0
blkCntr = 0

app = dash.Dash(__name__)
app.config['suppress_callback_exceptions']=True

def print_posi(poss):
  dbgFile = open("pos_info.txt", "a+")
  dbgFile.write("Start")
  dbgFile.write(str(poss))
  dbgFile.write("End")  
  dbgFile.close()
  

def print_block(latInfo):
  dbgFile = open("block_latency.txt", "a+")
  dbgFile.write(latInfo)
  dbgFile.write("\n")
  dbgFile.close()
  
def parse_peer_tr( monReq, Gr, ipAddrDict, edgeTracker ):
  global nodeId
  global edgeCntr
  peerNodeId = 0
  updateGraph = False

  # If this is the first time a Sender's IP Addr has been
  # received, assign it a node Id
  if( monReq.sender_ip not in ipAddrDict ) :
    ipAddrDict[monReq.sender_ip] = nodeId
    nodeId = nodeId + 1
  
  peerNodeId = ipAddrDict[monReq.sender_ip]    

  for cntr in range(monReq.req_len):
    if( monReq.peerlist[cntr].last_seen_days == 0 and
        monReq.peerlist[cntr].last_seen_hours == 0):

      # If the Peer Ip Address is not already in ipAddrDict,
      # Assign it a nodeId
      if monReq.peerlist[cntr].ip_addr not in ipAddrDict:
        ipAddrDict[monReq.peerlist[cntr].ip_addr] = nodeId
        nodeId = nodeId + 1

      plNodeId = ipAddrDict[monReq.peerlist[cntr].ip_addr]
        
      if peerNodeId not in edgeTracker:
        edgeTracker[peerNodeId] = {}

      if plNodeId not in edgeTracker:
        edgeTracker[plNodeId] = {}

      # Only add an edge if it's not already there.
      if( plNodeId not in edgeTracker[peerNodeId] ):
        edgeTracker[plNodeId][peerNodeId] = 1
        edgeTracker[peerNodeId][plNodeId] = 1
        Gr.add_edge(peerNodeId, plNodeId)
        updateGraph = True
        edgeCntr = edgeCntr + 1            

  return updateGraph



def parse_block_tr( monReq ):  
  blockHash = 0

  for cntr in range(31,0,-1) :
    blockHash = blockHash << 8
    blockHash = blockHash | (monReq.block_hash[cntr] & 0xff)

  print("Received Block Info w/ Sender Ip: {}\tHash: {}\t Time: {}".format(monReq.sender_ip, blockHash, monReq.cur_time))
  process_block_info(monReq.sender_ip, blockHash, monReq.cur_time)
  
    
def blockTime_sort(bl):
  return bl[1]

def process_block_info(senderIpAddr, blockHash, blockTime):
  global blockLat
  global latDataStr_mtx
  
  
  latDataStr_mtx.acquire()
  blockFnd = False
  blockIndex = 0
  processPrevBlock = False
  
  #  print( "process_block_info Entered w/ {}\t{}\t{}".format(senderIpAddr, blockHash, blockTime))
  #print( "process_block_info Array Len {}".format(len(blockLat)))

  for blIndx in range(len(blockLat)):
    #print( "process_block_info Array Len {}".format(len(blockLat)))

    # Check if an entry for the block is already there
    if( blockLat[blIndx]['block_hash'] == blockHash ):
      blockFnd = True
      blockIndex = blIndx
      break;

  if( blockFnd ) :
    # Block Hash found.
    #print("Block entry found in Index {}".format(blockIndex))

    # Check if we've already received from this IP Address from another Monitor
    rcvdAlready = False
    for elem in blockLat[blockIndex]['node_list'] :
      if( elem[0] == senderIpAddr ):
        rcvdAlready = True
      
    if not rcvdAlready :
      # Append into the array
      blockLat[blockIndex]['node_list'].append( [senderIpAddr, int(blockTime)] )
    
      # Sort by Time
      blockLat[blockIndex]['node_list'].sort(key=blockTime_sort)

    
  else :
    if( len(blockLat) > 1 ):
      processPrevBlock = True
      
    # New block detected.  Create a new dict
    #print("Creating New Block entry")
    newBlock = dict()
    newBlock['block_hash'] = blockHash
    newBlock['node_list'] = [[senderIpAddr, int(blockTime)]]
    newBlock['analysis_done'] = False
    blockLat.append(newBlock)

  latDataStr_mtx.release()
    
  if( processPrevBlock ):
    analyze_block()    
  
  return

def analyze_block():
  global blockLat
  global nodeLat
  global latDataStr_mtx
  global averageLat
  global minLat
  global maxLat
  global blkCntr
  
  latDataStr_mtx.acquire()
  # We only want to do upto the previous one
  arrLen = len(blockLat) - 1
  for blIndx in range( arrLen ):
    if( not blockLat[blIndx]['analysis_done'] ) :
      # Figure out the block propagation
      firstRcvd = blockLat[blIndx]['node_list'][0][1]
      lastRcvd = blockLat[blIndx]['node_list'][-1][1]

      # The values are in microseconds.  We want to store in ms
      blockLat[blIndx]['prop_dly'] = (lastRcvd-firstRcvd)

      blockLat[blIndx]['analysis_done'] = True
      #print("Latency for Block {} was {} us".format(blockLat[blIndx]['block_hash'], blockLat[blIndx]['prop_dly']))
      print_block("*********************************************************************************")
      print_block("Latency for Block {} was {} us\tNumber of Nodes that sent this block {}".format(blockLat[blIndx]['block_hash'], blockLat[blIndx]['prop_dly'], len(blockLat[blIndx]['node_list'])))

      if( minLat == 0 ):
        minLat = blockLat[blIndx]['prop_dly']

      if( maxLat == 0 ):
        maxLat = blockLat[blIndx]['prop_dly']

      if( blockLat[blIndx]['prop_dly'] < minLat ) :
        minLat = blockLat[blIndx]['prop_dly']

      if( blockLat[blIndx]['prop_dly'] > maxLat ) :
        maxLat = blockLat[blIndx]['prop_dly']

      cummulativeLat = (averageLat*blkCntr) + blockLat[blIndx]['prop_dly']
      blkCntr = blkCntr + 1
      averageLat = cummulativeLat/blkCntr
      print_block("Average Latency for ALL blocks: {} us ({} Blocks)".format(averageLat, blkCntr))
      print_block("Min Latency from All blocks: {} us\t Max Latency from All blocks: {}".format(minLat, maxLat))
      # If latency is greater than 15 seconds, then print out the information for debug
      if blockLat[blIndx]['prop_dly'] > 15000000 :
        print_block("\n")
        for xx in blockLat[blIndx]['node_list']:
          print_block("{}\t Diff: {}".format(str(xx), int(xx[1] - blockLat[blIndx]['node_list'][0][1])))
        
      print_block("*********************************************************************************")      
      # Now Store the node information
      for node in blockLat[blIndx]['node_list'] :
        if( node[0] in nodeLat ):
          # Append to existing Information

          # Figure out the us delay from when the block was first received
          propDly = node[1] - blockLat[blIndx]['node_list'][0][1]

          # Keep a running average of the delay
          avg_dly =  (((nodeLat[node[0]]['avg_dly']*nodeLat[node[0]]['numBlocksSent']) + propDly)/(nodeLat[node[0]]['numBlocksSent'] + 1))
          nodeLat[node[0]]['avg_dly'] = avg_dly
          if( propDly < nodeLat[node[0]]['min_dly'] ):
            nodeLat[node[0]]['min_dly'] = propDly

          if( propDly > nodeLat[node[0]]['max_dly'] ):
            nodeLat[node[0]]['max_dly'] = propDly

          nodeLat[node[0]]['last_bl_time'] = datetime.datetime.now()
                
          nodeLat[node[0]]['numBlocksSent'] = nodeLat[node[0]]['numBlocksSent'] + 1           
        else:
          # Create a new entry
          nodeInfo = dict()
          nodeInfo['numBlocksSent'] = 1
          nodeInfo['last_bl_time'] = datetime.datetime.now()
          dly = node[1] - blockLat[blIndx]['node_list'][0][1]
          nodeInfo['min_dly'] = dly
          nodeInfo['max_dly'] = dly
          nodeInfo['avg_dly'] = dly
          nodeLat[node[0]] = nodeInfo
          
  latDataStr_mtx.release()

def parse_monitor_handshake(monReq, Gr, ipAddrDict, monitorNodes):
  global nodeId
  monIp = ''

  monIp = monReq.mon_ip_h
  monIp = (monIp << 32) | monReq.mon_ip_l
      
  if( monIp in ipAddrDict ) :
    monitorNodes.append(ipAddrDict[monIp])
    print("Received Monitor w/ Node Id: {} \t w/ Ip Addr: {}".format( ipAddrDict[monIp], monIp))
    
  else :
    ipAddrDict[monIp] = nodeId
    monitorNodes.append(nodeId)
    #Gr.add_node(nodeId)
    print("Received Monitor w/ Node Id: {} \t w/ Ip Addr: {}".format( nodeId, monIp))
    nodeId = nodeId + 1
  

    
@app.callback(
  Output('Monero Network Graph', 'figure'),
  [Input('interval-component', 'n_intervals')])
def update_graph_live(n):
  global fig
  return fig


def process_data():
  global fig
  global data_q
  
  ipAddrDict = dict()         # Hash of all the Ip Addresses in the Network

  edgeTracker = dict(dict())  # Hash of hash for each node.  Key is Ip Address.
                              # The inside hash contains all the other nodes that
                              # are connected to that IP Address

  monitorNodes = []           # Array of Monitors

  Gr=nx.Graph()               #  G is an empty Graph

  posi=nx.fruchterman_reingold_layout(Gr)
  Xn=[posi[k][0] for k in range(len(posi))]
  Yn=[posi[k][1] for k in range(len(posi))]

  trace_nodes=dict(type='scatter',
                   x=Xn, 
                   y=Yn,
                   mode='markers',
                   marker=dict(size=6, color='rgb(259,65,0)'),
                   #                text=labels,
                   hoverinfo='text')

  Xe=[]
  Ye=[]

  for e in Gr.edges():
    Xe.extend([posi[e[0]][0], posi[e[1]][0], None])
    Ye.extend([posi[e[0]][1], posi[e[1]][1], None])

  trace_edges=dict(type='scatter',
                   mode='lines',
                   x=Xe,
                   y=Ye,
                   line=dict(width=.5, color='rgb(92,92,92)'),
                   hoverinfo='none' 
  )

  axis=dict(showline=False, # hide axis line, grid, ticklabels and  title
            zeroline=False,
            showgrid=False,
            showticklabels=False,
            title='' 
  )
  gTitle = "Monero (Partial) Network Topology. Number of Unique Nodes: " + str(len(ipAddrDict))

  layout=dict(title= gTitle,  
            font= dict(family='Balto'),
            width=2400,
            height=1500,
            autosize=False,
            showlegend=False,
            xaxis=axis,
            yaxis=axis,
            margin=dict(
            l=40,
            r=40,
            b=85,
            t=100,
            pad=0,
       
            ),
              hovermode='closest',
              plot_bgcolor='#ffffff', #set background color            
      )
        
  fig = dict(data=[trace_edges, trace_nodes], layout=layout)
  loopCntr = 2
  while True:
    updateGraph = False

    qSize = data_q.qsize()

    # We want to do batch processing if we can.  If there is nothing to process
    # then just have the data_q.get() block
    if( qSize == 0 ):
      qSize = 1
    
    for cntr in range(qSize):
      mon_req = data_q.get()

      if( mon_req.req_type == 1):
        print("Found Start of Peer Tracking")
        updateGraph = updateGraph | parse_peer_tr(mon_req, Gr, ipAddrDict, edgeTracker)
      elif( mon_req.req_type == 2):
        print("Found Start of Block Tracking")
        parse_block_tr(mon_req)
      elif( mon_req.req_type == 0):
        parse_monitor_handshake(mon_req, Gr, ipAddrDict, monitorNodes)
      else:
        print("mon_req.req_type Did not Match any known : {}".format(mon_req.req_type));

        data_q.task_done()
    
    if( updateGraph ) :
      posi=nx.fruchterman_reingold_layout(G=Gr)

      # X & Y coordinates for the normal nodes
      Xn = []
      Yn = []

      # X & Y coordinates for the monitor nodes
      Xm = []
      Ym = []

      #print_posi(posi)
      try:
        for kk in range(len(posi)):
          if( kk in monitorNodes ):
            Xm.append(posi[kk][0])
            Ym.append(posi[kk][1])
          else:
            Xn.append(posi[kk][0])
            Yn.append(posi[kk][1])
      except Exception as e:
        continue
#        socket.close()
#        context.term()
#        print("Closing Socket because {}".format(str(e)))
#        sys.exit()
      

      trace_nodes_normal=dict(type='scatter',
                              x=Xn, 
                              y=Yn,
                              mode='markers',
                              marker=dict(size=6, color='rgb(259,65,0)'),
                              #                text=labels,
                              hoverinfo='text')

      trace_nodes_monitor=dict(type='scatter',
                              x=Xm, 
                              y=Ym,
                              mode='markers',
                              marker=dict(size=18, color='rgb(65,105,225)'),
                              #                text=labels,
                              hoverinfo='text')


      try:
        Xe=[]
        Ye=[]
        for e in Gr.edges():
          Xe.extend([posi[e[0]][0], posi[e[1]][0], None])
          Ye.extend([posi[e[0]][1], posi[e[1]][1], None])
        
          trace_edges=dict(type='scatter',
                         mode='lines',
                         x=Xe,
                         y=Ye,
                         line=dict(width=.5, color='rgb(92,92,92)'),
                         hoverinfo='none' 
          )
        
          axis=dict(showline=False, # hide axis line, grid, ticklabels and  title
                    zeroline=False,
                    showgrid=False,
                    showticklabels=False,
                    title='' 
          )
          gTitle = "Monero (Partial) Network Topology. Number of Unique Nodes: " + str(len(ipAddrDict))
        
          layout=dict(title= gTitle,  
                      font= dict(family='Balto'),
                      width=2400,
                      height=1500,
                      autosize=False,
                      showlegend=False,
                      xaxis=axis,
                      yaxis=axis,
                      margin=dict(
                        l=40,
                        r=40,
                        b=85,
                        t=100,
                        pad=0,
                        
                      ),
                      hovermode='closest',
                      plot_bgcolor='#ffffff', #set background color            
          )
        
        fig = dict(data=[trace_edges, trace_nodes_normal, trace_nodes_monitor], layout=layout)
      except Exception as e:
        print("Number of Nodes: {} \t {}".format(nodeId, len(ipAddrDict)))
        print("Received Exception: {} ".format(e))
        #socket.close()
        #context.term()
        #print("Closing Socket because {}".format(str(e)))
        #sys.exit()
        


  return


def process_socket():
  global socket
  global data_q
  
  while True:  

    message = socket.recv()
    socket.send(b"ok")

    mon_req = monitor_req(message)
    data_q.put(mon_req)
  
if __name__ == '__main__':
  if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':

    print("Binding Socket")
    try:
      socket.bind("tcp://*:5565")
      socket_thr = threading.Thread(target=process_socket)
      socket_thr.daemon = True
      data_prc_thr = threading.Thread(target=process_data)
      data_prc_thr.daemon = True
      socket_thr.start()
      data_prc_thr.start()
    except Exception as e:
      socket.close()
      context.term()
      print("Closing Socket because {}".format(str(e)))
      sys.exit()

 
  print("Kicking off run_server")
  
  app.layout = html.Div([
    html.Div([dcc.Graph(id='Monero Network Graph'),
              dcc.Interval(id='interval-component', interval=1*1000, n_intervals=0)
    ])
  ])
  app.run_server(debug=True)

    
    





