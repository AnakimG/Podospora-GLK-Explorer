import os

import streamlit as st
from dotenv import load_dotenv
from neo4j import GraphDatabase, Result, RoutingControl
from neo4j_viz.neo4j import from_neo4j
from neo4j_viz.streamlit import display_widget

load_dotenv()

from summarizer import generate_summary

clickable_summary = st.components.v2.component(
    "clickable_summary",

    html="""
    <div id="summary"></div>
    """,

    css="""
    #summary {
        white-space: pre-wrap;
        line-height: 1.6;
    }

    .ne-link {
        border: none;
        background: none;
        padding: 0;
        margin: 0;
        color: #B85C73;
        cursor: pointer;
        font: inherit;
        text-decoration: underline;
    }

    .ne-link:hover {
        font-weight: 600;
    }
    """,

    js="""
    export default function(component) {

        const {
            parentElement,
            data,
            setTriggerValue
        } = component;

        const container = parentElement.querySelector("#summary");

        const summary = data?.summary ?? "";
        const entities = data?.entities ?? [];

        container.innerHTML = "";

        if (!entities.length) {
            container.textContent = summary;
            return;
        }

        // Les entités les plus longues passent en premier
        const sortedEntities = [...entities]
            .sort((a, b) => b.length - a.length);

        function escapeRegex(text) {
            return text.replace(/[.*+?^${}()|[\\]\\\\]/g, "\\\\$&");
        }

        const pattern = new RegExp(
            "(" +
            sortedEntities
                .map(escapeRegex)
                .join("|") +
            ")",
            "gi"
        );

        let lastIndex = 0;
        let match;

        while ((match = pattern.exec(summary)) !== null) {

            // Texte avant l'entité
            if (match.index > lastIndex) {
                container.appendChild(
                    document.createTextNode(
                        summary.slice(lastIndex, match.index)
                    )
                );
            }

            const text = match[0];

            const canonicalEntity = sortedEntities.find(
                entity => entity.toLowerCase() === text.toLowerCase()
            );

            const button = document.createElement("button");

            button.className = "ne-link";
            button.textContent = text;

            button.onclick = () => {
                setTriggerValue(
                    "entity_click",
                    canonicalEntity
                );
            };

            container.appendChild(button);

            lastIndex = pattern.lastIndex;
        }

        // Texte restant
        if (lastIndex < summary.length) {
            container.appendChild(
                document.createTextNode(
                    summary.slice(lastIndex)
                )
            );
        }
    }
    """
)

st.set_page_config(
    page_title="Podospora GLK Explorer",
    layout="wide",
)

st.title("Podospora GLK Explorer")
st.write("Graph of literature knowledge exploration")

uri = os.getenv("NEO4J_URI")
username = os.getenv("NEO4J_USERNAME")
password = os.getenv("NEO4J_PASSWORD")
database = os.getenv("NEO4J_DATABASE")

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


try:
    driver.verify_connectivity()

except Exception as e:
    st.error(f"Neo4j connection failed: {e}")


if "explore_entities" not in st.session_state:
    st.session_state.explore_entities = False
if st.button("Explore normalized entities"):
    st.session_state.explore_entities = True
    st.rerun()

