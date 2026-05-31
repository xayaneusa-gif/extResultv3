# app.py (PART 1 - CORE SETUP + FIXED LOGIC)
print("ðŸ”¥ FILE STARTED")

from flask import Flask, render_template, render_template_string, request, jsonify, send_file
import requests
import json
import re
import os
import threading
import urllib3
import xml.etree.ElementTree as ET
from datetime import datetime
from html import escape
from io import BytesIO
import base64
import tkinter as tk
from tkinter import messagebox, ttk
import sys
import streamlit as st

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:
    plt = None

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
        parsed = res.json()

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
        # ----------------------------
        # LOAD MBN
        # ----------------------------
        with open(os.path.join(run_folder, "res_mbn.json")) as f:
            data = json.load(f)

        mbn = data[0].get("mbn") if isinstance(data, list) else data.get("mbn")

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
        # ðŸ”¥ LOAD COOKIE FROM req1.txt EXACTLY LIKE ORIGINAL
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
        # ðŸ”¥ EXACT SAME REPLACE LOGIC
        # ----------------------------
        new_path = re.sub(
            r"__mobileNo=[^&]+",
            f"__mobileNo={mbn}",
            path
        )

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
        with open(os.path.join(run_folder, "res_mbn.json")) as f:
            data = json.load(f)

        mbn = data[0]["mbn"]
        std = data[0]["std"]

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
        parsed = res.json()

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


def _load_text_file(*parts):
    try:
        path = os.path.join(BASE_DIR, *parts)
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as file_obj:
                return file_obj.read()
    except Exception:
        pass
    return ""


INLINE_WEB_TEMPLATE = _load_text_file("templates", "index1.html")
INLINE_RESULT_TEMPLATE = _load_text_file("templates", "template.html") or _load_text_file("template.html")

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
        parsed = res.json()

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
        with open(os.path.join(run_folder, "res_mbn.json")) as f:
            data = json.load(f)

        mbn = data[0].get("mbn") if isinstance(data, list) else data.get("mbn")

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
        url = f"https://{host}{new_path}"

        res = requests.get(url, headers=headers, verify=False, timeout=10)

        return {"status": "success", "msg": "OTP Sent", "response": res.text}

    except Exception as e:
        return {"status": "error", "message": str(e)}


# ----------------------------
# STEP 3: VERIFY OTP
# ----------------------------
def step3_verify_otp(otp, run_folder):
    try:
        with open(os.path.join(run_folder, "res_mbn.json")) as f:
            data = json.load(f)

        mbn = data[0]["mbn"]
        std = data[0]["std"]

        method, path, headers = load_request(os.path.join(REQ_FOLDER, "req3.txt"))
        host = headers.get("Host")

        new_path = path
        new_path = re.sub(r"__std=[^&]+", f"__std={std}", new_path)
        new_path = re.sub(r"__mobileNo=[^&]+", f"__mobileNo={mbn}", new_path)
        new_path = re.sub(r"authValue=[^&]+", f"authValue={otp}", new_path)

        url = f"https://{host}{new_path}"

        res = requests.get(url, headers=headers, verify=False)
        parsed = res.json()

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
    


    # ----------------------------
