"""D10: seeded chaos dataset generator (synthetic data only, answer key built alongside).

Creates a dataset with names, labels, ID shapes, date formats and nesting that do NOT appear
in the toolkit's practice data, using the same truth.json schema so that
tools/bench/score_dev.py can score it:

    python tools/chaos/generate.py --seed dev-1 --out out/chaos/dev-1
    python tools/bench/run_bench.py --input out/chaos/dev-1/input --output out/chaos/dev-1/bench
    python tools/bench/score_dev.py --output out/chaos/dev-1/bench --dev out/chaos/dev-1

Seeds starting with "holdout" are reserved for the sealed held-out set (see docs).
Nothing here is real data: every name, number and village is invented.
"""
from __future__ import annotations

import argparse
import base64
import csv
import datetime as dt
import hashlib
import io
import json
import random
import re
import sys
from pathlib import Path

# (latin, devanagari). None of these appear in the toolkit data or in src/detection lists.
GIVEN = [("Lalremruata", None), ("Debashis", "देबाशीष"), ("Meenakshi", "मीनाक्षी"),
         ("Venkatesh", "वेंकटेश"), ("Lakshmanan", None), ("Gurvinder", "गुरविंदर"), ("Harleen", "हरलीन"),
         ("Zoya", "ज़ोया"), ("Imaad", "इमाद"), ("Sourav", "सौरव"), ("Padmini", "पद्मिनी"), ("Ishwarya", "ईश्वर्या"),
         ("Tenzin", "तेनज़िन"), ("Ananya", "अनन्या"), ("Rudra", "रुद्र"), ("Kiaan", "कियान"), ("Mehrunnisa", None),
         ("Chandrakant", "चंद्रकांत"), ("Bhavesh", "भावेश"), ("Nilufar", "नीलुफ़र"), ("Gopinath", "गोपीनाथ"),
         ("Swaroop", "स्वरूप"), ("Ruchika", "रुचिका"), ("Jasleen", "जसलीन"), ("Yashwant", "यशवंत"),
         ("Parveez", "परवेज़"), ("Thangam", None), ("Ibrahim", "इब्राहीम"), ("Sanvi", "सान्वी")]
SURN = [("Bhattacharjee", "भट्टाचार्जी"), ("Iyer", "अय्यर"), ("Reddy", "रेड्डी"),
        ("Gogoi", "गोगोई"), ("Sangma", "संगमा"), ("Kurian", "कुरियन"), ("Menon", "मेनन"), ("Pillai", "पिल्लई"),
        ("Dsouza", "डिसूज़ा"), ("Chettiar", "चेट्टियार"), ("Kakati", "काकती"),
        ("Bajwa", "बाजवा"), ("Hegde", "हेगड़े"), ("Mondal", "मंडल"), ("Rao", "राव")]
DOCTORS = ["Venkatesh Rao", "Ishita Banerjee", "Farhan Qureshi", "Lata Mangeshwar", "Anirudh Sethi"]
DISTRICTS = ["Lucknow", "Barabanki", "Sitapur", "Unnao", "Hardoi", "Bahraich"]
VILLAGE_SYL = ["Chand", "Ram", "Shiv", "Gopal", "Lakh", "Dev", "Mohan", "Kishan", "Sur", "Bhim", "Nand", "Raj"]
VILLAGE_SUF = ["pur", "ganj", "nagar", "pura", "garh", "mau", "kheda", "wara"]
MEDS = [("Tab Metformin 500 mg 1-0-1 x 14 days", "medication"), ("Tab Atorvastatin 10 mg 0-0-1 x 30 days", "medication"),
        ("Cap Omeprazole 20 mg 1-0-0 x 7 days", "medication"), ("Tab Cetirizine 10 mg 0-0-1 x 5 days", "medication")]
HOSP = [("KMC", "KMC-{y}-{n:05d}"), ("NHB", "NHB/{y2}/{n:06d}"), ("Raksha Care", "RC{n:07d}")]


