# app.py (PART 1 - CORE SETUP + FIXED LOGIC)
print("🔥 FILE STARTED")

from flask import Flask, render_template, request, jsonify, send_file
import requests
import json
import re
import os
import shutil
import threading
import subprocess
import urllib3
import xml.etree.ElementTree as ET
from datetime import datetime
from html import escape
from io import BytesIO
import base64
import tkinter as tk
from tkinter import messagebox, ttk

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:
    plt = None

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

PROGRESS_LOG = []
PROGRESS_SEQ = 0

# ----------------------------
# PATH SETUP (PORTABLE)
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

REQ_FOLDER = os.path.join(BASE_DIR, "requests")
RESP_BASE = os.path.join(REQ_FOLDER, "responses")
TEMPLATE_FILE = os.path.join(BASE_DIR, "template.html")
COMBINED_BASE = os.path.join(BASE_DIR, "combined")

if not os.path.exists(TEMPLATE_FILE):
    TEMPLATE_FILE = os.path.join(BASE_DIR, "templates", "template.html")

os.makedirs(RESP_BASE, exist_ok=True)
os.makedirs(COMBINED_BASE, exist_ok=True)

# ----------------------------
# CREATE UNIQUE RUN FOLDER
# ----------------------------
def create_run_folder():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESP_BASE, f"run_{ts}")
    os.makedirs(path, exist_ok=True)
    return path


def push_progress(message):
    global PROGRESS_SEQ
    PROGRESS_SEQ += 1
    PROGRESS_LOG.append({"id": PROGRESS_SEQ, "message": str(message)})
    if len(PROGRESS_LOG) > 400:
        del PROGRESS_LOG[:200]


# ----------------------------
# LOAD REQUEST HEADERS
# ----------------------------
def load_request(file):
    with open(file, "r", encoding="utf-8") as f:
        raw = f.read()

    lines = raw.splitlines()
    method, path, _ = lines[0].split()

    headers = {}
    for line in lines[1:]:
        if line.strip() == "":
            break
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()

    headers.pop("Content-Length", None)

    req1_file = os.path.join(REQ_FOLDER, "req1.txt")
    if os.path.exists(req1_file):
        with open(req1_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.lower().startswith("cookie:"):
                    headers["Cookie"] = line.split(":", 1)[1].strip()
                    break

    return method, path, headers


def update_jsession_and_req1():
    try:
        session = requests.Session()
        session.get("https://iums.kuk.ac.in/", verify=False, timeout=15)
        jsession = session.cookies.get("JSESSIONID")
        session.get("https://iums.kuk.ac.in/anon_studentResultReport.htm", verify=False, timeout=15)

        os.makedirs(REQ_FOLDER, exist_ok=True)
        jsession_path = os.path.join(REQ_FOLDER, "jsession.txt")
        with open(jsession_path, "w", encoding="utf-8") as f:
            if jsession:
                f.write(jsession)

        if not jsession:
            return {"status": "error", "message": "JSESSIONID not found from server response."}

        req1_path = os.path.join(REQ_FOLDER, "req1.txt")
        if not os.path.exists(req1_path):
            return {"status": "error", "message": "req1.txt not found in requests folder."}

        with open(req1_path, "r", encoding="utf-8") as f:
            raw = f.read()

        if re.search(r"JSESSIONID=[^;\s]+", raw):
            updated = re.sub(r"(JSESSIONID=)[^;\s]+", r"\1" + jsession, raw, count=1)
        elif re.search(r"(?im)^Cookie:\s*(.*)$", raw):
            updated = re.sub(r"(?im)^Cookie:\s*(.*)$", lambda m: f"Cookie: {m.group(1).strip()}; JSESSIONID={jsession}", raw, count=1)
        else:
            updated = raw.rstrip() + f"\nCookie: JSESSIONID={jsession}\n"

        with open(req1_path, "w", encoding="utf-8") as f:
            f.write(updated)

        return {"status": "success", "jsession": jsession, "message": "JSESSION updated successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ----------------------------
# STEP 1: FETCH MBN
# ----------------------------
def step1_fetch_mbn(roll, run_folder):
    try:
        method, path, headers = load_request(os.path.join(REQ_FOLDER, "req1.txt"))
        host = headers.get("Host")

        new_path = re.sub(r"examRollNumber=\d+", f"examRollNumber={roll}", path)
        url = f"https://{host}{new_path}"

        res = requests.get(url, headers=headers, verify=False, timeout=10)
        raw_text = (res.text or "").strip()
        try:
            parsed = res.json()
        except Exception:
            short = raw_text[:300] + ("..." if len(raw_text) > 300 else "")
            return {"status": "error", "message": f"Server returned non-JSON/empty response (HTTP {res.status_code}). Response: {short or '<empty>'}"}

        out = os.path.join(run_folder, "res_mbn.json")
        with open(out, "w") as f:
            json.dump(parsed, f, indent=4)

        return {"status": "success", "mbn": parsed}

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ----------------------------
# STEP 2: SEND OTP
# ----------------------------
def step2_send_otp(run_folder):
    try:
        with open(os.path.join(run_folder, "res_mbn.json"), "r", encoding="utf-8") as f:
            result_data = json.load(f)
        with open(os.path.join(run_folder, "res_mymbn.json"), "r", encoding="utf-8") as f:
            otp_data = json.load(f)

        std = result_data[0].get("std") if isinstance(result_data, list) else result_data.get("std")
        mbn = otp_data[0].get("mbn") if isinstance(otp_data, list) else otp_data.get("mbn")

        # ----------------------------
        # LOAD REQ2
        # ----------------------------
        with open(os.path.join(REQ_FOLDER, "req2.txt"), "r", encoding="utf-8") as f:
            raw = f.read()

        lines = raw.splitlines()

        method, path, _ = lines[0].split()

        headers = {}
        for line in lines[1:]:
            if line.strip() == "":
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()

        headers.pop("Content-Length", None)

        # ----------------------------
        # 🔥 LOAD COOKIE FROM req1.txt EXACTLY LIKE ORIGINAL
        # ----------------------------
        cookie_value = None

        with open(os.path.join(REQ_FOLDER, "req1.txt"), "r", encoding="utf-8") as f:
            for line in f:
                if line.lower().startswith("cookie:"):
                    cookie_value = line.split(":", 1)[1].strip()
                    break

        if cookie_value:
            headers["Cookie"] = cookie_value
        else:
            return {"status": "error", "message": "Cookie missing"}

        host = headers.get("Host")

        # ----------------------------
        # 🔥 EXACT SAME REPLACE LOGIC
        # ----------------------------
        new_path = re.sub(
            r"__mobileNo=[^&]+",
            f"__mobileNo={mbn}",
            path
        )
        if std:
            new_path = re.sub(r"__std=[^&]+", f"__std={std}", new_path)

        url = f"https://{host}{new_path}"

        print("\n======= OTP DEBUG =======")
        print("URL:", url)
        print("HEADERS:", headers)

        # ----------------------------
        # SEND REQUEST
        # ----------------------------
        response = requests.get(
            url,
            headers=headers,
            verify=False,
            timeout=10
        )

        print("RESPONSE:", response.text)
        print("=========================\n")

        return {
            "status": "success",
            "message": "OTP Attempted"
        }

    except Exception as e:
        return {"status": "error", "message": str(e)}

# ----------------------------
# STEP 3: VERIFY OTP
# ----------------------------
def step3_verify_otp(otp, run_folder):
    try:
        with open(os.path.join(run_folder, "res_mbn.json"), "r", encoding="utf-8") as f:
            result_data = json.load(f)
        with open(os.path.join(run_folder, "res_mymbn.json"), "r", encoding="utf-8") as f:
            otp_data = json.load(f)

        std = result_data[0]["std"]
        mbn = otp_data[0]["mbn"]

        method, path, headers = load_request(os.path.join(REQ_FOLDER, "req3.txt"))
        headers.pop("Content-Length", None)

        cookie_value = None
        with open(os.path.join(REQ_FOLDER, "req1.txt"), "r", encoding="utf-8") as f:
            for line in f:
                if line.lower().startswith("cookie:"):
                    cookie_value = line.split(":", 1)[1].strip()
                    break

        if cookie_value:
            headers["Cookie"] = cookie_value
        else:
            return {"status": "error", "message": "Cookie missing"}

        host = headers.get("Host")

        new_path = path
        new_path = re.sub(r"__std=[^&]+", f"__std={std}", new_path)
        new_path = re.sub(r"__mobileNo=[^&]+", f"__mobileNo={mbn}", new_path)
        new_path = re.sub(r"authValue=[^&]+", f"authValue={otp}", new_path)

        url = f"https://{host}{new_path}"

        res = requests.get(url, headers=headers, verify=False, timeout=10)
        raw_text = (res.text or "").strip()
        try:
            parsed = res.json()
        except Exception:
            short = raw_text[:300] + ("..." if len(raw_text) > 300 else "")
            return {"status": "error", "message": f"Server returned non-JSON/empty response (HTTP {res.status_code}). Response: {short or '<empty>'}"}

        # flatten same as your code
        if isinstance(parsed, list) and len(parsed) > 0:
            if isinstance(parsed[0], list):
                parsed = parsed[0][0]

        out = os.path.join(run_folder, "res_result.json")
        with open(out, "w") as f:
            json.dump(parsed, f, indent=4)

        return {"status": "success", "data": parsed}

    except Exception as e:
        return {"status": "error", "message": str(e)}
    

    # app.py (PART 1 - CORE SETUP + FIXED LOGIC)

from flask import Flask, render_template, request, jsonify, send_file
import requests
import json
import re
import os
import urllib3
import xml.etree.ElementTree as ET
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)

# ----------------------------
# PATH SETUP (PORTABLE)
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

REQ_FOLDER = os.path.join(BASE_DIR, "requests")
RESP_BASE = os.path.join(REQ_FOLDER, "responses")
TEMPLATE_FILE = os.path.join(BASE_DIR, "template.html")
COMBINED_BASE = os.path.join(BASE_DIR, "combined")

if not os.path.exists(TEMPLATE_FILE):
    TEMPLATE_FILE = os.path.join(BASE_DIR, "templates", "template.html")

os.makedirs(RESP_BASE, exist_ok=True)
os.makedirs(COMBINED_BASE, exist_ok=True)

SUBJECT_STRENGTH_PROFILES = {
    "B23-GEO-104": {
        "label": "geographical awareness",
        "compliment": "shows strong spatial understanding and a solid grasp of environmental patterns",
    },
    "B23-CAP-102": {
        "label": "computing fundamentals",
        "compliment": "shows a reliable foundation in core computer science thinking",
    },
    "B23-CAP-101": {
        "label": "programming logic",
        "compliment": "shows promising coding logic and hands-on problem solving ability",
    },
    "B23-CAP-103": {
        "label": "system design thinking",
        "compliment": "shows clear analytical thinking in computer organization and logic building",
    },
    "B23-ECO-104": {
        "label": "economic awareness",
        "compliment": "shows a practical understanding of economic basics and decision making",
    },
    "B23-SEC-101": {
        "label": "digital productivity",
        "compliment": "shows useful practical skill in digital tools and workplace-style tasks",
    },
    "B23-PHY-104": {
        "label": "scientific reasoning",
        "compliment": "shows disciplined scientific reasoning and concept control",
    },
    "B23-SKT-103": {
        "label": "language discipline",
        "compliment": "shows strong language discipline and attention to structured expression",
    },
    "B23-HIN-104": {
        "label": "linguistic clarity",
        "compliment": "shows confidence in language expression and communication",
    },
    "B23-POL-104": {
        "label": "civic understanding",
        "compliment": "shows awareness of governance, structure, and public systems",
    },
    "B23-AEC-E111": {
        "label": "communication skills",
        "compliment": "shows developing communication ability and expressive clarity",
    },
    "B23-CAP-104": {
        "label": "mathematical reasoning",
        "compliment": "shows strong logical discipline and mathematical problem framing",
    },
    "B23-VAC-201": {
        "label": "environmental awareness",
        "compliment": "shows thoughtful awareness of sustainability and social responsibility",
    },
}

SUBJECT_IMPROVEMENT_PROFILES = {
    "B23-GEO-104": "Strengthen map practice, regional pattern revision, and short concept notes for physical features.",
    "B23-CAP-102": "Focus on core definitions, concept linking, and regular revision of computer science fundamentals.",
    "B23-CAP-101": "Increase hands-on coding practice, dry-run more problems, and revise syntax with logic building.",
    "B23-CAP-103": "Revise architecture diagrams, number systems, and logic flow so concepts become easier to apply.",
    "B23-ECO-104": "Practice simple economic examples and revise the meaning behind basic economic terms regularly.",
    "B23-SEC-101": "Build speed and accuracy through repeated spreadsheet and office-tool exercises.",
    "B23-PHY-104": "Work on formula revision, unit-based problem solving, and stepwise concept application.",
    "B23-SKT-103": "Improve recall with small daily language practice and repeated reading of key forms and structures.",
    "B23-HIN-104": "Strengthen writing clarity and regular reading practice to improve confidence in expression.",
    "B23-POL-104": "Revise constitutional structure, definitions, and key polity themes through short repeated notes.",
    "B23-AEC-E111": "Focus on communication basics, vocabulary clarity, and repeated writing-speaking practice.",
    "B23-CAP-104": "Improve stepwise mathematics practice and revise foundational logic with solved examples.",
    "B23-VAC-201": "Use concise revision sheets to improve retention of core environmental themes and applications.",
}

# ----------------------------
# CREATE UNIQUE RUN FOLDER
# ----------------------------
def create_run_folder():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(RESP_BASE, f"run_{ts}")
    os.makedirs(path, exist_ok=True)
    return path


# ----------------------------
# LOAD REQUEST HEADERS
# ----------------------------
def load_request(file):
    with open(file, "r", encoding="utf-8") as f:
        raw = f.read()

    lines = raw.splitlines()
    method, path, _ = lines[0].split()

    headers = {}
    for line in lines[1:]:
        if line.strip() == "":
            break
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip()] = v.strip()

    headers.pop("Content-Length", None)

    req1_file = os.path.join(REQ_FOLDER, "req1.txt")
    if os.path.exists(req1_file):
        with open(req1_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.lower().startswith("cookie:"):
                    headers["Cookie"] = line.split(":", 1)[1].strip()
                    break

    return method, path, headers


# ----------------------------
# STEP 1: FETCH MBN
# ----------------------------
def step1_fetch_mbn(roll, run_folder):
    try:
        method, path, headers = load_request(os.path.join(REQ_FOLDER, "req1.txt"))
        host = headers.get("Host")

        new_path = re.sub(r"examRollNumber=\d+", f"examRollNumber={roll}", path)
        url = f"https://{host}{new_path}"

        res = requests.get(url, headers=headers, verify=False, timeout=10)
        raw_text = (res.text or "").strip()
        try:
            parsed = res.json()
        except Exception:
            short = raw_text[:300] + ("..." if len(raw_text) > 300 else "")
            return {"status": "error", "message": f"Server returned non-JSON/empty response (HTTP {res.status_code}). Response: {short or '<empty>'}"}

        out = os.path.join(run_folder, "res_mbn.json")
        with open(out, "w") as f:
            json.dump(parsed, f, indent=4)

        return {"status": "success", "mbn": parsed}

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ----------------------------
# STEP 2: SEND OTP
# ----------------------------
def step2_send_otp(run_folder):
    try:
        with open(os.path.join(run_folder, "res_mbn.json"), "r", encoding="utf-8") as f:
            result_data = json.load(f)
        with open(os.path.join(run_folder, "res_mymbn.json"), "r", encoding="utf-8") as f:
            otp_data = json.load(f)

        std = result_data[0].get("std") if isinstance(result_data, list) else result_data.get("std")
        mbn = otp_data[0].get("mbn") if isinstance(otp_data, list) else otp_data.get("mbn")

        with open(os.path.join(REQ_FOLDER, "req2.txt"), "r", encoding="utf-8") as f:
            raw = f.read()

        lines = raw.splitlines()
        method, path, _ = lines[0].split()

        headers = {}
        for line in lines[1:]:
            if line.strip() == "":
                break
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip()] = v.strip()

        headers.pop("Content-Length", None)

        cookie_value = None
        with open(os.path.join(REQ_FOLDER, "req1.txt"), "r", encoding="utf-8") as f:
            for line in f:
                if line.lower().startswith("cookie:"):
                    cookie_value = line.split(":", 1)[1].strip()
                    break

        if cookie_value:
            headers["Cookie"] = cookie_value
        else:
            return {"status": "error", "message": "Cookie missing"}

        host = headers.get("Host")
        new_path = re.sub(r"__mobileNo=[^&]+", f"__mobileNo={mbn}", path)
        if std:
            new_path = re.sub(r"__std=[^&]+", f"__std={std}", new_path)
        url = f"https://{host}{new_path}"

        res = requests.get(url, headers=headers, verify=False, timeout=10)

        return {"status": "success", "msg": "OTP Sent", "response": res.text}

    except Exception as e:
        return {"status": "error", "message": str(e)}


def wipe_old_data_keep_latest(keep_run_folder=None):
    kept = {
        "run_folder": None,
        "deleted_runs": [],
        "failed_runs": [],
        "resp_base": RESP_BASE,
    }

    def remove_tree(path):
        if not os.path.exists(path):
            return
        def onerror(func, p, exc):
            try:
                os.chmod(p, 0o777)
                func(p)
            except Exception:
                pass
        try:
            shutil.rmtree(path, ignore_errors=False, onerror=onerror)
        except Exception:
            pass
        if os.path.exists(path):
            try:
                subprocess.run(["cmd", "/c", "rmdir", "/s", "/q", path], check=False, capture_output=True)
            except Exception:
                pass

    run_dirs = []
    if os.path.exists(RESP_BASE):
        for name in os.listdir(RESP_BASE):
            path = os.path.join(RESP_BASE, name)
            if os.path.isdir(path) and name.startswith("run_"):
                run_dirs.append((name, path))

    # Keep only the latest run folder by run timestamp encoded in its name.
    run_dirs.sort(key=lambda row: row[0], reverse=True)
    selected_keep = run_dirs[0] if run_dirs else None

    if selected_keep:
        kept["run_folder"] = selected_keep[0]

    for name, path in run_dirs:
        if selected_keep and name == selected_keep[0]:
            continue
        try:
            remove_tree(path)
            if not os.path.exists(path):
                kept["deleted_runs"].append(name)
            else:
                kept["failed_runs"].append(name)
        except Exception:
            kept["failed_runs"].append(name)

    return kept


