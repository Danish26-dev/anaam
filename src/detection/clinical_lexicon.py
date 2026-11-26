"""D2: general clinical vocabulary (public medical knowledge, not practice data)."""
from __future__ import annotations

DRUGS = frozenset("""
paracetamol acetaminophen dolo crocin calpol combiflam ibuprofen diclofenac aceclofenac
naproxen aspirin ecosprin clopidogrel clopitab atorvastatin atorva rosuvastatin rosuvas
amlodipine amlokind telmisartan telma losartan ramipril enalapril metoprolol atenolol
bisoprolol carvedilol furosemide lasix torsemide spironolactone aldactone hydrochlorothiazide
chlorthalidone nifedipine digoxin isosorbide nitroglycerin warfarin heparin enoxaparin
metformin glycomet glimepiride gliclazide sitagliptin januvia vildagliptin teneligliptin
dapagliflozin empagliflozin insulin glargine lispro aspart pioglitazone voglibose
levothyroxine thyronorm eltroxin carbimazole methimazole hydrocortisone prednisolone
methylprednisolone dexamethasone betamethasone fludrocortisone budesonide budecort
salbutamol asthalin levosalbutamol ipratropium duolin formoterol salmeterol tiotropium
montelukast montair deriphyllin theophylline doxofylline cetirizine cetzine levocetirizine
fexofenadine allegra chlorpheniramine amoxicillin augmentin clavulanate ampicillin
azithromycin azithral clarithromycin erythromycin doxycycline tetracycline ciprofloxacin
ciplox ofloxacin oflox levofloxacin norfloxacin norflox moxifloxacin ceftriaxone cefixime
taxim zifi cefuroxime cefpodoxime cefotaxime ceftazidime cefoperazone sulbactam piperacillin
tazobactam meropenem imipenem vancomycin linezolid gentamicin amikacin metronidazole
metrogyl flagyl tinidazole nitrofurantoin cotrimoxazole septran rifampicin isoniazid
pyrazinamide ethambutol artesunate artemether lumefantrine chloroquine primaquine quinine
fluconazole itraconazole albendazole ivermectin acyclovir oseltamivir pantoprazole pan
pantop omeprazole rabeprazole esomeprazole ranitidine rantac famotidine domperidone
domstal ondansetron ondem emeset metoclopramide sucralfate lactulose bisacodyl ors electral
loperamide racecadotril dicyclomine cyclopam drotaverine drotin mefenamic meftal tramadol
morphine pregabalin gabapentin amitriptyline sertraline escitalopram fluoxetine alprazolam
clonazepam lorazepam diazepam phenytoin levetiracetam valproate carbamazepine levodopa
carbidopa ropinirole pramipexole donepezil haloperidol olanzapine risperidone quetiapine
ferrous folic iron calcium shelcal vitamin becosules zincovit limcee dexorange cyanocobalamin
methylcobalamin multivitamin zinc potassium sodium bicarbonate magnesium tamsulosin
finasteride sildenafil oxytocin misoprostol progesterone estradiol clomiphene allopurinol
febuxostat colchicine hydroxychloroquine methotrexate sulfasalazine azathioprine tacrolimus
mycophenolate cyclosporine penicillamine trientine zinc acetate atropine adrenaline
noradrenaline dopamine dobutamine mannitol albumin dextrose saline ringer lignocaine
lidocaine bupivacaine propofol ketamine midazolam fentanyl neostigmine glycopyrrolate
salbutamol inhaler sachet sulphate sulfate acid carbonate hydrochloride
""".split())

DOSAGE_FORMS = frozenset("""
tab tabs tablet tablets cap caps capsule capsules inj injection syp syrup susp suspension
inh inhaler sachet drop drops oint ointment cream gel lotion neb nebulization supp
suppository pwd powder spray patch iv im sc po
""".split())

