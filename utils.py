import streamlit as st
from neo4j import GraphDatabase, Result, RoutingControl
import os
from dotenv import load_dotenv
from summarizer import generate_summary

load_dotenv()



uri = os.getenv("NEO4J_URI_AURA")
username = os.getenv("NEO4J_USERNAME_AURA")
password = os.getenv("NEO4J_PASSWORD_AURA")
database = os.getenv("NEO4J_DATABASE_AURA")

openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
@st.cache_resource
def get_driver():
    return GraphDatabase.driver(
        uri,
        auth=(username, password),
    )


driver = get_driver()


@st.cache_data
def get_normalized_entities():
    query = """
    MATCH (n:NormalizedEntity)
    RETURN n.value AS value
    ORDER BY value"""

    with driver.session(database=database) as session:
        result = session.run(query)
        return [record["value"] for record in result]


@st.cache_data
def get_statements(entity_value):
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


@st.cache_data
def generate_cached_summary(normalized_entity, statements):
    return generate_summary(normalized_entity, statements)


node_colors = {
    "Author": "#57c7e3",
    "Document": "#57c7e3",
    "Statement": "#aea18b",
    "Entity": "#e4afa4",
    "NormalizedEntity": "#B85C73",
}


@st.cache_data
def get_graph_stats():
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


def on_node_click(node):
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


def style_graph(VG):
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

