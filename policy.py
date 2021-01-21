from action import *
from resource import *
from connectors import *
from condition import Condition
from models import HeaderConstraintBuilder, PathConstraintBuilder
from pybatfish.datamodel.flow import HeaderConstraints, PathConstraints
from connectors import Connector
from pybatfish.question import bfq
from typing import List
import csv


# The user can do {action} for {resource} under {condition}.
class Policy(Connector):
    def __init__(self, action: List[Action], resource: List[Resource], condition: Condition = None):
        self.actions = action
        self.resources = resource
        self.condition = condition
        self.header_constraint = HeaderConstraintBuilder()
        self.path_constraint = PathConstraintBuilder()

    def build(self):
        self.build_header_constraint()
        self.build_path_constraint()

    def build_header_constraint(self):
        for action in self.actions:
            action.build_header_constraint(self.header_constraint)
        for resource in self.resources:
            resource.build_header_constraint(self.header_constraint)

    def build_path_constraint(self):
        for resource in self.resources:
            resource.build_path_constraint(self.path_constraint)

    def eval(self, ori_snapshot: str, new_snapshot: str) -> bool:
        result = bfq.differentialReachability(
            header=self.header_constraint.build(), pathConstraints=self.path_constraint.build()) \
            .answer(snapshot=ori_snapshot, reference_snapshot=new_snapshot).frame()
        return result.size > 0


class Waypoint(Connector):
    def __init__(self, src: str, dst: str, waypoint: str):
        self.src = src
        self.dst = dst
        self.waypoint = waypoint

    def eval(self, ori_snapshot: str, new_snapshot: str) -> bool:
        result = bfq.reachability(headers=HeaderConstraints(srcIps=self.src, dstIps=self.dst),
                                  pathConstraints=PathConstraints(transitLocations=self.waypoint)) \
            .answer(snapshot=new_snapshot).frame()
        return result.size > 0

    def __str__(self):
        return f"Waypoint({self.src}, {self.dst}, {self.waypoint})"


class Reachability(Connector):
    def __init__(self, src: str, dst: str):
        self.src = src
        self.dst = dst

    def eval(self, ori_snapshot: str, new_snapshot: str) -> bool:
        result = bfq.reachability(headers=HeaderConstraints(dstIps=self.dst),
                                  pathConstraints=PathConstraints(startLocation=self.src)) \
            .answer(snapshot=new_snapshot).frame()
        return result.size > 0

    def __str__(self):
        return f"Reachability({self.src}, {self.dst})"


def build_policies_from_csv(path: str) -> List[Connector]:
    policies = []
    with open(path) as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            policy = None
            src = row['source']
            dst = row['Destinations'].split(' ')[1][1:-1]
            dst_node = row['Destinations'].split(' ')[0].split(":")[0]
            specifics = row['specifics']
            if "HOLDSNOT" in row["Status"]:
                continue
            if "Reachability" in row['type']:
                policy = Reachability(src, dst)
            elif "Waypoint" in row['type'] and dst_node != specifics and src != specifics:
                policy = Waypoint(src, dst, specifics)
            elif "Isolation" in row['type']:
                policy = Not(Reachability(src, dst))
            if policy is None:
                continue
            policies.append(policy)
    return policies

