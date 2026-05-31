import os
import sys
import types
from datetime import datetime

import streamlit as st


def _safe_import_app_gui():
    try:
        import app_gui  # type: ignore
        return app_gui
    except Exception as first_error:
        # Streamlit Cloud may not provide tkinter runtime. Stub it and retry.
        tk_stub = types.ModuleType("tkinter")
        tk_stub.Tk = object
        tk_stub.StringVar = object
        tk_stub.END = "end"

        msg_stub = types.ModuleType("tkinter.messagebox")
        ttk_stub = types.ModuleType("tkinter.ttk")

        sys.modules["tkinter"] = tk_stub
        sys.modules["tkinter.messagebox"] = msg_stub
        sys.modules["tkinter.ttk"] = ttk_stub

        try:
            import app_gui  # type: ignore
            return app_gui
        except Exception as second_error:
            raise RuntimeError(
                f"Could not import app_gui. First error: {first_error}. Second error: {second_error}"
            )


app_gui = _safe_import_app_gui()

st.set_page_config(page_title="Result Extractor Streamlit", page_icon="📘", layout="wide")


def init_state():
    defaults = {
        "run_folder": None,
        "semesters": [],
        "status_log": ["Ready."],
        "generated_file": None,
        "generated_name": None,
        "otp_verified": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def log(message: str):
    ts = datetime.now().strftime("%H:%M:%S")
    st.session_state.status_log.insert(0, f"[{ts}] {message}")
    st.session_state.status_log = st.session_state.status_log[:80]


def list_saved_runs():
    runs = []
    if os.path.exists(app_gui.RESP_BASE):
        for name in os.listdir(app_gui.RESP_BASE):
            path = os.path.join(app_gui.RESP_BASE, name)
            if not (os.path.isdir(path) and name.startswith("run_")):
                continue

            sem_folders = []
            for child in os.listdir(path):
                child_path = os.path.join(path, child)
                if os.path.isdir(child_path) and child.startswith("sem_"):
                    sem_folders.append(child)

            sem_folders.sort()
            # Allow rebuild of overall report from saved run
            sem_folders.append("__all_semesters__")

            runs.append(
                {
                    "run_folder": name,
                    "path": path,
                    "sem_folders": sem_folders,
                    "modified": os.path.getmtime(path),
                }
            )
    runs.sort(key=lambda x: x["modified"], reverse=True)
    return runs


def _read_binary(path):
    with open(path, "rb") as f:
        return f.read()


def _progress_callback_factory():
    box = st.empty()

    def callback(message):
        box.info(str(message))
        log(str(message))

    return callback


def do_update_jsession():
    res = app_gui.update_jsession_and_req1()
    if res.get("status") == "success":
        log("JSESSION updated.")
        st.success(res.get("message", "JSESSION updated."))
    else:
        msg = res.get("message", "JSESSION update failed.")
        log(f"JSESSION update failed: {msg}")
        st.error(msg)


def do_send_otp(main_roll: str, otp_mob_roll: str):
    run_folder = app_gui.create_run_folder()
    st.session_state.run_folder = run_folder
    st.session_state.otp_verified = False
    st.session_state.semesters = []

    log(f"Run created: {os.path.basename(run_folder)}")
    log("Step 1: Fetching main roll data...")
    r1 = app_gui.step1_fetch_mbn(main_roll, run_folder)
    if r1.get("status") == "error":
        st.error(r1.get("message", "step1 failed"))
        return

    log("Step 1b: Fetching OTP-mobile roll data...")
    r1b = app_gui.step1_fetch_mymbn(otp_mob_roll, run_folder)
    if r1b.get("status") == "error":
        st.error(r1b.get("message", "step1b failed"))
        return

    log("Step 2: Sending OTP...")
    r2 = app_gui.step2_send_otp(run_folder)
    if r2.get("status") == "error":
        st.error(r2.get("message", "OTP send failed"))
        log(f"OTP send failed: {r2.get('message')}")
        return

    api_resp = str(r2.get("response", "")).strip()
    if api_resp:
        short_resp = api_resp if len(api_resp) <= 300 else (api_resp[:300] + "...")
        log(f"OTP API response: {short_resp}")

    msg = r2.get("msg") or r2.get("message") or "OTP request sent."
    if api_resp and "success" not in api_resp.lower():
        log(f"{msg} (server did not confirm success)")
        st.warning(f"{msg}. Server response: {short_resp}")
    else:
        log(msg)
        st.success(msg)


def do_verify_otp(otp: str):
    run_folder = st.session_state.run_folder
    if not run_folder:
        st.error("Please send OTP first.")
        return

    log("Step 3: Verifying OTP...")
    r3 = app_gui.step3_verify_otp(otp, run_folder)
    if r3.get("status") == "error":
        st.error(r3.get("message", "OTP verify failed"))
        log(f"OTP verify failed: {r3.get('message')}")
        return

    parsed = r3.get("data")
    if isinstance(parsed, dict):
        if parsed.get("success") is False:
            msg = parsed.get("message", "OTP verify failed.")
            st.error(msg)
            log(msg)
            return
        if parsed.get("data") in (None, [], {}):
            msg = parsed.get("message", "OTP verified but no semester data returned.")
            st.error(msg)
            log(msg)
            return

    semesters = app_gui.get_all_semesters(run_folder)
    st.session_state.semesters = semesters
    st.session_state.otp_verified = True
    log(f"OTP verified. Semester options: {len(semesters)}")
    st.success("OTP verified and semesters loaded.")


def do_generate_live(start_roll: int, end_roll: int, sem_value: dict, tone_mode: str, reappear_update_mode: str):
    run_folder = st.session_state.run_folder
    if not run_folder:
        st.error("Please complete OTP flow first.")
        return

    cb = _progress_callback_factory()
    r4 = app_gui.step4_fetch_range(start_roll, end_roll, run_folder, progress_callback=cb)
    if r4.get("status") == "error":
        st.error(r4.get("message", "Range fetch failed"))
        return

    r5 = app_gui.step5_fetch_dmc(
        run_folder,
        sem_value,
        progress_callback=cb,
        reappear_update_mode=reappear_update_mode,
    )
    if r5.get("status") == "error":
        st.error(r5.get("message", "DMC fetch failed"))
        return

    report_mode = "all_semesters" if isinstance(sem_value, dict) and sem_value.get("mode") == "all_semesters" else "single"
    out_file = app_gui.step6_generate_html(
        r5["folder"],
        run_folder,
        progress_callback=cb,
        tone_mode=tone_mode,
        report_mode=report_mode,
        reappear_update_mode=reappear_update_mode,
    )
    st.session_state.generated_file = out_file
    st.session_state.generated_name = os.path.basename(out_file)
    log(f"HTML generated: {out_file}")
    st.success("HTML generated.")


def do_generate_saved(run_name: str, sem_folder: str, tone_mode: str, reappear_update_mode: str):
    run_folder = os.path.join(app_gui.RESP_BASE, run_name)
    if sem_folder == "__all_semesters__":
        data_folder = run_folder
        report_mode = "all_semesters"
    else:
        data_folder = os.path.join(run_folder, sem_folder)
        report_mode = "single"

    cb = _progress_callback_factory()
    out_file = app_gui.step6_generate_html(
        data_folder,
        run_folder,
        progress_callback=cb,
        tone_mode=tone_mode,
        report_mode=report_mode,
        reappear_update_mode=reappear_update_mode,
    )
    st.session_state.generated_file = out_file
    st.session_state.generated_name = f"{run_name}_{sem_folder}_latest.html"
    log(f"Saved run generated: {out_file}")
    st.success("Saved run rebuilt with latest logic.")


def do_wipe_old_data():
    wipe_fn = getattr(app_gui, "wipe_old_data_keep_latest", None)
    if wipe_fn is None:
        st.error("Wipe function not found in app_gui.py")
        return

    result = wipe_fn()
    kept = result.get("run_folder", "none")
    deleted_count = len(result.get("deleted_runs", []))
    failed = result.get("failed_runs", [])
    log(f"Wipe complete. Kept: {kept}. Deleted: {deleted_count}.")
    if failed:
        st.warning(f"Wipe completed with failures: {', '.join(failed)}")
    else:
        st.success("Old run folders deleted, latest kept.")


init_state()

st.title("Result Extractor - Streamlit")
st.caption("Streamlit-compatible UI using the same extraction workflow as app_gui/app_web.")

tone = st.selectbox("Academic Tone", ["motivational", "teacher", "strict"], index=0)

left, right = st.columns([1.2, 0.8], gap="large")

with left:
    st.subheader("Live Flow")
    c1, c2 = st.columns(2)
    with c1:
        main_roll = st.text_input("Main Roll Number")
    with c2:
        otp_mob_roll = st.text_input("OTP Mob Roll Number")

    b1, b2, b3 = st.columns(3)
    with b1:
        if st.button("Update JSESSION", use_container_width=True):
            do_update_jsession()
    with b2:
        if st.button("Send OTP", use_container_width=True):
            if not main_roll.strip() or not otp_mob_roll.strip():
                st.error("Enter both Main Roll and OTP Mob Roll.")
            else:
                do_send_otp(main_roll.strip(), otp_mob_roll.strip())
    with b3:
        otp = st.text_input("OTP", label_visibility="collapsed", placeholder="Enter OTP")
        if st.button("Verify OTP", use_container_width=True):
            if not otp.strip():
                st.error("Enter OTP.")
            else:
                do_verify_otp(otp.strip())

    sem_labels = [x["label"] for x in st.session_state.semesters]
    selected_label = st.selectbox("Semester", options=sem_labels, index=0 if sem_labels else None, placeholder="Verify OTP first")

    r1, r2 = st.columns(2)
    with r1:
        start_roll_txt = st.text_input("Start Roll")
    with r2:
        end_roll_txt = st.text_input("End Roll")

    reappear_mode_label = st.selectbox(
        "Reappear Update Mode",
        [
            "Mode 2 - Keep current semester attempt (no update)",
            "Mode 1 - Update with latest non-empty attempt",
        ],
        index=0,
        key="reappear_mode_select",
        help="Mode 2 will freeze current semester result. Mode 1 will update reappear results with newer non-empty attempts.",
    )
    reappear_mode = "keep_current_sem" if reappear_mode_label.startswith("Mode 2") else "update_latest_non_empty"

    if st.button("Generate HTML (Live)", use_container_width=True):
        if not selected_label:
            st.error("Select semester.")
        elif not start_roll_txt.strip().isdigit() or not end_roll_txt.strip().isdigit():
            st.error("Start/End roll must be numeric.")
        else:
            sem_value = None
            for item in st.session_state.semesters:
                if item["label"] == selected_label:
                    sem_value = item["value"]
                    break
            if sem_value is None:
                st.error("Invalid semester selection.")
            else:
                do_generate_live(int(start_roll_txt.strip()), int(end_roll_txt.strip()), sem_value, tone, reappear_mode)

    st.divider()
    st.subheader("Load Saved Data")
    runs = list_saved_runs()
    run_names = [r["run_folder"] for r in runs]
    selected_run = st.selectbox("Saved Run", options=run_names, index=0 if run_names else None, placeholder="No saved run found")
    selected_run_obj = next((x for x in runs if x["run_folder"] == selected_run), None)
    sem_options = selected_run_obj["sem_folders"] if selected_run_obj else []
    selected_sem_folder = st.selectbox("Saved Semester", options=sem_options, index=0 if sem_options else None, placeholder="Select run first")

    if st.button("Rebuild HTML from Saved JSON", use_container_width=True):
        if not selected_run or not selected_sem_folder:
            st.error("Select saved run and semester.")
        else:
            do_generate_saved(selected_run, selected_sem_folder, tone, reappear_mode)

with right:
    st.subheader("Storage Management")
    confirm = st.checkbox("I understand old run folders will be deleted (latest will be kept).")
    if st.button("Wipe Old Data", use_container_width=True):
        if not confirm:
            st.warning("Please confirm before wipe.")
        else:
            do_wipe_old_data()

    st.subheader("Downloads")
    out_file = st.session_state.generated_file
    if out_file and os.path.exists(out_file):
        st.download_button(
            "Download Latest HTML",
            data=_read_binary(out_file),
            file_name=st.session_state.generated_name or "combined_result.html",
            mime="text/html",
            use_container_width=True,
        )
        st.code(out_file)
    else:
        st.info("No generated file yet.")

    st.subheader("Live Console")
    for line in st.session_state.status_log:
        st.write(line)
