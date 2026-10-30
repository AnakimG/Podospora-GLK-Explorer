import json

import streamlit as st
from dotenv import load_dotenv
from neo4j import GraphDatabase, Result, RoutingControl
from pathlib import Path

from summarizer import generate_summary

load_dotenv()


uri = st.secrets["NEO4J_URI_AURA"]
username = st.secrets["NEO4J_USERNAME_AURA"]
password = st.secrets["NEO4J_PASSWORD_AURA"]
database = st.secrets["NEO4J_DATABASE_AURA"]



category_colors = {
    "1/7/8 - Life Cycle - Reproduction and Morphogenesis ": "#A78BFA",  # violet
    "2 - Genomics and Genome Architecture ": "#FBD45D",  # jaune
    "3/4 - Mitochondria - Energy Metabolism and Aging ": "#4F86F7",  # bleu
    "5/6 - Signal Transduction - Regulation and Stress Response ": "#5FDCC4",  # turquoise
    "9 - Vegetative Incompatibility and Cell Death ": "#F5A65B",  # orange
    "10 - Comparative and Evolutionary Biology ": "#EE6F6F",  # corail
    "11 - Host–Pathogen and Symbiotic Interactions ": "#7BD389",  # vert
    "12 - Biotechnology and Applied Research ": "#F291CE",  # rose
}

category_key = {
    "category_1": "1/7/8 - Life Cycle - Reproduction and Morphogenesis ",
    "category_2": "2 - Genomics and Genome Architecture ",
    "category_3": "3/4 - Mitochondria - Energy Metabolism and Aging ",
    "category_4": "5/6 - Signal Transduction - Regulation and Stress Response ",
    "category_5": "9 - Vegetative Incompatibility and Cell Death ",
    "category_6": "10 - Comparative and Evolutionary Biology ",
    "category_7": "11 - Host–Pathogen and Symbiotic Interactions ",
    "category_8": "12 - Biotechnology and Applied Research ",
}

categories_name = {
    "1/7/8 - Life Cycle - Reproduction and Morphogenesis ": "Life Cycle - Reproduction and Morphogenesis",
    "2 - Genomics and Genome Architecture ": "Genomics and Genome Architecture",
    "3/4 - Mitochondria - Energy Metabolism and Aging ": "Mitochondria - Energy Metabolism and Aging",
    "5/6 - Signal Transduction - Regulation and Stress Response ": "Signal Transduction - Regulation and Stress Response",
    "9 - Vegetative Incompatibility and Cell Death ": "Vegetative Incompatibility and Cell Death",
    "10 - Comparative and Evolutionary Biology ": "Comparative and Evolutionary Biology",
    "11 - Host–Pathogen and Symbiotic Interactions ": "Host–Pathogen and Symbiotic Interactions",
    "12 - Biotechnology and Applied Research ": "Biotechnology and Applied Research",
}


@st.cache_resource
def get_driver():
    return GraphDatabase.driver(
        uri,
        auth=(username, password),
    )


driver = get_driver()

# ------------------------------------------------------------------------------------------------------------------------------------------------
#  Functions to interact with the Neo4j database
# ------------------------------------------------------------------------------------------------------------------------------------------------


@st.cache_data
def get_normalized_entities():
    """Fetch all normalized entities from the Neo4j database and return them as a list of strings."""

    query = """
    MATCH (n:NormalizedEntity)
    RETURN n.value AS value
    ORDER BY value"""

    with driver.session(database=database) as session:
        result = session.run(query)
        return [record["value"] for record in result]


@st.cache_data
def get_statements(entity_value):
    """Fetch statements associated with a given normalized entity value from the Neo4j database and return them as a list of dictionaries."""

    query = """
    MATCH (d:Document)
          -[:CONTAINS]->
          (s:Statement)
          -[:MENTIONS]->
          (e:Entity)
          -[:NORMALIZED_TO]->
          (n:NormalizedEntity {value: $value})

    RETURN DISTINCT
        s.value AS statement,
        d.title AS title,
        d.doi AS doi

    ORDER BY statement
    """

    with driver.session(database=database) as session:
        result = session.run(query, value=entity_value)

        return [
            {
                "statement": record["statement"],
                "title": record["title"],
                "doi": record["doi"],
            }
            for record in result
        ]


