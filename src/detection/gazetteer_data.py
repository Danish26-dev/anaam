"""General reference vocabulary (public knowledge, not practice data).

These lists support context rules and column classification. They are deliberately NOT
the main way names are found: hidden data uses new names, and canaries are in no list.
Do not add names copied from the practice dataset here.
"""
from __future__ import annotations

GIVEN_NAMES = """
aarav aarti aakash aamir aaron abdul abhay abhinav abhishek abid adarsh adil aditi aditya afroz
afsana ahmad ahmed aishwarya ajay ajit akash akbar akhil akhilesh akram alam alka alok altaf
aman amar amarjeet amir amit amita amitabh amrita amrit anand anil anita anjali anju ankit
ankita anmol anoop anshu anuj anupam anuradha anwar archana arif arjun arshad arun aruna
arvind asha ashish ashok ashraf asif aslam asma atul avinash ayaan ayesha azad azhar babita
babulal badri bala balram baldev balwant bhagwan bharat bharti bhavna bhupendra bilal brij
brijesh chanchal chanda chandan chandni chandra chetan chhaya chitra daljeet danish darshan
deepa deepak deepika dev devendra dhananjay dharmendra dheeraj dilip dinesh divya durga
faisal faiz farah farhan farida farooq fatima firoz ganesh gaurav gayatri geeta girish gita
gopal govind gulshan gurmeet gurpreet hamid hanif hari harish harjeet harpreet hasan hemant
hema hina hitesh hussain ibrahim imran indu iqbal irfan ishaan isha jagdish jai jameel
jaspreet jaswinder javed jaya jitendra john joseph jyoti kabir kailash kajal kalpana kamal
kamala kamla kanchan kapil karan karishma kavita kavya khalid kiran kishan kishore komal
krishna kuldeep kulwant kusum lakshmi lalit lata laxmi madhu madhuri mahendra mahesh
mamta manish manju manoj manpreet mary meena meera mohan mohammad mohammed mohd mona mukesh
munni murli nadeem nafees nagendra nanda narendra naresh nasir nasreen naveen nazia neelam
neeraj neetu neha nidhi nikhil nirmala nisha nitin noor om pankaj parveen pawan peter pooja
poonam prabhu pradeep prakash pramod prashant praveen prem prema preeti priya priyanka
pushpa radha rafiq rahim rahul raj rajan rajendra rajesh rajiv rajni rakesh ram rama ramesh
rani rashid rashmi ravi reena rehana rekha renu rina ritu rizwan rohit roshan rubina
rukhsana ruksana sabina sachin sadhana sagar sahil sajid sakshi salim salma salman sameer
sandeep sangeeta sanjay sanjeev santosh sapna sarita satish savita seema shabana shahid
shakeel shalini shankar shanti sharda sheela shilpa shiv shobha shoaib shyam shweta simran
sita sneha sohail sonia sudha sudhir sujata sukhwinder suman sumit sunil sunita suraj
suresh sushil sushma swati tabassum tara tariq tarun thomas uday uma umesh urmila usha
usman vandana varsha vidya vijay vikas vikram vimal vinay vinod vipin vishal vivek wasim
yasmin yogesh yusuf zainab zaheer zarina zubair
""".split()

SURNAMES = """
agarwal agrawal ahmed ali ansari arora awasthi bajpai bansal bhatt bhatnagar chaturvedi
chaudhary chaudhari choudhary chauhan chopra das dixit dubey dwivedi gautam gill gupta
hashmi jain jaiswal joshi kapoor kashyap khan khanna kushwaha lal lodhi malik maurya mehta
mirza mishra nishad pal pandey patel pathak paswan prajapati qureshi rai rajput rana
rathore rawat rizvi sahu saxena shah sharma sheikh shukla siddiqui sinha soni srivastava
thakur tiwari tripathi trivedi upadhyay verma yadav zaidi naqvi masih sandhu sidhu dhillon
bedi grewal kohli kaur singh kumar kumari devi bano begum khatoon khatun
""".split()

# Tokens that are part of names but do not identify anyone alone (scorer's generic tokens).
GENERIC_NAME_TOKENS = frozenset("""
md mohd mohammad mohammed muhammad kumar kumari devi singh kaur bano begum khatoon khatun
bibi lal ji jee sahab saheb sahib behenji bahenji didi babu bhai amma
""".split())

# Words that follow a name ("Asha ji", "Shahid sahab").
POSTFIX_HONORIFICS = frozenset("""
ji jee sahab saheb sahib sab babu bhai bhaiya bhaiyya didi behen behan behenji bahenji
bhabhi bhabhiji amma ammi abba chacha chachi chachu mama mami mausi bua dada dadi nana
nani baba madam aunty aunti uncle kaka kaki tai tau begum bibi khala
""".split())
POSTFIX_HONORIFICS_DEVA = frozenset("""
जी साहब साहेब भाई भैया दीदी बहन बहनजी भाभी अम्मा बाबू चाचा चाची मामा मौसी दादा दादी नाना नानी बाबा
""".split())

# Kin words that the scorer treats as part of a sender's name ("Kamal Bhaiya:").
KIN_TERMS = frozenset("""
bhaiya bhaiyya didi bhabhi chacha chachi chachu mama mami mausi bua dada dadi nana nani
kaka kaki tai tau beta beti bitiya jiju
""".split())

# Words before a name ("Smt Kamla", "श्री राम").
PREFIX_TITLES = frozenset("""
mr mrs ms miss shri sri shree smt shrimati sushri kumari km master late sh janab mohtarma
sardar baby
""".split())
PREFIX_TITLES_DEVA = frozenset("श्री श्रीमती सुश्री कुमारी स्व जनाब".split())

