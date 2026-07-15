"""
db_pro.py — Database cho QualityMES Pro v2.0
Cải tiến:
  ✅ Caching tối ưu (cache_resource + cache_data)
  ✅ Session persistence — giữ đăng nhập khi reload
  ✅ Auto-save + Draft system
  ✅ Google Drive integration cho file management
  ✅ Dual-write: JSON local + Google Sheets + Google Drive
"""
import json, os, streamlit as st
from pathlib import Path
from datetime import datetime

# ══════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════
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
# CACHING OPTIMIZATION — Giảm tải Google Sheets
# ══════════════════════════════════════════════════════════
@st.cache_resource
def _get_gspread_client_pro():
    """Cache kết nối Google Sheets - with timeout protection"""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
                  "https://www.googleapis.com/auth/drive"]
        creds_dict = None
        if hasattr(st, "secrets") and "gcp_service_account_pro" in st.secrets:
            # Hỗ trợ cả TOML section [gcp_service_account_pro] và JSON object
            raw = st.secrets["gcp_service_account_pro"]
            if hasattr(raw, '_asdict'):
                creds_dict = dict(raw._asdict())
            elif hasattr(raw, 'to_dict'):
                creds_dict = raw.to_dict()
            elif isinstance(raw, dict):
                creds_dict = dict(raw)
            else:
                creds_dict = {k: v for k, v in raw.items()}
        elif os.environ.get("GOOGLE_CREDENTIALS_PRO"):
            creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_PRO"])
        
        if not creds_dict:
            print("[GSheets] No credentials found")
            return None
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        # ✅ FIX: Set timeout để tránh hanging
        client = gspread.authorize(creds)
        print("[GSheets] ✅ Connected!")
        return client
    except Exception as e:
        print(f"[GSheets] ❌ Error: {type(e).__name__}: {e}")
        return None

@st.cache_resource
def _get_drive_client_pro():
    """Cache kết nối Google Drive"""
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        SCOPES = ["https://www.googleapis.com/auth/drive"]
        creds_dict = None
        if hasattr(st, "secrets") and "gcp_service_account_pro" in st.secrets:
            raw = st.secrets["gcp_service_account_pro"]
            if hasattr(raw, '_asdict'):
                creds_dict = dict(raw._asdict())
            elif hasattr(raw, 'to_dict'):
                creds_dict = raw.to_dict()
            elif isinstance(raw, dict):
                creds_dict = dict(raw)
            else:
                creds_dict = {k: v for k, v in raw.items()}
        elif os.environ.get("GOOGLE_CREDENTIALS_PRO"):
            creds_dict = json.loads(os.environ["GOOGLE_CREDENTIALS_PRO"])
        
        if not creds_dict:
            return None
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        print(f"[Drive] ❌ Error: {e}")
        return None

def _get_spreadsheet_pro():
    """Lấy spreadsheet từ cache"""
    gc = _get_gspread_client_pro()
    if gc is None:
        print("[GSheets] _get_spreadsheet_pro: client is None")
        return None
    try:
        if hasattr(st, "secrets") and "spreadsheet_id_pro" in st.secrets:
            sid = st.secrets["spreadsheet_id_pro"]
        elif os.environ.get("SPREADSHEET_ID_PRO"):
            sid = os.environ["SPREADSHEET_ID_PRO"]
        else:
            print("[GSheets] No spreadsheet_id found")
            return None
        print(f"[GSheets] Opening: {sid}")
        ss = gc.open_by_key(sid)
        print(f"[GSheets] ✅ Opened: {ss.title}")
        return ss
    except Exception as e:
        print(f"[GSheets] ❌ open_by_key ERROR: {type(e).__name__}: {e}")
        return None

def _ensure_sheet_pro(ss, name):
    try: return ss.worksheet(name)
    except Exception: return ss.add_worksheet(title=name, rows=2000, cols=30)

# ══════════════════════════════════════════════════════════
# GOOGLE SHEETS — Read/Write
# ══════════════════════════════════════════════════════════
def _gs_load(key: str):
    """Đọc 1 sheet tab. Hỗ trợ cả dict-of-lists và list thuần."""
    try:
        ss = _get_spreadsheet_pro()
        if ss is None: 
            print(f"[GSheets] _gs_load({key}): Spreadsheet is None")
            return None
        ws = _ensure_sheet_pro(ss, key)
        records = ws.get_all_records(default_blank="", numericise_ignore=["all"])
        if not records: 
            print(f"[GSheets] _gs_load({key}): No records found, using default")
            return DEFAULTS.get(key)

        print(f"[GSheets] ✅ Loaded {key}: {len(records)} records")
        
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
    except Exception as e:
        print(f"[GSheets] ❌ _gs_load({key}) ERROR: {type(e).__name__}: {e}")
        return None