def step1_fetch_mymbn(roll, run_folder):
    try:
        method, path, headers = load_request(os.path.join(REQ_FOLDER, "req_mymbn.txt"))
        host = headers.get("Host")

        new_path = re.sub(r"examRollNumber=\d+", f"examRollNumber={roll}", path)
        url = f"https://{host}{new_path}"

        res = requests.get(url, headers=headers, verify=False, timeout=10)
        raw_text = (res.text or "").strip()
        try:
            parsed = res.json()
        except Exception:
            short = raw_text[:300] + ("..." if len(raw_text) > 300 else "")
            return {"status": "error", "message": f"Server returned non-JSON/empty response (HTTP {res.status_code}). Response: {short or '<empty>'}"}

        run_out = os.path.join(run_folder, "res_mymbn.json")
        with open(run_out, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=4)

        shared_out = os.path.join(RESP_BASE, "res_mymbn.json")
        with open(shared_out, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=4)

        return {"status": "success", "mbn": parsed}

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ----------------------------
# STEP 3: VERIFY OTP
# ----------------------------
def step3_verify_otp(otp, run_folder):
    try:
        with open(os.path.join(run_folder, "res_mbn.json"), "r", encoding="utf-8") as f:
            result_data = json.load(f)
        with open(os.path.join(run_folder, "res_mymbn.json"), "r", encoding="utf-8") as f:
            otp_data = json.load(f)

        std = result_data[0].get("std") if isinstance(result_data, list) else result_data.get("std")
        mbn = otp_data[0].get("mbn") if isinstance(otp_data, list) else otp_data.get("mbn")
        if not std:
            return {"status": "error", "message": "STD value missing in res_mbn.json"}
        if not mbn:
            return {"status": "error", "message": "Mobile/MBN value missing in res_mymbn.json"}

        method, path, headers = load_request(os.path.join(REQ_FOLDER, "req3.txt"))
        headers.pop("Content-Length", None)

        cookie_value = None
        with open(os.path.join(REQ_FOLDER, "req1.txt"), "r", encoding="utf-8") as f:
            for line in f:
                if line.lower().startswith("cookie:"):
                    cookie_value = line.split(":", 1)[1].strip()
                    break

        if cookie_value:
            headers["Cookie"] = cookie_value
        else:
            return {"status": "error", "message": "Cookie missing"}

        host = headers.get("Host")

        new_path = path
        new_path = re.sub(r"__std=[^&]+", f"__std={std}", new_path)
        new_path = re.sub(r"__mobileNo=[^&]+", f"__mobileNo={mbn}", new_path)
        new_path = re.sub(r"authValue=[^&]+", f"authValue={otp}", new_path)

        url = f"https://{host}{new_path}"

        res = requests.get(url, headers=headers, verify=False, timeout=10)
        raw_text = (res.text or "").strip()
        try:
            parsed = res.json()
        except Exception:
            short = raw_text[:300] + ("..." if len(raw_text) > 300 else "")
            return {"status": "error", "message": f"Server returned non-JSON/empty response (HTTP {res.status_code}). Response: {short or '<empty>'}"}

        # flatten same as your code
        if isinstance(parsed, list) and len(parsed) > 0:
            if isinstance(parsed[0], list):
                parsed = parsed[0][0]

        out = os.path.join(run_folder, "res_result.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=4)

        shared_out = os.path.join(RESP_BASE, "res_result.json")
        with open(shared_out, "w", encoding="utf-8") as f:
            json.dump(parsed, f, indent=4)

        return {"status": "success", "data": parsed}

    except Exception as e:
        return {"status": "error", "message": str(e)}
    


    # ----------------------------
# GET ALL SEM OPTIONS (FIXED)
# ----------------------------
def get_all_semesters(run_folder):
    path = os.path.join(run_folder, "res_result.json")

    with open(path) as f:
        data = json.load(f)

    sem_list = []
    raw_sem_items = []

    def result_priority(result_text, is_generated=True):
        if not is_generated:
            return 0
        raw = (result_text or "").strip().lower()
        if raw in {"", "payment_done"}:
            return 0
        class_name = get_result_class(result_text or "")
        priority = {
            "status-pass": 5,
            "status-neutral": 4,
            "status-reappear": 3,
            "status-fail": 2,
            "status-rl": 1,
            "status-ab": 2,
        }
        return priority.get(class_name, 0)

    latest_map = {}

    def parse_sem_no(sem_name, fallback):
        text = str(sem_name or "").upper().strip()
        roman_map = {
            "SEMESTER-I": 1, "SEMESTER-II": 2, "SEMESTER-III": 3, "SEMESTER-IV": 4, "SEMESTER-V": 5,
            "SEMESTER-VI": 6, "SEMESTER-VII": 7, "SEMESTER-VIII": 8, "SEMESTER-IX": 9, "SEMESTER-X": 10
        }
        if text in roman_map:
            return roman_map[text]
        plain_roman = {
            "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
            "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10
        }
        if text in plain_roman:
            return plain_roman[text]
        match = re.search(r"(\d+)", text)
        if match:
            return int(match.group(1))
        return int(fallback) if str(fallback).isdigit() else None

    for sem in data["data"]:
        name = sem.get("semName")
        status = sem.get("semesterResult") or sem.get("resultStatus")
        no_of_sem = sem.get("noOfSem")

        label = f"{name} - {status}"

        if sem.get("examTypeKey") == "REAPPEAR":
            label += " (Reappear)"

        item_value = {
            "qlId": sem.get("qlId"),
            "usyId": sem.get("usyId"),
            "smId": sem.get("smId"),
            "esId": sem.get("esId"),
            "noOfSem": no_of_sem,
            "semNo": parse_sem_no(name, no_of_sem),
            "semName": name,
            "semesterResult": status,
            "isResultGenerated": bool(sem.get("isResultGenerated")),
            "examTypeKey": sem.get("examTypeKey"),
        }

        sem_list.append({
            "label": label,
            "value": item_value
        })
        raw_sem_items.append(item_value)

        # Override only within the same semester number.
        # This prevents semester V from replacing semester I/II/III/IV.
        sem_no = item_value.get("semNo")
        group_key = str(sem_no if sem_no is not None else (name or sem.get("smId") or no_of_sem))
        raw_status = " ".join(str(status or "").strip().lower().split())
        is_declared = bool(item_value["isResultGenerated"]) and raw_status not in {"", "payment_done"} and "not declared" not in raw_status

        es_id_text = str(item_value.get("esId") or "")
        sm_id_text = str(item_value.get("smId") or "")
        es_id_num = int(es_id_text) if es_id_text.isdigit() else -1
        sm_id_num = int(sm_id_text) if sm_id_text.isdigit() else -1

        # Selection rule per semester:
        # 1) prefer declared/non-blank result
        # 2) prefer latest attempt id (esId/smId)
        # 3) prefer reappear only as tie-break (same recency)
        # 4) use result class only as last fallback
        candidate_score = (
            1 if is_declared else 0,
            es_id_num,
            sm_id_num,
            1 if (item_value.get("examTypeKey") == "REAPPEAR" and is_declared) else 0,
            result_priority(status, item_value["isResultGenerated"]),
        )

        current = latest_map.get(group_key)
        candidate = {"score": candidate_score, "value": item_value}
        if current is None or candidate["score"] > current["score"]:
            latest_map[group_key] = candidate

    latest_values = [
        item["value"]
        for _, item in sorted(
            latest_map.items(),
            key=lambda kv: (
                int(str(kv[1]["value"].get("noOfSem") or 9999))
                if str(kv[1]["value"].get("noOfSem") or "").isdigit()
                else 9999,
                int(str(kv[1]["value"].get("semNo") or 9999))
                if str(kv[1]["value"].get("semNo") or "").isdigit()
                else 9999,
                str(kv[1]["value"].get("semName") or ""),
            ),
        )
    ]

    if latest_values:
        sem_list.append({
            "label": "Overall Academic Record (Latest Valid Results)",
            "value": {
                "mode": "all_semesters",
                "items": latest_values,
                "raw_items": raw_sem_items,
            }
        })

    return sem_list





# ----------------------------
# STEP 4: FETCH RANGE + XML
# ----------------------------
def step4_fetch_range(start_roll, end_roll, run_folder, progress_callback=None):
    try:
        method, path, headers = load_request(os.path.join(REQ_FOLDER, "req1.txt"))
        host = headers.get("Host")

        xml_path = os.path.join(run_folder, "data.xml")
        root = ET.Element("items")

        total_rolls = (end_roll - start_roll) + 1

        for index, roll in enumerate(range(start_roll, end_roll + 1), start=1):
            if progress_callback:
                progress_callback(f"Fetching roll range data: {index}/{total_rolls} (roll {roll})")

            url = f"https://{host}/restApi/result/verify-student.json?examRollNumber={roll}"

            try:
                res = requests.get(url, headers=headers, verify=False, timeout=10)
                text = res.text

                match = re.search(r"\[\{.*?\}\]", text, re.DOTALL)
                if not match:
                    continue

                json_text = match.group(0)
                if json_text.strip() == "[]":
                    continue

                item = ET.SubElement(root, "item")
                ET.SubElement(item, "url").text = url
                ET.SubElement(item, "response").text = json_text

            except:
                continue

        tree = ET.ElementTree(root)
        tree.write(xml_path, encoding="utf-8", xml_declaration=True)

        if progress_callback:
            progress_callback("Roll range fetch complete.")

        return {"status": "success", "xml": xml_path}

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ----------------------------
# STEP 5: FETCH DMC (FIXED SEM)
# ----------------------------
def step5_fetch_dmc(run_folder, sem_data, progress_callback=None, reappear_update_mode="update_latest_non_empty"):
    try:
        xml_path = os.path.join(run_folder, "data.xml")

        method, path, headers = load_request(os.path.join(REQ_FOLDER, "req1.txt"))
        host = headers.get("Host")

        url = f"https://{host}/restApi/fetchStudentDmcReport.json"

        tree = ET.parse(xml_path)
        root = tree.getroot()

        items = root.findall("item")
        total_items = len(items)

        semester_items = [sem_data]
        mode = "single"
        if isinstance(sem_data, dict) and sem_data.get("mode") == "all_semesters":
            semester_items = sem_data.get("raw_items") or sem_data.get("items") or []
            mode = "all_semesters"
        elif isinstance(sem_data, dict):
            # Single semester fetch: auto-expand to latest-valid chain for same semester
            # (Sem -> Reappear -> Reappear next...), then resolve with update rules.
            sem_no = sem_data.get("semNo")
            if sem_no is None:
                sem_name = str(sem_data.get("semName") or "").upper().strip()
                roman = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
                if sem_name.startswith("SEMESTER-"):
                    sem_name = sem_name.split("SEMESTER-", 1)[1].strip()
                if sem_name in roman:
                    sem_no = roman[sem_name]
                else:
                    m = re.search(r"(\d+)", sem_name)
                    if m:
                        sem_no = int(m.group(1))

            result_index_path = os.path.join(run_folder, "res_result.json")
            chain_items = []
            if sem_no is not None and os.path.exists(result_index_path):
                try:
                    with open(result_index_path, "r", encoding="utf-8") as f:
                        index_data = json.load(f)
                    for entry in index_data.get("data", []):
                        entry_name = str(entry.get("semName") or "").upper().strip()
                        entry_no = None
                        roman = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
                        if entry_name.startswith("SEMESTER-"):
                            entry_name = entry_name.split("SEMESTER-", 1)[1].strip()
                        if entry_name in roman:
                            entry_no = roman[entry_name]
                        else:
                            m = re.search(r"(\d+)", entry_name)
                            if m:
                                entry_no = int(m.group(1))
                            else:
                                no_txt = str(entry.get("noOfSem") or "")
                                if no_txt.isdigit():
                                    entry_no = int(no_txt)
                        if entry_no != sem_no:
                            continue
                        chain_items.append({
                            "qlId": entry.get("qlId"),
                            "usyId": entry.get("usyId"),
                            "smId": entry.get("smId"),
                            "esId": entry.get("esId"),
                            "noOfSem": entry.get("noOfSem"),
                            "semNo": sem_no,
                            "semName": entry.get("semName"),
                            "semesterResult": entry.get("semesterResult") or entry.get("resultStatus"),
                            "isResultGenerated": bool(entry.get("isResultGenerated")),
                            "examTypeKey": entry.get("examTypeKey"),
                        })
                except Exception:
                    chain_items = []

            if len(chain_items) > 1 and reappear_update_mode == "update_latest_non_empty":
                # Mode 1: walk full same-semester chain (older -> newer) and resolve latest valid attempt.
                chain_items.sort(key=lambda row: int(str(row.get("esId") or 0)) if str(row.get("esId") or "").isdigit() else 0)
                semester_items = chain_items
                mode = "single_latest"
            elif reappear_update_mode == "keep_current_sem":
                # Mode 2: do not walk reappear chain; fetch only selected/current semester item.
                semester_items = [sem_data]
                mode = "single"

        if mode == "all_semesters":
            uniq = {}
            for item in semester_items:
                key = (
                    str(item.get("qlId") or ""),
                    str(item.get("usyId") or ""),
                    str(item.get("smId") or ""),
                    str(item.get("esId") or ""),
                )
                uniq[key] = item
            semester_items = list(uniq.values())
            semester_items.sort(key=lambda row: (
                int(str(row.get("semNo") or 9999)) if str(row.get("semNo") or "").isdigit() else 9999,
                int(str(row.get("esId") or 999999999)) if str(row.get("esId") or "").isdigit() else 999999999,
            ))

        total_semesters = max(1, len(semester_items))

        def is_effectively_empty_payload(parsed_payload, raw_text):
            # JSON-empty shapes that should never override valid semester data.
            if parsed_payload == []:
                return True
            if isinstance(parsed_payload, list) and len(parsed_payload) == 1:
                inner = parsed_payload[0]
                if isinstance(inner, list) and len(inner) == 0:
                    return True

            # Raw text fallback: newline/space tolerant matches for [] and [[]].
            compact = re.sub(r"\s+", "", str(raw_text or ""))
            if compact in {"[]", "[[]]"}:
                return True
            return False

        def folder_for_sem(sem_item, sem_index):
            sem_no = sem_item.get("semNo")
            es_id = sem_item.get("esId")
            sm_id = sem_item.get("smId")
            if isinstance(sem_data, dict) and sem_data.get("mode") == "all_semesters":
                return os.path.join(run_folder, f"sem_{sem_no or sem_index}_{sm_id}_{es_id}")
            return os.path.join(run_folder, f"sem_{sm_id}")

        def parsed_result_class(parsed_payload):
            try:
                student = parsed_payload[0][0]
                sem_info = {}
                if student.get("studentSemesterArray"):
                    sem_info = student["studentSemesterArray"][0] or {}
                sem_result = str(sem_info.get("semester_result", "") or "")
                return get_result_class(sem_result)
            except Exception:
                return "status-neutral"

        def _to_int(value):
            try:
                txt = str(value).strip()
                return int(txt) if txt and txt.isdigit() else None
            except Exception:
                return None

        def payload_matches_selected_sem(parsed_payload, sem_item):
            """
            Mode-2 safety:
            keep JSON only if payload clearly belongs to selected exam-schedule/semester.
            """
            try:
                student = parsed_payload[0][0]
            except Exception:
                return False

            sem_info = {}
            try:
                arr = student.get("studentSemesterArray") or []
                if arr and isinstance(arr[0], dict):
                    sem_info = arr[0]
            except Exception:
                sem_info = {}

            req_es = _to_int(sem_item.get("esId"))
            req_sm = _to_int(sem_item.get("smId"))
            req_no = _to_int(sem_item.get("noOfSem") or sem_item.get("semNo"))

            got_es = _to_int(
                sem_info.get("examScheduleId")
                or sem_info.get("exam_schedule_id")
                or sem_info.get("esId")
                or student.get("examScheduleId")
            )
            got_sm = _to_int(
                sem_info.get("semesterId")
                or sem_info.get("semester_id")
                or sem_info.get("smId")
            )
            got_no = _to_int(
                sem_info.get("noOfSem")
                or sem_info.get("semNo")
                or sem_info.get("semesterNo")
            )

            # Strict checks when response provides ids.
            if req_es is not None and got_es is not None and req_es != got_es:
                return False
            if req_sm is not None and got_sm is not None and req_sm != got_sm:
                return False
            if req_no is not None and got_no is not None and req_no != got_no:
                return False

            # If ids are absent in payload, fallback to semester text check.
            if got_no is None and req_no is not None:
                sem_txt = str(student.get("semester", "") or sem_info.get("semester", "")).upper().strip()
                roman = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10}
                sem_txt = sem_txt.replace("SEMESTER-", "").strip()
                txt_no = roman.get(sem_txt)
                if txt_no is not None and txt_no != req_no:
                    return False

            return True

        if mode == "single_latest":
            target_sm = sem_data.get("smId") if isinstance(sem_data, dict) else None
            if not target_sm and semester_items:
                target_sm = semester_items[0].get("smId")
            final_folder = os.path.join(run_folder, f"sem_{target_sm}")
            os.makedirs(final_folder, exist_ok=True)

            for index, item in enumerate(items, start=1):
                response = item.find("response").text
                url_text = item.find("url").text
                roll_match = re.search(r"examRollNumber=(\d+)", url_text)
                roll = roll_match.group(1) if roll_match else "unknown"

                try:
                    data = json.loads(response)
                    std = data[0].get("std")
                except Exception:
                    continue

                chosen_payload = None
                chosen_class = "status-neutral"
                chosen_attempt_no = None

                for sem_index, sem_item in enumerate(semester_items, start=1):
                    post_data = {
                        "qualificationId": sem_item["qlId"],
                        "syllbusId": sem_item["usyId"],
                        "semesterId": sem_item["smId"],
                        "examScheduleId": sem_item["esId"],
                        "noOfSem": sem_item["noOfSem"],
                        "studentRegIds": std,
                        "stdOpenResFlag": "true"
                    }

                    try:
                        if progress_callback:
                            progress_callback(
                                f"Fetching DMC JSON: semester {sem_index}/{total_semesters}, roll {index}/{total_items} ({roll})"
                            )
                        res = requests.post(url, headers=headers, data=post_data, verify=False)
                        parsed = json.loads(res.text)

                        # Empty payload means latest attempt is not declared; stop chain and keep current chosen result.
                        if is_effectively_empty_payload(parsed, res.text):
                            if progress_callback:
                                progress_callback(f"Sem {sem_item.get('noOfSem', sem_index)} - {roll} empty (latest not declared), chain stopped")
                            break

                        new_class = parsed_result_class(parsed)
                        if chosen_payload is None:
                            chosen_payload = parsed
                            chosen_class = new_class
                            chosen_attempt_no = sem_index
                            continue

                        if reappear_update_mode == "update_latest_non_empty":
                            # Mode 1: if selected result is Re-appear, keep upgrading to newer real attempts (no attempt cap).
                            if chosen_class == "status-reappear":
                                chosen_payload = parsed
                                chosen_class = new_class
                                chosen_attempt_no = sem_index
                        else:
                            # Mode 2: keep first/current semester attempt only.
                            pass
                    except Exception:
                        continue

                if chosen_payload is not None:
                    try:
                        if isinstance(chosen_payload, list) and chosen_payload and isinstance(chosen_payload[0], list) and chosen_payload[0]:
                            chosen_payload[0][0]["__attempt_no"] = int(chosen_attempt_no or 1)
                            chosen_payload[0][0]["__attempt_label"] = f"Attempt {int(chosen_attempt_no or 1)}"
                    except Exception:
                        pass
                    file_path = os.path.join(final_folder, f"{roll}.json")
                    with open(file_path, "w", encoding="utf-8") as f:
                        json.dump(chosen_payload, f, indent=4)
                    if progress_callback:
                        progress_callback(f"Sem {semester_items[0].get('noOfSem', 1)} - {roll} Finished (latest-valid)")

            if progress_callback:
                progress_callback("DMC JSON fetch complete.")
            return {"status": "success", "folder": final_folder, "mode": "single"}

        for sem_index, sem_item in enumerate(semester_items, start=1):
            sem_folder = folder_for_sem(sem_item, sem_index)
            os.makedirs(sem_folder, exist_ok=True)

            for index, item in enumerate(items, start=1):
                response = item.find("response").text
                url_text = item.find("url").text

                roll_match = re.search(r"examRollNumber=(\d+)", url_text)
                roll = roll_match.group(1) if roll_match else "unknown"

                try:
                    data = json.loads(response)
                    std = data[0].get("std")
                except:
                    continue

                post_data = {
                    "qualificationId": sem_item["qlId"],
                    "syllbusId": sem_item["usyId"],
                    "semesterId": sem_item["smId"],
                    "examScheduleId": sem_item["esId"],
                    "noOfSem": sem_item["noOfSem"],
                    "studentRegIds": std,
                    "stdOpenResFlag": "true"
                }

                file_path = os.path.join(sem_folder, f"{roll}.json")

                try:
                    if progress_callback:
                        progress_callback(
                            f"Fetching DMC JSON: semester {sem_index}/{total_semesters}, roll {index}/{total_items} ({roll})"
                        )

                    res = requests.post(url, headers=headers, data=post_data, verify=False)

                    try:
                        parsed = json.loads(res.text)

                        if is_effectively_empty_payload(parsed, res.text):
                            if progress_callback:
                                progress_callback(f"Sem {sem_item.get('noOfSem', sem_index)} - {roll} skipped (empty [[]])")
                            continue

                        # Mode 2 only: if payload does not belong to selected exam schedule/semester,
                        # treat it as not-found for this selected sem and skip it.
                        if reappear_update_mode == "keep_current_sem" and mode == "single":
                            if not payload_matches_selected_sem(parsed, sem_item):
                                if progress_callback:
                                    progress_callback(
                                        f"Sem {sem_item.get('noOfSem', sem_index)} - {roll} skipped (payload not matching selected exam schedule/semester)"
                                    )
                                continue

                        with open(file_path, "w", encoding="utf-8") as f:
                            json.dump(parsed, f, indent=4)
                        if progress_callback:
                            progress_callback(f"Sem {sem_item.get('noOfSem', sem_index)} - {roll} Finished")
                    except Exception:
                        with open(file_path, "w") as f:
                            f.write(res.text)
                        if progress_callback:
                            progress_callback(f"Sem {sem_item.get('noOfSem', sem_index)} - {roll} Finished (raw)")

                except:
                    continue

        if progress_callback:
            progress_callback("DMC JSON fetch complete.")

        if mode == "all_semesters":
            return {"status": "success", "folder": run_folder, "mode": "all_semesters"}
        return {"status": "success", "folder": os.path.join(run_folder, f"sem_{sem_data['smId']}"), "mode": "single"}

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ----------------------------
# XML MARKS PARSER (UNCHANGED)
# ----------------------------
def parse_marks_xml(xml_string):
    result = {
        "theory_external": {"MO": [], "MPM": "-", "MM": "-"},
        "theory_internal": {"MO": [], "MPM": "-", "MM": "-"},
        "practical_external": {"MO": [], "MPM": "-", "MM": "-"},
        "practical_internal": {"MO": [], "MPM": "-", "MM": "-"},
    }

    if not xml_string:
        return result

    try:
        root = ET.fromstring(xml_string)

        for evalType in root.findall("evalType"):
            pType = evalType.findtext("pType", "").lower()
            eType = evalType.findtext("eType", "").lower()
            oMrk = evalType.findtext("oMrk", "0")
            pMrk = evalType.findtext("pMrk", "0")
            tMrk = evalType.findtext("tMrk", "0")

            key = None
            ptxt = f"{pType} {eType}".strip()
            is_practical = "pract" in ptxt
            is_theory = "theory" in ptxt
            is_external = "external" in ptxt
            is_internal = "internal" in ptxt

            if is_theory and is_external:
                key = "theory_external"
            elif is_theory and is_internal:
                key = "theory_internal"
            elif is_practical and is_external:
                key = "practical_external"
            elif is_practical and is_internal:
                key = "practical_internal"

            if key:
                mo_values = [
                    int(x.strip())
                    for x in oMrk.replace("+", ",").split(",")
                    if x.strip().isdigit()
                ]

                result[key]["MO"] = mo_values
                result[key]["MPM"] = pMrk
                result[key]["MM"] = tMrk

    except:
        pass

    return result


