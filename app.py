import streamlit as st
from neo4j_viz.neo4j import from_neo4j
from neo4j_viz.streamlit import display_widget
import html
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
    categories_name,
    on_node_click,
    generate_cached_summary,
    get_entity_cooccurrences,
    get_shared_articles,
    
    get_category_description,
    get_top_normalized_entities,
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


# --------------------------------------------------------------------------------------------------
# GESTION DES VARIABLES DE SESSION
# --------------------------------------------------------------------------------------------------

if "explore_entities" not in st.session_state:
    st.session_state.explore_entities = False
if "show_category_graph" not in st.session_state:
    st.session_state.show_category_graph = False
if"selected_category" not in st.session_state:
    st.session_state.selected_category = None
if "show_authors" not in st.session_state:
    st.session_state.show_authors = False

# --------------------------------------------------------------------------------------------------
# AFFICHAGE GRAPHE COMPLET
# --------------------------------------------------------------------------------------------------

# Affichage statistiques
if not st.session_state.explore_entities:

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
            graph_title = categories_name[category]
            graph_key = f"category_graph_{category}"
        

        st.subheader(graph_title)
        stats = get_graph_stats(selected_category=st.session_state.selected_category)

        col1, col2, col3, col4, col5 = st.columns(5)

        col1.metric("Documents", stats["documents"])
        col2.metric("Statements", stats["statements"])
        col3.metric("Entities", stats["entities"])
        col4.metric("Normalized entities", stats["normalized_entities"])
        col5.metric("Authors", stats["authors"])
        
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
        st.subheader("")
        st.subheader("")
        st.subheader("Explore knowledge graph by category")

        for i, category in enumerate(categories_name.keys()):

            category_name = categories_name[category]
            color = category_colors[category]

            st.markdown(
                f"""
                <style>
                .st-key-category_{i} button {{
                    background-color: {color} !important;
                    color: black !important;
                    border: none !important;
                }}

                .st-key-category_{i} button:hover {{
                    filter: brightness(0.9);
                }}
                </style>
                """,
                unsafe_allow_html=True,
            )

            if st.button(
                category_name,
                key=f"category_{i}",
            ):
                st.session_state.selected_category = category
                st.rerun()

        if st.session_state.selected_category is not None:

            if st.button(
                "Back to global graph",
                key="back_to_global",
            ):
                st.session_state.selected_category = None
                st.rerun()
    

    