def get_entity_graph(entity_values, show_authors=False, document_ids=None):
    """Fetch the graph data for the given normalized entity values and document IDs from the Neo4j database."""

    if document_ids is None:
        document_ids = []

    if show_authors:
        query = """
        MATCH (d:Document)
              -[c:CONTAINS]->
              (s:Statement)
              -[m:MENTIONS]->
              (e:Entity)
              -[n:NORMALIZED_TO]->
              (ne:NormalizedEntity)

        WHERE ne.value IN $entity_values

        OPTIONAL MATCH (a:Author)-[w:WROTE]->(d)

        RETURN d, c, s, m, e, n, ne, a, w

        UNION

        MATCH (d:Document)
              -[c:CONTAINS]->
              (s:Statement)
              -[m:MENTIONS]->
              (e:Entity)
              -[n:NORMALIZED_TO]->
              (ne:NormalizedEntity)

        WHERE elementId(d) IN $document_ids

        OPTIONAL MATCH (a:Author)-[w:WROTE]->(d)

        RETURN d, c, s, m, e, n, ne, a, w
        """

    else:
        query = """
        MATCH (d:Document)
              -[c:CONTAINS]->
              (s:Statement)
              -[m:MENTIONS]->
              (e:Entity)
              -[n:NORMALIZED_TO]->
              (ne:NormalizedEntity)

        WHERE ne.value IN $entity_values

        RETURN d, c, s, m, e, n, ne

        UNION

        MATCH (d:Document)
              -[c:CONTAINS]->
              (s:Statement)
              -[m:MENTIONS]->
              (e:Entity)
              -[n:NORMALIZED_TO]->
              (ne:NormalizedEntity)

        WHERE elementId(d) IN $document_ids

        RETURN d, c, s, m, e, n, ne
        """

    return driver.execute_query(
        query,
        entity_values=entity_values,
        document_ids=document_ids,
        database_=database,
        routing_=RoutingControl.READ,
    )


def get_full_graph():
    """Fetch the entire graph data from the Neo4j database, including authors, documents, statements, entities, and normalized entities."""

    query = """
    MATCH (a:Author)-[w:WROTE]->(d:Document)-[c:CONTAINS]->(s:Statement)
          -[m:MENTIONS]->(e:Entity)
          -[n:NORMALIZED_TO]->(ne:NormalizedEntity)

    RETURN a, w, d, c, s, m, e, n, ne
    """

    return driver.execute_query(
        query,
        database_=database,
        routing_=RoutingControl.READ,
    )


def generate_cached_summary(normalized_entity, statements):
    """Generate a summary for the given normalized entity and its associated statements using the `generate_summary` function."""

    return generate_summary(normalized_entity, statements)


node_colors = {
    "Author": "#57c7e3",
    "Document": "#57c7e3",
    "Statement": "#aea18b",
    "Entity": "#e4afa4",
    "NormalizedEntity": "#B85C73",
}


@st.cache_data
def get_graph_stats(selected_category):
    """Fetch the counts of various node types in the Neo4j database, including documents, statements, entities, normalized entities, and authors."""

    if selected_category:
        query = """
        MATCH (d:Document {category: $selected_category})-[:CONTAINS]->(s:Statement)-[:MENTIONS]->(e:Entity)-[:NORMALIZED_TO]->(ne:NormalizedEntity)
        OPTIONAL MATCH (a:Author)-[:WROTE]->(d)
        RETURN count(DISTINCT d) AS documents_count,
               count(DISTINCT s) AS statements_count,
               count(DISTINCT e) AS entities_count,
               count(DISTINCT ne) AS normalized_entities_count,
               count(DISTINCT a) AS authors_count
        """
        with driver.session(database=database) as session:
            result = session.run(query, selected_category=selected_category).single()
            return {
                "documents": result["documents_count"],
                "statements": result["statements_count"],
                "entities": result["entities_count"],
                "normalized_entities": result["normalized_entities_count"],
                "authors": result["authors_count"],
            }

    else:
        queries = {
            "documents": "MATCH (n:Document) RETURN count(n) AS count",
            "statements": "MATCH (n:Statement) RETURN count(n) AS count",
            "entities": "MATCH (n:Entity) RETURN count(n) AS count",
            "normalized_entities": "MATCH (n:NormalizedEntity) RETURN count(n) AS count",
            "authors": "MATCH (n:Author) RETURN count(n) AS count",
        }

        stats = {}

        with driver.session(database=database) as session:
            for name, query in queries.items():
                stats[name] = session.run(query).single()["count"]

        return stats