# GET ALL SEM OPTIONS (FIXED)
# ----------------------------
def get_all_semesters(run_folder):
    path = os.path.join(run_folder, "res_result.json")

    with open(path) as f:
        data = json.load(f)

    sem_list = []

    for sem in data["data"]:
        name = sem.get("semName")
        status = sem.get("semesterResult") or sem.get("resultStatus")

        label = f"{name} - {status}"

        if sem.get("examTypeKey") == "REAPPEAR":
            label += " (Reappear)"

        sem_list.append({
            "label": label,
            "value": {
                "qlId": sem.get("qlId"),
                "usyId": sem.get("usyId"),
                "smId": sem.get("smId"),
                "esId": sem.get("esId"),
                "noOfSem": sem.get("noOfSem")
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
def step5_fetch_dmc(run_folder, sem_data, progress_callback=None):
    try:
        xml_path = os.path.join(run_folder, "data.xml")

        method, path, headers = load_request(os.path.join(REQ_FOLDER, "req1.txt"))
        host = headers.get("Host")

        url = f"https://{host}/restApi/fetchStudentDmcReport.json"

        sem_folder = os.path.join(run_folder, f"sem_{sem_data['smId']}")
        os.makedirs(sem_folder, exist_ok=True)

        tree = ET.parse(xml_path)
        root = tree.getroot()

        items = root.findall("item")
        total_items = len(items)

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
                "qualificationId": sem_data["qlId"],
                "syllbusId": sem_data["usyId"],
                "semesterId": sem_data["smId"],
                "examScheduleId": sem_data["esId"],
                "noOfSem": sem_data["noOfSem"],
                "studentRegIds": std,
                "stdOpenResFlag": "true"
            }

            file_path = os.path.join(sem_folder, f"{roll}.json")

            try:
                if progress_callback:
                    progress_callback(f"Fetching DMC JSON: {index}/{total_items} (roll {roll})")

                res = requests.post(url, headers=headers, data=post_data, verify=False)

                try:
                    parsed = json.loads(res.text)
                    with open(file_path, "w") as f:
                        json.dump(parsed, f, indent=4)
                except:
                    with open(file_path, "w") as f:
                        f.write(res.text)

            except:
                continue

        if progress_callback:
            progress_callback("DMC JSON fetch complete.")

        return {"status": "success", "folder": sem_folder}

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
            if pType == "theory" and eType == "external":
                key = "theory_external"
            elif pType == "theory" and eType == "internal":
                key = "theory_internal"
            elif pType == "practical" and eType == "external":
                key = "practical_external"
            elif pType == "practical" and eType == "internal":
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
    }


def get_result_class(result_text):
    value = " ".join((result_text or "").strip().lower().split())

    if not value:
        return "status-neutral"
    if "rl" in value or "regn" in value:
        return "status-absent"
    if "reappear" in value or "re-appear" in value or value == "re" or value.startswith("re ") or "reappear in" in value:
        return "status-reappear"
    if "pass" in value:
        return "status-pass"
    if "fail" in value:
        return "status-fail"
    if "abs" in value:
        return "status-absent"
    return "status-neutral"


def get_result_row_style(result_text):
    class_name = get_result_class(result_text)
    styles = {
        "status-pass": "background:#e8f8ef;color:#157347;",
        "status-reappear": "background:#fff4db;color:#b26a00;",
        "status-absent": "background:#ffe5e8;color:#c62828;",
        "status-fail": "background:#ffe9e1;color:#d9480f;",
        "status-neutral": "background:#e8f8ef;color:#157347;",
    }
    return styles.get(class_name, styles["status-neutral"])


def render_subject_rows(subject_entries, subject_rank_lookup, subject_avg_lookup):
    rows = ""

    def fmt_mo(values):
        return "+".join(str(value) for value in values) if values else "-"

    for entry in subject_entries:
        subject_code = entry["subject_code"]
        subject_rank = subject_rank_lookup.get(subject_code, "-")
        subject_avg = subject_avg_lookup.get(subject_code, 0)
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
            f"<td>{escape(entry['subject_result'])}</td>"
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
            "status-absent": ("#ffe5e8", "#c62828", "#efb0b8"),
            "status-fail": ("#ffe9e1", "#d9480f", "#f0b199"),
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
        elif status_class == "status-absent":
            opening = "This record requires immediate academic attention, though completed subjects still show identifiable strengths."
        else:
            opening = f"This academic profile currently stands at rank #{current_rank} in the extracted batch."
    elif tone_mode == "motivational":
        if status_class == "status-pass":
            opening = f"This student has earned rank #{current_rank} and is already ahead of {better_than}% of the extracted batch, which is a strong foundation to build on."
        elif status_class == "status-reappear":
            opening = f"Even with a reappear status, this student still shows visible promise and a recoverable academic profile at rank #{current_rank}."
        elif status_class == "status-absent":
            opening = "This record needs recovery, but the completed work still shows that the student has strengths worth building on."
        else:
            opening = f"This result still shows growth potential, with the student currently placed at rank #{current_rank}."
    else:
        if status_class == "status-pass":
            opening = f"This student stands at rank #{current_rank} in the semester and is ahead of {better_than}% of the extracted batch."
        elif status_class == "status-reappear":
            opening = f"This student still shows meaningful potential despite a reappear status, with rank #{current_rank} in the extracted batch."
        elif status_class == "status-absent":
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
                tone = "This is encouraging work. Keep nurturing it, because this subject can remain one of the studentâ€™s dependable strengths."
            else:
                tone = (
                    f"This is encouraging work. Keep the same discipline and revision rhythm here, "
                    f"because this subject can remain one of the studentâ€™s reliable strengths."
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


# ----------------------------
# STEP 6: JSON â†’ HTML (FULL)
# ----------------------------
def step6_generate_html(data_folder, run_folder, progress_callback=None, tone_mode="motivational"):
    if INLINE_RESULT_TEMPLATE:
        template = INLINE_RESULT_TEMPLATE
    else:
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            template = f.read()

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

    rank_lookup = {}
    batch_count = len(ranked_snapshots)
    average_marks = 0
    highest_marks = 0
    lowest_marks = 0
    status_counts = {
        "Pass": 0,
        "Reappear": 0,
        "RL/Regn": 0,
    }
    shared_leaderboard_rows = ""
    top_three_rows = ""

    if ranked_snapshots:
        totals = [item["total_marks"] for item in ranked_snapshots]
        highest_marks = max(totals)
        lowest_marks = min(totals)
        average_marks = round(sum(totals) / len(totals), 2)

        for rank, snapshot in enumerate(ranked_snapshots, start=1):
            rank_lookup[snapshot["file_name"]] = rank
            result_style = get_result_row_style(snapshot["sem_result"])
            result_class = get_result_class(snapshot["sem_result"])
            if result_class == "status-pass":
                status_counts["Pass"] += 1
            elif result_class == "status-reappear":
                status_counts["Reappear"] += 1
            elif result_class == "status-absent":
                status_counts["RL/Regn"] += 1
            row_html = (
                "<tr>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{result_style}\">{rank}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{result_style}\">{escape(snapshot['student_name'])}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{result_style}\">{escape(snapshot['roll_no'])}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{result_style}\">{escape(str(snapshot['total_marks']))}</td>"
                f"<td style=\"border:1px solid #d8dfeb;padding:8px;{result_style}\">{escape(snapshot['sem_result'])}</td>"
                "</tr>"
            )
            shared_leaderboard_rows += row_html
            if rank <= 3:
                top_three_rows += row_html

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
        html = html.replace("{{ROLL_NO}}", snapshot["roll_no"])
        html = html.replace("{{REG_NO}}", snapshot["reg_no"])
        html = html.replace("{{STUDENT_NAME}}", snapshot["student_name"])
        html = html.replace("{{FATHER_NAME}}", snapshot["father_name"])
        html = html.replace("{{MOTHER_NAME}}", snapshot["mother_name"])
        html = html.replace("{{INSTITUTE}}", snapshot["institute"])
        html = html.replace("{{DEGREE}}", snapshot["degree"])
        html = html.replace("{{EXAM_SCHEDULE}}", snapshot["exam_schedule"])
        html = html.replace("{{SEMESTER}}", snapshot["semester"])
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

        subject_scoreboard_html += f"""
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

    summary_html = f"""
<div style="font-family: 'Segoe UI', Tahoma, sans-serif; margin-bottom: 24px; background: #ffffff; border: 1px solid #d8dfeb; border-radius: 14px; padding: 18px;">
    <h2 style="margin: 0 0 14px; color: #2f6fed;">Semester Comparison Dashboard</h2>
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px;">
        <div style="border: 1px solid #d8dfeb; border-radius: 10px; padding: 12px; background: #fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Batch Size</small><strong style="font-size:20px;">{batch_count}</strong></div>
        <div style="border: 1px solid #d8dfeb; border-radius: 10px; padding: 12px; background: #fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Highest Marks</small><strong style="font-size:20px;">{highest_marks}</strong></div>
        <div style="border: 1px solid #d8dfeb; border-radius: 10px; padding: 12px; background: #fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Lowest Marks</small><strong style="font-size:20px;">{lowest_marks}</strong></div>
        <div style="border: 1px solid #d8dfeb; border-radius: 10px; padding: 12px; background: #fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Average Marks</small><strong style="font-size:20px;">{average_marks}</strong></div>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-bottom:16px;">
        <div style="border: 1px solid #d8dfeb; border-radius: 10px; padding: 12px; background: #fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Hardest Subject</small><strong>{escape(hardest_text)}</strong></div>
        <div style="border: 1px solid #d8dfeb; border-radius: 10px; padding: 12px; background: #fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Easiest Subject</small><strong>{escape(easiest_text)}</strong></div>
        <div style="border: 1px solid #d8dfeb; border-radius: 10px; padding: 12px; background: #fafbff;"><small style="display:block;color:#667085;margin-bottom:6px;">Subjects Analyzed</small><strong>{len(subject_summary)}</strong></div>
    </div>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:16px;">
        <div style="border:1px solid #b7e4c7;border-radius:10px;padding:12px;background:#e8f8ef;"><small style="display:block;color:#667085;margin-bottom:6px;">Pass Count</small><strong style="color:#157347;">{status_counts['Pass']}</strong></div>
        <div style="border:1px solid #f1d08a;border-radius:10px;padding:12px;background:#fff4db;"><small style="display:block;color:#667085;margin-bottom:6px;">Reappear Count</small><strong style="color:#b26a00;">{status_counts['Reappear']}</strong></div>
        <div style="border:1px solid #efb0b8;border-radius:10px;padding:12px;background:#ffe5e8;"><small style="display:block;color:#667085;margin-bottom:6px;">RL / Regn Count</small><strong style="color:#c62828;">{status_counts['RL/Regn']}</strong></div>
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
    <div style="margin-top:16px;">
        <h3 style="margin:0 0 10px;color:#344054;font-size:16px;">Subject Scoreboards</h3>
        {subject_scoreboard_html}
    </div>
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
                out.write("<div style=\"height:18px\"></div>")

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
    if INLINE_WEB_TEMPLATE:
        return render_template_string(INLINE_WEB_TEMPLATE)
    return render_template("index1.html")


@app.route("/start", methods=["POST"])
def start_process():
    global RUN_FOLDER
    roll = request.form.get("roll")

    RUN_FOLDER = create_run_folder()

    res1 = step1_fetch_mbn(roll, RUN_FOLDER)
    if res1["status"] == "error":
        return jsonify(res1)

    res2 = step2_send_otp(RUN_FOLDER)
    return jsonify({"status": "otp_sent"})


@app.route("/verify", methods=["POST"])
def verify():
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
    start_roll = int(request.form.get("start"))
    end_roll = int(request.form.get("end"))
    sem_data = json.loads(request.form.get("sem"))
    tone_mode = request.form.get("tone_mode", "motivational").strip().lower() or "motivational"

    r4 = step4_fetch_range(start_roll, end_roll, RUN_FOLDER)
    if r4["status"] == "error":
        return jsonify(r4)

    r5 = step5_fetch_dmc(RUN_FOLDER, sem_data)
    if r5["status"] == "error":
        return jsonify(r5)

    final_file = step6_generate_html(r5["folder"], RUN_FOLDER, tone_mode=tone_mode)

    return send_file(final_file)


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.route("/runs", methods=["GET"])
def list_saved_runs():
    runs = []
    if os.path.exists(RESP_BASE):
        for name in os.listdir(RESP_BASE):
            path = os.path.join(RESP_BASE, name)
            if os.path.isdir(path) and name.startswith("run_"):
                sem_folders = []
                for child in os.listdir(path):
                    child_path = os.path.join(path, child)
                    if os.path.isdir(child_path) and child.startswith("sem_"):
                        sem_folders.append(child)
                runs.append({
                    "run_folder": name,
                    "sem_folders": sem_folders,
                    "modified": os.path.getmtime(path),
                })

    runs.sort(key=lambda item: item["modified"], reverse=True)
    return jsonify({"status": "success", "runs": runs})


@app.route("/load-existing", methods=["POST"])
def load_existing():
    run_name = request.form.get("run_folder", "").strip()
    sem_folder = request.form.get("sem_folder", "").strip()
    tone_mode = request.form.get("tone_mode", "motivational").strip().lower() or "motivational"

    if not run_name or not sem_folder:
        return jsonify({"status": "error", "message": "Run folder and semester folder are required."}), 400

    run_folder = os.path.join(RESP_BASE, run_name)
    data_folder = os.path.join(run_folder, sem_folder)

    if not os.path.isdir(run_folder):
        return jsonify({"status": "error", "message": "Selected run folder was not found."}), 404
    if not os.path.isdir(data_folder):
        return jsonify({"status": "error", "message": "Selected semester data folder was not found."}), 404

    try:
        final_file = step6_generate_html(data_folder, run_folder, tone_mode=tone_mode)
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500

    return send_file(final_file, as_attachment=True, download_name=f"{run_name}_{sem_folder}_latest.html")


DEFAULT_TONE = "motivational"
TONE_OPTIONS = {
    "motivational": "Motivational",
    "teacher": "Teacher Style",
    "strict": "Strict Academic",
}


def ensure_streamlit_state():
    defaults = {
        "run_folder": None,
        "semesters": [],
        "status_log": ["Ready. Enter a roll number to begin."],
        "generated_file": None,
        "generated_name": None,
        "verified": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def add_streamlit_status(message):
    timestamp = datetime.now().strftime("%H:%M:%S")
    st.session_state.status_log.insert(0, f"[{timestamp}] {message}")
    st.session_state.status_log = st.session_state.status_log[:30]


def list_streamlit_saved_runs():
    runs = []
    if os.path.exists(RESP_BASE):
        for name in os.listdir(RESP_BASE):
            path = os.path.join(RESP_BASE, name)
            if os.path.isdir(path) and name.startswith("run_"):
                sem_folders = []
                for child in os.listdir(path):
                    child_path = os.path.join(path, child)
                    if os.path.isdir(child_path) and child.startswith("sem_"):
                        sem_folders.append(child)
                runs.append({
                    "run_folder": name,
                    "path": path,
                    "sem_folders": sorted(sem_folders),
                    "modified": os.path.getmtime(path),
                })
    runs.sort(key=lambda item: item["modified"], reverse=True)
    return runs


def read_binary_file(path):
    with open(path, "rb") as file_obj:
        return file_obj.read()


def streamlit_progress_callback():
    box = st.empty()

    def callback(message):
        box.info(message)
        add_streamlit_status(message)

    return callback


def run_streamlit_send_otp(roll_number):
    run_folder = create_run_folder()
    st.session_state.run_folder = run_folder
    st.session_state.verified = False
    st.session_state.semesters = []
    add_streamlit_status("Fetching mobile number...")

    res1 = step1_fetch_mbn(roll_number, run_folder)
    if res1["status"] == "error":
        st.error(res1["message"])
        add_streamlit_status(f"Step 1 error: {res1['message']}")
        return

    add_streamlit_status("Sending OTP...")
    res2 = step2_send_otp(run_folder)
    if res2["status"] == "error":
        st.error(res2["message"])
        add_streamlit_status(f"OTP error: {res2['message']}")
        return

    st.success("OTP sent successfully.")
    add_streamlit_status("OTP sent. Enter OTP and verify.")


def run_streamlit_verify_otp(otp_value):
    run_folder = st.session_state.run_folder
    if not run_folder:
        st.error("Please send OTP first.")
        return

    add_streamlit_status("Verifying OTP...")
    result = step3_verify_otp(otp_value, run_folder)
    if result["status"] == "error":
        st.error(result["message"])
        add_streamlit_status(f"Verify error: {result['message']}")
        return

    parsed = result.get("data")
    if isinstance(parsed, dict):
        api_success = parsed.get("success")
        api_message = parsed.get("message") or "No semester data was returned."
        api_data = parsed.get("data")
        if api_success is False or not api_data:
            st.error(api_message)
            add_streamlit_status(f"Verification failed: {api_message}")
            return

    semesters = get_all_semesters(run_folder)
    st.session_state.semesters = semesters
    st.session_state.verified = True
    add_streamlit_status(f"OTP verified. {len(semesters)} semester options loaded.")
    st.success("OTP verified and semester data loaded.")


def run_streamlit_generate_live(start_roll, end_roll, semester_value, tone_mode):
    run_folder = st.session_state.run_folder
    if not run_folder:
        st.error("Please complete OTP verification first.")
        return

    callback = streamlit_progress_callback()
    callback("Fetching roll range...")
    r4 = step4_fetch_range(int(start_roll), int(end_roll), run_folder, progress_callback=callback)
    if r4["status"] == "error":
        st.error(r4["message"])
        add_streamlit_status(f"Range error: {r4['message']}")
        return

    callback("Fetching DMC files...")
    r5 = step5_fetch_dmc(run_folder, semester_value, progress_callback=callback)
    if r5["status"] == "error":
        st.error(r5["message"])
        add_streamlit_status(f"DMC error: {r5['message']}")
        return

    callback("Generating final HTML...")
    final_file = step6_generate_html(
        r5["folder"],
        run_folder,
        progress_callback=callback,
        tone_mode=tone_mode,
    )
    st.session_state.generated_file = final_file
    st.session_state.generated_name = os.path.basename(final_file)
    add_streamlit_status(f"HTML generated: {final_file}")
    st.success("Combined HTML generated successfully.")


def run_streamlit_generate_saved(run_name, sem_folder, tone_mode):
    run_folder = os.path.join(RESP_BASE, run_name)
    data_folder = os.path.join(run_folder, sem_folder)
    callback = streamlit_progress_callback()
    callback(f"Rebuilding report from saved JSON: {run_name}/{sem_folder}")

    final_file = step6_generate_html(
        data_folder,
        run_folder,
        progress_callback=callback,
        tone_mode=tone_mode,
    )
    st.session_state.generated_file = final_file
    st.session_state.generated_name = f"{run_name}_{sem_folder}_latest.html"
    add_streamlit_status(f"Saved data rebuilt: {final_file}")
    st.success("Saved JSON rebuilt with latest logic.")


ensure_streamlit_state()
st.set_page_config(page_title="Result Extractor", page_icon="📘", layout="wide")

st.title("Result Extractor Dashboard")
st.caption("Single-file Streamlit build for upload and mobile-friendly usage.")

left_col, right_col = st.columns([1.25, 0.75], gap="large")

with left_col:
    st.subheader("Fresh Extraction")

    roll_number = st.text_input("Roll Number", key="roll_number")
    otp_value = st.text_input("OTP", key="otp_value")
    tone_mode = st.selectbox(
        "Academic Tone",
        options=list(TONE_OPTIONS.keys()),
        format_func=lambda key: TONE_OPTIONS[key],
        index=0,
        key="tone_mode_live",
    )

    action_col1, action_col2 = st.columns(2)
    with action_col1:
        if st.button("Send OTP", use_container_width=True):
            if not roll_number.strip():
                st.error("Roll number is required.")
            else:
                run_streamlit_send_otp(roll_number.strip())
    with action_col2:
        if st.button("Verify OTP", use_container_width=True):
            if not otp_value.strip():
                st.error("OTP is required.")
            else:
                run_streamlit_verify_otp(otp_value.strip())

    semester_labels = [item["label"] for item in st.session_state.semesters]
    selected_label = st.selectbox(
        "Semester",
        options=semester_labels,
        index=0 if semester_labels else None,
        placeholder="Verify OTP first",
        key="semester_label",
    )

    range_col1, range_col2 = st.columns(2)
    with range_col1:
        start_roll = st.text_input("Start Roll", key="start_roll")
    with range_col2:
        end_roll = st.text_input("End Roll", key="end_roll")

    if st.button("Generate HTML From Live Data", use_container_width=True):
        if not selected_label:
            st.error("Please verify OTP and select a semester.")
        elif not start_roll.strip() or not end_roll.strip():
            st.error("Start and end roll numbers are required.")
        elif not start_roll.strip().isdigit() or not end_roll.strip().isdigit():
            st.error("Start and end roll must be numeric.")
        else:
            sem_value = None
            for item in st.session_state.semesters:
                if item["label"] == selected_label:
                    sem_value = item["value"]
                    break
            if not sem_value:
                st.error("Selected semester is invalid.")
            else:
                run_streamlit_generate_live(start_roll.strip(), end_roll.strip(), sem_value, tone_mode)

    st.divider()
    st.subheader("Load Saved JSON")

    saved_runs = list_streamlit_saved_runs()
    run_names = [item["run_folder"] for item in saved_runs]
    selected_run = st.selectbox(
        "Saved Run Folder",
        options=run_names,
        index=0 if run_names else None,
        placeholder="No saved runs found",
        key="saved_run_name",
    )

    selected_run_obj = next((item for item in saved_runs if item["run_folder"] == selected_run), None)
    selected_sem = st.selectbox(
        "Saved Semester Folder",
        options=(selected_run_obj["sem_folders"] if selected_run_obj else []),
        index=0 if selected_run_obj and selected_run_obj["sem_folders"] else None,
        placeholder="Select a saved run first",
        key="saved_sem_name",
    )

    saved_tone_mode = st.selectbox(
        "Saved Report Tone",
        options=list(TONE_OPTIONS.keys()),
        format_func=lambda key: TONE_OPTIONS[key],
        index=0,
        key="tone_mode_saved",
    )

    if st.button("Rebuild From Saved JSON", use_container_width=True):
        if not selected_run or not selected_sem:
            st.error("Select both a saved run and semester folder.")
        else:
            run_streamlit_generate_saved(selected_run, selected_sem, saved_tone_mode)

with right_col:
    st.subheader("Live Console")
    st.info(st.session_state.status_log[0] if st.session_state.status_log else "Ready.")

    if st.session_state.generated_file and os.path.exists(st.session_state.generated_file):
        file_bytes = read_binary_file(st.session_state.generated_file)
        st.download_button(
            "Download Latest HTML",
            data=file_bytes,
            file_name=st.session_state.generated_name or "combined_result.html",
            mime="text/html",
            use_container_width=True,
        )
        with st.expander("Generated HTML Path", expanded=False):
            st.code(st.session_state.generated_file)

    st.markdown("### Status History")
    for item in st.session_state.status_log:
        st.write(item)

    st.markdown("### Notes")
    st.write("- Default tone is motivational.")
    st.write("- Files are stored in the same normal folders used by this project.")
    st.write("- This file is intended for Streamlit upload as the single Python app entrypoint.")