def build_student_snapshot(student):
    grand_total = 0
    subject_entries = []
    semester_info = {}
    if student.get("studentSemesterArray"):
        semester_info = student["studentSemesterArray"][0] or {}

    for subj in student.get("studentSubjectResultArray", []):
        marks = parse_marks_xml(subj.get("marks_details_xml", ""))

        total_marks = sum(sum(marks[key]["MO"]) for key in marks)
        grand_total += total_marks

        theory_external = marks["theory_external"]
        theory_internal = marks["theory_internal"]
        practical_external = marks["practical_external"]
        practical_internal = marks["practical_internal"]

        def fmt_mo(values):
            return "+".join(str(value) for value in values) if values else "-"

        subject_entries.append({
            "subject_code": str(subj.get("subject_code", "")),
            "subject_name": str(subj.get("subject_name", "")),
            "subject_credit": str(subj.get("subject_credit", "")),
            "theory_external": theory_external,
            "theory_internal": theory_internal,
            "practical_external": practical_external,
            "practical_internal": practical_internal,
            "total_marks": total_marks,
            "grade_letter": str(subj.get("grade_letter", "")),
            "grade_point": str(subj.get("grade_point", "")),
            "credit_grade_point": str(subj.get("credit_grade_point", "")),
            "subject_result": str(subj.get("subject_result", "")),
            "remark": str(subj.get("topicName") or subj.get("topicType") or ""),
        })

    raw_attempt = (
        student.get("__attempt_no")
        or semester_info.get("attemptNo")
        or semester_info.get("attempt_no")
        or semester_info.get("examAttemptNo")
        or semester_info.get("exam_attempt_no")
    )
    attempt_no = None
    try:
        attempt_no = int(str(raw_attempt))
    except Exception:
        attempt_no = None
    attempt_label = str(student.get("__attempt_label") or "").strip()
    if not attempt_label and attempt_no:
        attempt_label = f"Attempt {attempt_no}"

    return {
        "roll_no": str(student.get("examRollNo", "")),
        "reg_no": str(student.get("student_registration_number", "")),
        "student_name": str(student.get("studentName", "")),
        "father_name": str(student.get("fatherName", "")),
        "mother_name": str(student.get("motherName", "")),
        "institute": str(student.get("instituteName", "")),
        "degree": str(student.get("degreeName", "")),
        "exam_schedule": str(student.get("examScheduleName", "")),
        "semester": str(student.get("semester", "")),
        "subject_entries": subject_entries,
        "total_marks": grand_total,
        "sem_result": str(semester_info.get("semester_result", "")),
        "sgpa": str(semester_info.get("sgpa", "")),
        "result_date": str(semester_info.get("result_Date", "")),
        "exam_attempt_no": attempt_no,
        "exam_attempt_label": attempt_label,
    }


def get_result_class(result_text):
    value = " ".join((result_text or "").strip().lower().split())

    if not value:
        return "status-neutral"
    if "rl" in value or "regn" in value:
        return "status-rl"
    if "reappear" in value or "re-appear" in value or value == "re" or value.startswith("re ") or "reappear in" in value:
        return "status-reappear"
    if value == "ab" or value.startswith("ab ") or " absent" in f" {value}" or "absent" in value:
        return "status-ab"
    if "pass" in value:
        return "status-pass"
    if "fail" in value:
        return "status-fail"
    return "status-neutral"


def get_result_row_style(result_text):
    class_name = get_result_class(result_text)
    styles = {
        "status-pass": "background:#e8f8ef;color:#157347;",
        "status-reappear": "background:#fff4db;color:#b26a00;",
        "status-rl": "background:#ffe5e8;color:#c62828;",
        "status-ab": "background:#e8f1ff;color:#1d4ed8;",
        "status-fail": "background:#fff7cc;color:#8a6a00;",
        "status-neutral": "background:#e8f8ef;color:#157347;",
    }
    return styles.get(class_name, styles["status-neutral"])


def get_component_result_status(component):
    """Return pass/fail/na for a marks component based on MO vs MPM."""
    try:
        mo_values = component.get("MO") or []
        obtained = sum(float(v) for v in mo_values) if isinstance(mo_values, list) else float(mo_values or 0)
    except Exception:
        obtained = 0.0

    try:
        mpm = float(component.get("MPM") or 0)
    except Exception:
        mpm = 0.0

    # If no pass-threshold is defined, treat as NA (neutral).
    if mpm <= 0:
        return "na", obtained, mpm
    return ("pass" if obtained >= mpm else "fail"), obtained, mpm


def component_box_html(label, component):
    status, obtained, mpm = get_component_result_status(component)
    if status == "pass":
        bg, fg, bd = "#e8f8ef", "#157347", "#b7e4c7"
        verdict = "PASS"
    elif status == "fail":
        bg, fg, bd = "#ffe5e8", "#c62828", "#efb0b8"
        verdict = "FAIL"
    else:
        bg, fg, bd = "#f5f7fb", "#475467", "#d8dfeb"
        verdict = "NA"

    return (
        f"<div style=\"border:1px solid {bd};border-radius:10px;padding:8px;background:{bg};\">"
        f"<small style=\"display:block;color:#667085;margin-bottom:4px;\">{escape(label)}</small>"
        f"<strong style=\"color:{fg};font-size:12px;\">{verdict}</strong>"
        f"<div style=\"margin-top:4px;color:#667085;font-size:11px;\">{obtained:g}/{mpm:g}</div>"
        "</div>"
    )


def render_subject_rows(subject_entries, subject_rank_lookup, subject_avg_lookup):
    rows = ""

    def fmt_mo(values):
        return "+".join(str(value) for value in values) if values else "-"

    for entry in subject_entries:
        subject_code = entry["subject_code"]
        subject_rank = subject_rank_lookup.get(subject_code, "-")
        subject_avg = subject_avg_lookup.get(subject_code, 0)
        subject_result = entry.get("subject_result", "")
        result_class = get_result_class(subject_result)
        result_badge = f"<span class=\"result-badge {result_class}\" style=\"font-size:11px;padding:3px 8px;\">{escape(subject_result)}</span>"
        delta = entry["total_marks"] - subject_avg
        if delta > 0:
            insight = f"Above avg +{delta:.1f}"
        elif delta < 0:
            insight = f"Below avg {delta:.1f}"
        else:
            insight = "At avg"

        rows += (
            "<tr>"
            f"<td>{escape(subject_code)}</td>"
            f"<td>{escape(entry['subject_name'])}</td>"
            f"<td>{escape(entry['subject_credit'])}</td>"
            f"<td>{escape(fmt_mo(entry['theory_external']['MO']))}</td>"
            f"<td>{escape(str(entry['theory_external']['MPM']))}</td>"
            f"<td>{escape(str(entry['theory_external']['MM']))}</td>"
            f"<td>{escape(fmt_mo(entry['theory_internal']['MO']))}</td>"
            f"<td>{escape(str(entry['theory_internal']['MPM']))}</td>"
            f"<td>{escape(str(entry['theory_internal']['MM']))}</td>"
            f"<td>{escape(fmt_mo(entry['practical_external']['MO']))}</td>"
            f"<td>{escape(str(entry['practical_external']['MPM']))}</td>"
            f"<td>{escape(str(entry['practical_external']['MM']))}</td>"
            f"<td>{escape(fmt_mo(entry['practical_internal']['MO']))}</td>"
            f"<td>{escape(str(entry['practical_internal']['MPM']))}</td>"
            f"<td>{escape(str(entry['practical_internal']['MM']))}</td>"
            f"<td>{escape(str(entry['total_marks']))}</td>"
            f"<td>{escape(str(subject_rank))}</td>"
            f"<td>{escape(entry['grade_letter'])}</td>"
            f"<td>{escape(entry['grade_point'])}</td>"
            f"<td>{escape(entry['credit_grade_point'])}</td>"
            f"<td>{result_badge}</td>"
            f"<td>{escape(insight)}</td>"
            "</tr>"
        )

    return rows


def render_subject_scorecards(subject_entries, subject_rank_lookup, subject_avg_lookup):
    cards = ""

    for entry in subject_entries:
        subject_code = entry.get("subject_code", "")
        marks = entry.get("total_marks", 0)
        rank = subject_rank_lookup.get(subject_code, "-")
        batch_avg = subject_avg_lookup.get(subject_code, 0)
        delta = round(marks - batch_avg, 2)
        subject_result = entry.get("subject_result", "")
        result_class = get_result_class(subject_result)

        card_styles = {
            "status-pass": ("#e8f8ef", "#157347", "#b7e4c7"),
            "status-reappear": ("#fff4db", "#b26a00", "#f1d08a"),
            "status-rl": ("#ffe5e8", "#c62828", "#efb0b8"),
            "status-ab": ("#e8f1ff", "#1d4ed8", "#b6ccff"),
            "status-fail": ("#fff7cc", "#8a6a00", "#ead67a"),
            "status-neutral": ("#e8f8ef", "#157347", "#b7e4c7"),
        }
        card_bg, card_text, card_border = card_styles.get(result_class, card_styles["status-neutral"])

        if delta > 0:
            delta_text = f"+{delta}"
            delta_color = "#157347"
            delta_bg = "#e8f8ef"
        elif delta < 0:
            delta_text = str(delta)
            delta_color = "#b26a00"
            delta_bg = "#fff4db"
        else:
            delta_text = "0"
            delta_color = "#157347"
            delta_bg = "#e8f8ef"

        external_box = component_box_html("External", entry.get("theory_external", {}))
        practical_box = component_box_html("Practical", entry.get("practical_external", {}))

        cards += (
            f"<div style=\"border:1px solid {card_border};border-radius:12px;padding:12px;background:{card_bg};\">"
            f"<div style=\"display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:8px;\">"
            f"<div style=\"font-size:12px;color:#667085;\">{escape(subject_code)}</div>"
            f"<div style=\"padding:4px 8px;border-radius:999px;background:#ffffff;color:{card_text};font-size:11px;font-weight:700;border:1px solid {card_border};\">{escape(subject_result or 'NA')}</div>"
            "</div>"
            f"<div style=\"font-weight:700;color:#1d2939;margin-bottom:10px;line-height:1.35;\">{escape(entry.get('subject_name', '-'))}</div>"
            "<div style=\"display:grid;grid-template-columns:repeat(2,1fr);gap:8px;\">"
            f"<div style=\"border:1px solid #d8dfeb;border-radius:10px;padding:10px;background:#ffffff;\"><small style=\"display:block;color:#667085;margin-bottom:4px;\">Marks</small><strong>{marks}</strong></div>"
            f"<div style=\"border:1px solid #d8dfeb;border-radius:10px;padding:10px;background:#ffffff;\"><small style=\"display:block;color:#667085;margin-bottom:4px;\">Subject Rank</small><strong>#{rank}</strong></div>"
            f"<div style=\"border:1px solid #d8dfeb;border-radius:10px;padding:10px;background:#ffffff;\"><small style=\"display:block;color:#667085;margin-bottom:4px;\">Batch Avg</small><strong>{batch_avg}</strong></div>"
            f"<div style=\"border:1px solid {delta_bg};border-radius:10px;padding:10px;background:{delta_bg};\"><small style=\"display:block;color:#667085;margin-bottom:4px;\">Vs Avg</small><strong style=\"color:{delta_color};\">{delta_text}</strong></div>"
            "</div>"
            "<div style=\"display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:8px;\">"
            f"{external_box}"
            f"{practical_box}"
            "</div>"
            "</div>"
        )

    return cards


def build_subject_analytics(student_snapshots):
    subject_scores = {}
    student_lookup = {
        snapshot.get("file_name", ""): snapshot
        for snapshot in student_snapshots
    }

    for snapshot in student_snapshots:
        student_key = snapshot.get("file_name", "")
        for entry in snapshot.get("subject_entries", []):
            subject_code = entry.get("subject_code", "")
            if not subject_code:
                continue
            subject_scores.setdefault(subject_code, {
                "subject_name": entry.get("subject_name", ""),
                "scores": []
            })
            subject_scores[subject_code]["scores"].append({
                "student_key": student_key,
                "marks": entry.get("total_marks", 0),
                "subject_result": entry.get("subject_result", ""),
            })

    rank_map = {}
    avg_map = {}
    subject_summary = []

    for subject_code, payload in subject_scores.items():
        scores = payload["scores"]
        if not scores:
            continue

        ordered = sorted(scores, key=lambda item: (-item["marks"], item["student_key"]))
        avg_value = round(sum(item["marks"] for item in ordered) / len(ordered), 2)
        avg_map[subject_code] = avg_value

        last_marks = None
        display_rank = 0
        ranking_rows = []
        for index, item in enumerate(ordered, start=1):
            if item["marks"] != last_marks:
                display_rank = index
                last_marks = item["marks"]
            rank_map.setdefault(item["student_key"], {})[subject_code] = display_rank
            student_data = student_lookup.get(item["student_key"], {})
            ranking_rows.append({
                "rank": display_rank,
                "student_name": student_data.get("student_name", ""),
                "roll_no": student_data.get("roll_no", ""),
                "marks": item["marks"],
                "result": item.get("subject_result", ""),
            })

        topper_marks = ordered[0]["marks"]
        subject_summary.append({
            "subject_code": subject_code,
            "subject_name": payload["subject_name"],
            "average": avg_value,
            "top_marks": topper_marks,
            "entries": len(ordered),
            "ranking_rows": ranking_rows,
        })

    easiest_subject = None
    hardest_subject = None
    if subject_summary:
        easiest_subject = max(subject_summary, key=lambda item: item["average"])
        hardest_subject = min(subject_summary, key=lambda item: item["average"])

    return rank_map, avg_map, subject_summary, easiest_subject, hardest_subject


