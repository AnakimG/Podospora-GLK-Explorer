import html

import streamlit as st
from neo4j_viz.neo4j import from_neo4j
from neo4j_viz.streamlit import display_widget

from utils import (
    categories_name,
    category_colors,
    check_neo4j_connection,
    generate_cached_summary,
    get_category_description,
    get_category_graph,
    get_entity_cooccurrences,
    get_entity_graph,
    get_full_graph,
    get_graph_stats,
    get_normalized_entities,
    get_shared_articles,
    get_statements,
    get_top_normalized_entities,
    node_colors,
    on_node_click,
    on_node_expand,
    style_full_graph,
    style_graph,
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
            "(?<![a-zA-Z0-9])(" +
            sortedEntities
                .map(e => escapeRegex(e) + (e.toLowerCase().endsWith("s") ? "" : "s?"))
                .join("|") +
            ")(?![a-zA-Z0-9])",
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
                entity => {
                    const e = entity.toLowerCase();
                    const t = text.toLowerCase();
                    return e === t || (!e.endsWith("s") && e + "s" === t);
                }
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
    check_neo4j_connection()

except Exception as e:
    st.error(f"Neo4j connection failed: {e}")


# --------------------------------------------------------------------------------------------------
# GESTION DES VARIABLES DE SESSION
# --------------------------------------------------------------------------------------------------

if "explore_entities" not in st.session_state:
    st.session_state.explore_entities = False
if "show_category_graph" not in st.session_state:
    st.session_state.show_category_graph = False
if "selected_category" not in st.session_state:
    st.session_state.selected_category = None
if "show_narrative" not in st.session_state:
    st.session_state.show_narrative = False
if "current_summary" not in st.session_state:
    st.session_state.current_summary = None

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

        widget.on_node_event("double_click", on_node_expand)

        display_widget(
            widget,
            key=graph_key,
        )
    
    with col_category:
        if st.session_state.selected_category is None:
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
                    use_container_width=True,
                ):
                    st.session_state.selected_category = category
                    st.rerun()
        else:
            st.subheader("")
            st.write("")
            st.subheader("Most frequent normalized entities")
            category = st.session_state.selected_category
            top_entities = get_top_normalized_entities(category)
            
            with st.container(height=700):
                if top_entities:
                    # Sort by document count, from highest to lowest
                    top_entities = sorted(
                        top_entities,
                        key=lambda item: item.get("document_count", 0),
                        reverse=True,
                    )
                    for entity_data in top_entities:
                        entity_name = entity_data.get("normalized_entity", "Unknown")
                        document_count = entity_data.get("document_count", 0)
                        with st.container(border=True):
                            col_name, col_count = st.columns([4, 1])
                            with col_name:
                                if st.button(
                                    entity_name,
                                    key=f"top_entity_{entity_name}",
                                    use_container_width=True,
                                ):
                                    st.session_state.explore_entities = True
                                    st.session_state.pending_selected_entity = entity_name
                                    if "opened_normalized_entities" not in st.session_state:
                                        st.session_state.opened_normalized_entities = []
                                    if entity_name not in st.session_state.opened_normalized_entities:
                                        st.session_state.opened_normalized_entities.append(entity_name)
                                    st.rerun()
                            with col_count:
                                st.markdown(f"**{document_count}** papers")
                else:
                    st.info("No normalized entities found for this category.")
    

    

