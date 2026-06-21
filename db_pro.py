"""
db_pro.py — Database cho QualityMES Pro
Lưu trữ tách biệt hoàn toàn với App A:
  - JSON local: thư mục riêng /tmp/quality_mes_pro/
  - Google Sheets: dùng secrets riêng (spreadsheet_id_pro + gcp_service_account_pro)
"""
import json, os, streamlit as st
from pathlib import Path
from datetime import datetime

DATA_DIR = Path(os.environ.get("QUALITY_MES_PRO_DIR", "/tmp/quality_mes_pro"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

KEYS = ["users_list","project_list","iqc_data","ipqc_data","oqc_data",
        "ncr_data","capa_data","dev_data","log_list"]

DEFAULTS = {
    "users_list": [{"Tài khoản":"admin","Họ tên":"Quản lý","Mật khẩu":"admin123","Phân quyền":"Quản lý","Trạng thái":"Hoạt động"}],
    "project_list": [], "iqc_data": {}, "ipqc_data": {}, "oqc_data": {},
    "ncr_data": {}, "capa_data": {}, "dev_data": [], "log_list": [],
}

def _path(k): return DATA_DIR / f"pro_{k}.json"

# ══════════════════════════════════════════════════════════
# GOOGLE SHEETS — dùng secrets RIÊNG cho App Pro
#   st.secrets["spreadsheet_id_pro"]
#   st.secrets["gcp_service_account_pro"]
# (khác hoàn toàn với App A dùng "spreadsheet_id" + "gcp_service_account")
# ══════════════════════════════════════════════════════════
def _get_gspread_client_pro():
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
                  "https://www.googleapis.com/auth/drive"]
        if hasattr(st, "secrets") and "gcp_service_account_pro" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account_pro"])
        elif os.environ.get("GOOGLE_CREDENTIALS_PRO"):
            creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_PRO"])
        else:
            return None
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception:
        return None

def _get_spreadsheet_pro():
    gc = _get_gspread_client_pro()
    if gc is None: return None
    try:
        if hasattr(st, "secrets") and "spreadsheet_id_pro" in st.secrets:
            sid = st.secrets["spreadsheet_id_pro"]
        elif os.environ.get("SPREADSHEET_ID_PRO"):
            sid = os.environ["SPREADSHEET_ID_PRO"]
        else:
            return None
        return gc.open_by_key(sid)
    except Exception:
        return None

def _ensure_sheet_pro(ss, name):
    try: return ss.worksheet(name)
    except Exception: return ss.add_worksheet(title=name, rows=2000, cols=30)

def _gs_load(key: str):
    """Đọc 1 sheet tab. Hỗ trợ cả dict-of-lists (theo dự án) và list thuần."""
    try:
        ss = _get_spreadsheet_pro()
        if ss is None: return None
        ws = _ensure_sheet_pro(ss, key)
        records = ws.get_all_records(default_blank="")
        if not records: return DEFAULTS.get(key)

        is_dict_type = key in ("iqc_data","ipqc_data","oqc_data","ncr_data","capa_data")
        if is_dict_type:
            result = {}
            for rec in records:
                da = rec.get("_project_code","")
                if not da: continue
                row = {}
                for k, v in rec.items():
                    if k == "_project_code": continue
                    if isinstance(v, str) and v.startswith("["):
                        try: row[k] = json.loads(v)
                        except: row[k] = v
                    else: row[k] = v
                result.setdefault(da, []).append(row)
            return result
        else:
            result = []
            for rec in records:
                row = {}
                for k, v in rec.items():
                    if isinstance(v, str) and v.startswith("["):
                        try: row[k] = json.loads(v)
                        except: row[k] = v
                    else: row[k] = v
                result.append(row)
            return result
    except Exception:
        return None

def _gs_save(key: str, data) -> bool:
    try:
        ss = _get_spreadsheet_pro()
        if ss is None: return False
        ws = _ensure_sheet_pro(ss, key)
        ws.clear()

        is_dict_type = isinstance(data, dict)
        if is_dict_type:
            # Flatten dict-of-lists thành rows kèm cột _project_code
            flat_rows = []
            for da_code, lst in data.items():
                for row in lst:
                    r = dict(row)
                    r["_project_code"] = da_code
                    flat_rows.append(r)
            if not flat_rows:
                return True
            all_keys = list({k for row in flat_rows for k in row.keys()})
            ws.append_row(all_keys, value_input_option="RAW")
            rows_to_write = []
            for row in flat_rows:
                r = []
                for k in all_keys:
                    v = row.get(k, "")
                    if isinstance(v, list): v = json.dumps(v, ensure_ascii=False)
                    r.append(str(v) if v is not None else "")
                rows_to_write.append(r)
            ws.append_rows(rows_to_write, value_input_option="RAW")
        else:
            if not data: return True
            all_keys = list({k for row in data for k in row.keys()})
            ws.append_row(all_keys, value_input_option="RAW")
            rows_to_write = []
            for row in data:
                r = []
                for k in all_keys:
                    v = row.get(k, "")
                    if isinstance(v, list): v = json.dumps(v, ensure_ascii=False)
                    r.append(str(v) if v is not None else "")
                rows_to_write.append(r)
            ws.append_rows(rows_to_write, value_input_option="RAW")
        return True
    except Exception:
        return False

# ══════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════
def load_all() -> dict:
    """Đọc toàn bộ — thử Google Sheets trước, fallback JSON local."""
    result = {}
    for k in KEYS:
        gs_data = _gs_load(k)
        if gs_data is not None:
            _path(k).write_text(json.dumps(gs_data, ensure_ascii=False, indent=2), encoding="utf-8")
            result[k] = gs_data
            continue
        p = _path(k)
        if p.exists():
            try:
                result[k] = json.loads(p.read_text(encoding="utf-8"))
                continue
            except Exception:
                pass
        result[k] = DEFAULTS.get(k)
    return result

def save_key(key: str, data) -> None:
    """Ghi 1 key — luôn ghi JSON local, thêm Google Sheets nếu đã cấu hình."""
    _path(key).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    _gs_save(key, data)

def backup_all(session_state) -> bytes:
    backup = {k: session_state.get(k, DEFAULTS.get(k)) for k in KEYS}
    backup["_app"] = "QualityMES_Pro"
    backup["_exported_at"] = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
    return json.dumps(backup, ensure_ascii=False, indent=2).encode("utf-8")

def restore_all(data_bytes: bytes, session_state) -> tuple:
    try:
        data = json.loads(data_bytes.decode("utf-8"))
        restored = []
        for k in KEYS:
            if k in data:
                session_state[k] = data[k]
                save_key(k, data[k])
                restored.append(k)
        return True, f"Đã khôi phục: {', '.join(restored)}"
    except Exception as e:
        return False, f"Lỗi: {e}"

def gs_status_pro() -> dict:
    ss = _get_spreadsheet_pro()
    if ss is None:
        return {"connected": False, "message": "Lưu local (JSON)"}
    try:
        return {"connected": True, "message": f"Đã kết nối: {ss.title}"}
    except Exception as e:
        return {"connected": False, "message": f"Lỗi: {e}"}