LAB_TESTS = [
    "Haemoglobin", "Hemoglobin", "Hb", "HbA1c", "Random Blood Sugar", "Fasting Blood Sugar",
    "Post Prandial Blood Sugar", "RBS", "FBS", "PPBS", "Blood Sugar", "Serum Creatinine",
    "Creatinine", "Blood Urea", "Urea", "BUN", "Serum Sodium", "Sodium", "Serum Potassium",
    "Potassium", "Chloride", "Serum Calcium", "Calcium", "TSH", "T3", "T4", "Free T4",
    "Platelet Count", "Platelets", "Total WBC Count", "WBC", "TLC", "DLC", "RBC", "ESR", "CRP",
    "SGPT", "SGOT", "ALT", "AST", "ALP", "Serum Bilirubin", "Bilirubin", "Total Bilirubin",
    "Albumin", "Total Protein", "Cholesterol", "Total Cholesterol", "Triglycerides", "HDL",
    "LDL", "VLDL", "Uric Acid", "INR", "PT", "aPTT", "Haematocrit", "Hematocrit", "PCV", "MCV",
    "MCH", "MCHC", "Ferritin", "Vitamin D", "Vitamin B12", "Troponin", "CPK", "LDH", "Amylase",
    "Lipase", "PSA", "NS1", "Dengue NS1", "Widal", "Malaria", "HIV", "HBsAg", "Urine Albumin",
    "Urine Sugar", "Serum Ceruloplasmin", "Ceruloplasmin", "Cortisol", "Serum Cortisol",
]

LAB_UNITS = [
    "g/dL", "g/dl", "gm/dL", "gm/dl", "mg/dL", "mg/dl", "mmol/L", "mmol/l", "mEq/L", "mEq/l",
    "mIU/L", "mIU/l", "mIU/mL", "uIU/mL", "µIU/mL", "IU/L", "U/L", "IU/mL", "ng/mL", "ng/ml",
    "pg/mL", "pg/ml", "ug/dL", "µg/dL", "mcg/dL", "/uL", "/µL", "/ul", "/cumm", "cells/cumm",
    "lakh/cumm", "x10^3/uL", "x10^9/L", "%", "fL", "fl", "pg", "mm/hr", "sec", "seconds",
]

DOSE_UNITS = ["mg", "mcg", "µg", "ug", "g", "gm", "kg", "ml", "mL", "IU", "iu", "units", "unit",
              "U", "%", "puffs", "puff", "drops", "sachet", "sachets", "tab", "tabs", "cc", "L"]

FREQUENCY_WORDS = ["OD", "BD", "BID", "TDS", "TID", "QID", "QDS", "HS", "SOS", "PRN", "STAT",
                   "AC", "PC", "QHS", "Q4H", "Q6H", "Q8H", "Q12H", "OW", "EOD"]

DISEASES = [
    "hypertension", "essential hypertension", "diabetes", "diabetes mellitus", "type 2 diabetes",
    "dm", "dm2", "t2dm", "htn", "cad", "ihd", "copd", "asthma", "tb", "tuberculosis",
    "pulmonary tuberculosis", "typhoid", "typhoid fever", "enteric fever", "dengue",
    "dengue fever", "malaria", "anaemia", "anemia", "hypothyroidism", "hyperthyroidism",
    "uti", "urinary tract infection", "pneumonia", "gastroenteritis", "acute gastroenteritis",
    "jaundice", "hepatitis", "cirrhosis", "ckd", "chronic kidney disease", "aki", "stroke",
    "epilepsy", "seizure", "migraine", "arthritis", "osteoarthritis", "rheumatoid arthritis",
    "cataract", "hernia", "inguinal hernia", "appendicitis", "cholecystitis", "cholelithiasis",
    "pancreatitis", "sepsis", "covid", "covid-19", "influenza", "bronchitis", "sinusitis",
    "pharyngitis", "tonsillitis", "otitis media", "conjunctivitis", "dermatitis", "scabies",
    "psoriasis", "obesity", "dyslipidemia", "heart failure", "angina", "myocardial infarction",
    "atrial fibrillation", "parkinsonism", "dementia", "depression", "anxiety", "schizophrenia",
    "infection", "fever", "viral fever", "cellulitis", "abscess", "fracture", "burns",
    "pre-eclampsia", "eclampsia", "pregnancy", "ectopic pregnancy", "leprosy", "filariasis",
    "kala azar", "chikungunya", "leptospirosis", "scrub typhus", "encephalitis", "meningitis",
    "renal calculus", "kidney stone", "bph", "glaucoma", "otitis", "gout", "lupus",
]

