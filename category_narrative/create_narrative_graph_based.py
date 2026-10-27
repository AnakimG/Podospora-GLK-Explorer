import dspy
import os
import csv
from pathlib import Path
import json
from collections import defaultdict
from dotenv import load_dotenv

# ----------------
# Configuration
# ----------------
load_dotenv()

lm = dspy.LM(
    model="openrouter/qwen/qwen3.5-9b",  # "openrouter/google/gemma-3-4b-it",# "openrouter/qwen/qwen-2.5-7b-instruct",
    api_key=os.getenv("OPENROUTER_API_KEY"),
    api_base="https://openrouter.ai/api/v1",
    temperature=0.7,
    cache=False,
)
dspy.configure(lm=lm)

# ----------------
# Signature
# ----------------


class Summarize(dspy.Signature):
    """Summarize to few phrases abstract of scientif articles."""

    abstract: str = dspy.InputField(desc="The abstract to summarize.")
    summarized_abstract: str = dspy.OutputField(
        desc="The summarized abstract containing the main information from the original abstract."
    )


class SummarizeCategory(dspy.Signature):
    """Write a short scientific description of a category of articles based on their summarized abstracts.
    The description should explain the main research topic, biological processes, mechanisms, or phenomena
    covered by the category. Write a coherent short paragraph, not a list of keywords."""

    category_name: str = dspy.InputField(desc="The name of the category to summarize.")
    summarized_abstracts: list[str] = dspy.InputField(
        desc="A list of summarized abstracts from articles belonging to the category."
    )

    summarized_category: str = dspy.OutputField(
        desc="A concise scientific description of the category, synthesizing the main topics and biological phenomena shared across the articles. Write 1–3 sentences in prose, not keywords or a list."
    )


# ----------------
# Agent
# ----------------
SUMMARIZER = dspy.Predict(signature=Summarize)

CAT_SUMMARIZER = dspy.ChainOfThought(signature=SummarizeCategory)

# ---------------------------------------
# Fonctions qui va chercher les abstracts 
#----------------------------------------
categories = {
    "1/7/8 - Life Cycle - Reproduction and Morphogenesis ",
    "2 - Genomics and Genome Architecture ",
    "3/4 - Mitochondria - Energy Metabolism and Aging ",
    "5/6 - Signal Transduction - Regulation and Stress Response ",
    "9 - Vegetative Incompatibility and Cell Death ",
    "10 - Comparative and Evolutionary Biology ",
    "11 - Host–Pathogen and Symbiotic Interactions ",
    "12 - Biotechnology and Applied Research ",
}

def load_category_from_csv(csv_path:str)->dict:

    with open(csv_path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        categories = {}

        for row in reader:
            doi = row.get("doi",'').strip()
            category = row.get("category",'')

            categories[doi]=category

        return categories

categories = load_category_from_csv("/Users/anakim.gualdoni/Documents/Podospora-GLK-explorer/category_narrative/category.csv")

paper_objects_dir = Path(
    "/Users/anakim.gualdoni/Documents/podospora-anserina-graph/paper_objects"
)

abstracts_by_category = defaultdict(list)

for doi, category in categories.items():

    safe_doi = doi.replace("/", "_")
    json_path = paper_objects_dir / f"{safe_doi}.json"

    if not json_path.exists():
        print(f"⚠️ Fichier introuvable : {safe_doi}.json")
        continue

    with open(json_path, "r", encoding="utf-8") as f:
        paper = json.load(f)

    abstract = paper.get("abstract")

    if abstract:
        abstracts_by_category[category].append({
            "doi": doi,
            "abstract": abstract
        })

print(abstracts_by_category)

## Création des summarized abstracts par catégorie et écriture dans un fichier JSON 

summarized_abstracts_by_category = {}

for category in abstracts_by_category.keys():
    print(f"Processing category {category}\n")

    summarized_abstracts = []

    for paper in abstracts_by_category[category]:
        print(f"Processing abstract for DOI {paper['doi']}\n")

        summary = SUMMARIZER(
            abstract=paper["abstract"]
        ).summarized_abstract

        summarized_abstracts.append({
            "doi": paper["doi"],
            "summarized_abstract": summary
        })

    summarized_abstracts_by_category[category] = summarized_abstracts

# Écriture dans le fichier JSON
with open("/Users/anakim.gualdoni/Documents/Podospora-GLK-explorer/category_narrative/summarized_abstracts_by_category.json", "w", encoding="utf-8") as f:
    json.dump(
        summarized_abstracts_by_category,
        f,
        ensure_ascii=False,
        indent=2
    )
        

# summarized_abstracts = ['The HET-s prion converts soluble HET-S into an integral membrane protein that destabilizes lipid membranes. Structural changes expose a transmembrane segment, causing oligomerization and membrane leakage. This mechanism resembles pore-forming toxins and induces cell death.', 'In Podospora anserina, the NLR NWD2 uses an N-terminal β-solenoid motif to induce [Het-s] prion formation and activate the HET-S pore-forming protein. This mechanism triggers programmed cell death, demonstrating the importance of amyloid and prion-like signaling in fungal immunity.', 'In the fungus Podospora anserina, allorecognition loci define reproductively isolated groups through pleiotropic effects on sexual compatibility. Antagonistic interactions between unlinked het-r and het-v genes under balancing selection drive the origin and coexistence of these groups.', 'This study examines heterokaryon incompatibility in filamentous fungi controlled by het/vic loci. It focuses on the [Het-s] prion in Podospora anserina, detailing its discovery, unique architecture, and functions in meiotic drive and programmed cell death.', 'This study analyzes transcriptional changes during heterokaryon incompatibility in *Podospora anserina*, revealing massive gene reprogramming with specific domain enrichment and proteolytic activity. The response resembles host-pathogen interactions and shows significant overlap with *Neurospora crassa*.', 'Researchers propose a conserved fungal signal transduction mechanism where STAND proteins template amyloid folds in effector proteins to induce toxicity, suggesting evolutionary conservation of amyloid-based signaling across species.', 'This study utilizes Self-Consistent Path Sampling (SCPS) simulations to investigate prion replication mechanisms, overcoming limitations of standard molecular dynamics. Results from the HET-s prion domain suggest that prion propagation across evolutionarily distant species shares common templating features.', 'The [Het-s] prion in Podospora anserina induces cell death by triggering conformational changes in Het-S via co-amyloidogenesis. This exposes transmembrane helices that form pores, leading to cytosolic leakage. These findings expand the functional repertoire of amyloids and suggest parallels to pathological toxicity.', 'This study characterizes gasdermin-based cell death in the fungus *Podospora anserina*, revealing that HET-Q1 activity is controlled by proteolytic cleavage via the HET-Q2 protease. Genomic analysis shows gasdermin genes cluster with protease-encoding genes, establishing evolutionary parallels between fungal and mammalian gasdermin-dependent cell death pathways.']
summarized_category = {}

for category, summarized_abstracts in summarized_abstracts_by_category.items():
    print(f"Processing category {category}\n")
    result = CAT_SUMMARIZER(
        category_name=category,
        summarized_abstracts=[item["summarized_abstract"] for item in summarized_abstracts],
    )
    summarized_category[category] = result.summarized_category

with open("/Users/anakim.gualdoni/Documents/Podospora-GLK-explorer/category_narrative/summarized_category.json", "w", encoding="utf-8") as f:
    json.dump(
        summarized_category,
        f,
        ensure_ascii=False,
        indent=2
    )

dspy.inspect_history(n=1)
