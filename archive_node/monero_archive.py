#!/usr/bin/python3
import sys
import re
import threading 
import os
import queue
import datetime

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

peer_tr_st = re.compile("^START_PEER_TRACKING")
peer_bl_tr_sendr = re.compile("^Sender: (\d+\.\d+\.\d+\.\d+)");
peer_tr_list = re.compile("rpc port")
peer_tr_end = re.compile("^END_PEER_TRACKING")
block_tr_st = re.compile("^START_BLOCK_TRACKING")
block_tr_end = re.compile("^END_BLOCK_TRACKING")
block_tr_hash = re.compile("^Block Hash:")
peer_bl_tr_time = re.compile("^Time:")
mon_tr_st = re.compile("^START_MONITOR_HANDSHAKE")
mon_tr_name = re.compile("^Name: (\w+)");
mon_tr_ip = re.compile("^IP: (\d+\.\d+\.\d+\.\d+)");
mon_tr_end = re.compile("^END_MONITOR_HANDSHAKE")


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

app = dash.Dash(__name__)
app.config['suppress_callback_exceptions']=True

def print_posi(poss):
  dbgFile = open("pos_info.txt", "a+")
  dbgFile.write("Start")
  dbgFile.write(str(poss))
  dbgFile.write("End")  
  dbgFile.close()
  

def parse_peer_tr( msgArr, Gr, ipAddrDict, edgeTracker ):
  peerIpAddr = ""
  peerSenderIpAddr = ""
  global nodeId
  global edgeCntr
  peerNodeId = 0
  
  for pt_myline in msgArr:

    if( peer_bl_tr_sendr.search(pt_myline) != None):
      peerIpAddrObj = re.search( r"Sender: (\d+\.\d+\.\d+\.\d+)", pt_myline, re.M|re.I)
      if( peerIpAddrObj ):
        peerSenderIpAddr = peerIpAddrObj.group(1)
        if peerSenderIpAddr in ipAddrDict:
          peerNodeId = ipAddrDict[peerSenderIpAddr]
        else:
          ipAddrDict[peerSenderIpAddr] = nodeId
          #print("\n0 Adding Ip Address {} in Dict w/ Node Id: {}".format(peerSenderIpAddr, nodeId))
          peerNodeId = nodeId
          nodeId = nodeId + 1
      
    elif( peer_bl_tr_time.search(pt_myline) != None):
      peerTimeObj = re.search( r"Time: (\d+)", pt_myline, re.M|re.I)
        
      if( peerTimeObj ) :
        timeVal = peerTimeObj.group(1)
           
    elif( peer_tr_list.search(pt_myline) != None):
      peerIpObj = re.search(r"^\w+\W+(\d+\.\d+\.\d+\.\d+):", pt_myline, re.M|re.I)
      peerLastSeenObj = re.search(r"last_seen: d(\d+)\.h(\d+)", pt_myline, re.M|re.I)
          
      peerIpAddr = ""
      lastSeenDay = "99"
      lastSeenHour = "99"

      if( peerLastSeenObj ):
        lastSeenDay = peerLastSeenObj.group(1)
        lastSeenHour = peerLastSeenObj.group(2)        
      
      if( (lastSeenDay == '0') and (lastSeenHour == '0') and peerIpObj ) :
#      if( (lastSeenDay == '0') and peerIpObj ) :
        peerIpAddr = peerIpObj.group(1)
        if peerIpAddr in ipAddrDict:

          # Only add an edge if it hasn't already been added previously
          if not peerNodeId in edgeTracker :
            #print("\n0 Adding an Empty Hash for Node Id: {}".format(peerNodeId))
            edgeTracker[peerNodeId] = {}

          if not ipAddrDict[peerIpAddr] in edgeTracker :
            #print("\n1 Adding an Empty Hash for Node Id: {}".format(ipAddrDict[peerIpAddr]))
            edgeTracker[ipAddrDict[peerIpAddr]] = {}

              
          if not (ipAddrDict[peerIpAddr] in edgeTracker[peerNodeId] ) :
            #print("\n0 Adding Edge between {} and {}".format(peerNodeId, ipAddrDict[peerIpAddr]))
            Gr.add_edge(peerNodeId, ipAddrDict[peerIpAddr])
            
            edgeTracker[peerNodeId][ipAddrDict[peerIpAddr]] = 1
            edgeTracker[ipAddrDict[peerIpAddr]][peerNodeId] = 1
            edgeCntr = edgeCntr + 1
              
        else :

          ipAddrDict[peerIpAddr] = nodeId
          #print("\n1 Adding Ip Address {} in Dict w/ Node Id: {}".format(peerSenderIpAddr, nodeId))
          
          # Add the list of nodes that are connected
          if not peerNodeId in edgeTracker :
            #print("\n2 Adding an Empty Hash for Node Id: {}".format(peerNodeId))
            edgeTracker[peerNodeId] = {}

          if not ipAddrDict[peerIpAddr] in edgeTracker :
            #print("\n2 Adding an Empty Hash for Node Id: {}".format(ipAddrDict[peerIpAddr]))
            edgeTracker[ipAddrDict[peerIpAddr]] = {}
              
          if( not( ipAddrDict[peerIpAddr] in edgeTracker[peerNodeId] ) ):
            #print("\n1Adding Edge between {} and {}".format(peerNodeId, nodeId))
            edgeTracker[nodeId][peerNodeId] = 1
            edgeTracker[peerNodeId][nodeId] = 1
            Gr.add_edge(peerNodeId, nodeId)
            edgeCntr = edgeCntr + 1            

          nodeId = nodeId + 1

    elif( peer_tr_end.search(pt_myline) != None):
      print("Peerlist sent by IpAddr : ",peerSenderIpAddr)
      return