def build_practical_analytics(student_snapshots):
    practical_scores = {}
    student_lookup = {
        snapshot.get("file_name", ""): snapshot
        for snapshot in student_snapshots
    }

    def comp_sum(component):
        try:
            mo = component.get("MO") or []
            if isinstance(mo, list):
                return float(sum(float(x or 0) for x in mo))
            return float(mo or 0)
        except Exception:
            return 0.0
    def comp_mpm(component):
        try:
            return float(component.get("MPM") or 0)
        except Exception:
            return 0.0

    for snapshot in student_snapshots:
        student_key = snapshot.get("file_name", "")
        for entry in snapshot.get("subject_entries", []):
            subject_code = entry.get("subject_code", "")
            if not subject_code:
                continue

            practical_external = entry.get("practical_external", {}) or {}
            practical_internal = entry.get("practical_internal", {}) or {}

            practical_marks = comp_sum(practical_external) + comp_sum(practical_internal)
            practical_min_pass = comp_mpm(practical_external) + comp_mpm(practical_internal)

            # Skip subjects where no practical data exists for this student.
            has_practical_data = False
            try:
                if any(float(x or 0) > 0 for x in (practical_external.get("MO") or [])):
                    has_practical_data = True
                if any(float(x or 0) > 0 for x in (practical_internal.get("MO") or [])):
                    has_practical_data = True
                if float(practical_external.get("MM") or 0) > 0 or float(practical_internal.get("MM") or 0) > 0:
                    has_practical_data = True
                if float(practical_external.get("MPM") or 0) > 0 or float(practical_internal.get("MPM") or 0) > 0:
                    has_practical_data = True
            except Exception:
                pass

            if not has_practical_data:
                continue

            practical_scores.setdefault(subject_code, {
                "subject_name": entry.get("subject_name", ""),
                "scores": []
            })
            practical_scores[subject_code]["scores"].append({
                "student_key": student_key,
                "marks": round(practical_marks, 2),
                "min_pass": round(practical_min_pass, 2),
                "practical_status": "pass" if practical_min_pass > 0 and practical_marks >= practical_min_pass else ("fail" if practical_min_pass > 0 else "na"),
                "subject_result": entry.get("subject_result", ""),
            })

    practical_summary = []
    for subject_code, payload in practical_scores.items():
        scores = payload.get("scores", [])
        if not scores:
            continue

        ordered = sorted(scores, key=lambda item: (-item["marks"], item["student_key"]))
        avg_value = round(sum(item["marks"] for item in ordered) / len(ordered), 2)

        last_marks = None
        display_rank = 0
        ranking_rows = []
        for index, item in enumerate(ordered, start=1):
            if item["marks"] != last_marks:
                display_rank = index
                last_marks = item["marks"]
            student_data = student_lookup.get(item["student_key"], {})
            ranking_rows.append({
                "rank": display_rank,
                "student_name": student_data.get("student_name", ""),
                "roll_no": student_data.get("roll_no", ""),
                "marks": item["marks"],
                "min_pass": item.get("min_pass", 0),
                "practical_status": item.get("practical_status", "na"),
                "result": item.get("subject_result", ""),
            })

        practical_summary.append({
            "subject_code": subject_code,
            "subject_name": payload.get("subject_name", ""),
            "average": avg_value,
            "top_marks": ordered[0]["marks"],
            "entries": len(ordered),
            "ranking_rows": ranking_rows,
        })

    return sorted(practical_summary, key=lambda row: row.get("subject_name", ""))


def build_student_subject_metrics(snapshot, subject_avg_lookup, subject_rank_lookup):
    subject_entries = snapshot.get("subject_entries", [])
    if not subject_entries:
        return {
            "best_subject": "-",
            "weakest_subject": "-",
            "subjects_above_average": "0",
            "consistency_score": "-",
            "consistency_band": "No Data",
        }

    best_entry = max(subject_entries, key=lambda item: item["total_marks"])
    weakest_entry = min(subject_entries, key=lambda item: item["total_marks"])

    above_average = 0
    marks_list = []
    for entry in subject_entries:
        subject_code = entry.get("subject_code", "")
        marks_list.append(float(entry.get("total_marks", 0)))
        if entry.get("total_marks", 0) > subject_avg_lookup.get(subject_code, 0):
            above_average += 1

    best_rank = subject_rank_lookup.get(best_entry.get("subject_code", ""), "-")
    weakest_rank = subject_rank_lookup.get(weakest_entry.get("subject_code", ""), "-")

    avg_marks = sum(marks_list) / len(marks_list)
    spread = max(marks_list) - min(marks_list)
    normalized_spread = spread / max(1.0, avg_marks)
    consistency_score = max(0, min(100, round(100 - (normalized_spread * 28), 1)))
    if consistency_score >= 80:
        consistency_band = "Highly Stable"
    elif consistency_score >= 65:
        consistency_band = "Balanced"
    elif consistency_score >= 50:
        consistency_band = "Moderately Uneven"
    else:
        consistency_band = "Needs Balance"

    return {
        "best_subject": f"{best_entry.get('subject_name', '-')} (Rank {best_rank})",
        "weakest_subject": f"{weakest_entry.get('subject_name', '-')} (Rank {weakest_rank})",
        "subjects_above_average": f"{above_average}/{len(subject_entries)}",
        "consistency_score": f"{consistency_score}",
        "consistency_band": consistency_band,
    }


def build_student_compliment(snapshot, subject_avg_lookup, subject_rank_lookup, current_rank, batch_count, tone_mode="teacher"):
    subject_entries = snapshot.get("subject_entries", [])
    if not subject_entries:
        return {
            "performance_note": "This result shows a completed semester record. More detailed strengths will appear when subject data is available.",
            "strength_tags": "<span style=\"display:inline-block;padding:6px 10px;border-radius:999px;background:#eef2f8;color:#344054;font-size:12px;font-weight:700;\">Semester Record Available</span>",
        }

    ranked_subjects = sorted(
        subject_entries,
        key=lambda item: (
            -(item.get("total_marks", 0) - subject_avg_lookup.get(item.get("subject_code", ""), 0)),
            -item.get("total_marks", 0),
            item.get("subject_name", ""),
        )
    )

    top_subject = ranked_subjects[0]
    second_subject = ranked_subjects[1] if len(ranked_subjects) > 1 else None
    top_code = top_subject.get("subject_code", "")
    top_profile = SUBJECT_STRENGTH_PROFILES.get(top_code, {
        "label": "subject strength",
        "compliment": f"shows encouraging command in {top_subject.get('subject_name', 'this subject').lower()}",
    })

    top_delta = round(top_subject.get("total_marks", 0) - subject_avg_lookup.get(top_code, 0), 2)
    top_rank = subject_rank_lookup.get(top_code, "-")
    better_than = 0
    if batch_count and isinstance(current_rank, int):
        better_than = round(((batch_count - current_rank) / batch_count) * 100, 1)
    rank_ratio = 0
    if batch_count and isinstance(current_rank, int):
        rank_ratio = current_rank / batch_count

    status_class = get_result_class(snapshot.get("sem_result", ""))
    if tone_mode == "strict":
        if status_class == "status-pass":
            opening = f"Current semester rank is #{current_rank}, placing the student ahead of {better_than}% of the extracted batch."
        elif status_class == "status-reappear":
            opening = f"The student currently holds rank #{current_rank}; however, the reappear status indicates that performance recovery is required."
        elif status_class in {"status-rl", "status-ab"}:
            opening = "This record requires immediate academic attention, though completed subjects still show identifiable strengths."
        else:
            opening = f"This academic profile currently stands at rank #{current_rank} in the extracted batch."
    elif tone_mode == "motivational":
        if status_class == "status-pass":
            opening = f"This student has earned rank #{current_rank} and is already ahead of {better_than}% of the extracted batch, which is a strong foundation to build on."
        elif status_class == "status-reappear":
            opening = f"Even with a reappear status, this student still shows visible promise and a recoverable academic profile at rank #{current_rank}."
        elif status_class in {"status-rl", "status-ab"}:
            opening = "This record needs recovery, but the completed work still shows that the student has strengths worth building on."
        else:
            opening = f"This result still shows growth potential, with the student currently placed at rank #{current_rank}."
    else:
        if status_class == "status-pass":
            opening = f"This student stands at rank #{current_rank} in the semester and is ahead of {better_than}% of the extracted batch."
        elif status_class == "status-reappear":
            opening = f"This student still shows meaningful potential despite a reappear status, with rank #{current_rank} in the extracted batch."
        elif status_class in {"status-rl", "status-ab"}:
            opening = "This record needs academic attention, but the completed subject performance still highlights clear learning strengths."
        else:
            opening = f"This performance profile highlights identifiable strengths, with current semester rank at #{current_rank}."

    if top_delta > 0:
        strength_line = (
            f"The clearest strength is {top_subject.get('subject_name', 'this subject')}, where the student {top_profile['compliment']} "
            f"and performed {top_delta} marks above the batch average with subject rank #{top_rank}."
        )
    else:
        strength_line = (
            f"The clearest academic signal is in {top_subject.get('subject_name', 'this subject')}, where the student {top_profile['compliment']} "
            f"and earned subject rank #{top_rank}."
        )

    bridge_line = ""
    if second_subject:
        second_profile = SUBJECT_STRENGTH_PROFILES.get(second_subject.get("subject_code", ""), {
            "label": second_subject.get("subject_name", "academic growth"),
            "compliment": f"shows positive promise in {second_subject.get('subject_name', 'another key subject').lower()}",
        })
        bridge_line = f" Secondary strength also appears in {second_subject.get('subject_name', 'another subject')}, which {second_profile['compliment']}."

    strength_tags = []
    for entry in ranked_subjects[:3]:
        profile = SUBJECT_STRENGTH_PROFILES.get(entry.get("subject_code", ""), None)
        tag_text = profile["label"] if profile else entry.get("subject_name", "subject strength")
        strength_tags.append(
            "<span style=\"display:inline-block;padding:6px 10px;border-radius:999px;background:#e8f8ef;color:#157347;font-size:12px;font-weight:700;border:1px solid #b7e4c7;margin:0 8px 8px 0;\">"
            f"{escape(tag_text.title())}"
            "</span>"
        )

    return {
        "performance_note": opening + " " + strength_line + bridge_line,
        "strength_tags": "".join(strength_tags),
    }


def build_student_advice(snapshot, subject_avg_lookup, tone_mode="teacher"):
    subject_entries = snapshot.get("subject_entries", [])
    if not subject_entries:
        return {
            "advice_note": "Subject-level advice will appear when detailed subject marks are available.",
            "advice_tags": "",
        }

    reappear_subjects = [
        entry for entry in subject_entries
        if get_result_class(entry.get("subject_result", "")) == "status-reappear"
    ]

    weakest_subjects = sorted(
        subject_entries,
        key=lambda item: (
            (item.get("total_marks", 0) - subject_avg_lookup.get(item.get("subject_code", ""), 0)),
            item.get("total_marks", 0),
            item.get("subject_name", ""),
        )
    )

    selected_subjects = []
    seen_codes = set()

    for entry in reappear_subjects:
        subject_code = entry.get("subject_code", "")
        if subject_code and subject_code not in seen_codes:
            selected_subjects.append(entry)
            seen_codes.add(subject_code)

    for entry in weakest_subjects:
        subject_code = entry.get("subject_code", "")
        if subject_code and subject_code not in seen_codes:
            selected_subjects.append(entry)
            seen_codes.add(subject_code)
        if len(selected_subjects) >= max(2, len(reappear_subjects)):
            break

    advice_lines = []
    advice_tags = []

    for entry in selected_subjects:
        subject_code = entry.get("subject_code", "")
        subject_name = entry.get("subject_name", "this subject")
        delta = round(entry.get("total_marks", 0) - subject_avg_lookup.get(subject_code, 0), 2)
        is_reappear = get_result_class(entry.get("subject_result", "")) == "status-reappear"
        advice_text = SUBJECT_IMPROVEMENT_PROFILES.get(
            subject_code,
            "Build consistency through repeated revision, short notes, and targeted practice in this subject."
        )

        if is_reappear:
            lead = (
                f"{subject_name} is a reappear subject and should be treated as the highest-priority recovery area for this student."
            )
            if tone_mode == "motivational":
                tone = f"This can absolutely be recovered with focused effort. {advice_text}"
            elif tone_mode == "strict":
                tone = f"Immediate structured correction is required here. {advice_text}"
            else:
                tone = advice_text
        elif delta < 0:
            lead = f"{subject_name} needs the most attention, currently {abs(delta)} marks below the batch average."
            if tone_mode == "motivational":
                tone = f"This is a recoverable area. {advice_text}"
            else:
                tone = advice_text
        else:
            lead = f"{subject_name} is already a positive area in this result."
            if tone_mode == "strict":
                tone = "This performance should now be maintained with disciplined revision so the subject remains a reliable scoring area."
            elif tone_mode == "motivational":
                tone = "This is encouraging work. Keep nurturing it, because this subject can remain one of the student’s dependable strengths."
            else:
                tone = (
                    f"This is encouraging work. Keep the same discipline and revision rhythm here, "
                    f"because this subject can remain one of the student’s reliable strengths."
                )

        advice_lines.append(f"{lead} {tone}")

        if is_reappear:
            advice_tags.append(
                "<span style=\"display:inline-block;padding:6px 10px;border-radius:999px;background:#fff4db;color:#b26a00;font-size:12px;font-weight:700;border:1px solid #f1d08a;margin:0 8px 8px 0;\">"
                f"Reappear Focus: {escape(subject_name)}"
                "</span>"
            )
        elif delta < 0:
            advice_tags.append(
                "<span style=\"display:inline-block;padding:6px 10px;border-radius:999px;background:#fff4db;color:#b26a00;font-size:12px;font-weight:700;border:1px solid #f1d08a;margin:0 8px 8px 0;\">"
                f"Improve {escape(subject_name)}"
                "</span>"
            )
        else:
            advice_tags.append(
                "<span style=\"display:inline-block;padding:6px 10px;border-radius:999px;background:#e8f8ef;color:#157347;font-size:12px;font-weight:700;border:1px solid #b7e4c7;margin:0 8px 8px 0;\">"
                f"Keep Building {escape(subject_name)}"
                "</span>"
            )

    return {
        "advice_note": " ".join(advice_lines),
        "advice_tags": "".join(advice_tags),
    }


def build_subject_chart_html(subject_summary):
    if not subject_summary:
        return ""

    enriched_subjects = []
    for item in subject_summary:
        topper_gap = round(item["top_marks"] - item["average"], 2)
        competitiveness = round(100 - topper_gap, 2)
        if item["average"] >= 55 and topper_gap <= 18:
            difficulty = "Easy"
        elif item["average"] >= 38 and topper_gap <= 26:
            difficulty = "Moderate"
        else:
            difficulty = "Hard"
        enriched_subjects.append({
            **item,
            "topper_gap": topper_gap,
            "competitiveness": competitiveness,
            "difficulty": difficulty,
        })

    if not enriched_subjects:
        return ""

    strongest_subject = max(enriched_subjects, key=lambda item: item["average"])
    largest_gap_subject = max(enriched_subjects, key=lambda item: item["topper_gap"])
    most_competitive_subject = min(enriched_subjects, key=lambda item: item["topper_gap"])

    teacher_guidance_cards = ""
    for item in sorted(enriched_subjects, key=lambda row: (-row["topper_gap"], row["subject_name"]))[:4]:
        if item["difficulty"] == "Hard":
            guidance = "Maintain the same teaching depth, but add more low-stakes revision checkpoints and structured student practice so learners convert concepts into marks."
        elif item["difficulty"] == "Moderate":
            guidance = "This subject is teachable with good outcomes; a little more reinforcement, recap rhythm, and student accountability can lift the middle group."
        else:
            guidance = "The teaching direction here is already producing stable outcomes. The next gain can come from pushing stronger students while keeping weaker students engaged."
        teacher_guidance_cards += (
            "<div style=\"border:1px solid #d8dfeb;border-radius:12px;padding:12px;background:#fafbff;\">"
            f"<div style=\"display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:8px;\">"
            f"<strong style=\"color:#1d2939;\">{escape(item['subject_name'])}</strong>"
            f"<span style=\"padding:4px 8px;border-radius:999px;background:#eef2f8;color:#344054;font-size:12px;font-weight:700;\">{item['difficulty']}</span>"
            "</div>"
            f"<div style=\"font-size:13px;color:#475467;line-height:1.6;\">{guidance}</div>"
            "</div>"
        )

    matrix_rows = ""
    for item in sorted(enriched_subjects, key=lambda row: (-row["average"], row["subject_name"])):
        gap_tone = "#157347" if item["topper_gap"] <= 12 else "#b26a00" if item["topper_gap"] <= 24 else "#c62828"
        difficulty_bg = "#e8f8ef" if item["difficulty"] == "Easy" else "#fff4db" if item["difficulty"] == "Moderate" else "#ffe5e8"
        difficulty_text = "#157347" if item["difficulty"] == "Easy" else "#b26a00" if item["difficulty"] == "Moderate" else "#c62828"
        matrix_rows += (
            "<tr>"
            f"<td style=\"border:1px solid #d8dfeb;padding:8px;\">{escape(item['subject_code'])}</td>"
            f"<td style=\"border:1px solid #d8dfeb;padding:8px;\">{escape(item['subject_name'])}</td>"
            f"<td style=\"border:1px solid #d8dfeb;padding:8px;\">{item['average']}</td>"
            f"<td style=\"border:1px solid #d8dfeb;padding:8px;\">{item['top_marks']}</td>"
            f"<td style=\"border:1px solid #d8dfeb;padding:8px;color:{gap_tone};font-weight:700;\">{item['topper_gap']}</td>"
            f"<td style=\"border:1px solid #d8dfeb;padding:8px;\"><span style=\"display:inline-block;padding:4px 8px;border-radius:999px;background:{difficulty_bg};color:{difficulty_text};font-weight:700;font-size:12px;\">{item['difficulty']}</span></td>"
            f"<td style=\"border:1px solid #d8dfeb;padding:8px;\">{item['entries']}</td>"
            "</tr>"
        )

    return f"""
<div style="margin-top:16px;">
    <h3 style="margin:0 0 10px;color:#344054;font-size:16px;">Advanced Subject Analytics</h3>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:14px;">
        <div style="border:1px solid #d8dfeb;border-radius:12px;padding:12px;background:#fafbff;">
            <small style="display:block;color:#667085;margin-bottom:6px;">Strongest Subject</small>
            <strong>{escape(strongest_subject['subject_name'])}</strong>
            <div style="margin-top:6px;color:#475467;font-size:13px;">Average {strongest_subject['average']}</div>
        </div>
        <div style="border:1px solid #d8dfeb;border-radius:12px;padding:12px;background:#fafbff;">
            <small style="display:block;color:#667085;margin-bottom:6px;">Largest Topper Gap</small>
            <strong>{escape(largest_gap_subject['subject_name'])}</strong>
            <div style="margin-top:6px;color:#475467;font-size:13px;">Gap {largest_gap_subject['topper_gap']} marks</div>
        </div>
        <div style="border:1px solid #d8dfeb;border-radius:12px;padding:12px;background:#fafbff;">
            <small style="display:block;color:#667085;margin-bottom:6px;">Most Competitive</small>
            <strong>{escape(most_competitive_subject['subject_name'])}</strong>
            <div style="margin-top:6px;color:#475467;font-size:13px;">Gap {most_competitive_subject['topper_gap']} marks</div>
        </div>
    </div>
    <div style="border:1px solid #d8dfeb;border-radius:14px;padding:12px;background:#ffffff;">
        <table style="width:100%;border-collapse:collapse;">
            <thead>
                <tr>
                    <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Subject Code</th>
                    <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Subject Name</th>
                    <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Batch Avg</th>
                    <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Top Marks</th>
                    <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Topper Gap</th>
                    <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Difficulty</th>
                    <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Students</th>
                </tr>
            </thead>
            <tbody>{matrix_rows}</tbody>
        </table>
    </div>
    <div style="margin-top:14px;">
        <h4 style="margin:0 0 10px;color:#344054;font-size:15px;">Teacher Support Advisory</h4>
        <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:12px;">
            {teacher_guidance_cards}
        </div>
    </div>
</div>
"""


def extract_body_content(html_text):
    lower = html_text.lower()
    body_start = lower.find("<body")
    if body_start == -1:
        return html_text

    body_open_end = lower.find(">", body_start)
    body_close = lower.rfind("</body>")
    if body_open_end == -1 or body_close == -1:
        return html_text

    return html_text[body_open_end + 1:body_close]


