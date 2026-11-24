"""Evaluate a union of selected maps with the certified regional route engine."""
from dataclasses import replace

from experiments.constructive_axial import evaluate


def evaluate_active_union(inputs, lines, clearance, reference, methods):
    analysis=inputs["analysis"]
    strict=analysis["maps"]["strict_backward"]
    ids=sorted(set(strict["line_ids"])|{i for method in methods.values()
                 for i in method["maps"]["final"]})
    remap={old:new for new,old in enumerate(ids)}
    active=[replace(lines[old],line_id=new) for new,old in enumerate(ids)]
    incidence=analysis["incidence"]
    region_lines={region:[remap[i] for i in candidates if i in remap]
                  for region,candidates in incidence["region_lines"].items()}
    filtered=inputs|{"analysis":analysis|{
        "incidence":incidence|{"region_lines":region_lines},
        "maps":analysis["maps"]|{"strict_backward":strict|{
            "line_ids":[remap[i] for i in strict["line_ids"]]}}}}
    maps={name:{"maps":{"final":[remap[i] for i in value["maps"]["final"]]}}
          for name,value in methods.items()}
    result=evaluate(filtered,active,clearance,reference,maps)
    result["active_graph_candidate_ids"]=ids
    return result
