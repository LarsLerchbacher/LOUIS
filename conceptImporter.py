import gzip, csv, json
from Model import *

model = Model("base", False)
model.log("Importing data from ConceptNet")

ALLOWED_RELATIONS = {
    "/r/IsA":        "is_a",
    "/r/Causes":     "causes",
    "/r/HasProperty":"has_property",
    "/r/UsedFor":    "is_for",
    "/r/CapableOf":  "can",
    "/r/Antonym":    "opposite_of",
    "/r/RelatedTo":  "related_to",
}

MIN_WEIGHT = 2.0

with open("conceptnet-assertions-5.7.0.csv", encoding="utf-8") as f:
    reader = csv.reader(f, delimiter="\t")
    for row in reader:
        relation = row[1]
        start    = row[2]
        end      = row[3]
        weight   = json.loads(row[4])["weight"]

        # filter
        if relation not in ALLOWED_RELATIONS:
            continue
        if not start.startswith("/c/en/") or not end.startswith("/c/en/"):
            continue
        if weight < MIN_WEIGHT:
            continue

        # extract concept names
        start_label = start.split("/")[3]
        end_label   = end.split("/")[3]

        # use your existing modules
        start = model.get_node(start_label)
        end = model.get_node(end_label)
        if len(model.cursor.execute("SELECT id FROM relations WHERE subj = ? AND type = ? AND obj = ?;", (start_label, ALLOWED_RELATIONS[relation], end_label)).fetchall()) == 0:
                model.add_relation(start_label, ALLOWED_RELATIONS[relation], end_label)