def extract_head_content(html_text):
    lower = html_text.lower()
    head_start = lower.find("<head")
    if head_start == -1:
        return ""

    head_open_end = lower.find(">", head_start)
    head_close = lower.find("</head>", head_start)
    if head_open_end == -1 or head_close == -1:
        return ""

    return html_text[head_open_end + 1:head_close]


SEMESTER_ROMAN_MAP = {
    "I": 1, "II": 2, "III": 3, "IV": 4, "V": 5,
    "VI": 6, "VII": 7, "VIII": 8, "IX": 9, "X": 10,
}


def parse_semester_number(value, fallback=None):
    text = str(value or "").upper().strip()
    if not text and fallback is not None:
        text = str(fallback).upper().strip()

    if text.startswith("SEMESTER-"):
        text = text.split("SEMESTER-", 1)[1].strip()
    if text in SEMESTER_ROMAN_MAP:
        return SEMESTER_ROMAN_MAP[text]

    match = re.search(r"(\d+)", text)
    if match:
        return int(match.group(1))

    fallback_text = str(fallback or "").strip()
    return int(fallback_text) if fallback_text.isdigit() else None


def sort_semester_label(label):
    sem_no = parse_semester_number(label)
    return sem_no if sem_no is not None else 9999


def parse_date_safe(value):
    if not value:
        return datetime.min
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    return datetime.min


def result_priority_score(result_text):
    normalized = " ".join(str(result_text or "").strip().lower().split())
    if not normalized or "not declared" in normalized or normalized == "payment_done":
        return 0
    class_name = get_result_class(result_text or "")
    priority = {
        "status-pass": 5,
        "status-neutral": 4,
        "status-reappear": 3,
        "status-fail": 2,
        "status-rl": 1,
        "status-ab": 2,
    }
    return priority.get(class_name, 0)


def roll_sort_key(roll_text):
    digits = re.sub(r"\D", "", str(roll_text or ""))
    if digits:
        return (0, int(digits))
    return (1, str(roll_text or "").lower())


def format_semester_label(sem_no, existing_text=""):
    if sem_no is not None:
        return f"Semester {sem_no}"
    text = str(existing_text or "").strip()
    return text or "Semester"


def snapshot_priority(snapshot):
    base = result_priority_score(snapshot.get("sem_result", ""))
    if not snapshot.get("subject_entries"):
        return max(0, base - 1)
    return base


def build_missing_semester_snapshot(identity, sem_no, sem_label):
    return {
        "roll_no": identity.get("roll_no", ""),
        "reg_no": identity.get("reg_no", ""),
        "student_name": identity.get("student_name", ""),
        "father_name": identity.get("father_name", ""),
        "mother_name": identity.get("mother_name", ""),
        "institute": identity.get("institute", ""),
        "degree": identity.get("degree", ""),
        "exam_schedule": identity.get("exam_schedule", ""),
        "semester": sem_label,
        "subject_entries": [],
        "total_marks": 0,
        "sem_result": "Result Not Declared",
        "sgpa": "-",
        "result_date": "-",
        "sem_no": sem_no,
        "is_placeholder": True,
        "exam_attempt_no": None,
        "exam_attempt_label": "-",
    }


def has_real_result_data(snapshot):
    if not snapshot:
        return False
    sem_text = str(snapshot.get("sem_result", "") or "").strip().lower()
    if sem_text in {"", "result not declared", "payment_done"} or "not declared" in sem_text:
        return False
    if snapshot.get("is_placeholder"):
        return False
    return bool(snapshot.get("subject_entries"))


def parse_source_folder_ids(source_folder):
    text = str(source_folder or "")
    match = re.match(r"sem_(\d+)_([^_]+)_([^_]+)", text)
    if not match:
        return (-1, -1)
    sm_text = match.group(2)
    es_text = match.group(3)
    sm_id = int(sm_text) if str(sm_text).isdigit() else -1
    es_id = int(es_text) if str(es_text).isdigit() else -1
    return (sm_id, es_id)


def build_semester_polygon_chart(semesters, semester_avg=None):
    series = []
    for sem in semesters:
        if sem.get("is_placeholder"):
            continue
        marks = float(sem.get("total_marks", 0) or 0)
        sem_label = str(sem.get("semester", "") or "Sem").replace("Semester ", "S")
        sem_no = sem.get("sem_no")
        avg = None
        if semester_avg and sem_no in semester_avg:
            avg = float(semester_avg.get(sem_no) or 0)
        series.append((sem_label, marks, avg))

    if len(series) < 2:
        return (
            "<div style=\"border:1px solid #d8dfeb;border-radius:12px;padding:12px;background:#ffffff;color:#667085;\">"
            "<strong style=\"color:#344054;\">Semester Frequency Polygon</strong><div style=\"margin-top:6px;\">At least 2 declared semesters are needed for frequency polygon view.</div>"
            "</div>"
        )

    w, h = 560.0, 250.0
    pad_l, pad_r, pad_t, pad_b = 46.0, 16.0, 16.0, 36.0
    inner_w = w - pad_l - pad_r
    inner_h = h - pad_t - pad_b
    max_student = max(v for _, v, _ in series)
    max_batch = max((a for _, _, a in series if a is not None), default=0.0)
    max_marks = max(max_student, max_batch, 100.0)
    n = len(series)
    step_x = inner_w / (n - 1) if n > 1 else inner_w

    pts = []
    avg_pts = []
    for i, (_, val, avg) in enumerate(series):
        x = pad_l + (i * step_x)
        y = pad_t + inner_h - ((val / max_marks) * inner_h)
        pts.append((x, y))
        if avg is not None:
            ay = pad_t + inner_h - ((avg / max_marks) * inner_h)
            avg_pts.append((x, ay))
        else:
            avg_pts.append(None)

    polyline = " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)
    fill_poly = f"{pad_l:.2f},{pad_t + inner_h:.2f} " + polyline + f" {pad_l + ((n - 1) * step_x):.2f},{pad_t + inner_h:.2f}"

    y_grid = []
    y_labels = []
    for level in range(0, 6):
        y = pad_t + (inner_h * (level / 5.0))
        val = max_marks * (1 - level / 5.0)
        y_grid.append(f"<line x1=\"{pad_l:.2f}\" y1=\"{y:.2f}\" x2=\"{w - pad_r:.2f}\" y2=\"{y:.2f}\" stroke=\"#e6edf8\" stroke-width=\"1\"/>")
        y_labels.append(f"<text x=\"{pad_l - 8:.2f}\" y=\"{y + 4:.2f}\" fill=\"#7a879b\" font-size=\"10\" text-anchor=\"end\">{int(val)}</text>")

    avg_poly = " ".join(f"{x:.2f},{y:.2f}" for p in avg_pts if p for x, y in [p])

    x_labels = []
    point_nodes = []
    for i, (label, val, avg) in enumerate(series):
        x, y = pts[i]
        x_labels.append(f"<text x=\"{x:.2f}\" y=\"{h - 12:.2f}\" fill=\"#566273\" font-size=\"10\" text-anchor=\"middle\">{escape(label)}</text>")
        point_nodes.append(
            f"<circle class=\"fp-node\" data-label=\"{escape(label)}\" data-series=\"Student\" data-value=\"{int(val)}\" cx=\"{x:.2f}\" cy=\"{y:.2f}\" r=\"3.8\" fill=\"#5b7cff\"/>"
        )
        if avg is not None:
            ay = avg_pts[i][1] if avg_pts[i] else y
            point_nodes.append(
                f"<circle class=\"fp-node\" data-label=\"{escape(label)}\" data-series=\"Batch Avg\" data-value=\"{int(avg)}\" cx=\"{x:.2f}\" cy=\"{ay:.2f}\" r=\"3.3\" fill=\"#16a085\"/>"
            )

    return (
        "<div style=\"border:1px solid #d8dfeb;border-radius:12px;padding:12px;background:linear-gradient(180deg,#fbfcff,#f4f8ff);margin-bottom:10px;\">"
        "<div style=\"display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px;\">"
        "<strong style=\"color:#344054;\">Semester Frequency Polygon</strong>"
        f"<span style=\"font-size:12px;color:#667085;\">Scale Max: {int(max_marks)} | Student + Batch Avg</span>"
        "</div>"
        f"<div class=\"fp-chart\" style=\"position:relative;\">"
        f"<svg viewBox=\"0 0 {int(w)} {int(h)}\" width=\"100%\" height=\"250\" role=\"img\" aria-label=\"Semester frequency polygon\">"
        + "".join(y_grid)
        + "".join(y_labels)
        + f"<polyline points=\"{fill_poly}\" fill=\"rgba(91,124,255,0.14)\" stroke=\"none\"/>"
        + f"<polyline points=\"{polyline}\" fill=\"none\" stroke=\"#5b7cff\" stroke-width=\"2.4\"/>"
        + (f"<polyline points=\"{avg_poly}\" fill=\"none\" stroke=\"#16a085\" stroke-width=\"2.1\" stroke-dasharray=\"5 4\"/>" if avg_poly else "")
        + "".join(point_nodes)
        + "".join(x_labels)
        + "</svg>"
        + "<div class=\"fp-tooltip\" style=\"display:none;position:absolute;pointer-events:none;background:#0f172a;color:#ffffff;padding:6px 8px;border-radius:8px;font-size:12px;z-index:5;\"></div>"
        + "</div></div>"
    )