def parse_block_tr( msgArr ):  
  blSenderIpAddr = ''
  blHash = ''
  blTime = ''

  for bt_myline in msgArr:
    if( peer_bl_tr_sendr.search(bt_myline) != None) :
      blIpaddrObj = re.search(r"Sender: (\d+\.\d+\.\d+\.\d+):", bt_myline, re.M|re.I)
      if( blIpaddrObj ) :
        blSenderIpAddr = blIpaddrObj.group(1)
    elif( block_tr_hash.search(bt_myline) != None) :
      blHashObj = re.search(r"^Block Hash: <(\w+)>", bt_myline, re.M|re.I)

      if( blHashObj ) :
        blHash = blHashObj.group(1)
          
    elif( peer_bl_tr_time.search(bt_myline) != None) :
      blTimeObj = re.search(r"^Time: (\d+)", bt_myline, re.M|re.I)

      if( blTimeObj ) :
        blTime = blTimeObj.group(1)

    elif( block_tr_end.search(bt_myline) != None):
      print("\nFound Block Sent by: {}" .format(blSenderIpAddr))
      break
      #return

  #print("Ip: {}\t Hash: {} \t Time: {}".format(blSenderIpAddr, blHash, blTime))
  # We only want to process the data if all information was
  # properly extracted.
  if( blSenderIpAddr != '' and
      blHash != '' and
      blTime != '' ) :
    process_block_info(blSenderIpAddr, blHash, blTime)
    
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
      print("Latency for Block {} was {} us".format(blockLat[blIndx]['block_hash'], blockLat[blIndx]['prop_dly']))
       
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

def parse_monitor_handshake(msgArr, Gr, ipAddrDict, monitorNodes, monitorNames):
  global nodeId
  monName = ''
  monIp = ''
  
  for pm_myline in msgArr:
    print("\nHandshake: {}", pm_myline)
    
    if( mon_tr_name.search(pm_myline) != None):
      monNameObj = re.search(r"Name: (\w+)", pm_myline, re.M|re.I)
      print("\nSearching for Name")
      if(monNameObj):
        monName = monNameObj.group(1)
        print("\nSetting Name to {}".format(monName))
        
    elif( mon_tr_ip.search(pm_myline) != None):
      monIpObj = re.search(r"Ip: (\d+\.\d+\.\d+\.\d+)", pm_myline, re.M|re.I)
      print("\nSearching for Ip")
      if(monIpObj):
        monIp = monIpObj.group(1)
        print("\nSetting Ip to {}".format(monIp))
        
    elif( mon_tr_end.search(pm_myline) != None):
      break

  if( monIp !=  '' ):
    ipAddrDict[monIp] = nodeId
    monitorNodes.append(nodeId)
    monitorNames[nodeId] = monName
    Gr.add_node(nodeId)
    print("Received Monitor {} w/ Node Id: {} \t w/ Ip Addr: {}".format(monName, nodeId, monIp))
    nodeId = nodeId + 1
  else:
    print("\nmonIp is empty {}".format(monIp))
  

    
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

  monitorNames = dict()       # Hash of Names of Monitors.  Key is nodeId(Found in monitorNodes)

  
  Gr=nx.Graph()               #  G is an empty Graph

  posi=nx.fruchterman_reingold_layout(Gr)
  Xn=[posi[k][0] for k in range(len(posi))]
  Yn=[posi[k][1] for k in range(len(posi))]

  trace_nodes=dict(type='scatter',
                   x=Xn, 
                   y=Yn,
                   mode='markers',
                   marker=dict(size=8, color='rgb(259,65,0)'),
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
            height=1600,
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

  while True:
    msg_arr = data_q.get()

    if( peer_tr_st.search(msg_arr[0]) != None):
      print("Found Start of Peer Tracking")
      parse_peer_tr(msg_arr, Gr, ipAddrDict, edgeTracker)

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
                              marker=dict(size=8, color='rgb(259,65,0)'),
                              #                text=labels,
                              hoverinfo='text')

      trace_nodes_monitor=dict(type='scatter',
                              x=Xm, 
                              y=Ym,
                              mode='markers',
                              marker=dict(size=24, color='rgb(65,105,225)'),
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
                      height=1600,
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
        


    elif( block_tr_st.search(msg_arr[0]) != None):
      #print("Found Start of Block Tracking")
      parse_block_tr(msg_arr)
    elif( mon_tr_st.search(msg_arr[0]) != None):
      parse_monitor_handshake(msg_arr, Gr, ipAddrDict, monitorNodes, monitorNames)
    else:
      print("Did not Match any String: {}".format(msg_arr[0]));

    
  return


def process_socket():
  global socket
  global data_q
  
  while True:  
    message = b'Hello'

    message = socket.recv()
    
    socket.send(b"ok")

    msg_str = str(message,'utf-8')
    msg_arr = msg_str.split('\n')  
    data_q.put(msg_arr)
  

if __name__ == '__main__':
  if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':

    print("Binding Socket")
    try:
      socket.bind("tcp://*:5555")
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

    
    





