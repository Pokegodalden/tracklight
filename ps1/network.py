"""Line/bound-aware topology. Protection geometry is intentionally not expanded."""
from collections import defaultdict


def build_network(lines, stations, sectors, locations, fail):
    """Accept directed, connected, unbranched lines. Sequence gaps are harmless.

    Follow explicit endpoints; never connect consecutive sector seq numbers.
    EB/WB use the same spatial order, not an inferred direction of train travel.
    """
    chains = {}
    for line in lines:
        members = {r["station_id"]: r for r in stations if r["line_code"] == line}
        edges = [s for s in sectors if s["line_code"] == line]
        outgoing, incoming = defaultdict(list), defaultdict(list)
        for s in edges:
            outgoing[s["from_station_id"]].append(s)
            incoming[s["to_station_id"]].append(s)
            if members[s["from_station_id"]]["seq"] >= members[s["to_station_id"]]["seq"]:
                fail("topology_order", s, "from_station_id", "Sector endpoints must follow increasing station order; reversed edges are unsupported.")
        if any(len(v) > 1 for v in outgoing.values()) or any(len(v) > 1 for v in incoming.values()):
            fail("unsupported_branch", edges[0] if edges else None, "line_code", f"Line {line} branches; supply a reviewed routing policy before import.")
            continue
        starts = [s for s in members if not incoming[s]]
        ordered, seen = [], set()
        current = starts[0] if len(starts) == 1 else None
        visited_stations = {current} if current is not None else set()
        while current is not None and outgoing[current]:
            edge = outgoing[current][0]
            if edge["sector_id"] in seen:
                break
            seen.add(edge["sector_id"])
            ordered.append(edge["sector_id"])
            current = edge["to_station_id"]
            visited_stations.add(current)
        if not edges or len(ordered) != len(edges) or visited_stations != set(members):
            fail("unsupported_topology", edges[0] if edges else None, "line_code", f"Line {line} must be one connected, acyclic chain containing every station.")
            continue
        chains[line] = ordered

    sector_index = {s["sector_id"]: s for s in sectors}
    nodes, links = [], []
    for loc in locations:
        node = {k: loc[k] for k in ("location_id", "location_kind", "line_code", "bound", "source")}
        node["capacity_resource_id"] = loc["location_id"]
        nodes.append(node)
        if loc["location_kind"] == "tunnel sector":
            sector = sector_index[loc["sector_id"]]
            for station in (sector["from_station_id"], sector["to_station_id"]):
                links.append({"tunnel_location_id": loc["location_id"],
                              "platform_location_id": f"PLAT:{loc['line_code']}:{station}:{loc['bound']}",
                              "source": sector["source"]})
    interchanges = defaultdict(list)
    for station in stations:
        if station["is_interchange"]:
            interchanges[station["station_id"]].append(station["line_code"])
    return {"line_sector_order": chains, "nodes": nodes, "incidence_links": links,
            "interchanges": [{"station_id": s, "line_codes": sorted(ls),
                              "shared_capacity": False, "live_propagation": "UNVERIFIED"}
                             for s, ls in sorted(interchanges.items())],
            "cross_line_travel_edges": [], "protection_edges": None,
            "protection_status": "UNVERIFIED", "unconfigured_rules": ["R12", "R15", "R17"]}


def working_span(activity, network, locations, sectors):
    """Return inclusive SEC endpoints + incident platforms under provisional R04."""
    start, end = (locations[activity[k]] for k in ("start_location_id", "end_location_id"))
    if start["location_kind"] != "tunnel sector" or end["location_kind"] != "tunnel sector":
        raise ValueError("Platform endpoints need a reviewed span policy; this version supports SEC endpoints only.")
    if (start["line_code"], start["bound"]) != (end["line_code"], end["bound"]):
        raise ValueError("An activity span must stay on one line and bound; cross-line/bound routes are unsupported.")
    chain = network["line_sector_order"][start["line_code"]]
    first, last = chain.index(start["sector_id"]), chain.index(end["sector_id"])
    if first > last:
        raise ValueError("Reversed spatial endpoints are unsupported; endpoints are not silently swapped (including WB).")
    result = []
    for sector_id in chain[first:last+1]:
        s = sectors[sector_id]
        platform = f"PLAT:{s['line_code']}:{s['from_station_id']}:{start['bound']}"
        if not result:
            result.append(platform)
        result.extend([f"{sector_id}:{start['bound']}",
                       f"PLAT:{s['line_code']}:{s['to_station_id']}:{start['bound']}"])
    return result