def build_all_semester_student_reports(run_folder, template, progress_callback=None, tone_mode="motivational", reappear_update_mode="update_latest_non_empty"):
    semester_folders = [
        os.path.join(run_folder, name)
        for name in os.listdir(run_folder)
        if os.path.isdir(os.path.join(run_folder, name)) and name.startswith("sem_")
    ]
    semester_folders.sort()

    expected_semesters = {}
    result_index_path = os.path.join(run_folder, "res_result.json")
    if os.path.exists(result_index_path):
        try:
            with open(result_index_path, "r", encoding="utf-8") as f:
                sem_index_data = json.load(f)
            for item in sem_index_data.get("data", []):
                sem_no = parse_semester_number(item.get("semName"), item.get("noOfSem"))
                if sem_no is None:
                    continue
                expected_semesters[sem_no] = format_semester_label(sem_no, item.get("semName", ""))
        except Exception:
            pass

    student_map = {}
    for sem_folder in semester_folders:
        folder_name = os.path.basename(sem_folder)
        folder_sem_match = re.match(r"sem_(\d+)", folder_name)
        folder_sem_no = int(folder_sem_match.group(1)) if folder_sem_match else None

        if folder_sem_no is not None and folder_sem_no not in expected_semesters:
            expected_semesters[folder_sem_no] = format_semester_label(folder_sem_no, "")

        for file_name in os.listdir(sem_folder):
            if not file_name.endswith(".json"):
                continue
            json_path = os.path.join(sem_folder, file_name)
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            try:
                student = data[0][0]
            except Exception:
                continue

            snapshot = build_student_snapshot(student)
            sem_no = parse_semester_number(snapshot.get("semester"), folder_sem_no)
            sem_result_text = str(snapshot.get("sem_result", "") or "").strip()
            if not sem_result_text:
                snapshot["sem_result"] = "Result Not Declared"
            snapshot["sem_no"] = sem_no
            snapshot["semester"] = format_semester_label(sem_no, snapshot.get("semester", ""))
            snapshot["file_name"] = file_name
            snapshot["source_folder"] = folder_name
            snapshot["is_placeholder"] = (not snapshot.get("subject_entries")) and result_priority_score(snapshot.get("sem_result", "")) == 0

            if sem_no is not None and sem_no not in expected_semesters:
                expected_semesters[sem_no] = snapshot["semester"]

            student_key = snapshot["reg_no"] or snapshot["roll_no"] or file_name
            student_map.setdefault(student_key, {
                "identity": snapshot,
                "semesters": [],
                "history": [],
            })

            student_map[student_key]["semesters"].append(snapshot)
            student_map[student_key]["history"].append(snapshot)

    semester_order = sorted(expected_semesters.keys())
    if not semester_order:
        sem_numbers = set()
        for payload in student_map.values():
            for sem in payload.get("semesters", []):
                sem_no = sem.get("sem_no")
                if sem_no is not None:
                    sem_numbers.add(sem_no)
        semester_order = sorted(sem_numbers)

    selected_snapshots = []
    for student_key, payload in student_map.items():
        attempts_by_sem = {}
        for snapshot in payload["semesters"]:
            sem_key = snapshot.get("sem_no")
            if sem_key is None:
                sem_key = snapshot.get("semester") or snapshot.get("source_folder") or "unknown"
            attempts_by_sem.setdefault(sem_key, []).append(snapshot)

        semester_snapshots = []
        if semester_order:
            for sem_no in semester_order:
                attempts = attempts_by_sem.get(sem_no, [])
                attempts = sorted(
                    attempts,
                    key=lambda snap: (
                        parse_source_folder_ids(snap.get("source_folder", ""))[1],
                        parse_date_safe(snap.get("result_date")),
                    )
                )

                chosen = None
                real_attempt_pos = 0
                chosen_attempt_pos = None
                for snap in attempts:
                    if not has_real_result_data(snap):
                        continue
                    real_attempt_pos += 1
                    if chosen is None:
                        chosen = snap
                        chosen_attempt_pos = real_attempt_pos
                        continue

                    if reappear_update_mode == "update_latest_non_empty":
                        chosen_is_re = get_result_class(chosen.get("sem_result", "")) == "status-reappear"
                        if chosen_is_re:
                            chosen = snap
                            chosen_attempt_pos = real_attempt_pos
                    else:
                        # keep_current_sem mode: freeze at first/current real attempt
                        pass

                if chosen is not None:
                    chosen["exam_attempt_no"] = chosen_attempt_pos
                    chosen["exam_attempt_label"] = f"Attempt {chosen_attempt_pos}" if chosen_attempt_pos else "-"
                    semester_snapshots.append(chosen)
                    continue

                semester_snapshots.append(
                    build_missing_semester_snapshot(
                        payload["identity"],
                        sem_no,
                        expected_semesters.get(sem_no, format_semester_label(sem_no, "")),
                    )
                )
        else:
            best_semesters = []
            for sem_key, attempts in attempts_by_sem.items():
                attempts = sorted(
                    attempts,
                    key=lambda snap: (
                        parse_source_folder_ids(snap.get("source_folder", ""))[1],
                        parse_date_safe(snap.get("result_date")),
                    )
                )
                chosen = None
                real_attempt_pos = 0
                chosen_attempt_pos = None
                for snap in attempts:
                    if not has_real_result_data(snap):
                        continue
                    real_attempt_pos += 1
                    if chosen is None:
                        chosen = snap
                        chosen_attempt_pos = real_attempt_pos
                        continue
                    if reappear_update_mode == "update_latest_non_empty":
                        if get_result_class(chosen.get("sem_result", "")) == "status-reappear":
                            chosen = snap
                            chosen_attempt_pos = real_attempt_pos
                    else:
                        # keep_current_sem mode: freeze at first/current real attempt
                        pass
                if chosen is not None:
                    chosen["exam_attempt_no"] = chosen_attempt_pos
                    chosen["exam_attempt_label"] = f"Attempt {chosen_attempt_pos}" if chosen_attempt_pos else "-"
                    best_semesters.append(chosen)
            semester_snapshots = sorted(
                best_semesters,
                key=lambda row: (sort_semester_label(row.get("semester")), parse_date_safe(row.get("result_date")))
            )

        valid_semesters = [sem for sem in semester_snapshots if not sem.get("is_placeholder")]
        total_latest_marks = sum(item.get("total_marks", 0) for item in valid_semesters)
        selected_snapshots.append({
            "student_key": student_key,
            "identity": payload["identity"],
            "semesters": semester_snapshots,
            "history": payload["history"],
            "overall_total": total_latest_marks,
        })

    ranked_students = sorted(
        selected_snapshots,
        key=lambda item: (-item["overall_total"], item["identity"]["student_name"], roll_sort_key(item["identity"]["roll_no"]))
    )
    rank_lookup = {}
    last_overall_total = None
    display_rank = 0
    for index, item in enumerate(ranked_students, start=1):
        current_total = item.get("overall_total", 0)
        if current_total != last_overall_total:
            display_rank = index
            last_overall_total = current_total
        rank_lookup[item["student_key"]] = display_rank

    display_students = sorted(
        selected_snapshots,
        key=lambda item: (roll_sort_key(item["identity"]["roll_no"]), item["identity"]["student_name"])
    )

    sem_peer_subjects = {}
    for peer in selected_snapshots:
        for peer_sem in peer["semesters"]:
            if peer_sem.get("is_placeholder"):
                continue
            sem_no = peer_sem.get("sem_no")
            sem_key = sem_no if sem_no is not None else peer_sem.get("semester", "")
            sem_peer_subjects.setdefault(sem_key, []).append(peer_sem)

    semester_total_avg = {}
    for sem_key, sem_items in sem_peer_subjects.items():
        values = [float(row.get("total_marks", 0) or 0) for row in sem_items]
        if values:
            semester_total_avg[sem_key] = round(sum(values) / len(values), 2)

    head_html = extract_head_content(template)
    chain_css = """
<style>
.student-chain{border:2px solid #c9d7ee;border-radius:16px;padding:14px;background:#fdfefe;box-shadow:0 10px 22px rgba(16,24,40,.07);}
.student-chain + .student-chain{margin-top:14px;}
.student-chain.chain-a{border-color:#6d8dff;box-shadow:0 10px 22px rgba(109,141,255,.18);}
.student-chain.chain-b{border-color:#00b894;box-shadow:0 10px 22px rgba(0,184,148,.18);}
.student-chain.chain-c{border-color:#f39c12;box-shadow:0 10px 22px rgba(243,156,18,.18);}
.student-chain.chain-d{border-color:#e84393;box-shadow:0 10px 22px rgba(232,67,147,.18);}
.student-header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin:0 0 10px;padding:12px;border:1px solid #d4deef;border-radius:12px;background:linear-gradient(180deg,#f7faff,#eff5ff);}
.student-header h3{margin:0;color:#1d2939;font-size:18px;}
.student-meta{font-size:13px;color:#475467;}
.student-boundary{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;border-radius:10px;font-size:12px;font-weight:700;letter-spacing:.04em;margin:0 0 10px;color:#1d2939;background:#f4f6fb;border:1px dashed #cad5e5;}
.student-chain .section{background:linear-gradient(180deg,#ffffff,#f7faff);border-color:#bfd0ea;}
.student-chain .section-title{color:#3f5bd8;border-bottom-color:#d7e2ff;}
.student-chain .summary-tile{background:linear-gradient(180deg,#fcfdff,#f1f6ff);}
.semester-timeline{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px;}
.timeline-chip{padding:6px 10px;border-radius:999px;border:1px solid #cad5e5;background:#eef2f8;color:#344054;font-weight:600;font-size:12px;}
.timeline-chip.status-pass{background:#e8f8ef;border-color:#b7e4c7;color:#157347;}
.timeline-chip.status-reappear{background:#fff4db;border-color:#f1d08a;color:#b26a00;}
.timeline-chip.status-rl{background:#ffe5e8;border-color:#efb0b8;color:#c62828;}
.timeline-chip.status-ab{background:#e8f1ff;border-color:#b6ccff;color:#1d4ed8;}
.timeline-chip.status-fail{background:#fff7cc;border-color:#ead67a;color:#8a6a00;}
.student-start-grid,.student-end-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:0 0 10px;}
.student-pill{border:1px solid #d8dfeb;border-radius:10px;padding:10px;background:#fff;}
.student-pill small{display:block;color:#667085;margin-bottom:4px;}
.student-pill strong{color:#1d2939;}
.pill-pass{background:#e8f8ef;border-color:#b7e4c7;}
.pill-reappear{background:#fff4db;border-color:#f1d08a;}
.pill-pending{background:#ffe5e8;border-color:#efb0b8;}
@media (max-width: 900px){.student-start-grid,.student-end-grid{grid-template-columns:1fr 1fr;}}
</style>
"""
    if chain_css not in head_html:
        head_html += chain_css

    generated_reports = []
    for index, item in enumerate(display_students, start=1):
        if progress_callback:
            progress_callback(f"Building overall report: {index}/{len(display_students)} ({item['identity']['student_name']})")

        current_rank = rank_lookup.get(item["student_key"], "-")
        batch_count = len(ranked_students)
        better_than = "-"
        gap_from_top = "-"
        if isinstance(current_rank, int) and batch_count:
            better_than = f"{((batch_count - current_rank) / batch_count) * 100:.1f}%"
        if ranked_students:
            gap_from_top = str(max(0, ranked_students[0]["overall_total"] - item["overall_total"]))

        semester_blocks = []
        marks_series = [sem["total_marks"] for sem in item["semesters"] if not sem.get("is_placeholder")]
        spike_note = "Stable academic pattern."
        if len(marks_series) >= 2:
            change = marks_series[-1] - marks_series[0]
            if change > 0:
                spike_note = f"Amazing upward trend: marks improved by {change} points across valid semester records."
            elif change < 0:
                spike_note = f"Performance dipped by {abs(change)} points across valid semester records; a structured comeback plan can recover this."
            else:
                spike_note = "Consistent semester-to-semester marks pattern is visible."

        if len(marks_series) >= 2:
            if marks_series[-1] > marks_series[0]:
                spike_tag = "Rising"
            elif marks_series[-1] < marks_series[0]:
                spike_tag = "Declining"
            else:
                spike_tag = "Stable"
        else:
            spike_tag = "Single Snapshot"

        timeline_chips = []
        for sem_snapshot in item["semesters"]:
            result_class = get_result_class(sem_snapshot.get("sem_result", ""))
            sem_label = escape(sem_snapshot.get("semester", "Semester"))
            sem_result = escape(sem_snapshot.get("sem_result", "Result Not Declared"))
            timeline_chips.append(f"<span class=\"timeline-chip {result_class}\">{sem_label}: {sem_result}</span>")

        declared_count = len([sem for sem in item["semesters"] if not sem.get("is_placeholder")])
        pending_count = len(item["semesters"]) - declared_count
        reappear_count = len([
            sem for sem in item["semesters"]
            if get_result_class(sem.get("sem_result", "")) == "status-reappear"
        ])

        for sem_snapshot in item["semesters"]:
            sem_no = sem_snapshot.get("sem_no")
            sem_key = sem_no if sem_no is not None else sem_snapshot.get("semester", "")
            peer_semesters = sem_peer_subjects.get(sem_key, [])
            student_subject_ranks = {}
            subject_avg_map = {}
            subject_summary_map = {}

            for peer_sem in peer_semesters:
                for entry in peer_sem.get("subject_entries", []):
                    code = entry["subject_code"]
                    subject_summary_map.setdefault(code, []).append(entry["total_marks"])

            for code, values in subject_summary_map.items():
                if not values:
                    continue
                subject_avg_map[code] = round(sum(values) / len(values), 2)
                ordered = sorted(values, reverse=True)
                target = next((entry["total_marks"] for entry in sem_snapshot.get("subject_entries", []) if entry["subject_code"] == code), None)
                if target is not None:
                    student_subject_ranks[code] = ordered.index(target) + 1

            subject_rows = render_subject_rows(sem_snapshot.get("subject_entries", []), student_subject_ranks, subject_avg_map)
            subject_scorecards = render_subject_scorecards(sem_snapshot.get("subject_entries", []), student_subject_ranks, subject_avg_map)
            subject_metrics = build_student_subject_metrics(sem_snapshot, subject_avg_map, student_subject_ranks)
            compliment_payload = build_student_compliment(
                sem_snapshot, subject_avg_map, student_subject_ranks, current_rank, len(ranked_students), tone_mode=tone_mode
            )
            advice_payload = build_student_advice(sem_snapshot, subject_avg_map, tone_mode=tone_mode)

            html = template
            attempt_no = sem_snapshot.get("exam_attempt_no")
            attempt_text = sem_snapshot.get("exam_attempt_label") or "-"
            if sem_snapshot.get("sem_result", "").strip().lower().find("re-appear") == -1 and sem_snapshot.get("sem_result", "").strip().lower().find("reappear") == -1:
                if not attempt_no or int(attempt_no) <= 1:
                    attempt_text = "-"
            html = html.replace("{{ROLL_NO}}", sem_snapshot["roll_no"])
            html = html.replace("{{REG_NO}}", sem_snapshot["reg_no"])
            html = html.replace("{{STUDENT_NAME}}", sem_snapshot["student_name"])
            html = html.replace("{{FATHER_NAME}}", sem_snapshot["father_name"])
            html = html.replace("{{MOTHER_NAME}}", sem_snapshot["mother_name"])
            html = html.replace("{{INSTITUTE}}", sem_snapshot["institute"])
            html = html.replace("{{DEGREE}}", sem_snapshot["degree"])
            html = html.replace("{{EXAM_SCHEDULE}}", sem_snapshot["exam_schedule"])
            html = html.replace("{{SEMESTER}}", sem_snapshot["semester"])
            html = html.replace("{{EXAM_ATTEMPT}}", str(attempt_text))
            html = html.replace("{{SUBJECT_ROWS}}", subject_rows)
            html = html.replace("{{TOTAL_MARKS}}", str(sem_snapshot["total_marks"]))
            html = html.replace("{{SEM_RESULT}}", sem_snapshot["sem_result"])
            html = html.replace("{{SGPA}}", sem_snapshot["sgpa"])
            html = html.replace("{{RESULT_DATE}}", sem_snapshot["result_date"])
            html = html.replace("{{RESULT_CLASS}}", get_result_class(sem_snapshot["sem_result"]))
            html = html.replace("{{CLASS_RANK}}", str(current_rank))
            html = html.replace("{{BATCH_COUNT}}", str(len(ranked_students)))
            html = html.replace("{{BETTER_THAN}}", better_than)
            html = html.replace("{{GAP_FROM_TOP}}", gap_from_top)
            html = html.replace("{{SUBJECT_SCORECARDS}}", subject_scorecards)
            html = html.replace("{{BEST_SUBJECT}}", subject_metrics["best_subject"])
            html = html.replace("{{WEAKEST_SUBJECT}}", subject_metrics["weakest_subject"])
            html = html.replace("{{ABOVE_AVG_SUBJECTS}}", subject_metrics["subjects_above_average"])
            html = html.replace("{{CONSISTENCY_SCORE}}", subject_metrics["consistency_score"])
            html = html.replace("{{CONSISTENCY_BAND}}", subject_metrics["consistency_band"])
            html = html.replace("{{PERFORMANCE_NOTE}}", compliment_payload["performance_note"])
            html = html.replace("{{STRENGTH_TAGS}}", compliment_payload["strength_tags"])
            html = html.replace("{{ADVICE_NOTE}}", advice_payload["advice_note"])
            html = html.replace("{{ADVICE_TAGS}}", advice_payload["advice_tags"])
            semester_blocks.append(extract_body_content(html))

        overall_summary = f"""
<div class="section" style="margin-bottom:12px;">
    <h2 class="section-title">Overall Academic Record</h2>
    <div class="summary-grid">
        <div class="summary-tile"><small>Overall Rank</small><strong>#{rank_lookup.get(item['student_key'], '-')}</strong></div>
        <div class="summary-tile"><small>Valid Semesters Found</small><strong>{len([sem for sem in item['semesters'] if not sem.get('is_placeholder')])}</strong></div>
        <div class="summary-tile"><small>Total Across Valid Results</small><strong>{item['overall_total']}</strong></div>
        <div class="summary-tile"><small>Spike Rate</small><strong>{spike_tag}</strong></div>
        <div class="summary-tile"><small>Trend Insight</small><strong>{escape(spike_note)}</strong></div>
    </div>
</div>
"""

        student_header = (
            "<div class=\"student-header\">"
            f"<div><h3>{escape(item['identity'].get('student_name', '-'))}</h3>"
            f"<div class=\"student-meta\">{escape(item['identity'].get('degree', '-'))} | {escape(item['identity'].get('institute', '-'))}</div></div>"
            f"<div class=\"student-meta\">Roll: {escape(item['identity'].get('roll_no', '-'))}<br>Reg: {escape(item['identity'].get('reg_no', '-'))}</div>"
            "</div>"
        )
        chain_class = ["chain-a", "chain-b", "chain-c", "chain-d"][(index - 1) % 4]
        boundary_start = (
            "<div class=\"student-boundary\">"
            "<span>Student Result Start</span>"
            f"<span>Record #{index}</span>"
            "</div>"
        )
        boundary_end = (
            "<div class=\"student-boundary\" style=\"margin-top:10px;\">"
            "<span>Student Result End</span>"
            f"<span>Roll {escape(item['identity'].get('roll_no', '-'))}</span>"
            "</div>"
        )
        student_start = f"""
<div class="student-start-grid">
    <div class="student-pill"><small>Total Semesters</small><strong>{len(item['semesters'])}</strong></div>
    <div class="student-pill pill-pass"><small>Declared</small><strong>{declared_count}</strong></div>
    <div class="student-pill pill-reappear"><small>Reappear Semesters</small><strong>{reappear_count}</strong></div>
    <div class="student-pill pill-pending"><small>Pending / Not Declared</small><strong>{pending_count}</strong></div>
</div>
"""
        student_end = f"""
<div class="student-end-grid">
    <div class="student-pill"><small>Overall Total (Valid)</small><strong>{item['overall_total']}</strong></div>
    <div class="student-pill"><small>Overall Rank</small><strong>#{rank_lookup.get(item['student_key'], '-')}</strong></div>
    <div class="student-pill"><small>Trend</small><strong>{escape(spike_tag)}</strong></div>
    <div class="student-pill"><small>Gap From Top</small><strong>{escape(gap_from_top)}</strong></div>
</div>
"""
        timeline_html = f"<div class=\"semester-timeline\">{''.join(timeline_chips)}</div>"
        polygon_html = build_semester_polygon_chart(item["semesters"], semester_total_avg)

        report_html = (
            "<!DOCTYPE html><html><head>" + head_html + "</head><body>"
            + f"<div class=\"student-chain {chain_class}\">"
            + boundary_start
            + student_header
            + student_start
            + timeline_html
            + polygon_html
            + overall_summary
            + "".join(semester_blocks)
            + student_end
            + boundary_end
            + "</div></body></html>"
        )
        file_name = f"{item['identity']['roll_no'] or item['student_key']}_overall.html"
        generated_reports.append({
            "file_name": file_name,
            "html": report_html,
            "student_name": item["identity"]["student_name"],
            "overall_total": item["overall_total"],
            "spike_tag": spike_tag,
            "roll_no": item["identity"].get("roll_no", ""),
        })

    return generated_reports