# Affichage description des categories 
    if st.session_state.selected_category is not None:

        category = st.session_state.selected_category

        # Retrieve category description
        category_descriptions = get_category_description()

        description = category_descriptions.get(
            category,
            "No description available."
        )

        color = category_colors[category]
        
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
                margin-bottom: 2rem;
            ">
                {safe_description}
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()
        st.subheader("Explore other categories")
        
        # Grid of category buttons
        cols = st.columns(3)
        for i, category_id in enumerate(categories_name.keys()):
            col_idx = i % 3
            category_name = categories_name[category_id]
            cat_color = category_colors[category_id]
            
            with cols[col_idx]:
                st.markdown(
                    f"""
                    <style>
                    .st-key-category_bottom_{i} button {{
                        background-color: {cat_color} !important;
                        color: black !important;
                        border: none !important;
                    }}
                    .st-key-category_bottom_{i} button:hover {{
                        filter: brightness(0.9);
                    }}
                    </style>
                    """,
                    unsafe_allow_html=True,
                )
                if st.button(
                    category_name,
                    key=f"category_bottom_{i}",
                    use_container_width=True,
                ):
                    st.session_state.selected_category = category_id
                    st.rerun()
        
        if st.button(
            "Back to global graph",
            key="back_to_global_bottom",
            use_container_width=True,
        ):
            st.session_state.selected_category = None
            st.session_state.opened_normalized_entities = []
            st.session_state.opened_documents = []
            st.session_state.opened_authors = []
            st.session_state.opened_statements = []
            st.rerun()




# --------------------------------------------------------------------------------------------------
# MISE EN PLACE ET AFFICHAGE GRAPHE POUR EXPLORATION
# --------------------------------------------------------------------------------------------------
    if st.button("Explore normalized entities"):
        st.session_state.explore_entities = True
        st.session_state.opened_normalized_entities = []
        st.session_state.opened_documents = []
        st.session_state.opened_authors = []
        st.session_state.opened_statements = []
        if "prev_entity" in st.session_state:
            del st.session_state.prev_entity
        st.rerun()

else:
    if st.button("Back to global graph"):
        st.session_state.explore_entities = False
        st.session_state.opened_normalized_entities = []
        st.session_state.opened_documents = []
        st.session_state.opened_authors = []
        st.session_state.opened_statements = []
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

    # Maintain the previous entity in the exploration graph to preserve the exploration path
    if "prev_entity" in st.session_state and st.session_state.prev_entity != selected_entity:
        if "opened_normalized_entities" not in st.session_state:
            st.session_state.opened_normalized_entities = []
        if st.session_state.prev_entity not in st.session_state.opened_normalized_entities:
            st.session_state.opened_normalized_entities.append(st.session_state.prev_entity)

    st.session_state.prev_entity = selected_entity

    col_graph, col_summary = st.columns([5, 2])

    with col_graph:
        st.subheader("Knowledge graph")

        if st.button("Clear exploration graph", key="clear_exploration_graph"):
            st.session_state.opened_normalized_entities = []
            st.session_state.opened_documents = []
            st.session_state.opened_authors = []
            st.session_state.opened_statements = []
            st.rerun()

        entity_values = list(
            dict.fromkeys(
                [selected_entity]
                + st.session_state.get("opened_normalized_entities", [])
            )
        )

        result = get_entity_graph(
            entity_values,
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

    statements = get_statements(selected_entity)

    with col_summary:
        st.subheader("Graph-based narrative of knowledge statements")

        # Reset narrative if entity changed
        if st.session_state.get("narrative_entity") != selected_entity:
            st.session_state.show_narrative = False
            st.session_state.narrative_entity = selected_entity

        if st.button("Generate Graph-based Narrative"):
            st.session_state.show_narrative = True

        if st.session_state.get("show_narrative"):
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
                        col_select, col_add, col_count = st.columns([3, 1, 1])

                        with col_select:
                            if st.button(
                                entity,
                                key=f"cooccurrence_{selected_entity}_{entity}",
                                type="primary" if is_selected else "secondary",
                                use_container_width=True,
                            ):
                                st.session_state[association_key] = entity
                                st.rerun()

                        with col_add:
                            if st.button(
                                "➕",
                                key=f"add_to_graph_{selected_entity}_{entity}",
                                help="Add this entity and its neighborhood to the graph",
                                use_container_width=True,
                            ):
                                if "opened_normalized_entities" not in st.session_state:
                                    st.session_state.opened_normalized_entities = []
                                if entity not in st.session_state.opened_normalized_entities:
                                    st.session_state.opened_normalized_entities.append(entity)
                                st.rerun()

                        with col_count:
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
            