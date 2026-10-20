import streamlit as st
from neo4j_viz.neo4j import from_neo4j
from neo4j_viz.streamlit import display_widget
from utils import (
    driver,
    get_graph_stats,
    get_full_graph,
    get_entity_graph,
    get_statements,
    get_normalized_entities,
    get_category_graph,
    style_graph,
    style_full_graph,
    node_colors,
    category_colors,
    on_node_click,
    generate_cached_summary
)


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

try:
    driver.verify_connectivity()

except Exception as e:
    st.error(f"Neo4j connection failed: {e}")


if "explore_entities" not in st.session_state:
    st.session_state.explore_entities = False
if st.button("Explore normalized entities"):
    st.session_state.explore_entities = True
    st.rerun()
if "show_category_graph" not in st.session_state:
    st.session_state.show_category_graph = False
if"selected_category" not in st.session_state:
    st.session_state.selected_category = None


# --------------------------------------------------------------------------------------------------
# AFFICHAGE GRAPHE COMPLET
# --------------------------------------------------------------------------------------------------

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
    col_graph, col_category = st.columns([6,2])

    with col_graph: 

        if st.session_state.selected_category is None:
            result = get_full_graph()
            graph_title = "Global knowledge graph"
            graph_key = "global_graph"

        else:
            category = st.session_state.selected_category
            result = get_category_graph(category)
            graph_title = category
            graph_key = f"category_graph_{category}"

        st.subheader(graph_title)
        VG = from_neo4j(result)
        style_full_graph(VG)

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

        display_widget(
            widget,
            key=graph_key,
        )
    
    with col_category:

        st.subheader("Explore knowledge graph by category")

        categories = [
        "1/7/8 - Life Cycle - Reproduction and Morphogenesis ",
        "2 - Genomics and Genome Architecture ",
        "3/4 - Mitochondria - Energy Metabolism and Aging ",
        "5/6 - Signal Transduction - Regulation and Stress Response ",
        "9 - Vegetative Incompatibility and Cell Death ",
        "10 - Comparative and Evolutionary Biology ",
        "11 - Host–Pathogen and Symbiotic Interactions ",
        "12 - Biotechnology and Applied Research ",
    ]
        
        for i, category in enumerate(categories):
            if st.button(category, key=f"category_{i}"):
                st.session_state.selected_category = category
                st.rerun()
        
        if st.session_state.selected_category is not None:
            if st.button("Back to global graph"):
                st.session_state.selected_category = None
                st.rerun()

# --------------------------------------------------------------------------------------------------
# MISE EN PLACE ET AFFICHAGE GRAPHE POUR EXPLORATION
# --------------------------------------------------------------------------------------------------

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
            if selected_entity == "het-s":
                summary = (
                    "In the fungus Podospora anserina, the het-s allele encodes the HET-S "
                    "protein, which controls heterokaryon incompatibility and mediates "
                    "non-self recognition leading to programmed cytotoxicity. Structurally, "
                    "HET-S comprises an N-terminal alpha-helical HeLo domain and a C-terminal "
                    "prion-forming domain (PFD). Activation occurs when HET-S undergoes a "
                    "trans-conformation, often templated by the [Het-s] prion or the adjacent "
                    "gene product NWD2, causing the PFD to adopt a beta-solenoid amyloid fold. "
                    "This conformational change triggers HET-S to relocate to the cell "
                    "membrane, where it oligomerizes and forms pores that disrupt membrane "
                    "integrity and induce toxicity. The process shares propagation mechanisms "
                    "with mammalian prions and is linked to meiotic drive, with high-resolution "
                    "structural data confirming the amyloid nature of the protein."
                )

            else:
                summary_texts = [item["statement"] for item in statements]

                with st.spinner("Generating narrative..."):
                    summary = generate_cached_summary(
                        selected_entity,
                        summary_texts
                    )

            st.subheader("Graph-based narrative")

            # Session à revoir pour gérer les clicks
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