class Gen:
    def __init__(self, seed: str):
        self.r = random.Random(seed)
        self.files: dict[str, dict] = {}
        self.persons = []
        self.used_phones: set[str] = set()

    # ------------------------------------------------------------------ people
    def phone(self) -> str:
        while True:
            p = str(self.r.choice("6789")) + "".join(self.r.choice("0123456789") for _ in range(9))
            if p not in self.used_phones:
                self.used_phones.add(p)
                return p

    def person(self, i: int) -> dict:
        r = self.r
        g, s = r.choice(GIVEN), r.choice(SURN)
        rg = r.choice(GIVEN)
        hosp = HOSP[i % len(HOSP)]
        n = r.randint(100, 99999)
        mrn = hosp[1].format(y=2026, y2=26, n=n)
        age = r.choice([r.randint(3, 17), r.randint(18, 70), r.randint(71, 98)])
        dob = dt.date(2026, 11, 20) - dt.timedelta(days=age * 365 + r.randint(0, 360))
        p = dict(i=i, given=g, surn=s, rel=(rg, s), male=r.random() < 0.5, age=age, dob=dob, mrn=mrn,
                 core=re.findall(r"\d+", mrn)[-1], hosp=hosp[0], phone=self.phone(), phone2=self.phone(),
                 aadhaar="".join(r.choice("0123456789") for _ in range(12)), pin=str(r.randint(200000, 285999)),
                 village=r.choice(VILLAGE_SYL) + r.choice(VILLAGE_SUF) + r.choice(["", " Kalan", " Khurd"]),
                 district=r.choice(DISTRICTS), house=r.randint(1, 900), doctor=r.choice(DOCTORS))
        p["aadhaar"] = str(r.randint(2, 9)) + p["aadhaar"][1:]
        return p

    @staticmethod
    def full(p, deva=False):
        if deva and p["given"][1] and p["surn"][1]:
            return f'{p["given"][1]} {p["surn"][1]}'
        return f'{p["given"][0]} {p["surn"][0]}'

    @staticmethod
    def relname(p):
        return f'{p["rel"][0][0]} {p["rel"][1][0]}'

    # ------------------------------------------------------------------ truth helpers
    @staticmethod
    def name_ent(kind, surface, role, script="latin", channel="content", generic=()):
        toks = [t.casefold() for t in re.findall(r"[^\W\d_]+", surface) if t.casefold() not in generic]
        return dict(type=kind, surface=surface, person="P", role=role, script=script, channel=channel,
                    match="name", tokens=toks, full=True, critical=kind == "PATIENT_NAME")

    @staticmethod
    def digit_ent(kind, surface, key, channel="content", script="latin"):
        return dict(type=kind, surface=surface, person="P", role="patient", script=script, channel=channel,
                    match="digits", key=key, critical=True)

    @staticmethod
    def text_ent(kind, surface, channel="content", script="latin", match="text"):
        return dict(type=kind, surface=surface, person="P", role="patient", script=script, channel=channel,
                    match=match, key=surface.casefold(), critical=False)

    def add_file(self, rel, raw: bytes, fmt, units, delimiter=None, expect="sanitize"):
        self.files[rel] = dict(path=rel, format=fmt, encoding="utf-8", delimiter=delimiter, expect=expect,
                               category="chaos", clean=False, sha256=hashlib.sha256(raw).hexdigest(),
                               size=len(raw), generalizable=[], units=units, raw=raw)

    @staticmethod
    def unit(loc, entities, preserve=(), exclude=()):
        return dict(loc=loc, patient=None, cid=None, link="none", tags=[], entities=list(entities),
                    preserve=[dict(text=t, kind=k, weight=1.0, **({"trap": tr} if tr else {})) for t, k, tr in preserve],
                    dates=[], fields=[], exclude=list(exclude))

    def fmt_date(self, d: dt.date) -> str:
        return self.r.choice([d.strftime("%d-%b-%Y"), d.strftime("%d.%m.%Y"), d.strftime("%Y/%m/%d"), d.isoformat(),
                              f"{d.day} {d.strftime('%B %Y')}", d.strftime("%d/%m/%Y")])

    def fmt_phone(self, p: str, deva=False) -> str:
        form = self.r.choice(["plain", "plus91", "dash", "space", "zero", "dash91"])
        out = {"plain": p, "plus91": f"+91 {p[:5]} {p[5:]}", "dash": f"{p[:5]}-{p[5:]}", "space": f"{p[:3]} {p[3:6]} {p[6:]}",
               "zero": f"0{p}", "dash91": f"+91-{p}"}[form]
        return out.translate(str.maketrans("0123456789", "०१२३४५६७८९")) if deva else out

    def fmt_aadhaar(self, a: str) -> str:
        return self.r.choice([a, f"{a[:4]} {a[4:8]} {a[8:]}", f"{a[:4]}-{a[4:8]}-{a[8:]}"])

    # ------------------------------------------------------------------ files
    def registration_csv(self, rel, people, headers, delimiter=","):
        rows, units = [], []
        for i, p in enumerate(people):
            name = self.full(p)
            ph, ad = self.fmt_phone(p["phone"]), self.fmt_aadhaar(p["aadhaar"])
            dobs = self.fmt_date(p["dob"])
            addr = f'Plot {p["house"]}, near {self.r.choice(["Shiv Mandir", "Water Tank", "Govt School"])}, ' \
                   f'Block {p["district"]}'
            rows.append([p["mrn"], name, "M" if p["male"] else "F", str(p["age"]), dobs,
                         "S/o " + self.relname(p) if p["male"] else "D/o " + self.relname(p), addr, p["village"],
                         p["pin"], ph, ad])
            ents = [self.digit_ent("MRN", p["mrn"], p["core"]), self.name_ent("PATIENT_NAME", name, "patient"),
                    self.name_ent("RELATIVE_NAME", self.relname(p), "relative"),
                    self.text_ent("HOUSE", f'Plot {p["house"]}'), self.text_ent("LANDMARK", addr.split(", ")[1]),
                    self.text_ent("VILLAGE", p["village"]),
                    dict(self.text_ent("PIN", p["pin"], match="digits_exact"), key=p["pin"]),
                    self.digit_ent("PHONE", ph, p["phone"]), self.digit_ent("AADHAAR", ad, p["aadhaar"]),
                    dict(self.text_ent("DOB", dobs, match="dob"), key=p["dob"].isoformat())]
            units.append(self.unit(f"row:{i}", ents))
        buf = io.StringIO()
        w = csv.writer(buf, delimiter=delimiter, lineterminator="\n")
        w.writerow(headers)
        w.writerows(rows)
        self.add_file(rel, buf.getvalue().encode("utf-8"), "csv" if delimiter == "," else "tsv", units, delimiter)

    def json_visits(self, rel, people):
        visits, units = [], []
        for i, p in enumerate(people):
            name = self.full(p)
            note_name = p["given"][0]
            sty = self.r.choice(["ji", "sahab", "bhai", "didi"])
            bp = f"{self.r.randint(100, 170)}/{self.r.randint(60, 100)}"
            med, kind = self.r.choice(MEDS)
            doc = f'Dr. {p["doctor"]}'
            visits.append({"enc_ref": f'E{self.r.randint(10**6, 10**7)}', "beneficiary": {"fullName": name,
                           "msisdn": self.fmt_phone(p["phone"]), "yrs": p["age"]},
                           "guardianName": self.relname(p), "attending": doc,
                           "clinicalNote": f"{note_name} {sty} ka BP {bp}, {med}. Review with {doc}. Referred by ASHA worker.",
                           "uhid": p["mrn"]})
            ents = [self.name_ent("PATIENT_NAME", name, "patient"), self.digit_ent("PHONE", visits[-1]["beneficiary"]["msisdn"], p["phone"]),
                    self.name_ent("RELATIVE_NAME", self.relname(p), "relative"), self.digit_ent("MRN", p["mrn"], p["core"]),
                    self.name_ent("PATIENT_NAME", f"{note_name} {sty}", "patient", "hinglish",
                                  generic={"ji", "sahab", "bhai", "didi"})]
            pres = [(f"BP {bp}", "vital", None), (med, kind, "1-0-1"), (doc, "doctor", "doctor"),
                    ("Referred by ASHA worker", "context", "asha")]
            units.append(self.unit(f"/encounters/{i}", ents, pres))
        raw = (json.dumps({"source": "chaos-his", "encounters": visits}, ensure_ascii=False, indent=2) + "\n").encode()
        self.add_file(rel, raw, "json", units)

    def discharge_text(self, rel, p, style):
        name, dname = self.full(p), self.full(p, deva=True)
        d1 = dt.date(2026, self.r.randint(1, 10), self.r.randint(1, 25))
        d2 = d1 + dt.timedelta(days=self.r.randint(2, 9))
        ph = self.fmt_phone(p["phone"])
        bp = f"{self.r.randint(100, 170)}/{self.r.randint(60, 100)}"
        med, kind = self.r.choice(MEDS)
        doc = f'Dr. {p["doctor"]}'
        rel_name = self.relname(p)
        if style == "en":
            text = (f'{p["hosp"]} Hospital - Discharge\nName of Patient: {name}     Age: {p["age"]} Yrs / {"M" if p["male"] else "F"}\n'
                    f'Hospital ID: {p["mrn"]}\nGuardian: {rel_name}\nResidence: Plot {p["house"]}, near Shiv Mandir, '
                    f'{p["village"]}, Block {p["district"]}, Dist. {p["district"]} - {p["pin"]}\nCell: {ph}\n'
                    f'Admitted: {self.fmt_date(d1)}\nDischarged: {self.fmt_date(d2)}\nC/O fever x 3 days\n'
                    f'BP {bp}. {med}\nSeen by {doc}.\nNext of kin: {rel_name} ({self.fmt_phone(p["phone2"])})\n')
            ents = [self.name_ent("PATIENT_NAME", name, "patient"), self.digit_ent("MRN", p["mrn"], p["core"]),
                    self.name_ent("RELATIVE_NAME", rel_name, "relative"), self.text_ent("HOUSE", f'Plot {p["house"]}'),
                    self.text_ent("LANDMARK", "near Shiv Mandir"), self.text_ent("VILLAGE", p["village"]),
                    dict(self.text_ent("PIN", p["pin"], match="digits_exact"), key=p["pin"]),
                    self.digit_ent("PHONE", ph, p["phone"]), self.digit_ent("PHONE", self.fmt_phone(p["phone2"]), p["phone2"])]
            pres = [(f"BP {bp}", "vital", None), (med, kind, "1-0-1"), (doc, "doctor", "doctor"), ("C/O fever x 3 days", "complaint", "c/o-complaint")]
        else:
            if not p["given"][1] or not p["surn"][1]:
                return False
            rn = f'{p["rel"][0][1] or p["rel"][0][0]} {p["surn"][1]}'
            text = (f'{p["hosp"]} अस्पताल - डिस्चार्ज\nरोगी का नाम: {dname}    आयु: {p["age"]} वर्ष\n'
                    f'पति/पिता का नाम: {rn}\nपंजीकरण सं.: {p["mrn"]}\nसंपर्क: {self.fmt_phone(p["phone"], deva=True)}\n'
                    f'BP {bp}, {med}\n{doc}\n')
            ents = [self.name_ent("PATIENT_NAME", dname, "patient", "deva"), self.name_ent("RELATIVE_NAME", rn, "relative", "deva"),
                    self.digit_ent("MRN", p["mrn"], p["core"]),
                    self.digit_ent("PHONE", self.fmt_phone(p["phone"], deva=True), p["phone"], script="deva")]
            pres = [(f"BP {bp}", "vital", None), (med, kind, "1-0-1"), (doc, "doctor", "doctor")]
        self.add_file(rel, text.encode("utf-8"), "text", [self.unit("doc", ents, pres)])
        return True

    def named_file(self, rel_dir, p):
        name = self.full(p).replace(" ", "_")
        rel = f'{rel_dir}/{name}_{p["mrn"].replace("/", "-")}_{self.r.randint(1, 99)}.txt'
        text = f'Lab summary. HbA1c {self.r.randint(5, 11)}.{self.r.randint(0, 9)} %. Haemoglobin 12.1 g/dL.\n'
        ents = [self.name_ent("PATIENT_NAME", name, "patient", channel="filename"),
                self.digit_ent("MRN", p["mrn"], p["core"], channel="filename")]
        self.add_file(rel, text.encode(), "text", [self.unit("doc", [], [("Haemoglobin 12.1 g/dL", "lab", None)]),
                                                   self.unit("@filename", ents)])

    def canary_files(self, rel_dir):
        r = self.r
        for k in range(3):
            g, s = r.choice(GIVEN), r.choice(SURN)
            nm, ph = f"{g[0]} {s[0]}", self.phone()
            ent = lambda ch="content": [dict(self.name_ent("CANARY", nm, "patient", channel=ch), canary=True),
                                        dict(self.digit_ent("PHONE", ph, ph, channel=ch), canary=True)]
            if k == 0:
                text = f"Gate log\n09:15 - {nm} (visitor, ward 3), mob {ph}\n09:40 - {r.choice(DOCTORS)} took round.\n"
                self.add_file(f"{rel_dir}/gate_log_{k}.txt", text.encode(), "text", [self.unit("doc", ent())])
            elif k == 1:
                payload = base64.b64encode(f"Witness: {nm}. Contact {ph}. Procedure explained.".encode()).decode()
                raw = json.dumps({"form": "consent", "scan": {"mime": "text/plain", "blob": payload}}, indent=2).encode()
                self.add_file(f"{rel_dir}/consent_{k}.json", raw, "json", [self.unit("doc", ent("base64"))])
            else:
                raw = json.dumps({"tickets": [{"id": "T-9", "raised_by": {"display": nm, "tel": ph}, "state": "open"}]},
                                 indent=2).encode()
                self.add_file(f"{rel_dir}/ticket_{k}.json", raw, "json", [self.unit("/tickets/0", ent())])

    def clean_files(self, rel_dir):
        t = "Hypertension protocol: Tab Amlodipine 5 mg 0-0-1. Dr. Ishita Banerjee is the nodal officer. Ward 4 (Medicine).\n"
        self.add_file(f"{rel_dir}/protocol.txt", t.encode(), "text",
                      [self.unit("doc", [], [("Tab Amlodipine 5 mg 0-0-1", "medication", "1-0-1"),
                                             ("Dr. Ishita Banerjee", "doctor", "doctor"), ("Ward 4 (Medicine)", "ward", "hospital-ward")])])

    def build(self, n=24):
        people = [self.person(i) for i in range(n)]
        h1 = ["Hosp ID", "Pt. Full Name", "Sex", "Yrs", "Dt of Birth", "Father/Husband", "Home Address", "Gram/Mohalla",
              "Postal Code", "Contact#", "Aadhar #"]
        h2 = ["Case No", "Beneficiary", "Gender", "Age (y)", "D.O.B.", "Guardian", "Residence", "Locality/Village",
              "PIN", "Mobile (primary)", "UID"]
        self.registration_csv("registration/unit_a_patients.csv", people[:8], h1)
        self.registration_csv("registration/unit_b_patients.tsv", people[8:16], h2, delimiter="\t")
        self.json_visits("opd/encounters_a.json", people[:6])
        self.json_visits("opd/encounters_b.json", people[6:12])
        for i, p in enumerate(people[:14]):
            self.discharge_text(f"discharge/summary_{i:03d}.txt", p, "en")
        for i, p in enumerate(people[:14]):
            self.discharge_text(f"discharge/hindi_{i:03d}.txt", p, "hi")
        for p in people[12:20]:
            self.named_file("lab", p)
        self.canary_files("misc")
        self.clean_files("clean")
        return people

    def write(self, out: Path, seed: str):
        inp = out / "input"
        for rel, f in self.files.items():
            (inp / rel).parent.mkdir(parents=True, exist_ok=True)
            (inp / rel).write_bytes(f["raw"])
        files = {}
        for rel, f in self.files.items():
            body = {k: v for k, v in f.items() if k != "raw"}
            body["units"] = {u["loc"]: u for u in f["units"]}   # truth schema: dict keyed by locator
            files[rel] = body
        truth = dict(schema="raksha-truth/1", generator_version="chaos-1", seed=seed, profile="chaos", chaos=True,
                     files=files, patients={}, traps={}, linkability={}, canaries=[])
        (out / "truth").mkdir(parents=True, exist_ok=True)
        (out / "truth" / "truth.json").write_text(json.dumps(truth, ensure_ascii=False), encoding="utf-8")
        return len(files)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--n", type=int, default=24)
    a = ap.parse_args()
    g = Gen(a.seed)
    g.build(a.n)
    n = g.write(Path(a.out), a.seed)
    print(f"wrote {n} files for seed {a.seed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