# ----------------------------
# STEP 6: JSON → HTML (FULL)
# ----------------------------
def step6_generate_html(data_folder, run_folder, progress_callback=None, tone_mode="motivational", report_mode="single", reappear_update_mode="update_latest_non_empty"):

    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        template = f.read()

    if report_mode == "all_semesters":
        combined_reports = build_all_semester_student_reports(run_folder, template, progress_callback=progress_callback, tone_mode=tone_mode, reappear_update_mode=reappear_update_mode)
        merged_path = os.path.join(COMBINED_BASE, "combined_all_semesters.html")
        head_html = extract_head_content(template)
        all_sem_layout_css = """
<style>
.student-chain{border:2px solid #c9d7ee;border-radius:16px;padding:14px;background:#fdfefe;box-shadow:0 10px 22px rgba(16,24,40,.07);}
.student-chain + .student-chain{margin-top:14px;}
.student-chain.chain-a{border-color:#6d8dff;box-shadow:0 10px 22px rgba(109,141,255,.18);}
.student-chain.chain-b{border-color:#00b894;box-shadow:0 10px 22px rgba(0,184,148,.18);}
.student-chain.chain-c{border-color:#f39c12;box-shadow:0 10px 22px rgba(243,156,18,.18);}
.student-chain.chain-d{border-color:#e84393;box-shadow:0 10px 22px rgba(232,67,147,.18);}
.student-header{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin:0 0 10px;padding:12px;border:1px solid #d4deef;border-radius:12px;background:linear-gradient(180deg,#f7faff,#eff5ff);}
.student-header h3{margin:0;color:#1d2939;font-size:18px;}
.student-meta{font-size:13px;color:#475467;}
.student-boundary{display:flex;justify-content:space-between;align-items:center;padding:8px 12px;border-radius:10px;font-size:12px;font-weight:700;letter-spacing:.04em;margin:0 0 10px;color:#1d2939;background:#f4f6fb;border:1px dashed #cad5e5;}
.student-chain .section{background:linear-gradient(180deg,#ffffff,#f7faff);border-color:#bfd0ea;}
.student-chain .section-title{color:#3f5bd8;border-bottom-color:#d7e2ff;}
.student-chain .summary-tile{background:linear-gradient(180deg,#fcfdff,#f1f6ff);}
.semester-timeline{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px;}
.timeline-chip{padding:6px 10px;border-radius:999px;border:1px solid #cad5e5;background:#eef2f8;color:#344054;font-weight:600;font-size:12px;}
.timeline-chip.status-pass{background:#e8f8ef;border-color:#b7e4c7;color:#157347;}
.timeline-chip.status-reappear{background:#fff4db;border-color:#f1d08a;color:#b26a00;}
.timeline-chip.status-rl{background:#ffe5e8;border-color:#efb0b8;color:#c62828;}
.timeline-chip.status-ab{background:#e8f1ff;border-color:#b6ccff;color:#1d4ed8;}
.timeline-chip.status-fail{background:#fff7cc;border-color:#ead67a;color:#8a6a00;}
.student-start-grid,.student-end-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:0 0 10px;}
.student-pill{border:1px solid #d8dfeb;border-radius:10px;padding:10px;background:#fff;}
.student-pill small{display:block;color:#667085;margin-bottom:4px;}
.student-pill strong{color:#1d2939;}
.pill-pass{background:#e8f8ef;border-color:#b7e4c7;}
.pill-reappear{background:#fff4db;border-color:#f1d08a;}
.pill-pending{background:#ffe5e8;border-color:#efb0b8;}
@media (max-width: 900px){.student-start-grid,.student-end-grid{grid-template-columns:1fr 1fr;}}
</style>
"""
        if all_sem_layout_css not in head_html:
            head_html += all_sem_layout_css

        spike_up = sum(1 for item in combined_reports if item["spike_tag"] == "Rising")
        spike_down = sum(1 for item in combined_reports if item["spike_tag"] == "Declining")
        spike_stable = sum(1 for item in combined_reports if item["spike_tag"] not in {"Rising", "Declining"})

        practical_section_html = ""
        if practical_scoreboard_html:
            practical_section_html = (
                "<div><h3 style=\"margin:0 0 10px;color:#344054;font-size:16px;\">Practical Rankboards</h3>"
                + practical_scoreboard_html
                + "</div>"
            )

        summary_html = f"""
<div style="font-family:'Segoe UI',Tahoma,sans-serif;margin-bottom:24px;background:#ffffff;border:1px solid #d8dfeb;border-radius:14px;padding:18px;">
    <h2 style="margin:0 0 14px;color:#2f6fed;">Overall Academic Record Dashboard</h2>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;">
        <div style="border:1px solid #d8dfeb;border-radius:10px;padding:12px;background:#fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Students Covered</small><strong style="font-size:20px;">{len(combined_reports)}</strong></div>
        <div style="border:1px solid #d8dfeb;border-radius:10px;padding:12px;background:#e8f8ef;"><small style="display:block;color:#667085;margin-bottom:6px;">Rising Trend</small><strong style="font-size:20px;color:#157347;">{spike_up}</strong></div>
        <div style="border:1px solid #d8dfeb;border-radius:10px;padding:12px;background:#fff4db;"><small style="display:block;color:#667085;margin-bottom:6px;">Declining Trend</small><strong style="font-size:20px;color:#b26a00;">{spike_down}</strong></div>
        <div style="border:1px solid #d8dfeb;border-radius:10px;padding:12px;background:#fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Stable / Single</small><strong style="font-size:20px;">{spike_stable}</strong></div>
    </div>
</div>
"""

        with open(merged_path, "w", encoding="utf-8") as out:
            out.write("<!DOCTYPE html><html><head>")
            out.write(head_html)
            out.write("</head><body>")
            out.write(summary_html)
            for item in combined_reports:
                out.write(extract_body_content(item["html"]))
                out.write("<div style=\"height:36px\"></div>")
            out.write("</body></html>")

        if progress_callback:
            progress_callback(f"All-semester HTML generation complete. Output saved to {merged_path}")
        return merged_path

    folder_name = os.path.basename(data_folder)

    output_folder = os.path.join(
        COMBINED_BASE,
        f"{folder_name}_html",
        f"combined_{folder_name}"
    )

    os.makedirs(output_folder, exist_ok=True)

    generated_files = []
    student_snapshots = []

    json_files = [file_name for file_name in os.listdir(data_folder) if file_name.endswith(".json")]
    total_files = len(json_files)

    for index, file_name in enumerate(json_files, start=1):
        if not file_name.endswith(".json"):
            continue

        if progress_callback:
            progress_callback(f"Generating HTML: {index}/{total_files} ({file_name})")

        json_path = os.path.join(data_folder, file_name)

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        try:
            student = data[0][0]
        except:
            continue

        snapshot = build_student_snapshot(student)
        snapshot["file_name"] = file_name
        student_snapshots.append(snapshot)

    ranked_snapshots = sorted(
        student_snapshots,
        key=lambda item: (-item["total_marks"], item["student_name"], item["roll_no"])
    )

    subject_rank_map, subject_avg_map, subject_summary, easiest_subject, hardest_subject = build_subject_analytics(student_snapshots)
    practical_summary = build_practical_analytics(student_snapshots)

    rank_lookup = {}
    batch_count = len(ranked_snapshots)
    average_marks = 0
    highest_marks = 0
    lowest_marks = 0
    status_counts = {
        "Pass": 0,
        "Reappear": 0,
        "RL/Regn": 0,
        "Absent": 0,
    }
    shared_leaderboard_rows = ""
    top_three_rows = ""
    top_three_practical_rows = ""

    if ranked_snapshots:
        totals = [item["total_marks"] for item in ranked_snapshots]
        highest_marks = max(totals)
        lowest_marks = min(totals)
        average_marks = round(sum(totals) / len(totals), 2)

        last_total = None
        display_rank = 0
        for idx, snapshot in enumerate(ranked_snapshots, start=1):
            current_total = snapshot["total_marks"]
            if current_total != last_total:
                display_rank = idx
                last_total = current_total

            rank_lookup[snapshot["file_name"]] = display_rank
            result_style = get_result_row_style(snapshot["sem_result"])
            result_class = get_result_class(snapshot["sem_result"])
            if result_class == "status-pass":
                status_counts["Pass"] += 1
            elif result_class == "status-reappear":
                status_counts["Reappear"] += 1
            elif result_class == "status-rl":
                status_counts["RL/Regn"] += 1
            elif result_class == "status-ab":
                status_counts["Absent"] += 1
            row_html = (
                "<tr>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{result_style}\">{display_rank}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{result_style}\">{escape(snapshot['student_name'])}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{result_style}\">{escape(snapshot['roll_no'])}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{result_style}\">{escape(str(snapshot['total_marks']))}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{result_style}\">{escape(snapshot['sem_result'])}</td>"
                "</tr>"
            )
            shared_leaderboard_rows += row_html
            if display_rank <= 3:
                top_three_rows += row_html

    practical_student_totals = []
    for snapshot in student_snapshots:
        p_obtained = 0.0
        p_min_pass = 0.0
        p_subject_count = 0
        for entry in snapshot.get("subject_entries", []):
            pex = entry.get("practical_external", {}) or {}
            pin = entry.get("practical_internal", {}) or {}
            try:
                ex_mo = sum(float(x or 0) for x in (pex.get("MO") or []))
            except Exception:
                ex_mo = 0.0
            try:
                in_mo = sum(float(x or 0) for x in (pin.get("MO") or []))
            except Exception:
                in_mo = 0.0
            try:
                ex_mpm = float(pex.get("MPM") or 0)
            except Exception:
                ex_mpm = 0.0
            try:
                in_mpm = float(pin.get("MPM") or 0)
            except Exception:
                in_mpm = 0.0
            has_practical = (ex_mo > 0 or in_mo > 0 or ex_mpm > 0 or in_mpm > 0)
            if not has_practical:
                continue
            p_subject_count += 1
            p_obtained += (ex_mo + in_mo)
            p_min_pass += (ex_mpm + in_mpm)

        if p_subject_count > 0:
            practical_student_totals.append({
                "student_name": snapshot.get("student_name", ""),
                "roll_no": snapshot.get("roll_no", ""),
                "obtained": round(p_obtained, 2),
                "min_pass": round(p_min_pass, 2),
            })

    practical_student_totals = sorted(
        practical_student_totals,
        key=lambda row: (-row["obtained"], row["student_name"], row["roll_no"])
    )
    last_p_total = None
    p_rank = 0
    for idx, row in enumerate(practical_student_totals, start=1):
        if row["obtained"] != last_p_total:
            p_rank = idx
            last_p_total = row["obtained"]
        if row["min_pass"] > 0 and row["obtained"] >= row["min_pass"]:
            p_style = "background:#e8f8ef;color:#157347;"
            p_status = "Pass"
        elif row["min_pass"] > 0:
            p_style = "background:#ffe5e8;color:#c62828;"
            p_status = "Fail"
        else:
            p_style = "background:#eef2f8;color:#344054;"
            p_status = "NA"
        if p_rank <= 3:
            top_three_practical_rows += (
                "<tr>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{p_style}\">{p_rank}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{p_style}\">{escape(row['student_name'])}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{p_style}\">{escape(row['roll_no'])}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{p_style}\">{row['obtained']}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{p_style}\">{p_status}</td>"
                "</tr>"
            )

    for snapshot in student_snapshots:
        current_rank = rank_lookup.get(snapshot["file_name"], "-")
        percentile_text = "-"
        gap_from_top = "-"
        if batch_count and isinstance(current_rank, int):
            better_than = ((batch_count - current_rank) / batch_count) * 100
            percentile_text = f"{better_than:.1f}%"
        if ranked_snapshots:
            gap_from_top = str(max(0, highest_marks - snapshot["total_marks"]))

        student_subject_ranks = subject_rank_map.get(snapshot["file_name"], {})
        subject_rows = render_subject_rows(
            snapshot.get("subject_entries", []),
            student_subject_ranks,
            subject_avg_map
        )
        subject_scorecards = render_subject_scorecards(
            snapshot.get("subject_entries", []),
            student_subject_ranks,
            subject_avg_map
        )
        subject_metrics = build_student_subject_metrics(
            snapshot,
            subject_avg_map,
            student_subject_ranks
        )
        compliment_payload = build_student_compliment(
            snapshot,
            subject_avg_map,
            student_subject_ranks,
            current_rank,
            batch_count,
            tone_mode=tone_mode
        )
        advice_payload = build_student_advice(
            snapshot,
            subject_avg_map,
            tone_mode=tone_mode
        )

        html = template
        attempt_no = snapshot.get("exam_attempt_no")
        attempt_text = snapshot.get("exam_attempt_label") or "-"
        if snapshot.get("sem_result", "").strip().lower().find("re-appear") == -1 and snapshot.get("sem_result", "").strip().lower().find("reappear") == -1:
            if not attempt_no or int(attempt_no) <= 1:
                attempt_text = "-"
        html = html.replace("{{ROLL_NO}}", snapshot["roll_no"])
        html = html.replace("{{REG_NO}}", snapshot["reg_no"])
        html = html.replace("{{STUDENT_NAME}}", snapshot["student_name"])
        html = html.replace("{{FATHER_NAME}}", snapshot["father_name"])
        html = html.replace("{{MOTHER_NAME}}", snapshot["mother_name"])
        html = html.replace("{{INSTITUTE}}", snapshot["institute"])
        html = html.replace("{{DEGREE}}", snapshot["degree"])
        html = html.replace("{{EXAM_SCHEDULE}}", snapshot["exam_schedule"])
        html = html.replace("{{SEMESTER}}", snapshot["semester"])
        html = html.replace("{{EXAM_ATTEMPT}}", str(attempt_text))
        html = html.replace("{{SUBJECT_ROWS}}", subject_rows)
        html = html.replace("{{TOTAL_MARKS}}", str(snapshot["total_marks"]))
        html = html.replace("{{SEM_RESULT}}", snapshot["sem_result"])
        html = html.replace("{{SGPA}}", snapshot["sgpa"])
        html = html.replace("{{RESULT_DATE}}", snapshot["result_date"])
        html = html.replace("{{RESULT_CLASS}}", get_result_class(snapshot["sem_result"]))
        html = html.replace("{{CLASS_RANK}}", str(current_rank))
        html = html.replace("{{BATCH_COUNT}}", str(batch_count))
        html = html.replace("{{BETTER_THAN}}", percentile_text)
        html = html.replace("{{GAP_FROM_TOP}}", gap_from_top)
        html = html.replace("{{SUBJECT_SCORECARDS}}", subject_scorecards)
        html = html.replace("{{BEST_SUBJECT}}", subject_metrics["best_subject"])
        html = html.replace("{{WEAKEST_SUBJECT}}", subject_metrics["weakest_subject"])
        html = html.replace("{{ABOVE_AVG_SUBJECTS}}", subject_metrics["subjects_above_average"])
        html = html.replace("{{CONSISTENCY_SCORE}}", subject_metrics["consistency_score"])
        html = html.replace("{{CONSISTENCY_BAND}}", subject_metrics["consistency_band"])
        html = html.replace("{{PERFORMANCE_NOTE}}", compliment_payload["performance_note"])
        html = html.replace("{{STRENGTH_TAGS}}", compliment_payload["strength_tags"])
        html = html.replace("{{ADVICE_NOTE}}", advice_payload["advice_note"])
        html = html.replace("{{ADVICE_TAGS}}", advice_payload["advice_tags"])

        out_file = os.path.join(output_folder, snapshot["file_name"].replace(".json", ".html"))

        with open(out_file, "w", encoding="utf-8") as f:
            f.write(html)

        generated_files.append(out_file)

    # ----------------------------
    # MERGE (FIXED PATH)
    # ----------------------------
    merged_path = os.path.join(
        COMBINED_BASE,
        f"combined_{folder_name}.html"
    )

    sorted_subject_summary = sorted(subject_summary, key=lambda row: (-row["average"], row["subject_name"]))

    subject_chart_html = build_subject_chart_html(subject_summary)

    subject_overview_rows = ""
    for item in sorted_subject_summary[:8]:
        subject_overview_rows += (
            "<tr>"
            f"<td style=\"border:1px solid #d8dfeb;padding:8px;\">{escape(item['subject_code'])}</td>"
            f"<td style=\"border:1px solid #d8dfeb;padding:8px;\">{escape(item['subject_name'])}</td>"
            f"<td style=\"border:1px solid #d8dfeb;padding:8px;\">{item['average']}</td>"
            f"<td style=\"border:1px solid #d8dfeb;padding:8px;\">{item['top_marks']}</td>"
            "</tr>"
        )

    subject_scoreboard_html = ""
    practical_scoreboard_html = ""
    practical_board_by_code = {}
    for item in practical_summary:
        practical_rows_html = ""
        for row in item.get("ranking_rows", []):
            p_status = row.get("practical_status", "na")
            if p_status == "pass":
                row_style = "background:#e8f8ef;color:#157347;"
            elif p_status == "fail":
                row_style = "background:#ffe5e8;color:#c62828;"
            else:
                row_style = "background:#eef2f8;color:#344054;"
            practical_rows_html += (
                "<tr>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{row_style}\">{row['rank']}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{row_style}\">{escape(row['student_name'])}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{row_style}\">{escape(row['roll_no'])}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{row_style}\">{row['marks']}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{row_style}\">{'Pass' if p_status == 'pass' else ('Fail' if p_status == 'fail' else 'NA')}</td>"
                "</tr>"
            )

        practical_card_html = f"""
<div style="border:1px solid #d8dfeb;border-radius:14px;padding:16px;background:#ffffff;margin-top:16px;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:12px;">
        <div>
            <h3 style="margin:0;color:#344054;font-size:17px;">{escape(item['subject_name'])}</h3>
            <div style="color:#667085;font-size:13px;margin-top:4px;">{escape(item['subject_code'])}</div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3, minmax(120px, 1fr));gap:10px;min-width:min(100%, 420px);">
            <div style="border:1px solid #d8dfeb;border-radius:10px;padding:10px;background:#fafbff;"><small style="display:block;color:#667085;margin-bottom:4px;">Practical Avg</small><strong>{item['average']}</strong></div>
            <div style="border:1px solid #d8dfeb;border-radius:10px;padding:10px;background:#fafbff;"><small style="display:block;color:#667085;margin-bottom:4px;">Top Practical</small><strong>{item['top_marks']}</strong></div>
            <div style="border:1px solid #d8dfeb;border-radius:10px;padding:10px;background:#fafbff;"><small style="display:block;color:#667085;margin-bottom:4px;">Students</small><strong>{item['entries']}</strong></div>
        </div>
    </div>
    <table style="width:100%;border-collapse:collapse;">
        <thead>
            <tr>
                <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Rank</th>
                <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Student</th>
                <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Roll No</th>
                <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Practical Marks</th>
                <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Semester Result</th>
            </tr>
        </thead>
        <tbody>{practical_rows_html}</tbody>
    </table>
</div>
"""
        practical_scoreboard_html += practical_card_html
        practical_board_by_code[item.get("subject_code", "")] = practical_card_html

    subject_board_by_code = {}
    for item in sorted(subject_summary, key=lambda row: row["subject_name"]):
        subject_rows_html = ""
        for row in item.get("ranking_rows", []):
            row_style = get_result_row_style(row.get("result", ""))
            subject_rows_html += (
                "<tr>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{row_style}\">{row['rank']}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{row_style}\">{escape(row['student_name'])}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{row_style}\">{escape(row['roll_no'])}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{row_style}\">{row['marks']}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{row_style}\">{escape(row['result'])}</td>"
                "</tr>"
            )

        subject_card_html = f"""
<div style="border:1px solid #d8dfeb;border-radius:14px;padding:16px;background:#ffffff;margin-top:16px;">
    <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;margin-bottom:12px;">
        <div>
            <h3 style="margin:0;color:#344054;font-size:17px;">{escape(item['subject_name'])}</h3>
            <div style="color:#667085;font-size:13px;margin-top:4px;">{escape(item['subject_code'])}</div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(3, minmax(120px, 1fr));gap:10px;min-width:min(100%, 420px);">
            <div style="border:1px solid #d8dfeb;border-radius:10px;padding:10px;background:#fafbff;"><small style="display:block;color:#667085;margin-bottom:4px;">Batch Avg</small><strong>{item['average']}</strong></div>
            <div style="border:1px solid #d8dfeb;border-radius:10px;padding:10px;background:#fafbff;"><small style="display:block;color:#667085;margin-bottom:4px;">Top Marks</small><strong>{item['top_marks']}</strong></div>
            <div style="border:1px solid #d8dfeb;border-radius:10px;padding:10px;background:#fafbff;"><small style="display:block;color:#667085;margin-bottom:4px;">Students</small><strong>{item['entries']}</strong></div>
        </div>
    </div>
    <table style="width:100%;border-collapse:collapse;">
        <thead>
            <tr>
                <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Rank</th>
                <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Student</th>
                <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Roll No</th>
                <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Subject Marks</th>
                <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Semester Result</th>
            </tr>
        </thead>
        <tbody>{subject_rows_html}</tbody>
    </table>
</div>
"""
        subject_scoreboard_html += subject_card_html
        subject_board_by_code[item.get("subject_code", "")] = subject_card_html

    hardest_text = "-"
    easiest_text = "-"
    if hardest_subject:
        hardest_text = f"{hardest_subject['subject_name']} ({hardest_subject['average']})"
    if easiest_subject:
        easiest_text = f"{easiest_subject['subject_name']} ({easiest_subject['average']})"

    lower_rank_note = ""
    if ranked_snapshots:
        lower_slice = ranked_snapshots[max(0, len(ranked_snapshots) - min(5, len(ranked_snapshots))):]
        lower_names = ", ".join(item["student_name"] for item in lower_slice[:3])
        if tone_mode == "strict":
            lower_rank_note = (
                "The lower end of the ranking table should be read as a recovery zone, not as a fixed ceiling. "
                f"Students such as {escape(lower_names)} can still improve significantly through structured follow-up, subject-wise correction, and disciplined practice."
            )
        elif tone_mode == "motivational":
            lower_rank_note = (
                "The lower end of the ranking table still carries growth potential. "
                f"Students such as {escape(lower_names)} should be seen as candidates for strong comeback progress when guided with focused support and consistent effort."
            )
        else:
            lower_rank_note = (
                "The lower end of the ranking table should be approached with encouragement and guided recovery. "
                f"Students such as {escape(lower_names)} still show room for meaningful improvement when support is targeted subject by subject."
            )

    paired_subject_blocks_html = ""
    for item in sorted(subject_summary, key=lambda row: row["subject_name"]):
        sub_code = item.get("subject_code", "")
        subject_card = subject_board_by_code.get(sub_code, "")
        practical_card = practical_board_by_code.get(sub_code, "")
        if practical_card:
            paired_subject_blocks_html += (
                "<div style=\"margin-top:16px;display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start;\">"
                + subject_card
                + practical_card
                + "</div>"
            )
        else:
            paired_subject_blocks_html += (
                "<div style=\"margin-top:16px;\">"
                + subject_card
                + "</div>"
            )

    scoreboard_layout_html = (
        "<div>"
        "<h3 style=\"margin:0 0 10px;color:#344054;font-size:16px;\">Subject and Practical Rankboards</h3>"
        + paired_subject_blocks_html
        + "</div>"
    )

    summary_html = f"""
<div style="font-family: 'Segoe UI', Tahoma, sans-serif; margin-bottom: 24px; background: #ffffff; border: 1px solid #d8dfeb; border-radius: 14px; padding: 18px;">
    <h2 style="margin: 0 0 14px; color: #2f6fed;">Semester Comparison Dashboard</h2>
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px;">
        <div style="border: 1px solid #d8dfeb; border-radius: 10px; padding: 12px; background: #fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Batch Size</small><strong style="font-size:20px;">{batch_count}</strong></div>
        <div style="border: 1px solid #d8dfeb; border-radius: 10px; padding: 12px; background: #fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Highest Marks</small><strong style="font-size:20px;">{highest_marks}</strong></div>
        <div style="border: 1px solid #d8dfeb; border-radius: 10px; padding: 12px; background: #fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Lowest Marks</small><strong style="font-size:20px;">{lowest_marks}</strong></div>
        <div style="border: 1px solid #d8dfeb; border-radius: 10px; padding: 12px; background: #fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Average Marks</small><strong style="font-size:20px;">{average_marks}</strong></div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px;">
        <div style="border: 1px solid #d8dfeb; border-radius: 10px; padding: 12px; background: #fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Hardest Subject</small><strong>{escape(hardest_text)}</strong></div>
        <div style="border: 1px solid #d8dfeb; border-radius: 10px; padding: 12px; background: #fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Easiest Subject</small><strong>{escape(easiest_text)}</strong></div>
        <div style="border: 1px solid #d8dfeb; border-radius: 10px; padding: 12px; background: #fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Subjects Analyzed</small><strong>{len(subject_summary)}</strong></div>
        <div style="border: 1px solid #d8dfeb; border-radius: 10px; padding: 12px; background: #fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Practical Boards</small><strong>{len(practical_summary)}</strong></div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:16px;">
        <div style="border:1px solid #b7e4c7;border-radius:10px;padding:12px;background:#e8f8ef;"><small style="display:block;color:#667085;margin-bottom:6px;">Pass Count</small><strong style="color:#157347;">{status_counts['Pass']}</strong></div>
        <div style="border:1px solid #f1d08a;border-radius:10px;padding:12px;background:#fff4db;"><small style="display:block;color:#667085;margin-bottom:6px;">Reappear Count</small><strong style="color:#b26a00;">{status_counts['Reappear']}</strong></div>
        <div style="border:1px solid #efb0b8;border-radius:10px;padding:12px;background:#ffe5e8;"><small style="display:block;color:#667085;margin-bottom:6px;">RL / Regn Count</small><strong style="color:#c62828;">{status_counts['RL/Regn']}</strong></div>
        <div style="border:1px solid #efb0b8;border-radius:10px;padding:12px;background:#ffe5e8;"><small style="display:block;color:#667085;margin-bottom:6px;">Absent (AB)</small><strong style="color:#c62828;">{status_counts['Absent']}</strong></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
        <div>
            <h3 style="margin:0 0 10px;color:#344054;font-size:16px;">Top Rank Snapshot</h3>
            <table style="width:100%;border-collapse:collapse;">
                <thead>
                    <tr>
                        <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Rank</th>
                        <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Student</th>
                        <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Roll No</th>
                        <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Marks</th>
                        <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Result</th>
                    </tr>
                </thead>
                <tbody>{top_three_rows}</tbody>
            </table>
            <div style="height:12px"></div>
            <h3 style="margin:0 0 10px;color:#344054;font-size:16px;">Top Rank Snapshot (Practical)</h3>
            <table style="width:100%;border-collapse:collapse;">
                <thead>
                    <tr>
                        <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Rank</th>
                        <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Student</th>
                        <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Roll No</th>
                        <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Practical Marks</th>
                        <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Status</th>
                    </tr>
                </thead>
                <tbody>{top_three_practical_rows}</tbody>
            </table>
        </div>
        <div>
            <h3 style="margin:0 0 10px;color:#344054;font-size:16px;">Full Ranking</h3>
            <table style="width:100%;border-collapse:collapse;">
                <thead>
                    <tr>
                        <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Rank</th>
                        <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Student</th>
                        <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Roll No</th>
                        <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Marks</th>
                        <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Result</th>
                    </tr>
                </thead>
                <tbody>{shared_leaderboard_rows}</tbody>
            </table>
            <div style="margin-top:12px;border:1px solid #d8dfeb;border-radius:12px;padding:12px;background:#fafbff;color:#475467;line-height:1.7;">
                <strong style="color:#344054;">Rankboard Reflection:</strong> {lower_rank_note}
            </div>
        </div>
    </div>
    <div style="margin-top:16px;">
        <h3 style="margin:0 0 10px;color:#344054;font-size:16px;">Subject Intelligence</h3>
        <table style="width:100%;border-collapse:collapse;">
            <thead>
                <tr>
                    <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Subject Code</th>
                    <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Subject Name</th>
                    <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Batch Average</th>
                    <th style="border:1px solid #d8dfeb;padding:8px;background:#eef2f8;">Top Marks</th>
                </tr>
            </thead>
            <tbody>{subject_overview_rows}</tbody>
        </table>
    </div>
    {subject_chart_html}
    {scoreboard_layout_html}
</div>
"""

    merged_head = extract_head_content(template)

    with open(merged_path, "w", encoding="utf-8") as out:
        out.write("<!DOCTYPE html><html><head>")
        out.write(merged_head)
        out.write("</head><body>")
        out.write(summary_html)

        for file in generated_files:
            with open(file, "r", encoding="utf-8") as f:
                out.write(extract_body_content(f.read()))
                out.write("<div style=\"height:28px\"></div>")

        out.write("</body></html>")

    if progress_callback:
        progress_callback(f"HTML generation complete. Output saved to {merged_path}")

    return merged_path