# Tokens that can precede a postfix honorific without being a name.
NOT_NAME_BEFORE_HONORIFIC = frozenset("""
doctor dr sister nurse madam sir bhai didi mata pita guru pandit maulana inspector master
ward bed patient mareez marij babu baba nana nani dada dadi
""".split())

# Hinglish postpositions that follow a name ("Anita ka BP").
HINGLISH_POSTPOSITIONS = frozenset("ka ki ke ko ne se par".split())
HINDI_POSTPOSITIONS = frozenset("का की के को ने से पर".split())

MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3, "apr": 4,
    "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7, "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9, "oct": 10, "october": 10, "nov": 11,
    "november": 11, "dec": 12, "december": 12,
}
MONTHS_DEVA = {
    "जनवरी": 1, "फ़रवरी": 2, "फरवरी": 2, "मार्च": 3, "अप्रैल": 4, "मई": 5, "जून": 6,
    "जुलाई": 7, "अगस्त": 8, "सितंबर": 9, "सितम्बर": 9, "अक्टूबर": 10, "अक्तूबर": 10,
    "नवंबर": 11, "नवम्बर": 11, "दिसंबर": 12, "दिसम्बर": 12,
}

# Uttar Pradesh districts (public administrative names).
UP_DISTRICTS = [
    "Agra", "Aligarh", "Ambedkar Nagar", "Amethi", "Amroha", "Auraiya", "Ayodhya", "Faizabad",
    "Azamgarh", "Baghpat", "Bahraich", "Ballia", "Balrampur", "Banda", "Barabanki", "Bareilly",
    "Basti", "Bhadohi", "Bijnor", "Budaun", "Bulandshahr", "Chandauli", "Chitrakoot", "Deoria",
    "Etah", "Etawah", "Farrukhabad", "Fatehpur", "Firozabad", "Gautam Buddh Nagar", "Ghaziabad",
    "Ghazipur", "Gonda", "Gorakhpur", "Hamirpur", "Hapur", "Hardoi", "Hathras", "Jalaun",
    "Jaunpur", "Jhansi", "Kannauj", "Kanpur Dehat", "Kanpur Nagar", "Kanpur", "Kasganj",
    "Kaushambi", "Lakhimpur Kheri", "Kheri", "Kushinagar", "Lalitpur", "Lucknow", "Maharajganj",
    "Mahoba", "Mainpuri", "Mathura", "Mau", "Meerut", "Mirzapur", "Moradabad", "Muzaffarnagar",
    "Pilibhit", "Pratapgarh", "Prayagraj", "Allahabad", "Rae Bareli", "Raebareli", "Rampur",
    "Saharanpur", "Sambhal", "Sant Kabir Nagar", "Shahjahanpur", "Shamli", "Shravasti",
    "Siddharthnagar", "Sitapur", "Sonbhadra", "Sultanpur", "Unnao", "Varanasi", "Noida",
]
STATES = ["Uttar Pradesh", "UP", "Bihar", "Delhi", "Madhya Pradesh", "Uttarakhand", "India"]

# Capitalized English and Hinglish words common in notes that are never person names.
COMMON_WORDS = frozenset("""
a about above abhi admission admitted adv advice advised after again age aged all also am an
and any appointment are as at attachment attendant attended author ayi aaya b bad bed bedside
before behind being below bill billing birth blood bola both breakfast bp bundle by c call
called camp care case cell centre center certificate chart check checked city claim clerk
clinic code collected complaint complaints condition consent consultant contact continue
course current daily data date day days dear department details diagnosis diet discharge
discharged district div doctor document dose dr due duty e each emergency en english entry
evening every exam export exported f family female fever file final first follow followed
following for form forwarded free from full general given good govt h had has have he health
her here high him his history home hospital house i id if ii in inform informed initial
inpatient ipd is it its kal ka ki ko ke lab last left letter lena list lo log male medical
medicine medicines medications mobile morning mr mrs ms my n name nahi naam near new next
night no none normal not note notes nurse nursing o of off old on one only op opd or order
other our out outpatient page paid pain patient patients pending per phone please plan pm
post present presenting primary procedure ref referral referred registration remarks report
reported result results review reviewed right room round routine rx s sample
section see seen sent service sex she since sir sister so son staff stable start status
summary surgery t take taken test tests the their them then there this time to today
total treated treatment tue unit up urgent use v very visit visited visitor visits vitals w
ward was we week weeks well were wife with x yes you your
hai hain ho gaya gayi gaye raat neend theek se li diya diye bhi mein main aur kya kab koi
kuch problem karo karna lena hai to toh ab abhi aaj kal subah shaam din saal mahina
monday tuesday wednesday thursday friday saturday sunday
january february march april june july august september october november december
""".split())

HINDI_COMMON_WORDS = frozenset("""
मरीज़ मरीज रोगी नाम पता पिता पति माता आयु उम्र वर्ष साल दिन महीना ग्राम गाँव गांव तहसील जिला ज़िला
मोबाइल फ़ोन फोन तारीख भर्ती छुट्टी निदान सारांश डिस्चार्ज पर्चा ओपीडी मकान नं पंजीकरण सं आईपीडी
पेशाब संक्रमण दवा दवाई जांच जाँच खून शुगर बुखार दर्द खांसी उल्टी दस्त कमजोरी महिला पुरुष है हैं था थी
को का की के ने से में पर और या तथा भी नहीं हाँ जी डॉ डॉक्टर अस्पताल वार्ड बेड बिस्तर इलाज सलाह
पुत्र पुत्री पत्नी सुपुत्र सुपुत्री धर्मपत्नी अभिभावक परिजन मोहल्ला पास पीछे सामने बगल
""".split())
