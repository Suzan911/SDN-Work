#!/usr/bin/env python
'''
Fat tree topology create by mininet
Author : Yi Tseng
'''
import logging
import pdb
import os
from functools import partial

from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.node import OVSSwitch
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.link import Link, Intf, TCLink
from mininet.topo import Topo
from mininet.util import dumpNodeConnections
from p4_mininet import P4DockerSwitch

logging.basicConfig(level=logging.DEBUG)
LOG = logging.getLogger('FatTreeTopo')
lib_path = os.path.abspath(os.path.join('..', 'targets', 'load_balance', 'tests', 'pd_thrift'))

class FatTreeTopo(Topo):
    core_switches = []
    pods = []

    def __init__(self, k=4, ac_bw=1000, pod_bw=100, ac_pkt_lost=5, pod_pkt_lost=0):
        '''
        Param:
        k: k value for this fat tree(Default: 4)
        ac_bw: bandwidth between aggregation and core(Default 1Gbps)
        pod_bw: bandwidth between switches in pod(Default 100Mbps)
        ac_pkt_lost: packet lost between aggregation and core(Default: 5%)
        pod_pkt_lost: packet lost between switches in pod(Default: 0%)
        '''
        self.num_pods = k
        self.num_cores = (k / 2) ** 2
        self.num_aggres = (k ** 2) / 2
        self.num_aggres_per_pod = self.num_aggres / self.num_pods
        self.num_edges = (k ** 2) / 2
        self.num_edges_per_pod = self.num_edges / self.num_pods
        self.num_host_per_edge = k / 2
        self.ac_bw = ac_bw
        self.pod_bw = pod_bw
        self.ac_pkt_lost = ac_pkt_lost
        self.pod_pkt_lost = pod_pkt_lost

        Topo.__init__(self)

    def create_core(self):
        '''
        Create core switches
        '''
        for i in range(0, self.num_cores):
            switch_name = 's1%d' % (i, )
            self.core_switches.append(self.addSwitch(switch_name, target_name='p4dockerswitch', cls=P4DockerSwitch, sai_port=self.global_sai_port_count, pcap_dump=False))
            self.global_sai_port_count = self.global_sai_port_count + 1

    def create_pods(self):
        '''
        Create pods
        '''
        for pi in range(0, self.num_pods):
            self.pods.append({'aggr': [], 'edge': []})

            # create aggregation layer
            for ai in range(0, self.num_aggres_per_pod):
                switch_name = 's2%d%d' % (pi, ai, )
                self.pods[pi]['aggr'].append(self.addSwitch(switch_name, target_name='p4dockerswitch', cls=P4DockerSwitch, sai_port=self.global_sai_port_count, pcap_dump=False))
                self.global_sai_port_count = self.global_sai_port_count + 1

            # create edge layer
            for ei in range(0, self.num_edges_per_pod):
                switch_name = 's3%d%d' % (pi, ei, )
                edge_switch = self.addSwitch(switch_name, target_name='p4dockerswitch', cls=P4DockerSwitch, sai_port=self.global_sai_port_count, pcap_dump=False)
                self.global_sai_port_count = self.global_sai_port_count + 1

                # create hosts
                for hi in range(0, self.num_host_per_edge):
                    host_name = 'h%d%d%d' % (pi, ei, hi, )
                    host = self.addHost(host_name)
                    self.addLink(edge_switch, host)

            # link aggregation and edge
            for aggr_switch in self.pods[pi]['aggr']:

                for edge_switch in self.pods[pi]['edge']:
                    LOG.info('add link from %s to %s', aggr_switch, edge_switch)
                    self.addLink(aggr_switch,
                                 edge_switch,
                                 bw=self.pod_bw,
                                 loss=self.pod_pkt_lost)

    def link_core_to_pods(self):
        '''
        link aggregation layer to core layer
        aggregation switch can link to core switch directly
        pod number doesn't matter
        ex:
        k = 8
        4 aggregation switch in a pod
        A0 -> C0~C3
        A1 -> C4~C7
        A2 -> C8~C11
        A3 -> C12~C15
        '''
        num_cores_per_aggr = self.num_cores / self.num_aggres_per_pod

        for pod in self.pods:

            for ai in range(0, self.num_aggres_per_pod):  # ai for aggregation index
                cis = ai * num_cores_per_aggr  # start index
                cie = ai * num_cores_per_aggr + num_cores_per_aggr  # end index

                for ci in range(cis, cie):  # ci for core index
                    aggr_switch = pod['aggr'][ai]
                    core_switch = self.core_switches[ci]
                    LOG.info('add link from %s to %s', aggr_switch, core_switch)
                    self.addLink(aggr_switch,
                                 core_switch,
                                 bw=self.ac_bw,
                                 loss=self.ac_pkt_lost)

    def set_protocols_to_all_switch(self, protocols):
        pdb.set_trace()
        for core_switch in self.core_switches:
            set_protocol(core_switch)

        for pod in self.pods:

            for aggr_switch in pod['aggr']:
                set_protocol(aggr_switch)

            for edge_switch in pod['edge']:
                set_protocol(edge_switch)

    def init_fat_tree(self):
        self.global_sai_port_count = 25000
        self.create_core()
        self.create_pods()
        self.link_core_to_pods()

if __name__ == '__main__':
    fat_tree = FatTreeTopo(4)
    fat_tree.init_fat_tree()
    net = Mininet(topo=fat_tree, controller=None)
    net.start()

    CLI(net)
    net.stop()

