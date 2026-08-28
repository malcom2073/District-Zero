import xml.etree.ElementTree as ET
import re, sys

BASE = "/home/mcarpenter/.local/share/Steam/steamapps/common/7 Days To Die"
van = ET.parse(f"{BASE}/Data/Config/entitygroups.xml").getroot()

def entries_from_elem(elem):
    out = []
    for child in elem:
        if child.tag == "e" and child.get("n"):
            out.append(child.get("n"))
        elif child.tag == "entity" and child.get("name"):
            out.append(child.get("name"))
    # also CSV-style text lines
    if elem.text:
        for m in re.finditer(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*(,|\r?$)", elem.text.replace('\r',''), re.M):
            out.append(m.group(1))
    return out

groups = {}
order = []
for g in van.findall("entitygroup"):
    groups[g.get("name")] = entries_from_elem(g)
    order.append(g.get("name"))

dz = ET.parse(f"{BASE}/Mods/District Zero/Config/entitygroups.xml").getroot()

def xpath_group_name(xp):
    m = re.search(r"@name='([^']+)'", xp)
    return m.group(1) if m else None

for node in dz:
    if node.tag == "remove":
        xp = node.get("xpath", "")
        if "@name=" in xp and "entitygroup[" in xp and "starts-with" not in xp:
            n = xpath_group_name(xp)
            if n in groups:
                del groups[n]; order.remove(n)
        elif "starts-with(@name," in xp:
            pref = re.search(r"starts-with\(@name,'([^']+)'\)", xp).group(1)
            for n in [n for n in order if n.startswith(pref)]:
                del groups[n]; order.remove(n)
        elif "starts-with(@n,'animal')" in xp:
            for n in order:
                groups[n] = [e for e in groups[n] if not e.startswith("animal")]
        else:
            print("UNHANDLED remove:", xp)
    elif node.tag == "append" and node.get("xpath","").strip() == "/entitygroups":
        for g in node.findall("entitygroup"):
            n = g.get("name")
            ents = entries_from_elem(g)
            if n not in groups: order.append(n)
            groups.setdefault(n, []).extend(ents)
    elif node.tag == "append" and "starts-with(@name," in node.get("xpath",""):
        xp = node.get("xpath")
        pref = re.search(r"starts-with\(@name,'([^']+)'\)", xp).group(1)
        ents = []
        for child in node:
            if child.tag == "e" and child.get("n"): ents.append(child.get("n"))
            elif child.tag == "entity" and child.get("name"): ents.append(child.get("name"))
        for n in [n for n in order if n.startswith(pref)]:
            groups[n].extend(ents)
    elif node.tag in ("append", "set"):
        xp = node.get("xpath", "")
        n = xpath_group_name(xp)
        if n is None:
            print("UNHANDLED append/set:", xp); continue
        ents = []
        for child in node:
            if child.tag == "e" and child.get("n"): ents.append(child.get("n"))
            elif child.tag == "entity" and child.get("name"): ents.append(child.get("name"))
        if node.text:
            for m in re.finditer(r"^\s*([A-Za-z][A-Za-z0-9_]*)\s*(,|\r?$)", node.text.replace('\r',''), re.M):
                ents.append(m.group(1))
        if node.tag == "append":
            groups.setdefault(n, []).extend(ents)
            if n not in order: order.append(n)
        else:
            groups[n] = ents

# --- simulate OUR patch: strip humanoid zombies everywhere ---
zombie_re = re.compile(r"^zombie")
emptied = {}
for n in order:
    kept = [e for e in groups[n] if not zombie_re.match(e)]
    removed = [e for e in groups[n] if zombie_re.match(e)]
    if removed and not kept:
        emptied[n] = (len(removed), sorted(set(removed)))
    groups[n] = kept

# cross-reference: where is each emptied group used?
refs = {}
for f, tag in [("Data/Config/spawning.xml","spawning"), ("Data/Config/gamestages.xml","gamestages"), ("Data/Config/gameevents.xml","gameevents")]:
    txt = open(f"{BASE}/{f}").read()
    for m in re.finditer(r'(?:entitygroup|group)="([^"]+)"', txt):
        refs.setdefault(m.group(1), set()).add(tag)

print(f"{len(groups)} groups total after DZ merge; {len(emptied)} would be emptied by zombie-strip\n")
print("=== EMPTIED GROUPS (removed-count | referenced-by | sample entities) ===")
for n in sorted(emptied):
    cnt, sample = emptied[n]
    r = sorted(refs.get(n) or []) or ["<unreferenced/POI-sleeper>"]
    print(f"{n}  [{cnt} ent, refs={r}]  e.g. {sample[:3]}")

# sanity: any remaining zombie entries anywhere?
leftover = [(n,e) for n in order for e in groups[n] if zombie_re.match(e)]
print(f"\nLeftover zombie entries after strip: {len(leftover)}")
