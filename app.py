import streamlit as st
import os
import json
import random
import re
from streamlit_agraph import agraph, Node, Edge, Config

# =========================
# PATH CONFIG
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

QUESTION_MAP_PATH = os.path.join(BASE_DIR, "data", "database_no6869", "log","question_history.json")
CHECKPOINT_DIR = os.path.join(BASE_DIR, "data", "database_no6869")

# Where expert results will be saved
EXPERT_DIR = os.path.join(BASE_DIR, "expert_logs")

st.set_page_config(page_title="LLM Theory Evaluator", layout="wide")

ADMIN_PASSWORD = "admin123"  # change this
# =========================
# CORE DATA FUNCTIONS
# =========================
def load_question_map():
    try:
        with open(QUESTION_MAP_PATH, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        st.error(f"Could not find question_history.json at {QUESTION_MAP_PATH}")
        return {}

def load_hypotheses(checkpoint_folder, max_samples=None):
    folder_name = os.path.splitext(checkpoint_folder)[0]
    folder_path = os.path.join(CHECKPOINT_DIR, folder_name)
    
    if not os.path.exists(folder_path):
        st.error(f"Checkpoint folder not found: {folder_path}")
        return []
    
    pattern = re.compile(r"^checkpoint_.*_run\d+\.json$")
    files = [f for f in os.listdir(folder_path) if pattern.match(f)]
    
    hypotheses = []
    for f in sorted(files):
        path = os.path.join(folder_path, f)
        with open(path, 'r', encoding='utf-8') as file:
            data = json.load(file)
            hyp = data.get("final_theory", "")
            if hyp:
                hypotheses.append({"file": f, "text": hyp})
    
    if max_samples:
        random.shuffle(hypotheses)
        return hypotheses[:max_samples]
    return hypotheses

def save_expert_data(expert_id, data):
    os.makedirs(EXPERT_DIR, exist_ok=True)
    path = os.path.join(EXPERT_DIR, f"{expert_id}.json")
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

# =========================
# SESSION STATE SETUP
# =========================
if 'expert_data' not in st.session_state:
    st.session_state.expert_data = {"mode_A": {}, "mode_B": {}}
if 'temp_edges' not in st.session_state:
    st.session_state.temp_edges = []

# Function to reset inputs when switching questions/runs
def reset_inputs():
    keys_to_reset = ['h_pre', 'u_pre', 'h_post', 'u_post', 'temp_edges', 'node_input', 'reveal_llm']
    for key in keys_to_reset:
        if key in st.session_state:
            if key == 'u_pre' or key == 'u_post': st.session_state[key] = 3
            elif key == 'temp_edges': st.session_state[key] = []
            elif key == 'reveal_llm': st.session_state[key] = False
            else: st.session_state[key] = ""

def ensure_structure(data):
    if "mode_A" not in data:
        data["mode_A"] = {}
    if "mode_B" not in data:
        data["mode_B"] = {}
    return data

# =========================
# SIDEBAR: LOGIN & SETUP
# =========================
with st.sidebar:
    st.title("Researcher Portal")
    expert_id_input = st.text_input("Expert ID", placeholder="e.g., xingru")
#######admin toggle
    is_admin = False
    admin_input = st.text_input("Admin Password (optional)", type="password")

    if admin_input == ADMIN_PASSWORD:
        is_admin = True
        st.success("Admin mode enabled")
#######a
    # 🔑 FIXED LOGIN SWITCH
    if expert_id_input:
        path = os.path.join(EXPERT_DIR, f"{expert_id_input}.json")

        if st.session_state.get("current_user") != expert_id_input:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    st.session_state.expert_data = json.load(f)
            else:
                st.session_state.expert_data = {}

            st.session_state.expert_data = ensure_structure(st.session_state.expert_data)
            st.session_state.current_user = expert_id_input

            reset_inputs()
        
    mode = st.radio("Select Evaluation Mode", ["Home", "Mode A (EUD)", "Mode B (EMVS/CDI)"])
    
    question_map = load_question_map()
    q_list = list(question_map.keys())
    # selected_q = st.selectbox("Select Question to Evaluate", q_list)
    selected_q = st.selectbox("Select Question to Evaluate", q_list, on_change=reset_inputs)
# =========================
# HOME SCREEN
# =========================
if mode == "Home":
    st.header(f"Welcome, {expert_id_input if expert_id_input else 'Researcher'}")
    st.write("Select a mode from the sidebar to begin your evaluation.")
    if expert_id_input:
        st.success(f"Log-in successful. Your data will be saved as `{expert_id_input}.json`")

# =========================
# MODE A: EUD (Expert Utility Delta)
# =========================
elif mode == "Mode A (EUD)" and expert_id_input:
    st.header("🧠 Mode A: Augmented Intelligence (EUD)")

    with st.expander("❓ View Current Question Details", expanded=True):
            st.write(f"**Question ID:** {selected_q}")

    already_done = selected_q in st.session_state.expert_data["mode_A"]

    if already_done and not is_admin:
        st.warning("You have already completed Mode A for this question. (Read-only)")

        record = st.session_state.expert_data["mode_A"][selected_q]

        st.subheader("Your Previous Submission")
        st.write("**Initial Hypothesis:**", record["H_pre"])
        st.write("**U_pre:**", record["U_pre"])
        st.write("**Final Hypothesis:**", record["H_post"])
        st.write("**U_post:**", record["U_post"])

        if "shown_llm_files" in record:
            st.subheader("LLM Theories You Were Shown")

            checkpoint = question_map[selected_q]["checkpoint_file"]
            all_hyps = load_hypotheses(checkpoint)

            # map file → text
            hyp_map = {h["file"]: h["text"] for h in all_hyps}

            for i, f in enumerate(record["shown_llm_files"]):
                st.markdown(f"**Theory {i+1} ({f})**")
                st.info(hyp_map.get(f, "⚠️ Text not found"))
        st.stop()

    st.subheader("Step 1: Initial Hypothesis")
    h_pre = st.text_area("Formulate your initial hypothesis based on the question:", key="h_pre")
    u_pre = st.slider("Rate your confidence/utility (1-5)", 1, 5, 3, key="u_pre")

    if st.button("Submit & Reveal LLM Theories"):
        st.session_state.reveal_llm = True

    if st.session_state.get("reveal_llm"):
        checkpoint = question_map[selected_q]["checkpoint_file"]
        llm_hyps = load_hypotheses(checkpoint, max_samples=3)
        
        st.divider()
        st.subheader("Step 2: Review LLM-Generated Theories")
        for i, h in enumerate(llm_hyps):
            st.info(f"**Theory {i+1}** ({h['file']}):\n\n{h['text']}")
        
        st.divider()
        st.subheader("Step 3: Final Hypothesis")
        h_post = st.text_area("Rewrite or refine your hypothesis after reviewing the LLM output:", key="h_post")
        u_post = st.slider("Rate your NEW confidence/utility (1-5)", 1, 5, 3, key="u_post")

        if st.button("Save Mode A Evaluation"):
            st.session_state.expert_data["mode_A"][selected_q] = {
                "H_pre": h_pre, "U_pre": u_pre,
                "H_post": h_post, "U_post": u_post,
                "shown_llm_files": [h['file'] for h in llm_hyps]
            }
            save_expert_data(expert_id_input, st.session_state.expert_data)
            st.success("Mode A progress saved!")

# =========================
# MODE B: VISUAL GRAPH INTERFACE
# =========================
elif mode == "Mode B (EMVS/CDI)" and expert_id_input:
    st.header("🔬 Mode B: Scientific Validity & Causal Mapping")
    with st.expander("❓ View Current Question Details", expanded=True):
            st.write(f"**Question ID:** {selected_q}")

    checkpoint = question_map[selected_q]["checkpoint_file"]
    hyps = load_hypotheses(checkpoint)

    if hyps:
        h_idx = st.selectbox("Select Theory Run to Evaluate", range(len(hyps)), 
                             format_func=lambda x: hyps[x]['file'],on_change=reset_inputs)
        current_hyp = hyps[h_idx]
        
        st.info("### Current Theory Text")
        st.markdown(current_hyp['text'])

        already_done = (
            selected_q in st.session_state.expert_data["mode_B"]
            and current_hyp['file'] in st.session_state.expert_data["mode_B"][selected_q]
        )

        if already_done and not is_admin:
            st.warning("This theory has already been evaluated. (Read-only)")

            record = st.session_state.expert_data["mode_B"][selected_q][current_hyp['file']]

            st.subheader("Previous Evaluation")
            st.write("**EMVS:**", record["EMVS"])
            st.write("**Nodes:**", record["nodes"])
            st.write("**Edges:**", record["edges"])
            st.stop()  # 🔑 prevents editing

        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("1. Metric Scoring")
            c1, c2 = st.columns(2)
            corr = c1.slider("Correctness", 1, 5, 3)
            comp = c2.slider("Completeness", 1, 5, 3)
            caus = c1.slider("Causal Clarity", 1, 5, 3)
            inte = c2.slider("Integration", 1, 5, 3)

            st.subheader("2. Node Extraction")
            st.caption("Enter keywords found in the theory text to create graph nodes.")
            node_input = st.text_area("List Nodes (separated by commas)", placeholder="e.g., FCC Phase, BCC Threshold")
            nodes_list = [n.strip() for n in node_input.split(",") if n.strip()]

        with col2:
            st.subheader("3. Directed Causal Links")
            if nodes_list:
                s_col, t_col = st.columns(2)
                source = s_col.selectbox("From (Source)", nodes_list)
                target = t_col.selectbox("To (Target)", nodes_list)
                
                if st.button("Add Directed Edge"):
                    if (source, target) not in st.session_state.temp_edges:
                        st.session_state.temp_edges.append((source, target))
                
                if st.button("Clear Graph"):
                    st.session_state.temp_edges = []

                # Visualization
                nodes = [Node(id=n, label=n, size=15, color="#007bff") for n in nodes_list]
                edges = [Edge(source=s, target=t, type="CURVE_SMOOTH") for s, t in st.session_state.temp_edges]
                
                config = Config(width=500, height=350, directed=True, physics=True)
                agraph(nodes=nodes, edges=edges, config=config)
            else:
                st.warning("Enter nodes in Step 2 to enable the drawing tool.")

        if st.button("Submit Evaluation & Log Data"):
            eval_record = {
                "EMVS": {"correctness": corr, "completeness": comp, "causal_clarity": caus, "integration": inte},
                "nodes": nodes_list,
                "edges": st.session_state.temp_edges
            }
            if selected_q not in st.session_state.expert_data["mode_B"]:
                st.session_state.expert_data["mode_B"][selected_q] = {}
            st.session_state.expert_data["mode_B"][selected_q][current_hyp['file']] = eval_record
            save_expert_data(expert_id_input, st.session_state.expert_data)
            st.success(f"Successfully logged evaluation for {current_hyp['file']}")

elif not expert_id_input:
    st.warning("Please enter your Expert ID in the sidebar to begin.")