def get_document_neighbors(document_id):
    """Fetch the neighboring nodes and relationships for a given document ID from the Neo4j database."""

    query = """
    MATCH (d:Document)-[c:CONTAINS]->(s:Statement)
          -[m:MENTIONS]->(e:Entity)
          -[n:NORMALIZED_TO]->(ne:NormalizedEntity)

    WHERE elementId(d) = $document_id

    RETURN d, c, s, m, e, n, ne
    """

    with driver.session(database=database) as session:
        result = session.run(
            query,
            document_id=document_id,
        )

        return result.to_eager_result()


def get_category_graph(category):
    """Fetch the graph data for a specific category from the Neo4j database, including authors,documents, statements, entities, and normalized entities associated with that category."""

    query = """
    MATCH (a:Author)-[w:WROTE]->(d:Document {category: $category})
    -[c:CONTAINS]->(s:Statement)
    -[m:MENTIONS]->(e:Entity)
    -[n:NORMALIZED_TO]->(ne:NormalizedEntity)
    
    RETURN a, w, d, c, s, m, e, n, ne"""

    with driver.session(database=database) as session:
        result = session.run(
            query,
            category=category,
        )

        return result.to_eager_result()


# ------------------------------------------------------------------------------------------------------------------------------------------------
# Functions to get category description and 10 most frequent normalized entities
# ------------------------------------------------------------------------------------------------------------------------------------------------

PROJECT_DIR = Path(__file__).resolve().parent

@st.cache_data
def get_category_description():
    """Load the category descriptions from a JSON file and return them as a dictionary."""

    category_file = PROJECT_DIR / "category_narrative" / "summarized_category.json"
    
    with open(
        category_file, "r", encoding="utf-8"
    ) as f:
        return json.load(f)

def get_top_normalized_entities(category, limit=10):
    """Fetch the top normalized entities for a given category from the Neo4j database, ranked by the number of associated documents."""

    query = """
    MATCH (d:Document {category: $category})
          -[:CONTAINS]->
          (:Statement)
          -[:MENTIONS]->
          (:Entity)
          -[:NORMALIZED_TO]->
          (n:NormalizedEntity)

    RETURN n.value AS normalized_entity, count(DISTINCT d) AS document_count
    ORDER BY document_count DESC
    LIMIT $limit
    """

    with driver.session(database=database) as session:
        result = session.run(query, category=category, limit=limit)

        return [
            {
                "normalized_entity": record["normalized_entity"],
                "document_count": record["document_count"],
            }
            for record in result
        ]

# ------------------------------------------------------------------------------------------------------------------------------------------------
# Functions to get co-occurring entities
# ------------------------------------------------------------------------------------------------------------------------------------------------


@st.cache_data
def get_entity_cooccurrences(entity_value):
    """Return normalized entities co-occurring with a given entity,
    ranked by the number of shared documents.
    """

    query = """
    MATCH (d:Document)
          -[:CONTAINS]->
          (:Statement)
          -[:MENTIONS]->
          (:Entity)
          -[:NORMALIZED_TO]->
          (n1:NormalizedEntity {value: $value})

    MATCH (d)
          -[:CONTAINS]->
          (:Statement)
          -[:MENTIONS]->
          (:Entity)
          -[:NORMALIZED_TO]->
          (n2:NormalizedEntity)

    WHERE n1.value <> n2.value

    RETURN
        n2.value AS entity,
        count(DISTINCT d) AS shared_articles

    ORDER BY shared_articles DESC, entity
    """

    with driver.session(database=database) as session:
        result = session.run(query, value=entity_value)

        return [
            {
                "entity": record["entity"],
                "shared_articles": record["shared_articles"],
            }
            for record in result
        ]