## AFFICHAGE GRAPHE COMPLET
# Affichage statistiques
if not st.session_state.explore_entities:
    st.subheader("Global graph")
    stats = get_graph_stats()

    col1, col2, col3, col4, col5 = st.columns(5)

    col1.metric("Documents", stats["documents"])
    col2.metric("Statements", stats["statements"])
    col3.metric("Entities", stats["entities"])
    col4.metric("Normalized entities", stats["normalized_entities"])
    col5.metric("Authors", stats["authors"])

    # Visualisation du graphe

    result = get_full_graph()

    VG = from_neo4j(result)

    style_full_graph(VG)

    legend = {}

    legend["Statement"] = node_colors["Statement"]
    legend["Entity"] = node_colors["Entity"]
    legend["NormalizedEntity"] = node_colors["NormalizedEntity"]

    legend["Life Cycle - Reproduction and Morphogenesis"] = category_colors[
        "1/7/8 - Life Cycle - Reproduction and Morphogenesis "
    ]
    legend["Genomics and Genome Architecture"] = category_colors[
        "2 - Genomics and Genome Architecture "
    ]
    legend["Mitochondria - Energy Metabolism and Aging"] = category_colors[
        "3/4 - Mitochondria - Energy Metabolism and Aging "
    ]
    legend["Signal Transduction - Regulation and Stress Response"] = category_colors[
        "5/6 - Signal Transduction - Regulation and Stress Response "
    ]
    legend["Vegetative Incompatibility and Cell Death"] = category_colors[
        "9 - Vegetative Incompatibility and Cell Death "
    ]
    legend["Comparative and Evolutionary Biology"] = category_colors[
        "10 - Comparative and Evolutionary Biology "
    ]
    legend["Host–Pathogen and Symbiotic Interactions"] = category_colors[
        "11 - Host–Pathogen and Symbiotic Interactions "
    ]
    legend["Biotechnology and Applied Research"] = category_colors[
        "12 - Biotechnology and Applied Research "
    ]

    VG.set_legend(nodes=legend)
    VG.show_legend(True)

    widget = VG.render_widget(
        width="100%",
        height="700px",
    )

    display_widget(
        widget,
        key="global_graph",
    )


## MISE EN PLACE ET AFFICAHGE GRAPHE POUR EXPLORATION
if "show_authors" not in st.session_state:
    st.session_state.show_authors = False

else:
    if st.button("Back to global graph"):
        st.session_state.explore_entities = False
        st.rerun()

    entities = get_normalized_entities()
    
    if "pending_selected_entity" in st.session_state:
        pending = st.session_state.pending_selected_entity

        if pending in entities:
            st.session_state.entity_selector = pending

        del st.session_state.pending_selected_entity

    selected_entity = st.selectbox(
        "Select a normalized entity to explore", entities, key="entity_selector"
    )

    col_graph, col_summary = st.columns([5, 2])

    with col_graph:
        st.subheader("Knowledge graph")

        entity_values = list(
            dict.fromkeys(
                [selected_entity]
                + st.session_state.get("opened_normalized_entities", [])
            )
        )

        result = get_entity_graph(
            entity_values,
            show_authors=st.session_state.show_authors,
            document_ids=st.session_state.get("opened_documents", []),
        )

        # ─────────────────────────────────────
        # GRAPHE DOCUMENT
        # ─────────────────────────────────────

        VG = from_neo4j(result)

        style_graph(VG)

        legend = {}
        legend["Statement"] = node_colors["Statement"]
        legend["Entity"] = node_colors["Entity"]
        legend["NormalizedEntity"] = node_colors["NormalizedEntity"]

        VG.set_legend(nodes=legend)
        VG.show_legend(True)

        widget = VG.render_widget(
            width="100%",
            height="700px",
        )

        widget.on_node_event("click", on_node_click)

        display_widget(
            widget,
            key="document_neighborhood",
        )

        if st.button("Authors"):
            st.session_state.show_authors = not st.session_state.show_authors
            st.rerun()

    statements = get_statements(selected_entity)

    with col_summary:
        st.subheader("Graph-based narrative of knowledge statements")

        if st.button("Generate Graph-based Narrative"):
            summary_texts = [item["statement"] for item in statements]

            with st.spinner("Generating narrative..."):
                summary = generate_cached_summary(
                    selected_entity,
                    summary_texts
                )

            st.subheader("Summary")

            result_summary = clickable_summary(
                data={
                    "summary": summary,
                    "entities": entities,
                },
                key="clickable_summary",
                on_entity_click_change=lambda: None,
            )

            if result_summary.entity_click:
                clicked_entity = result_summary.entity_click

                if "opened_normalized_entities" not in st.session_state:
                    st.session_state.opened_normalized_entities = []

                if clicked_entity not in st.session_state.opened_normalized_entities:
                    st.session_state.opened_normalized_entities.append(
                        clicked_entity
                    )

                st.session_state.pending_selected_entity = clicked_entity

                st.rerun()

    st.subheader("Knowledge statements")
    st.write(f"{len(statements)} statements found.")

    for item in statements:
        st.write(f"**{item['statement']}**")
        st.caption(item["title"])

        if item["doi"]:
            st.markdown(f"[DOI](https://doi.org/{item['doi']})")