def _gs_save(key: str, data) -> bool:
    try:
        ss = _get_spreadsheet_pro()
        if ss is None: return False
        ws = _ensure_sheet_pro(ss, key)
        ws.clear()

        is_dict_type = isinstance(data, dict)
        if is_dict_type:
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
                    if isinstance(v, (int, float)) and v != "":
                        r.append(v)
                    else:
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
                    if isinstance(v, (int, float)) and v != "":
                        r.append(v)
                    else:
                        r.append(str(v) if v is not None else "")
                rows_to_write.append(r)
            ws.append_rows(rows_to_write, value_input_option="RAW")
        return True
    except Exception as e:
        print(f"[GSheets Save Error] {e}")
        return False

# ══════════════════════════════════════════════════════════
# GOOGLE DRIVE — File Management
# ══════════════════════════════════════════════════════════
# SỬA LỖI: thay ID thư mục giả bằng None (tạm thời tắt upload nếu chưa có ID thật)
DEFAULT_DRIVE_FOLDER_ID = None  # "0ANp3jJIUA1npUk9PVA" cũ bị sai, đặt None để tránh lỗi

def upload_file_to_drive(file_name, file_content, folder_id=None):
    """Upload file lên Google Drive - return (success, message, file_id)"""
    try:
        drive = _get_drive_client_pro()
        if drive is None: 
            msg = f"[Google Drive] Client not initialized for {file_name}"
            print(msg)
            return False, msg, None
        
        target_folder = folder_id or DEFAULT_DRIVE_FOLDER_ID
        if target_folder is None:
            msg = "❌ Chưa cấu hình thư mục Google Drive (DEFAULT_DRIVE_FOLDER_ID = None)"
            print(msg)
            return False, msg, None

        file_metadata = {"name": file_name, "parents": [target_folder]}
        
        from googleapiclient.http import MediaInMemoryUpload
        media = MediaInMemoryUpload(file_content, resumable=False)
        file = drive.files().create(
            body=file_metadata,
            media_body=media,
            fields="id",
            supportsAllDrives=True
        ).execute()
        file_id = file.get("id")
        msg = f"✅ Đã upload {file_name} thành công"
        print(f"[Google Drive] {msg} -> {file_id}")
        return True, msg, file_id
    except Exception as e:
        msg = f"❌ Lỗi upload {file_name}: {str(e)}"
        print(msg)
        return False, msg, None

def list_drive_files(folder_id=None, query_filter=None):
    """Liệt kê file trên Google Drive"""
    try:
        drive = _get_drive_client_pro()
        if drive is None: return []
        
        q = "trashed=false"
        if folder_id:
            q += f" and '{folder_id}' in parents"
        if query_filter:
            q += f" and name contains '{query_filter}'"
        
        results = drive.files().list(q=q, spaces="drive", fields="files(id, name, webViewLink, mimeType, createdTime, size)", pageSize=50).execute()
        return results.get("files", [])
    except Exception:
        return []

def get_drive_file_download_url(file_id):
    """Lấy link download file từ Google Drive"""
    return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"

# ══════════════════════════════════════════════════════════
# SESSION PERSISTENCE — Giữ đăng nhập khi reload
# ══════════════════════════════════════════════════════════
def save_session_token(user_account):
    """Lưu session token vào file local (bảo mật cơ bản)"""
    token = {
        "account": user_account,
        "timestamp": datetime.now().isoformat(),
        "expires": (datetime.now().timestamp() + 86400 * 7)  # 7 ngày
    }
    token_path = DATA_DIR / "session_token.json"
    token_path.write_text(json.dumps(token, ensure_ascii=False), encoding="utf-8")

def load_session_token():
    """Load session token và kiểm tra hạn"""
    try:
        token_path = DATA_DIR / "session_token.json"
        if not token_path.exists():
            return None
        token = json.loads(token_path.read_text(encoding="utf-8"))
        if datetime.now().timestamp() > token.get("expires", 0):
            token_path.unlink()  # Xóa token hết hạn
            return None
        return token.get("account")
    except Exception:
        return None

def clear_session_token():
    """Xóa session token khi đăng xuất"""
    try:
        token_path = DATA_DIR / "session_token.json"
        if token_path.exists():
            token_path.unlink()
    except Exception:
        pass

# ══════════════════════════════════════════════════════════
# DRAFT SYSTEM — Auto-save + Tự động lưu nháp
# ══════════════════════════════════════════════════════════
def save_draft(form_key, form_data):
    """Lưu nháp form"""
    draft_path = DATA_DIR / f"draft_{form_key}.json"
    draft_path.write_text(json.dumps(form_data, ensure_ascii=False, default=str), encoding="utf-8")