# ----------------------------
# ROUTES (WEB INTERFACE)
# ----------------------------

RUN_FOLDER = None

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/start", methods=["POST"])
def start_process():
    global RUN_FOLDER
    roll = (request.form.get("roll") or "").strip()
    otp_roll = (request.form.get("otp_roll") or "").strip()

    if not roll or not otp_roll:
        return jsonify({"status": "error", "message": "Both roll number fields are required."})

    RUN_FOLDER = create_run_folder()

    res1 = step1_fetch_mbn(roll, RUN_FOLDER)
    if res1["status"] == "error":
        return jsonify(res1)

    res_my = step1_fetch_mymbn(otp_roll or roll, RUN_FOLDER)
    if res_my["status"] == "error":
        return jsonify(res_my)

    res2 = step2_send_otp(RUN_FOLDER)
    return jsonify({"status": "otp_sent"})


@app.route("/verify", methods=["POST"])
def verify():
    if not RUN_FOLDER:
        return jsonify({"status": "error", "message": "Session not started. Please start OTP flow first."})

    otp = request.form.get("otp")

    res = step3_verify_otp(otp, RUN_FOLDER)

    if res["status"] == "error":
        return jsonify(res)

    sems = get_all_semesters(RUN_FOLDER)

    return jsonify({
        "status": "success",
        "sems": sems
    })


@app.route("/fetch", methods=["POST"])
def fetch():
    global PROGRESS_LOG, PROGRESS_SEQ
    PROGRESS_LOG = []
    PROGRESS_SEQ = 0

    start_roll = int(request.form.get("start"))
    end_roll = int(request.form.get("end"))
    sem_data = json.loads(request.form.get("sem"))
    tone_mode = request.form.get("tone_mode", "motivational").strip().lower() or "motivational"

    def progress_callback(message):
        push_progress(message)

    push_progress("Started roll-range fetch.")
    r4 = step4_fetch_range(start_roll, end_roll, RUN_FOLDER, progress_callback=progress_callback)
    if r4["status"] == "error":
        push_progress(f"Range error: {r4['message']}")
        return jsonify(r4)

    push_progress("Started DMC fetch.")
    r5 = step5_fetch_dmc(RUN_FOLDER, sem_data, progress_callback=progress_callback, reappear_update_mode="update_latest_non_empty")
    if r5["status"] == "error":
        push_progress(f"DMC error: {r5['message']}")
        return jsonify(r5)

    push_progress("Started HTML generation.")
    final_file = step6_generate_html(
        r5["folder"],
        RUN_FOLDER,
        progress_callback=progress_callback,
        tone_mode=tone_mode,
        report_mode=r5.get("mode", "single")
    )
    push_progress("Generation complete.")

    return send_file(final_file)


@app.route("/progress", methods=["GET"])
def progress_feed():
    since = request.args.get("since", "0").strip()
    try:
        since_id = int(since)
    except ValueError:
        since_id = 0
    items = [item for item in PROGRESS_LOG if item["id"] > since_id]
    latest = PROGRESS_LOG[-1]["id"] if PROGRESS_LOG else since_id
    return jsonify({"status": "success", "latest": latest, "items": items})


@app.route("/wipe-data", methods=["POST"])
def wipe_data():
    kept = wipe_old_data_keep_latest()
    return jsonify({
        "status": "success",
        "kept_run_folder": kept["run_folder"],
        "deleted_runs": kept.get("deleted_runs", []),
        "failed_runs": kept.get("failed_runs", []),
        "resp_base": kept.get("resp_base", RESP_BASE),
    })


@app.route("/update-jsession", methods=["POST"])
def update_jsession_route():
    result = update_jsession_and_req1()
    code = 200 if result.get("status") == "success" else 400
    return jsonify(result), code


if __name__ == "__main__":
    print("🚀 Starting server...")
    class ResultExtractorGUI:
        def __init__(self, root):
            self.root = root
            self.root.title("Result Extractor")
            self.root.geometry("700x620")
            self.root.minsize(700, 620)
            self.root.configure(bg="#08110d")

            self.run_folder = None
            self.semesters = []

            self.roll_var = tk.StringVar()
            self.otp_roll_var = tk.StringVar()
            self.otp_var = tk.StringVar()
            self.start_var = tk.StringVar()
            self.end_var = tk.StringVar()
            self.sem_var = tk.StringVar()
            self.status_var = tk.StringVar(value="Enter roll number to begin.")

            self.colors = {
                "bg": "#08110d",
                "panel": "#0d1712",
                "panel_alt": "#101f18",
                "text": "#d7ffe8",
                "muted": "#7acb9e",
                "accent": "#37ff8b",
                "accent_dim": "#123524",
                "border": "#1f6a46",
                "warning": "#c7ff5e"
            }

            self.configure_styles()
            self.build_ui()

        def configure_styles(self):
            style = ttk.Style()
            try:
                style.theme_use("clam")
            except Exception:
                pass

            style.configure(
                "Cyber.TCombobox",
                fieldbackground=self.colors["panel_alt"],
                background=self.colors["panel_alt"],
                foreground=self.colors["text"],
                arrowcolor=self.colors["accent"]
            )

        def build_ui(self):
            container = tk.Frame(self.root, padx=18, pady=18, bg=self.colors["bg"])
            container.pack(fill="both", expand=True)

            hero = tk.Frame(
                container,
                bg=self.colors["panel"],
                highlightbackground=self.colors["border"],
                highlightthickness=1,
                padx=16,
                pady=14
            )
            hero.pack(fill="x", pady=(0, 14))

            tk.Label(
                hero,
                text="SECURE RESULT CONSOLE",
                font=("Consolas", 10, "bold"),
                fg=self.colors["accent"],
                bg=self.colors["panel"]
            ).pack(anchor="w")

            tk.Label(
                hero,
                text="Result Extractor",
                font=("Consolas", 20, "bold"),
                fg=self.colors["text"],
                bg=self.colors["panel"]
            ).pack(anchor="w", pady=(4, 2))

            tk.Label(
                hero,
                text="Minimal-change desktop shell with live request tracking",
                font=("Consolas", 10),
                fg=self.colors["muted"],
                bg=self.colors["panel"]
            ).pack(anchor="w")

            form = tk.Frame(
                container,
                bg=self.colors["panel"],
                highlightbackground=self.colors["border"],
                highlightthickness=1,
                padx=14,
                pady=14
            )
            form.pack(fill="x")
            form.columnconfigure(1, weight=1)

            label_style = {
                "font": ("Consolas", 10, "bold"),
                "fg": self.colors["accent"],
                "bg": self.colors["panel"]
            }
            entry_style = {
                "bg": self.colors["panel_alt"],
                "fg": self.colors["text"],
                "insertbackground": self.colors["accent"],
                "relief": "flat",
                "highlightthickness": 1,
                "highlightbackground": self.colors["border"],
                "highlightcolor": self.colors["accent"],
                "font": ("Consolas", 11)
            }
            button_style = {
                "width": 18,
                "bg": self.colors["accent_dim"],
                "fg": self.colors["accent"],
                "activebackground": self.colors["accent"],
                "activeforeground": "#041109",
                "relief": "flat",
                "bd": 0,
                "font": ("Consolas", 10, "bold"),
                "cursor": "hand2"
            }

            tk.Label(form, text="Roll Number", **label_style).grid(row=0, column=0, sticky="w", pady=6)
            tk.Entry(form, textvariable=self.roll_var, **entry_style).grid(row=0, column=1, sticky="ew", padx=(12, 0), pady=6)
            tk.Label(form, text="Primary Roll", fg=self.colors["muted"], bg=self.colors["panel"], font=("Consolas", 9)).grid(row=0, column=2, padx=(12, 0), pady=6)

            tk.Label(form, text="OTP Mob Roll", **label_style).grid(row=1, column=0, sticky="w", pady=6)
            tk.Entry(form, textvariable=self.otp_roll_var, **entry_style).grid(row=1, column=1, sticky="ew", padx=(12, 0), pady=6)
            tk.Button(form, text="Send OTP", command=self.start_otp_flow, **button_style).grid(row=1, column=2, padx=(12, 0), pady=6)

            tk.Label(form, text="OTP", **label_style).grid(row=2, column=0, sticky="w", pady=6)
            tk.Entry(form, textvariable=self.otp_var, **entry_style).grid(row=2, column=1, sticky="ew", padx=(12, 0), pady=6)
            tk.Button(form, text="Verify OTP", command=self.verify_otp_flow, **button_style).grid(row=2, column=2, padx=(12, 0), pady=6)

            tk.Label(form, text="Semester", **label_style).grid(row=3, column=0, sticky="w", pady=6)
            self.sem_combo = ttk.Combobox(form, textvariable=self.sem_var, state="readonly", style="Cyber.TCombobox", font=("Consolas", 10))
            self.sem_combo.grid(row=3, column=1, sticky="ew", padx=(12, 0), pady=6)

            tk.Label(form, text="Start Roll", **label_style).grid(row=4, column=0, sticky="w", pady=6)
            tk.Entry(form, textvariable=self.start_var, **entry_style).grid(row=4, column=1, sticky="ew", padx=(12, 0), pady=6)

            tk.Label(form, text="End Roll", **label_style).grid(row=5, column=0, sticky="w", pady=6)
            tk.Entry(form, textvariable=self.end_var, **entry_style).grid(row=5, column=1, sticky="ew", padx=(12, 0), pady=6)
            tk.Button(form, text="Generate HTML", command=self.run_generation_flow, **button_style).grid(row=5, column=2, padx=(12, 0), pady=6)

            tk.Label(form, text="Storage Mgmt", **label_style).grid(row=6, column=0, sticky="w", pady=6)
            tools_cell = tk.Frame(form, bg=self.colors["panel"])
            tools_cell.grid(row=6, column=1, sticky="w", padx=(12, 0), pady=6)
            tk.Label(tools_cell, text="Keep latest run only", fg=self.colors["muted"], bg=self.colors["panel"], font=("Consolas", 9)).pack(side="left")
            tk.Button(tools_cell, text="Update JSESSION", command=self.update_jsession_click, **button_style).pack(side="left", padx=(10, 0))
            tk.Button(form, text="Wipe Old Data", command=self.wipe_old_data, **button_style).grid(row=6, column=2, padx=(12, 0), pady=6)

            tk.Label(container, text="Status", font=("Consolas", 10, "bold"), fg=self.colors["warning"], bg=self.colors["bg"]).pack(anchor="w", pady=(16, 6))
            tk.Label(
                container,
                textvariable=self.status_var,
                justify="left",
                anchor="w",
                wraplength=590,
                font=("Consolas", 10),
                fg=self.colors["text"],
                bg=self.colors["bg"]
            ).pack(fill="x")

            tk.Label(container, text="Activity Log", font=("Consolas", 10, "bold"), fg=self.colors["warning"], bg=self.colors["bg"]).pack(anchor="w", pady=(16, 6))
            self.output_text = tk.Text(
                container,
                height=16,
                wrap="word",
                bg="#07100c",
                fg=self.colors["accent"],
                insertbackground=self.colors["accent"],
                relief="flat",
                bd=0,
                highlightthickness=1,
                highlightbackground=self.colors["border"],
                highlightcolor=self.colors["accent"],
                font=("Consolas", 10),
                selectbackground="#1f6a46",
                selectforeground="#effff5"
            )
            self.output_text.pack(fill="both", expand=True)

        def append_output(self, text):
            self.output_text.insert("end", text + "\n")
            self.output_text.see("end")

        def set_status(self, text):
            self.status_var.set(text)
            self.append_output(text)

        def run_in_thread(self, target):
            threading.Thread(target=target, daemon=True).start()

        def wipe_old_data(self):
            kept = wipe_old_data_keep_latest()
            kept_run = kept.get("run_folder") or "none"
            self.set_status(f"Old data wiped. Kept latest run folder: {kept_run}")

        def update_jsession_click(self):
            def worker():
                self.root.after(0, lambda: self.set_status("Updating JSESSION from iums.kuk.ac.in..."))
                res = update_jsession_and_req1()
                if res.get("status") != "success":
                    self.root.after(0, lambda: messagebox.showerror("JSESSION Error", res.get("message", "Update failed.")))
                    self.root.after(0, lambda: self.set_status("JSESSION update failed."))
                    return
                self.root.after(0, lambda: self.set_status("JSESSION updated in requests/jsession.txt and req1.txt."))
                self.root.after(0, lambda: messagebox.showinfo("JSESSION Updated", "JSESSION refreshed and req1.txt updated."))

            self.run_in_thread(worker)

        def start_otp_flow(self):
            roll = self.roll_var.get().strip()
            otp_roll = self.otp_roll_var.get().strip()
            if not roll:
                messagebox.showerror("Missing Input", "Please enter a roll number.")
                return
            if not otp_roll:
                messagebox.showerror("Missing Input", "Please enter OTP mobile roll number.")
                return

            def worker():
                self.run_folder = create_run_folder()
                self.root.after(0, lambda: self.set_status("Fetching result mobile and OTP mobile, then sending OTP..."))

                res1 = step1_fetch_mbn(roll, self.run_folder)
                if res1["status"] == "error":
                    self.root.after(0, lambda: messagebox.showerror("Step 1 Error", res1["message"]))
                    return

                res_my = step1_fetch_mymbn(otp_roll, self.run_folder)
                if res_my["status"] == "error":
                    self.root.after(0, lambda: messagebox.showerror("OTP Mobile Error", res_my["message"]))
                    return

                res2 = step2_send_otp(self.run_folder)
                if res2["status"] == "error":
                    self.root.after(0, lambda: messagebox.showerror("OTP Error", res2["message"]))
                    return

                self.root.after(0, lambda: self.set_status("OTP sent. Enter the OTP and click Verify OTP."))

            self.run_in_thread(worker)

        def verify_otp_flow(self):
            otp = self.otp_var.get().strip()
            if not self.run_folder:
                messagebox.showerror("Missing Step", "Please send OTP first.")
                return
            if not otp:
                messagebox.showerror("Missing Input", "Please enter the OTP.")
                return

            def worker():
                self.root.after(0, lambda: self.set_status("Verifying OTP and loading semesters..."))
                res = step3_verify_otp(otp, self.run_folder)
                if res["status"] == "error":
                    self.root.after(0, lambda: messagebox.showerror("Verify Error", res["message"]))
                    return

                parsed = res.get("data")
                if isinstance(parsed, dict):
                    api_success = parsed.get("success")
                    api_message = parsed.get("message") or "No semester data was returned."
                    api_data = parsed.get("data")
                    if api_success is False or not api_data:
                        self.root.after(0, lambda: messagebox.showerror("Verify Error", api_message))
                        self.root.after(0, lambda: self.set_status(f"Verification failed: {api_message}"))
                        return

                semesters = get_all_semesters(self.run_folder)
                self.semesters = semesters
                labels = [item["label"] for item in semesters]

                def update_semesters():
                    self.sem_combo["values"] = labels
                    if labels:
                        self.sem_combo.current(0)
                        self.set_status("OTP verified. Select semester, enter start/end roll, then generate HTML.")
                    else:
                        self.set_status("OTP verified but no semesters were found.")

                self.root.after(0, update_semesters)

            self.run_in_thread(worker)

        def run_generation_flow(self):
            if not self.run_folder:
                messagebox.showerror("Missing Step", "Please complete OTP verification first.")
                return
            if not self.semesters:
                messagebox.showerror("Missing Semester", "Please verify OTP and load semester options first.")
                return

            selected_label = self.sem_var.get().strip()
            start_roll = self.start_var.get().strip()
            end_roll = self.end_var.get().strip()

            if not selected_label:
                messagebox.showerror("Missing Input", "Please select a semester.")
                return
            if not start_roll or not end_roll:
                messagebox.showerror("Missing Input", "Please enter start and end roll numbers.")
                return
            if not start_roll.isdigit() or not end_roll.isdigit():
                messagebox.showerror("Invalid Input", "Start and end roll numbers must be numeric.")
                return

            sem_data = None
            for item in self.semesters:
                if item["label"] == selected_label:
                    sem_data = item["value"]
                    break

            if sem_data is None:
                messagebox.showerror("Selection Error", "Could not read the selected semester.")
                return

            def worker():
                def progress_update(message):
                    self.root.after(0, lambda msg=message: self.set_status(msg))

                self.root.after(0, lambda: self.set_status("Starting roll range fetch..."))

                r4 = step4_fetch_range(int(start_roll), int(end_roll), self.run_folder, progress_callback=progress_update)
                if r4["status"] == "error":
                    self.root.after(0, lambda: messagebox.showerror("Range Error", r4["message"]))
                    return

                r5 = step5_fetch_dmc(self.run_folder, sem_data, progress_callback=progress_update, reappear_update_mode="update_latest_non_empty")
                if r5["status"] == "error":
                    self.root.after(0, lambda: messagebox.showerror("DMC Error", r5["message"]))
                    return

                try:
                    final_file = step6_generate_html(
                        r5["folder"],
                        self.run_folder,
                        progress_callback=progress_update,
                        tone_mode="motivational",
                        report_mode=r5.get("mode", "single")
                    )
                except Exception as exc:
                    self.root.after(0, lambda: messagebox.showerror("HTML Error", str(exc)))
                    return

                def finish():
                    self.set_status(f"Done. HTML saved at: {final_file}")
                    try:
                        os.startfile(final_file)
                    except Exception:
                        pass

                self.root.after(0, finish)

            self.run_in_thread(worker)

    root = tk.Tk()
    ResultExtractorGUI(root)
    root.mainloop()
