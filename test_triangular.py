import sys

sys.path.insert(0, "tests")
from common_functions import build_steel_s235, build_ipe180
from fers_core import Node, Member, FERS, MemberSet, NodalSupport, DistributedLoad
from fers_core.loads.distributionshape import DistributionShape
import ujson

steel = build_steel_s235()
section = build_ipe180(steel)

calculation = FERS()
n1 = Node(0.0, 0.0, 0.0)
n2 = Node(5.0, 0.0, 0.0)
n1.nodal_support = NodalSupport()
member = Member(start_node=n1, end_node=n2, section=section)
calculation.add_member_set(MemberSet(members=[member]))

lc = calculation.create_load_case(name="Test")

# What does Rust expect for triangular from 0.0 to 0.6?
# Rust: magnitude=1000, end_magnitude=0.0, start_frac=0.0, end_frac=0.6
load = DistributedLoad(
    member=member,
    load_case=lc,
    distribution_shape=DistributionShape.TRIANGULAR,
    magnitude=1000.0,
    end_magnitude=0.0,
    direction=(0.0, 1.0, 0.0),
    start_frac=0.0,
    end_frac=0.6,
)

input_dict = calculation.to_dict()
print("=== Distributed Load as sent to Rust ===")
print(ujson.dumps(input_dict["load_cases"][0]["distributed_loads"][0], indent=2))
