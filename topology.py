from pathlib import Path
from pybatfish.question import bfq
from pybatfish.datamodel.flow import PathConstraints
from pybatfish.client.commands import bf_init_snapshot
from utils import *
from typing import Set, List, Tuple


class Topology(object):
    def __init__(self, reachable_nodes: Set[str], protected_nodes: Set[str], links: List[Tuple[str, str, str]]):
        self.reachable_nodes = reachable_nodes
        self.protected_nodes = protected_nodes
        self.links = links


def get_reachable_nodes_intersect(snapshot: str, switches: Set[str]) -> Set[str]:
    nodes = []
    results = bfq.nodeProperties().answer().frame()
    for _, result in results.iterrows():
        nodes.append(result.Node)
    reachable = {}
    for switch in switches:
        for node in nodes:
            results = bfq.reachability(
                pathConstraints=PathConstraints(startLocation=switch, endLocation=node)) \
                .answer(snapshot=snapshot)
            results = results.frame()
            if results.size > 0:
                if node not in reachable:
                    reachable[node] = 0
                reachable[node] += 1
    return set(map(lambda it: it[0], filter(lambda elem: elem[1] >= len(switches) // 3, reachable.items())))


def get_reachable_nodes(snapshot: str, config_path: str, switches: Set[str]) -> Set[str]:
    nodes = nodes_from_snapshot(config_path)
    reachable = set()
    switch_constraint = f"/{'|'.join(switches)}/"
    for node in nodes:
        if node in switches:
            reachable.add(node)
            continue
        results = bfq.reachability(
            pathConstraints=PathConstraints(startLocation=switch_constraint, endLocation=node)) \
            .answer(snapshot=snapshot)
        results = results.frame()
        if results.size > 0:
            reachable.add(node)
    return reachable

def get_reachable_interfaces_endnodes(snapshot: str, config_path: str, switches: Set[str]) -> Set[str]:
    nodes = get_reachable_nodes(snapshot, config_path, switches)
    return set([interface for node in nodes for interface in interfaces_from_snapshot(config_path, node)])


def get_reachable_interfaces(snapshot: str, switches: Set[str]) -> Set[str]:
    # bf_init_snapshot(str(snapshot), "reachable", overwrite=True)
    nodes = []
    results = bfq.nodeProperties().answer().frame()
    for _, result in results.iterrows():
        nodes.append(result.Node)
    reachable = set()
    for switch in switches:
        for node in nodes:
            results = bfq.reachability(
                pathConstraints=PathConstraints(startLocation=switch, endLocation=node)) \
                .answer(snapshot=snapshot)
            results = results.frame()
            for _, result in results.iterrows():
                for trace in result.Traces:
                    for hop in trace.hops:
                        for step in hop.steps:
                            if hasattr(step.detail, "outputInterface"):
                                reachable.add(f"{hop.node}:{step.detail.outputInterface}")
                            if hasattr(step.detail, "inputInterface"):
                                reachable.add(f"{hop.node}:{step.detail.inputInterface}")
    return reachable


def build_topology(base: str, config_path: str, reachable_nodes: Set[str], sensitive_nodes: Set[str]) -> Topology:
    reachable_interfaces = get_reachable_interfaces_endnodes(base, config_path, reachable_nodes)
    interfaces = set()
    results = bfq.interfaceProperties().answer().frame()
    for _, result in results.iterrows():
        interfaces.add(interface_to_str(result.Interface))
    links = []
    results = bfq.layer3Edges().answer(snapshot=base).frame()
    for _, result in results.iterrows():
        i1 = result.Interface
        i1_str = interface_to_str(i1)
        i2 = result.Remote_Interface
        i2_str = interface_to_str(i2)
        type = "accessible"
        if i1.hostname in sensitive_nodes or i2.hostname in sensitive_nodes:
            type = "sensitive"
        if i1_str not in reachable_interfaces or i2_str not in reachable_interfaces:
            type = "protected"
        links.append((i1_str, i2_str, type))
    return Topology(reachable_interfaces, interfaces.difference(reachable_interfaces), links)