# Affichage description des categories 
    if st.session_state.selected_category is not None:

        category = st.session_state.selected_category

        # Retrieve category description
        category_descriptions = get_category_description()
        # description_data = category_descriptions.get(category, {})

        description = category_descriptions.get(
            category,
            "No description available."
        )

        # Retrieve top normalized entities
        top_entities = get_top_normalized_entities(category)

        # Two-column layout
        description_col, entities_col = st.columns(
            [3, 2],
            gap="large"
        )
        color = category_colors[category]
        with description_col:
            st.markdown(
                """
                <div style="
                    font-size: 0.8rem;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.08em;
                    color: #888;
                    margin-bottom: 0.7rem;
                ">
                    Category overview
                </div>
                """,
                unsafe_allow_html=True,
            )

            safe_description = html.escape(str(description))

            st.markdown(
                f"""
                <div style="
                    background-color: rgba(128, 128, 128, 0.08);
                    border-left: 4px solid {color};
                    border-radius: 10px;
                    padding: 1.2rem 1.4rem;
                    line-height: 1.7;
                    min-height: 150px;
                ">
                    {safe_description}
                </div>
                """,
                unsafe_allow_html=True,
            )

        with entities_col:
            st.markdown(
                """
                <div style="
                    font-size: 0.8rem;
                    font-weight: 600;
                    text-transform: uppercase;
                    letter-spacing: 0.08em;
                    color: #888;
                    margin-bottom: 0.7rem;
                ">
                    Most frequent concepts
                </div>
                """,
                unsafe_allow_html=True,
            )

            if top_entities:

                # Sort by document count, from highest to lowest
                top_entities = sorted(
                    top_entities,
                    key=lambda item: item.get("document_count", 0),
                    reverse=True,
                )

                entity_rows = ""

                for entity_data in top_entities:
                    entity_name = html.escape(
                        str(entity_data.get("normalized_entity", "Unknown"))
                    )
                    document_count = entity_data.get("document_count", 0)

                    entity_rows += f"""
                    <div style="
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        gap: 12px;
                        padding: 10px 0;
                        border-bottom: 1px solid rgba(128, 128, 128, 0.18);
                    ">
                        <span style="
                            font-size: 0.9rem;
                            line-height: 1.4;
                        ">
                            {entity_name}
                        </span>
                        <span style="
                            flex-shrink: 0;
                            font-size: 0.78rem;
                            font-weight: 600;
                            background-color: {color};
                            border-radius: 12px;
                            padding: 4px 9px;
                            white-space: nowrap;
                        ">
                            {document_count} papers
                        </span>
                    </div>
                    """

                st.markdown(
                    f"""
                    <div style="
                        background-color: rgba(128, 128, 128, 0.08);
                        border-radius: 10px;
                        padding: 0.5rem 1rem;
                    ">
                        {entity_rows}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            else:
                st.info("No normalized entities found for this category.")




# --------------------------------------------------------------------------------------------------
# MISE EN PLACE ET AFFICHAGE GRAPHE POUR EXPLORATION
# --------------------------------------------------------------------------------------------------
    if st.button("Explore normalized entities"):
        st.session_state.explore_entities = True
        st.rerun()

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


# --------------------------------------------------------------------------------------------------
# KNOWLEDGE STATEMENTS
# --------------------------------------------------------------------------------------------------

    st.subheader("Knowledge statements")

    st.caption(
        f"{len(statements)} statements associated with "
        f"**{selected_entity}**"
    )

    # Number of statements displayed initially
    BATCH_SIZE = 5

    # Reset the visible count when the selected entity changes
    if st.session_state.get("statements_entity") != selected_entity:
        st.session_state.statements_entity = selected_entity
        st.session_state.visible_statements = BATCH_SIZE

    visible_count = st.session_state.get(
        "visible_statements", BATCH_SIZE
    )

    visible_statements = statements[:visible_count]

    for i, item in enumerate(visible_statements):

        with st.container(border=True):

            # Main scientific statement
            st.markdown(item["statement"] or "*Statement unavailable*")

            # Source article
            title = item["title"] or "Untitled article"
            st.caption(f"Source: {title}")

            # DOI link
            doi = item["doi"]

            if doi:
                doi = doi.strip()
                doi_url = (
                    doi
                    if doi.startswith(("http://", "https://"))
                    else f"https://doi.org/{doi}"
                )

                st.markdown(f"[Open article via DOI ↗]({doi_url})")

    if visible_count < len(statements):

        remaining = len(statements) - visible_count

        if st.button(
            f"Show 10 more statements ({remaining} remaining)",
            key="show_more_statements",
            use_container_width=True,
        ):
            st.session_state.visible_statements = min(
                visible_count + BATCH_SIZE,
                len(statements),
            )
            st.rerun()

    elif statements:
        st.caption("All statements are displayed.")


    
# --------------------------------------------------------------------------------------------------
# ENTITY COOCCURRENCE
# --------------------------------------------------------------------------------------------------

    st.subheader("Entity Co-occurrence")

    st.caption(
        f"Explore normalized entities that co-occur with "
        f"**{selected_entity}** in the same scientific articles."
    )

    cooccurrences = get_entity_cooccurrences(selected_entity)

    if not cooccurrences:
        st.info("No co-occurrences found for this entity.")

    else:
        max_count = max(
            item["shared_articles"] for item in cooccurrences
        )

        # Filter
        min_articles = st.slider(
            "Minimum number of shared articles",
            min_value=1,
            max_value=max_count,
            value=1,
            key="cooccurrence_threshold",
        )

        filtered_cooccurrences = [
            item for item in cooccurrences
            if item["shared_articles"] >= min_articles
        ]

        # Reset selection if the selected association is no longer available
        association_key = f"cooccurrence_selected_{selected_entity}"

        available_entities = {
            item["entity"] for item in filtered_cooccurrences
        }

        if st.session_state.get(association_key) not in available_entities:
            st.session_state[association_key] = (
                filtered_cooccurrences[0]["entity"]
                if filtered_cooccurrences else None
            )

        selected_association = st.session_state[association_key]

        # Summary metrics
        col1, col2, col3 = st.columns(3)

        col1.metric(
            "Associated entities",
            len(filtered_cooccurrences),
        )

        col2.metric(
            "Articles with selected entity",
            len({
                article["doi"] or article["title"]
                for article in get_statements(selected_entity)
            }),
        )

        col3.metric(
            "Most frequent co-occurrence",
            max_count,
            help="Maximum number of shared articles before filtering.",
        )

        st.divider()

        # Two-column exploration layout
        col_rank, col_articles = st.columns([1, 1.3], gap="large")

        with col_rank:
            st.markdown("#### Associated entities")
            st.caption("Select an entity to inspect its shared articles.")

            if not filtered_cooccurrences:
                st.info("No associations match this filter.")

            else:
                for item in filtered_cooccurrences:
                    entity = item["entity"]
                    count = item["shared_articles"]
                    is_selected = entity == selected_association

                    with st.container(border=True):
                        row1, row2 = st.columns([4, 1])

                        with row1:
                            if st.button(
                                entity,
                                key=f"cooccurrence_{selected_entity}_{entity}",
                                type="primary" if is_selected else "secondary",
                                use_container_width=True,
                            ):
                                st.session_state[association_key] = entity
                                st.rerun()

                        with row2:
                            st.markdown(
                                f"**{count}**",
                                help="Number of shared articles",
                            )

                        st.progress(
                            count / max_count,
                            text=f"{count} shared article(s)",
                        )

        with col_articles:
            if selected_association:
                shared_articles = get_shared_articles(
                    selected_entity,
                    selected_association,
                )

                st.markdown("#### Shared articles")
                st.markdown(
                    f"**{selected_entity}** ↔ "
                    f"**{selected_association}**"
                )

                st.caption(
                    f"{len(shared_articles)} shared article(s)"
                )

                if not shared_articles:
                    st.info("No shared articles found.")

                else:
                    for article in shared_articles:
                        title = article["title"] or "Untitled article"
                        doi = article["doi"]

                        with st.container(border=True):
                            st.markdown(f"**{title}**")

                            if doi:
                                doi = doi.strip()
                                doi_url = (
                                    doi
                                    if doi.startswith(("http://", "https://"))
                                    else f"https://doi.org/{doi}"
                                )

                                st.markdown(
                                    f"[Open article via DOI ↗]({doi_url})"
                                )
                            else:
                                st.caption("DOI unavailable")
            else:
                st.info("Select an associated entity to view shared articles.")
            