EPONYM_HEADS = ["disease", "syndrome", "palsy", "sarcoma", "lymphoma", "phenomenon", "sign",
                "test", "anaemia", "anemia", "ulcer", "encephalopathy", "disorder", "tumour",
                "tumor", "fracture", "procedure", "chorea", "crisis", "dementia", "thyroiditis",
                "contracture", "operation", "triad", "law"]

SYMPTOMS = frozenset("""
fever cough pain ache aches breathlessness dyspnoea dyspnea vomiting nausea diarrhoea
diarrhea loose motions motion stools headache giddiness dizziness weakness fatigue burning
swelling bleeding chest abdominal abdomen pain-abdomen body bodyache cold sore throat
palpitations palpitation rash itching constipation dysuria micturition urination
tingling numbness tremors tremor seizures fits syncope fainting jaundice yellowness
wheezing chills rigors sweating anorexia weight loss insomnia bukhar khansi dard ulti dast
chakkar kamzori sujan breath expectoration haemoptysis hematuria haematuria vomit loss
irritability difficulty pus discharge injury fall trauma bite burn
""".split())

PROCEDURES = [
    "appendicectomy", "appendectomy", "caesarean section", "c-section", "lscs",
    "cataract surgery", "phacoemulsification", "laparoscopic cholecystectomy",
    "cholecystectomy", "hernia repair", "inguinal hernia repair", "hernioplasty",
    "haemodialysis", "hemodialysis", "dialysis", "angioplasty", "angiography", "cabg",
    "biopsy", "endoscopy", "colonoscopy", "bronchoscopy", "whipple procedure",
    "pancreaticoduodenectomy", "deep brain stimulation", "hysterectomy", "tonsillectomy",
    "circumcision", "debridement", "skin grafting", "orif", "joint replacement",
    "knee replacement", "hip replacement", "thyroidectomy", "mastectomy", "lumbar puncture",
    "blood transfusion", "intubation", "tracheostomy", "chest tube insertion", "d&c",
    "normal delivery", "episiotomy", "surgery", "operation",
]

DEPARTMENTS = [
    "Medicine", "General Medicine", "Surgery", "General Surgery", "Paediatrics", "Pediatrics",
    "Gynaecology", "Gynecology", "Obstetrics", "Obstetrics and Gynaecology", "OBG",
    "Orthopaedics", "Orthopedics", "Ophthalmology", "ENT", "Dermatology", "Psychiatry",
    "Cardiology", "Neurology", "Nephrology", "Urology", "Gastroenterology", "Pulmonology",
    "Pulmonary Medicine", "Respiratory Medicine", "Oncology", "Endocrinology", "Radiology",
    "Pathology", "Anaesthesia", "Anesthesiology", "Emergency", "Casualty", "ICU", "NICU",
    "PICU", "CCU", "Dental", "Physiotherapy", "Neurosurgery", "Plastic Surgery",
    "Medical Oncology", "Rheumatology", "Geriatrics",
]

DEGREES = ["MBBS", "MD", "MS", "DM", "MCh", "DNB", "BAMS", "BUMS", "BHMS", "FRCS", "MRCP",
           "DGO", "DCH", "DA", "DO", "PhD"]

ORG_SUFFIXES = ["Hospital", "Hospitals", "Clinic", "Clinics", "Nursing Home", "Medical College",
                "Medical Centre", "Medical Center", "Health Centre", "Health Center",
                "Diagnostics", "Diagnostic Centre", "Diagnostic Center", "Pathology", "Path Lab",
                "Labs", "Lab", "Laboratory", "Laboratories", "Sadan", "Bhawan", "Trust",
                "Foundation", "Institute", "Polyclinic", "Dispensary", "PHC", "CHC", "Kendra",
                "Aushadhalaya", "Chikitsalaya", "Pharmacy", "Medicals", "Imaging"]
ORG_WORDS = frozenset("""
multispeciality multispecialty superspeciality charitable district government govt general
community primary seva city care life lifeline apollo fortis max medanta civil railway
military esic aiims state national memorial mission municipal
""".split())

CONTEXT_PHRASES = ["ASHA worker", "ASHA workers", "ASHA didi", "ASHA sahyogini",
                   "Anganwadi worker", "ANM", "ICD-10", "ICD 10", "LOINC", "SNOMED"]