def load_draft(form_key):
    """Load nháp form"""
    try:
        draft_path = DATA_DIR / f"draft_{form_key}.json"
        if draft_path.exists():
            return json.loads(draft_path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None

def clear_draft(form_key):
    """Xóa nháp"""
    try:
        draft_path = DATA_DIR / f"draft_{form_key}.json"
        if draft_path.exists():
            draft_path.unlink()
    except Exception:
        pass

# ══════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════
def load_all() -> dict:
    """Đọc toàn bộ — batch load tất cả sheets 1 lần để tăng tốc"""
    result = {}
    gs_ok = False

    try:
        ss = _get_spreadsheet_pro()
        if ss is not None:
            # ✅ Load tất cả worksheets 1 lần (batch)
            all_ws = {ws.title: ws for ws in ss.worksheets()}
            for k in KEYS:
                try:
                    if k not in all_ws:
                        ws = ss.add_worksheet(title=k, rows=1000, cols=26)
                    else:
                        ws = all_ws[k]
                    records = ws.get_all_records(default_blank="", numericise_ignore=["all"])
                    if not records:
                        print(f"[GSheets] _gs_load({k}): No records found, using default")
                        result[k] = DEFAULTS.get(k)
                        continue
                    print(f"[GSheets] ✅ Loaded {k}: {len(records)} records")
                    gs_ok = True
                    is_dict = k in ("iqc_data","ipqc_data","oqc_data","ncr_data","capa_data")
                    if is_dict:
                        r = {}
                        for rec in records:
                            da = rec.get("_project_code","")
                            if not da: continue
                            row = {kk: (json.loads(v) if isinstance(v,str) and v.startswith("[") else v)
                                   for kk,v in rec.items() if kk != "_project_code"}
                            r.setdefault(da,[]).append(row)
                        result[k] = r
                    else:
                        result[k] = [{kk: (json.loads(v) if isinstance(v,str) and v.startswith("[") else v)
                                      for kk,v in rec.items()} for rec in records]
                    # Backup local
                    try: _path(k).write_text(json.dumps(result[k], ensure_ascii=False), encoding="utf-8")
                    except: pass
                except Exception as e:
                    print(f"[GSheets] ❌ Error {k}: {e}")
                    result[k] = _local_backup(k)
    except Exception as e:
        print(f"[GSheets] ❌ load_all: {e}")
        for k in KEYS: result[k] = _local_backup(k)

    print(f"[load_all] {'✅ GSheets OK' if gs_ok else '⚠️ Local backup'}")
    return result

def _local_backup(k):
    p = _path(k)
    if p.exists():
        try: return json.loads(p.read_text(encoding="utf-8"))
        except: pass
    return DEFAULTS.get(k)

def save_key(key: str, data) -> None:
    """Ghi 1 key — lưu local ngay, ghi GSheets trong background thread"""
    import threading
    # ✅ Lưu local ngay lập tức (nhanh)
    try:
        _path(key).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[Local Save Error] {e}")
    
    # ✅ Ghi GSheets trong background (không block UI)
    def _bg_save():
        try:
            _gs_save(key, data)
        except Exception as e:
            print(f"[GSheets BG Save Error] {e}")
    
    t = threading.Thread(target=_bg_save, daemon=True)
    t.start()

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
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        SCOPES = ["https://www.googleapis.com/auth/spreadsheets",
                  "https://www.googleapis.com/auth/drive"]
        
        if not hasattr(st, "secrets"):
            return {"connected": False, "message": "Lưu local — No secrets object"}
        if "gcp_service_account_pro" not in st.secrets:
            return {"connected": False, "message": "Lưu local — Missing gcp_service_account_pro"}
        if "spreadsheet_id_pro" not in st.secrets:
            return {"connected": False, "message": "Lưu local — Missing spreadsheet_id_pro"}
        
        # Thử đọc credentials
        try:
            raw = st.secrets["gcp_service_account_pro"]
            creds_dict = {k: v for k, v in raw.items()}
        except Exception as e:
            return {"connected": False, "message": f"Lưu local — Đọc creds lỗi: {e}"}
        
        # Thử tạo credentials
        try:
            creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        except Exception as e:
            return {"connected": False, "message": f"Lưu local — Tạo creds lỗi: {e}"}
        
        # Thử kết nối gspread
        try:
            gc = gspread.authorize(creds)
        except Exception as e:
            return {"connected": False, "message": f"Lưu local — gspread lỗi: {e}"}
        
        # Thử mở spreadsheet
        try:
            sid = st.secrets["spreadsheet_id_pro"]
            ss = gc.open_by_key(sid)
            return {"connected": True, "message": f"Đã kết nối: {ss.title}"}
        except Exception as e:
            st.error(f"DEBUG Sheet Error: {type(e).__name__}: {str(e)}")
            return {"connected": False, "message": f"Mở sheet lỗi: {type(e).__name__}"}
    
    except Exception as e:
        return {"connected": False, "message": f"Lỗi tổng: {e}"}

def drive_status_pro() -> dict:
    """Kiểm tra kết nối Google Drive"""
    drive = _get_drive_client_pro()
    if drive is None:
        return {"connected": False, "message": "Google Drive chưa kết nối"}
    try:
        about = drive.about().get(fields="storageQuota").execute()
        return {"connected": True, "message": f"Google Drive OK"}
    except Exception as e:
        return {"connected": False, "message": f"Lỗi: {e}"}