@st.cache_data
def get_shared_articles(entity1, entity2):
    """Return articles containing both normalized entities."""

    query = """
    MATCH (d:Document)
          -[:CONTAINS]->
          (:Statement)
          -[:MENTIONS]->
          (:Entity)
          -[:NORMALIZED_TO]->
          (n1:NormalizedEntity {value: $entity1})

    MATCH (d)
          -[:CONTAINS]->
          (:Statement)
          -[:MENTIONS]->
          (:Entity)
          -[:NORMALIZED_TO]->
          (n2:NormalizedEntity {value: $entity2})

    RETURN DISTINCT
        d.title AS title,
        d.doi AS doi

    ORDER BY title
    """

    with driver.session(database=database) as session:
        result = session.run(
            query,
            entity1=entity1,
            entity2=entity2,
        )

        return [
            {
                "title": record["title"],
                "doi": record["doi"],
            }
            for record in result
        ]


# ------------------------------------------------------------------------------------------------------------------------------------------------
# Functions to handle node click events in the graph visualization
# ------------------------------------------------------------------------------------------------------------------------------------------------


def on_node_click(node):
    """Handle the click event on a node in the graph visualization. Depending on the type of node clicked (Document or NormalizedEntity), it updates the session state to keep track of opened documents and normalized entities."""

    labels = node.properties.get("labels", [])
    if "Document" in labels:
        document_id = node.id

        if "opened_documents" not in st.session_state:
            st.session_state.opened_documents = []

        if document_id not in st.session_state.opened_documents:
            st.session_state.opened_documents.append(document_id)

    elif "NormalizedEntity" in labels:
        normalized_entity = node.properties.get("value")

        if normalized_entity:
            if "opened_normalized_entities" not in st.session_state:
                st.session_state.opened_normalized_entities = []

            if normalized_entity not in st.session_state.opened_normalized_entities:
                st.session_state.opened_normalized_entities.append(normalized_entity)

            st.session_state.pending_selected_entity = normalized_entity


# ------------------------------------------------------------------------------------------------------------------------------------------------
# Graph Styling
# ------------------------------------------------------------------------------------------------------------------------------------------------


def style_graph(VG):
    """
    Apply styling to the nodes in the graph visualization based on their labels and properties.
    This function sets the color, size, and caption for each node according to its type (Author, Document, Statement, Entity, NormalizedEntity) and specific properties like category or value.
    """

    for node in VG.nodes:
        labels = node.properties.get("labels", [])

        if "Author" in labels:
            node.color = node_colors["Author"]
            node.size = 35
            node.caption = node.properties.get("name", "")

        if "Document" in labels:
            category = node.properties.get("category")
            node.color = category_colors.get(category, "#E5E5E5")
            node.size = 50
            node.caption = node.properties.get("title", "")

        elif "Statement" in labels:
            node.color = node_colors["Statement"]
            node.size = 40
            node.caption = node.properties.get("value", "")

        elif "Entity" in labels:
            node.color = node_colors["Entity"]
            node.size = 30
            node.caption = node.properties.get("value", "")

        elif "NormalizedEntity" in labels:
            node.color = node_colors["NormalizedEntity"]
            node.size = 70
            node.caption = node.properties.get("value", "")


def style_full_graph(VG):
    """
    Apply styling to the nodes in the full graph visualization based on their labels and properties.
    """

    for node in VG.nodes:
        labels = node.properties.get("labels", [])

        if "Document" in labels:
            # coloration des catégories
            category = node.properties.get("category")
            node.color = category_colors.get(category, "#E5E5E5")
            node.size = 70
            node.caption = node.properties.get("title", "")

        elif "Statement" in labels:
            node.color = node_colors["Statement"]
            node.size = 40
            node.caption = node.properties.get("value", "")

        elif "Entity" in labels:
            node.color = node_colors["Entity"]
            node.size = 30
            node.caption = node.properties.get("value", "")

        elif "Author" in labels:
            node.color = node_colors["Author"]
            node.size = 30
            node.caption = node.properties.get("name", "")

        elif "NormalizedEntity" in labels:
            node.color = node_colors["NormalizedEntity"]
            node.size = 40
            node.caption = node.properties.get("value", "")
