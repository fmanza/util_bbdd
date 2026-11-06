import json, pathlib
out = pathlib.Path(__file__).parent / "out" / "harness" / "cases.json"
cands = {"ent37": "a#37;b", "ent92": "a#92;b", "full": "a\uff05b\uff3cc", "pct_space": "a % b", "pct_end": "ab%", "bs_dbl": "a\\b",
         "init_ent": "#37;#37;{init: {'theme':'dark'}}#37;#37;", "ent_quot": "x #quot; y"}
cases = []
for k, v in cands.items():
    cases.append({"id": f"alias_{k}", "expect": "?", "desc": k, "text": 'erDiagram\n    e1["' + v + '"] {\n        INTEGER id PK\n    }'})
    cases.append({"id": f"comment_{k}", "expect": "?", "desc": k, "text": 'erDiagram\n    e1["t"] {\n        INTEGER id PK "' + v + '"\n    }'})
out.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
