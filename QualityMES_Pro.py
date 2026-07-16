import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, date
from collections import Counter
from db_pro import (load_all, save_key, backup_all, restore_all, gs_status_pro,
                    save_session_token, load_session_token, clear_session_token,
                    save_draft, load_draft, clear_draft,
                    upload_file_to_drive, list_drive_files, get_drive_file_download_url,
                    drive_status_pro)
import time
import uuid  # ✅ Thêm để tạo session ID

# ✅ Tạo session ID nếu chưa có (giữ đăng nhập khi refresh)
if "session_id" not in st.query_params:
    st.query_params["session_id"] = str(uuid.uuid4())
    st.rerun()

# ✅ FIX LỖI 1: Không load Google Sheets khi chưa đăng nhập
@st.cache_data(ttl=300, show_spinner=False)
def cached_load_all():
    return load_all()

# ══════════════════════════════════════════════════════════
# CONFIG & CSS
# ══════════════════════════════════════════════════════════
st.set_page_config(page_title="Quality MES Pro", layout="wide",
                   initial_sidebar_state="expanded", page_icon="🏭")

# Đọc logo từ App A (dùng chung)
import base64, os
_logo_path = os.path.join(os.path.dirname(__file__), "logo.png")
try:
    LOGO_SRC = "data:image/png;base64," + base64.b64encode(open(_logo_path,"rb").read()).decode()
except:
    LOGO_SRC = ""

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
html,body,[class*="css"]{font-family:'Inter','Segoe UI',system-ui,sans-serif}
.block-container{padding-top:2.2rem!important;padding-left:2rem!important;padding-right:2rem!important;max-width:100%!important}
h2{font-size:1.5rem!important;font-weight:700!important;color:#1e293b!important;
   border-left:4px solid #7c3aed;padding-left:12px!important;margin-bottom:.8rem!important}
/* Sidebar */
section[data-testid="stSidebar"]{background:#1e1b4b!important;border-right:1px solid #312e81}
section[data-testid="stSidebar"] *{color:#e0e7ff!important}
section[data-testid="stSidebar"] .stRadio label{font-size:13px!important;padding:6px 8px;border-radius:6px}
section[data-testid="stSidebar"] .stRadio label:hover{background:#312e81!important}
section[data-testid="stSidebar"] hr{border-color:#312e81!important}
/* Cards */
.mc{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px 20px;
    box-shadow:0 1px 3px rgba(0,0,0,.06);margin-bottom:10px;transition:box-shadow .2s}
.mc:hover{box-shadow:0 4px 12px rgba(0,0,0,.08)}
.mc-label{font-size:11px;color:#64748b;margin:0;text-transform:uppercase;letter-spacing:.06em;font-weight:600}
.mc-value{font-size:26px;font-weight:800;margin:5px 0 0;letter-spacing:-.02em}
/* Project card */
.pc{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px 22px;
    box-shadow:0 1px 4px rgba(0,0,0,.05);margin-bottom:10px;transition:all .2s;cursor:pointer}
.pc:hover{box-shadow:0 6px 20px rgba(124,58,237,.12);border-color:#7c3aed;transform:translateY(-1px)}
.pc-title{font-weight:700;font-size:15px;color:#1e293b;margin-bottom:4px}
.pc-sub{font-size:12px;color:#64748b}
/* Status */
.tt-pass{background:#dcfce7;color:#166534;font-weight:700;padding:3px 12px;border-radius:20px;font-size:12px}
.tt-fail{background:#fee2e2;color:#991b1b;font-weight:700;padding:3px 12px;border-radius:20px;font-size:12px}
.tt-warn{background:#fef9c3;color:#854d0e;font-weight:700;padding:3px 12px;border-radius:20px;font-size:12px}
.tt-ok{background:#d1fae5;color:#065f46;font-weight:700;padding:3px 12px;border-radius:20px;font-size:12px}
/* Buttons */
.stButton>button{border-radius:8px!important;font-weight:600!important;font-size:13px!important}
.stButton>button[kind="primary"]{background:#7c3aed!important;border-color:#7c3aed!important}
.stButton>button[kind="primary"]:hover{background:#6d28d9!important}
/* Table */
div[data-testid="stDataFrame"]{border:1px solid #e2e8f0!important;border-radius:10px!important;overflow:hidden}
div[data-testid="stDataFrame"] table{font-size:13px!important}
div[data-testid="stDataFrame"] thead th{background:#f8fafc!important;font-weight:700!important;
  font-size:11px!important;color:#64748b!important;text-transform:uppercase!important;
  letter-spacing:.05em!important;padding:10px 12px!important;border-bottom:2px solid #e2e8f0!important}
div[data-testid="stDataFrame"] tbody td{padding:8px 12px!important;color:#334155!important}
div[data-testid="stDataFrame"] tbody tr:hover td{background:#f8fafc!important}
/* Login */
.login-wrap{max-width:420px;margin:8vh auto 0 auto;background:#fff;border:1px solid #e2e8f0;
  border-radius:16px;padding:44px 40px 36px;box-shadow:0 8px 32px rgba(0,0,0,.10)}
.login-title{text-align:center;font-size:22px;font-weight:800;color:#1e293b;margin-bottom:4px}
.login-sub{text-align:center;font-size:13px;color:#64748b;margin-bottom:28px}
.login-err{background:#fdf2f8;border:1px solid #f0abfc;color:#701a75;border-radius:8px;
  padding:10px 14px;font-size:13px;font-weight:600;margin-bottom:16px;text-align:center}
hr{border-color:#f1f5f9!important;margin:8px 0!important}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════
def _load_data_from_sheets():
    """Load data sau khi đăng nhập - dùng cache 5 phút"""
    if not st.session_state.get("_data_loaded", False):
        data = cached_load_all()
        for k in ["users_list","project_list","iqc_data","ipqc_data",
                  "oqc_data","ncr_data","capa_data","dev_data","log_list"]:
            if k in data and data[k]:
                st.session_state[k] = data[k]
        st.session_state["_data_loaded"] = True
        st.session_state["_users_loaded"] = True

def _init(k, v):
    if k not in st.session_state:
        st.session_state[k] = v

_init("current_user",   None)
_init("login_error",    "")
_init("active_project", None)
_init("spc_df",         None)

# ══════════════════════════════════════════════════════════
# AUTO-SAVE SYSTEM
# ══════════════════════════════════════════════════════════
_init("last_save_time", time.time())
_init("unsaved_changes", False)

def auto_save():
    now = time.time()
    if st.session_state.get("unsaved_changes") and (now - st.session_state.last_save_time > 30):
        for key in ["iqc_data", "ipqc_data", "oqc_data", "ncr_data", "capa_data", "dev_data"]:
            if st.session_state.get(key):
                save_key(key, st.session_state[key])
        st.session_state.last_save_time = now
        st.session_state.unsaved_changes = False

_init("users_list", [
    {"Tài khoản":"admin","Họ tên":"Quản lý","Mật khẩu":"admin123","Phân quyền":"Quản lý","Trạng thái":"Hoạt động"},
])
_init("project_list", [
    {"Mã DA":"DA-001","Tên dự án":"Dự án mẫu","Khách hàng":"Khách hàng A",
     "Địa điểm":"TP.HCM","Ngày bắt đầu":"01-01-2026","Ngày kết thúc":"31-12-2026",
     "Trạng thái":"Đang chạy","Mô tả":"Dự án mẫu để demo","Người phụ trách":"Quản lý","Người tạo":"admin"},
])
_init("iqc_data",   {})
_init("ipqc_data",  {})
_init("oqc_data",   {})
_init("ncr_data",   {})
_init("capa_data",  {})
_init("dev_data",   {})
_init("log_list",   [])

# ══════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════
def ghi_log(phane, action, detail, da=None):
    entry = {"Thời gian": datetime.now().strftime("%d-%m-%Y %H:%M"),
             "Tài khoản": st.session_state.current_user["Tài khoản"] if st.session_state.current_user else "system",
             "Dự án": da or st.session_state.active_project or "-",
             "Phân hệ": phane, "Hành động": action, "Chi tiết": detail}
    st.session_state.log_list.insert(0, entry)
    save_key("log_list", st.session_state.log_list)

def persist(key):
    save_key(key, st.session_state[key])
    st.session_state.unsaved_changes = True

def cu():
    return st.session_state.current_user or {}

def unames():
    return [u["Họ tên"] for u in st.session_state.users_list]

def get_da_list(key):
    da = st.session_state.active_project
    if not da: return []
    return st.session_state[key].get(da, [])

def set_da_list(key, lst):
    da = st.session_state.active_project
    if not da: return
    st.session_state[key][da] = lst
    persist(key)

def pf(lst):
    p = sum(1 for x in lst if x.get("Trạng thái") == "Đạt (Pass)")
    return len(lst), p, len(lst) - p

def c_tt(v):
    s = str(v)
    if "Pass" in s or "Đạt" in s:    return "background:#dcfce7;color:#166534;font-weight:700"
    if "Failed" in s or "Không" in s: return "background:#fee2e2;color:#991b1b;font-weight:700"
    if "Đang" in s:                   return "background:#fef9c3;color:#854d0e;font-weight:700"
    if "Hoàn" in s or "Đóng" in s:   return "background:#d1fae5;color:#065f46;font-weight:700"
    return ""

def c_tinhtrang(v):
    if v == "Sử dụng tốt":    return "background:#dcfce7;color:#166534;font-weight:700"
    if v == "Chờ hiệu chuẩn": return "background:#fef9c3;color:#854d0e;font-weight:700"
    if v == "Hỏng":            return "background:#fee2e2;color:#991b1b;font-weight:700"
    return ""

def render_df(lst, badge_col=None, badge_fn=None):
    if not lst: st.info("Chưa có dữ liệu"); return
    df = pd.DataFrame(lst)
    hide_cols = ["Người tạo", "drive_files", "_project_code"]
    cols = [c for c in df.columns if c not in hide_cols]
    if "Files" in cols:
        df["Files"] = df["Files"].apply(lambda x: ", ".join(x) if isinstance(x, list) else str(x) if x else "")
    fn = badge_fn or c_tt
    s = df[cols].style.set_properties(**{"font-size":"13px","padding":"8px 12px"}) \
        .set_table_styles([
            {"selector":"thead th","props":[("background","#f8fafc"),("font-weight","700"),
             ("font-size","11px"),("color","#64748b"),("text-transform","uppercase"),
             ("letter-spacing","0.05em"),("border-bottom","2px solid #e2e8f0"),("padding","10px 12px")]},
            {"selector":"tbody tr:hover","props":[("background","#f8fafc")]},
            {"selector":"table","props":[("border-collapse","collapse"),("width","100%")]},
        ])
    if badge_col and badge_col in cols:
        s = s.map(fn, subset=[badge_col])
    st.dataframe(s, use_container_width=True, hide_index=True)

def co_quyen(nguoi_tao):
    role = cu().get("Vai trò","")
    if role in ["Quản lý","Trưởng QC"]: return True
    return nguoi_tao == cu().get("Tài khoản","")

def fmt_files(files):
    if not files: return "(Không có file)"
    return " | ".join(f.name for f in files)

# ══════════════════════════════════════════════════════════
# RENDER TABLE WITH EDIT/DELETE PER ROW
# ══════════════════════════════════════════════════════════
def table_actions(data_list_ref, id_field, phane, data_key, edit_fn,
                  badge_col="Trạng thái", badge_fn=None, all_users=False):
    lst = list(data_list_ref)
    if not lst: st.info("Chưa có dữ liệu"); return

    sc1, sc2 = st.columns([4, 1])
    kw = sc1.text_input("🔍 Tìm kiếm", placeholder="Nhập từ khóa...",
                         key=f"srch_{phane}", label_visibility="collapsed")
    sc2.caption(f"Tổng: **{len(lst)}** bản ghi")

    if kw.strip():
        kw_l = kw.lower()
        indices = [i for i,r in enumerate(lst)
                   if any(kw_l in str(v).lower() for v in r.values())]
        if not indices:
            st.warning(f"Không tìm thấy: **{kw}**"); return
        display = [lst[i] for i in indices]
        real_idx = indices
        sc2.caption(f"Kết quả: **{len(indices)}** / {len(lst)}")
    else:
        display = lst; real_idx = list(range(len(lst)))

    render_df(display, badge_col, badge_fn)
    st.markdown("---")

    for local_i, (ri, row) in enumerate(zip(real_idx, display)):
        can = all_users or co_quyen(row.get("Người tạo",""))
        rid = row.get(id_field, f"#{ri}")
        extra = "  ·  ".join(str(row.get(f,"-")) for f in
                              [k for k in row if k not in (id_field,"Người tạo","Files")][:3])
        cid, cinfo, cedit, cdel = st.columns([1.2, 5.5, 0.9, 0.9])
        cid.markdown(f"**{rid}**")
        cinfo.caption(extra)
        if can:
            with cedit.popover("✏️ Sửa"):
                edit_fn(ri, row, data_list_ref, data_key)
            with cdel.popover("🗑️ Xóa"):
                st.warning(f"Xác nhận xóa **{rid}**?")
                cy, cn = st.columns(2)
                if cy.button("✅ Xác nhận", key=f"yes_{phane}_{ri}", use_container_width=True):
                    data_list_ref.pop(ri)
                    set_da_list(data_key, data_list_ref) if data_key in ("iqc_data","ipqc_data","oqc_data","ncr_data","capa_data") else persist(data_key)
                    ghi_log(phane,"Xóa",f"Xóa {rid}")
                    st.rerun()
                cn.button("❌ Hủy", key=f"no_{phane}_{ri}", use_container_width=True)
        else:
            cedit.caption("🔒"); cdel.caption("—")

# ══════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════
if st.session_state.current_user is None and not st.session_state.get("_users_loaded", False):
    _data = cached_load_all()
    if _data.get("users_list"):
        st.session_state["users_list"] = _data["users_list"]
    st.session_state["_users_loaded"] = True

if st.session_state.current_user is None:
    saved_account = load_session_token()
    if saved_account:
        matched = next((u for u in st.session_state.users_list
                        if u["Tài khoản"] == saved_account
                        and u.get("Trạng thái") == "Hoạt động"), None)
        if matched:
            st.session_state.current_user = {
                "Tài khoản": matched["Tài khoản"],
                "Họ tên": matched["Họ tên"],
                "Vai trò": matched["Phân quyền"]
            }
            st.rerun()

if st.session_state.current_user is None:
    st.markdown("""<style>
        section[data-testid="stSidebar"]{display:none!important}
        .block-container{padding-top:0!important}
    </style>""", unsafe_allow_html=True)
    _, cc, _ = st.columns([1, 1.4, 1])
    with cc:
        logo_html = f'<img src="{LOGO_SRC}" style="width:56px;height:auto;border-radius:8px;display:block;margin:0 auto 8px"/>' if LOGO_SRC else "🏭"
        st.markdown(f"""<div class="login-wrap">
            {logo_html}
            <div class="login-title">QUALITY MES <span style="color:#7c3aed">PRO</span></div>
            <div class="login-sub">Quản lý chất lượng theo dự án · v1.0</div>
        </div>""", unsafe_allow_html=True)
        if st.session_state.login_error:
            st.markdown(f'<div class="login-err">⚠️ {st.session_state.login_error}</div>',
                        unsafe_allow_html=True)
        with st.form("frm_login", clear_on_submit=False):
            username = st.text_input("Tài khoản", placeholder="Nhập tên tài khoản...")
            password = st.text_input("Mật khẩu", type="password", placeholder="Nhập mật khẩu...")
            if st.form_submit_button("🔐 Đăng nhập", use_container_width=True, type="primary"):
                if not username or not password:
                    st.session_state.login_error = "Vui lòng điền đầy đủ tài khoản và mật khẩu."
                    st.rerun()
                matched = next((u for u in st.session_state.users_list
                                if u["Tài khoản"].lower()==username.lower()
                                and u["Mật khẩu"]==password
                                and u.get("Trạng thái")=="Hoạt động"), None)
                if matched:
                    st.session_state.current_user = {"Tài khoản":matched["Tài khoản"],
                        "Họ tên":matched["Họ tên"],"Vai trò":matched["Phân quyền"]}
                    st.session_state.login_error = ""
                    save_session_token(matched["Tài khoản"])
                    ghi_log("Auth","Đăng nhập",f"{matched['Họ tên']} đăng nhập","-")
                    st.rerun()
                else:
                    st.session_state.login_error = "Tài khoản hoặc mật khẩu không đúng."
                    st.rerun()
    st.stop()

# ══════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════
_load_data_from_sheets()
auto_save()

role_colors = {"Quản lý":"#f59e0b","Trưởng QC":"#10b981","Kiểm tra viên":"#818cf8"}
rc = role_colors.get(cu().get("Vai trò",""),"#94a3b8")
rb = {"Quản lý":"#451a03","Trưởng QC":"#064e3b","Kiểm tra viên":"#1e1b4b"}.get(cu().get("Vai trò",""),"#1e1b4b")

st.sidebar.markdown(f"""
<div style="padding:16px 4px 18px 4px;border-bottom:1px solid #312e81;margin-bottom:4px">
  <div style="display:flex;align-items:flex-end;gap:12px;margin-bottom:10px">
    {"<img src='"+LOGO_SRC+"' style='width:40px;height:auto;border-radius:6px;flex-shrink:0;margin-bottom:4px'/>" if LOGO_SRC else "🏭"}
    <div>
      <div style="font-size:18px;font-weight:900;color:#f1f5f9;letter-spacing:.03em;line-height:1;white-space:nowrap">
        QUALITY MES <span style="color:#a78bfa">PRO</span>
      </div>
    </div>
  </div>
  <div style="font-size:10px;color:#6d28d9;font-weight:700;letter-spacing:.12em;text-transform:uppercase;margin-bottom:14px">v1.0</div>
  <div style="font-size:11px;color:#94a3b8;text-transform:uppercase;letter-spacing:.08em;font-weight:600;margin-bottom:5px">Đăng nhập</div>
  <div style="font-size:15px;font-weight:700;color:#f1f5f9;margin-bottom:8px">👤 {cu().get('Họ tên','')}</div>
  <span style="background:{rb};color:{rc};padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;border:1px solid {rc}33">{cu().get('Vai trò','')}</span>
</div>
""", unsafe_allow_html=True)

_gs = gs_status_pro()
dot = "🟢" if _gs["connected"] else "🔴"
st.sidebar.markdown(f"<div style='font-size:11px;padding:4px 0;color:{'#4ade80' if _gs['connected'] else '#f87171'}'>{dot} {_gs['message']}</div>", unsafe_allow_html=True)

if st.sidebar.button("🔄 Reload data", use_container_width=True):
    st.cache_data.clear()
    st.session_state["_data_loaded"] = False
    for k in ["users_list","project_list","iqc_data","ipqc_data","oqc_data","ncr_data","capa_data","dev_data","log_list"]:
        if k in st.session_state:
            del st.session_state[k]
    st.rerun()

st.sidebar.markdown("---")

all_projects = st.session_state.project_list
proj_names = {f"{p['Mã DA']} — {p['Tên dự án']}": p["Mã DA"] for p in all_projects}

if proj_names:
    cur_da = st.session_state.active_project
    cur_label = next((k for k,v in proj_names.items() if v==cur_da), list(proj_names.keys())[0])
    sel_label = st.sidebar.selectbox("📁 Dự án đang xem:", list(proj_names.keys()),
                                      index=list(proj_names.keys()).index(cur_label),
                                      key="sidebar_da_sel")
    st.session_state.active_project = proj_names[sel_label]
else:
    st.session_state.active_project = None
    st.sidebar.info("Chưa có dự án. Vào Quản lý Dự án để tạo.")

st.sidebar.markdown("---")

MENU = ["🏠 Tổng quan","📁 Quản lý Dự án",
        "✅ IQC","🧪 IPQC","📦 OQC",
        "⚠️ NCR + CAPA","🔧 Thiết bị đo",
        "📊 Báo cáo SPC","📜 Nhật ký","👤 Người dùng"]
page = st.sidebar.radio("MENU", MENU, index=0)
st.sidebar.markdown("---")
if st.sidebar.button("🚪 Đăng xuất", use_container_width=True):
    ghi_log("Auth","Đăng xuất",f"{cu()['Họ tên']} đăng xuất","-")
    clear_session_token()
    st.session_state.current_user  = None
    st.session_state.active_project = None
    st.rerun()

AP = st.session_state.active_project
proj_info = next((p for p in all_projects if p["Mã DA"]==AP), None) if AP else None

def da_banner():
    if not proj_info: return
    tt_colors = {"Đang chạy":"#059669","Hoàn thành":"#1d4ed8","Tạm dừng":"#d97706","Hủy":"#dc2626"}
    clr = tt_colors.get(proj_info["Trạng thái"],"#64748b")
    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#f5f3ff,#ede9fe);border:1px solid #ddd6fe;
      border-radius:10px;padding:12px 18px;margin-bottom:16px;display:flex;align-items:center;gap:16px">
      <div style="font-size:22px;font-weight:900;color:#7c3aed">{proj_info['Mã DA']}</div>
      <div>
        <div style="font-size:14px;font-weight:700;color:#1e293b">{proj_info['Tên dự án']}</div>
        <div style="font-size:12px;color:#64748b">{proj_info['Khách hàng']} · {proj_info['Địa điểm']} · {proj_info['Ngày bắt đầu']} → {proj_info['Ngày kết thúc']}</div>
      </div>
      <span style="margin-left:auto;background:{clr}22;color:{clr};padding:4px 14px;
        border-radius:20px;font-size:12px;font-weight:700;border:1px solid {clr}44">{proj_info['Trạng thái']}</span>
    </div>
    """, unsafe_allow_html=True)

def require_project():
    if not AP or not proj_info:
        st.warning("⚠️ Vui lòng chọn dự án từ sidebar trước khi sử dụng phân hệ này.")
        st.stop()

# ══════════════════════════════════════════════════════════
# MENU 1: TỔNG QUAN
# ══════════════════════════════════════════════════════════
if page == "🏠 Tổng quan":
    st.markdown("## 🏠 Tổng quan")
    if not proj_info:
        st.info("Chọn hoặc tạo dự án từ sidebar để bắt đầu.")
    else:
        da_banner()
        il = get_da_list("iqc_data"); pl = get_da_list("ipqc_data"); ol = get_da_list("oqc_data")
        nl = get_da_list("ncr_data"); cl = get_da_list("capa_data")
        it,ip,if_ = pf(il); pt,pp,pf_ = pf(pl); ot,op,of_ = pf(ol)
        tot = it+pt+ot; totp = ip+pp+op
        yr = int(totp/tot*100) if tot else 0
        ncr_open = sum(1 for x in nl if x.get("Trạng thái") in ["Mở","Đang điều tra"])

        c1,c2,c3,c4 = st.columns(4)
        for col,lbl,val,clr in [
            (c1,"Tổng phiếu kiểm",tot,"#1e293b"),
            (c2,"Đạt (Pass)",f"{totp}/{tot}","#065f46"),
            (c3,"Không đạt",tot-totp,"#991b1b"),
            (c4,"Tỷ lệ đạt",f"{yr}%","#7c3aed"),
        ]:
            col.markdown(f'<div class="mc"><p class="mc-label">{lbl}</p><div class="mc-value" style="color:{clr}">{val}</div></div>', unsafe_allow_html=True)

        n1,n2,n3,n4 = st.columns(4)
        for col,lbl,val,clr in [
            (n1,"NCR phát sinh",len(nl),"#dc2626"),
            (n2,"NCR đang mở",ncr_open,"#d97706"),
            (n3,"CAPA đang TH",sum(1 for x in cl if x.get("Trạng thái CAPA")=="Đang tiến hành"),"#7c3aed"),
            (n4,"Thiết bị đo",len(st.session_state.dev_data),"#0d9488"),
        ]:
            col.markdown(f'<div class="mc"><p class="mc-label">{lbl}</p><div class="mc-value" style="color:{clr}">{val}</div></div>', unsafe_allow_html=True)

        st.write("")
        r1,r2,r3 = st.columns(3)
        for col,icon,bg,fc,title,p,f in [
            (r1,"✅","#f5f3ff","#7c3aed","IQC — Đầu vào",ip,if_),
            (r2,"🧪","#ecfdf5","#059669","IPQC — Quá trình",pp,pf_),
            (r3,"📦","#fffbeb","#d97706","OQC — Thành phẩm",op,of_),
        ]:
            col.markdown(f"""<div style="background:{bg};border:1px solid {fc}22;border-radius:10px;
              padding:16px 18px;margin-bottom:10px">
              <div style="font-size:14px;font-weight:700;color:#1e293b;margin-bottom:6px">{icon} {title}</div>
              <div style="font-size:12px;color:#64748b">
                Đạt: <b style="color:#065f46">{p}</b> &nbsp;|&nbsp; Không đạt: <b style="color:#991b1b">{f}</b>
              </div></div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════
# MENU 2: QUẢN LÝ DỰ ÁN
# ══════════════════════════════════════════════════════════
elif page == "📁 Quản lý Dự án":
    st.markdown("## 📁 Quản lý Dự án")

    if cu().get("Vai trò") in ["Quản lý","Trưởng QC"]:
        if "show_da_form" not in st.session_state: st.session_state.show_da_form = False
        if st.button("➕ Tạo dự án mới"): st.session_state.show_da_form = True

        if st.session_state.show_da_form:
            st.markdown("---")
            with st.form("frm_da_new", clear_on_submit=True):
                c1,c2 = st.columns(2)
                da_ma  = c1.text_input("Mã dự án *")
                da_ten = c2.text_input("Tên dự án *")
                da_kh  = c1.text_input("Khách hàng")
                da_dd  = c2.text_input("Địa điểm")
                da_bd  = c1.date_input("Ngày bắt đầu", value=date.today())
                da_kt  = c2.date_input("Ngày kết thúc", value=date.today())
                da_tt  = c1.selectbox("Trạng thái",["Đang chạy","Tạm dừng","Hoàn thành","Hủy"])
                un_d   = unames()
                da_pt  = c2.selectbox("Người phụ trách", un_d,
                           index=un_d.index(cu().get("Họ tên","")) if cu().get("Họ tên","") in un_d else 0)
                da_mo  = st.text_area("Mô tả", height=68)
                b1,b2,_ = st.columns([1.5,1.5,6])
                ok = b1.form_submit_button("✅ Tạo", use_container_width=True)
                ca = b2.form_submit_button("❌ Hủy", use_container_width=True)
                if ok:
                    if not da_ma or not da_ten: st.error("Điền Mã dự án và Tên dự án")
                    elif any(p["Mã DA"]==da_ma for p in all_projects): st.error("Mã DA đã tồn tại!")
                    else:
                        st.session_state.project_list.append({
                            "Mã DA":da_ma,"Tên dự án":da_ten,"Khách hàng":da_kh or "-",
                            "Địa điểm":da_dd or "-","Ngày bắt đầu":da_bd.strftime("%d-%m-%Y"),
                            "Ngày kết thúc":da_kt.strftime("%d-%m-%Y"),"Trạng thái":da_tt,
                            "Mô tả":da_mo or "-","Người phụ trách":da_pt,"Người tạo":cu().get("Tài khoản",""),
                        })
                        persist("project_list")
                        ghi_log("Dự án","Tạo mới",f"Tạo {da_ma}",da_ma)
                        st.session_state.active_project = da_ma
                        st.session_state.show_da_form = False
                        st.rerun()
                if ca: st.session_state.show_da_form = False; st.rerun()
            st.markdown("---")

    if not all_projects:
        st.info("Chưa có dự án. Bấm ➕ Tạo dự án mới.")
    else:
        s1,s2,s3,s4 = st.columns(4)
        s1.markdown(f'<div class="mc"><p class="mc-label">Tổng</p><div class="mc-value" style="color:#1e293b">{len(all_projects)}</div></div>', unsafe_allow_html=True)
        s2.markdown(f'<div class="mc"><p class="mc-label">Đang chạy</p><div class="mc-value" style="color:#059669">{sum(1 for p in all_projects if p["Trạng thái"]=="Đang chạy")}</div></div>', unsafe_allow_html=True)
        s3.markdown(f'<div class="mc"><p class="mc-label">Hoàn thành</p><div class="mc-value" style="color:#1d4ed8">{sum(1 for p in all_projects if p["Trạng thái"]=="Hoàn thành")}</div></div>', unsafe_allow_html=True)
        s4.markdown(f'<div class="mc"><p class="mc-label">Tạm dừng/Hủy</p><div class="mc-value" style="color:#dc2626">{sum(1 for p in all_projects if p["Trạng thái"] in ["Tạm dừng","Hủy"])}</div></div>', unsafe_allow_html=True)
        st.write("")

        def c_da(v):
            m={"Đang chạy":"background:#d1fae5;color:#065f46;font-weight:700",
               "Hoàn thành":"background:#dbeafe;color:#1e40af;font-weight:700",
               "Tạm dừng":"background:#fef9c3;color:#854d0e;font-weight:700",
               "Hủy":"background:#fee2e2;color:#991b1b;font-weight:700"}
            return m.get(v,"")

        df_p = pd.DataFrame([{"Mã DA":p["Mã DA"],"Tên dự án":p["Tên dự án"],"Khách hàng":p["Khách hàng"],
            "Địa điểm":p["Địa điểm"],"Bắt đầu":p["Ngày bắt đầu"],"Kết thúc":p["Ngày kết thúc"],
            "Phụ trách":p["Người phụ trách"],"Trạng thái":p["Trạng thái"]} for p in all_projects])
        st.dataframe(df_p.style.map(c_da,subset=["Trạng thái"])
            .set_properties(**{"font-size":"13px","padding":"8px 12px"})
            .set_table_styles([{"selector":"thead th","props":[("background","#f8fafc"),("font-weight","700"),
              ("font-size","11px"),("color","#64748b"),("text-transform","uppercase"),("padding","10px 12px")]}]),
            use_container_width=True, hide_index=True)

        st.markdown("---")
        for i,proj in enumerate(all_projects):
            can = cu().get("Vai trò") in ["Quản lý","Trưởng QC"] or proj.get("Người tạo")==cu().get("Tài khoản")
            badge = "🔓" if can else "🔒"
            with st.expander(f"{badge}  **{proj['Mã DA']}** — {proj['Tên dự án']}  ·  {proj['Trạng thái']}"):
                if not can: st.caption("🔒 Không có quyền sửa/xóa dự án này."); continue
                with st.form(f"frm_edit_da_{i}"):
                    c1,c2=st.columns(2)
                    e_ma=c1.text_input("Mã DA",value=proj["Mã DA"])
                    e_ten=c2.text_input("Tên dự án",value=proj["Tên dự án"])
                    e_kh=c1.text_input("Khách hàng",value=proj["Khách hàng"])
                    e_dd=c2.text_input("Địa điểm",value=proj["Địa điểm"])
                    e_bd=c1.text_input("Ngày bắt đầu",value=proj["Ngày bắt đầu"])
                    e_kt=c2.text_input("Ngày kết thúc",value=proj["Ngày kết thúc"])
                    tt_o=["Đang chạy","Tạm dừng","Hoàn thành","Hủy"]
                    e_tt=c1.selectbox("Trạng thái",tt_o,index=tt_o.index(proj["Trạng thái"]) if proj["Trạng thái"] in tt_o else 0,key=f"tt_da_{i}")
                    un_e=unames(); cur_pt=proj.get("Người phụ trách","")
                    e_pt=c2.selectbox("Người phụ trách",un_e,index=un_e.index(cur_pt) if cur_pt in un_e else 0,key=f"pt_da_{i}")
                    e_mo=st.text_area("Mô tả",value=proj.get("Mô tả","-"),height=68)
                    sa,sb,_=st.columns([1.5,1.5,6])
                    if sa.form_submit_button("💾 Lưu",use_container_width=True):
                        st.session_state.project_list[i].update({"Mã DA":e_ma,"Tên dự án":e_ten,"Khách hàng":e_kh,
                            "Địa điểm":e_dd,"Ngày bắt đầu":e_bd,"Ngày kết thúc":e_kt,
                            "Trạng thái":e_tt,"Người phụ trách":e_pt,"Mô tả":e_mo})
                        persist("project_list"); ghi_log("Dự án","Cập nhật",f"Sửa {e_ma}",e_ma); st.rerun()
                    if sb.form_submit_button("🗑️ Xóa dự án",use_container_width=True):
                        st.session_state.project_list.pop(i)
                        persist("project_list"); ghi_log("Dự án","Xóa",f"Xóa {proj['Mã DA']}",proj["Mã DA"]); st.rerun()

# ══════════════════════════════════════════════════════════
# HÀM IQC (đã sửa giống IPQC)
# ══════════════════════════════════════════════════════════
def form_iqc():
    require_project(); da_banner()
    st.markdown("## ✅ Kiểm tra đầu vào (IQC)")
    
    if st.session_state.get("last_drive_upload"):
        st.success("✅ Files đã upload lên Google Drive:")
        for f in st.session_state["last_drive_upload"]:
            st.markdown(f"📥 [{f['name']}]({f['url']})")
        if st.button("Đóng thông báo", key="close_drive_msg_iqc"):
            st.session_state["last_drive_upload"] = None
            st.rerun()
    
    draft_key = f"iqc_draft_{st.session_state.active_project}"
    if draft_key not in st.session_state:
        saved_draft = load_draft("iqc_form")
        if saved_draft:
            st.session_state[draft_key] = saved_draft
    if st.session_state.get(draft_key):
        draft = st.session_state[draft_key]
        col1, col2 = st.columns([4, 1])
        with col1:
            st.info(f"📝 Có nháp từ {draft.get('saved_at', 'lúc trước')} — nội dung chưa lưu")
        with col2:
            if st.button("🗑️ Xóa nháp", key="clear_iqc_draft"):
                st.session_state[draft_key] = None
                clear_draft("iqc_form")
                st.rerun()
    
    lst = get_da_list("iqc_data")
    csv = pd.DataFrame(lst).to_csv(index=False).encode("utf-8-sig") if lst else b""
    st.download_button("📥 CSV", data=csv, file_name=f"IQC_{AP}.csv", mime="text/csv", key="dl_iqc", disabled=not lst)
    
    _show_iqc = bool(st.session_state.get("last_created_iqc"))
    with st.expander("➕ Tạo phiếu IQC mới", expanded=_show_iqc):
        last_iqc = st.session_state.get("last_created_iqc")
        if last_iqc:
            st.success(f"✅ Đã tạo phiếu **{last_iqc['sp']}**")
            st.markdown("#### 📎 Upload file đính kèm ngay:")
            up_now_iqc = st.file_uploader("Chọn file", accept_multiple_files=True,
                                           type=["pdf","docx","xlsx","xls","jpg","jpeg","png"],
                                           key=f"iqc_upload_{id(last_iqc)}")
            c1u, c2u = st.columns(2)
            if up_now_iqc and c1u.button("☁️ Upload lên Drive", use_container_width=True, key="btn_up_iqc"):
                drive_files = []
                for file in up_now_iqc:
                    success, msg, file_id = upload_file_to_drive(file.name, file.getvalue())
                    if success and file_id:
                        drive_url = get_drive_file_download_url(file_id)
                        drive_files.append({"name": file.name, "id": file_id, "url": drive_url})
                        st.success(f"✅ {file.name}")
                    else:
                        st.error(msg)
                if drive_files:
                    idx = last_iqc["idx"]
                    lst[idx]["drive_files"] = list(lst[idx].get("drive_files", [])) + drive_files
                    lst[idx]["Files"] = [f["name"] for f in lst[idx]["drive_files"]]
                    set_da_list("iqc_data", lst)
                    st.session_state["last_created_iqc"] = None
                    st.session_state["last_drive_upload"] = drive_files
                    st.rerun()
            if c2u.button("⏭️ Bỏ qua", use_container_width=True, key="btn_skip_iqc"):
                st.session_state["last_created_iqc"] = None
                st.rerun()
            if st.button("Đóng thông báo", key="close_iqc_msg"):
                st.session_state["last_created_iqc"] = None
                st.rerun()
            st.divider()
        
        with st.form("frm_iqc_new", clear_on_submit=True):
            c1, c2 = st.columns(2)
            sp = c1.text_input("Số phiếu *")
            vt = c2.text_input("Tên vật tư *")
            nc = c1.text_input("Nhà cung cấp")
            lo = c2.text_input("Lô hàng")
            sl = c1.text_input("SL mẫu")
            tt = c2.selectbox("Trạng thái", ["Đạt (Pass)", "Không đạt (Failed)"])
            un = unames()
            nk = c1.selectbox("Người kiểm", un, index=un.index(cu().get("Họ tên", "")) if cu().get("Họ tên", "") in un else 0)
            ng = c2.date_input("Ngày kiểm", value=date.today())
            gi = c1.time_input("Giờ kiểm", value=datetime.now().time())
            gc = st.text_area("Ghi chú", height=100)

            if sp or vt:
                draft_data = {"số_phiếu": sp, "tên_vật_tư": vt,
                              "nhà_cung_cấp": nc, "lô": lo,
                              "saved_at": datetime.now().strftime("%H:%M:%S")}
                save_draft("iqc_form", draft_data)
                st.session_state[draft_key] = draft_data

            if st.form_submit_button("✅ Tạo phiếu", use_container_width=True):
                if sp and vt:
                    lst.append({
                        "Số phiếu": sp,
                        "Tên vật tư": vt,
                        "Nhà cung cấp": nc or "-",
                        "Lô": lo or "-",
                        "SL mẫu": sl or "-",
                        "Thời gian kiểm": f"{ng.strftime('%d-%m-%Y')} {gi.strftime('%H:%M')}",
                        "Người kiểm": nk,
                        "Files": [],
                        "drive_files": [],
                        "Trạng thái": tt,
                        "Ghi chú": gc or "-",
                        "Người tạo": cu().get("Tài khoản", "")
                    })
                    set_da_list("iqc_data", lst)
                    clear_draft("iqc_form")
                    st.session_state[draft_key] = None
                    st.session_state["last_created_iqc"] = {"sp": sp, "idx": len(lst) - 1}
                    ghi_log("IQC", "Tạo mới", f"Tạo {sp}")
                    st.rerun()
                else:
                    st.error("Điền Số phiếu và Tên vật tư")

    def edit_iqc(idx, row, lst_ref, dk):
        cur_drive_files = list(row.get("drive_files", []))
        if cur_drive_files:
            st.markdown("**📎 Files đã upload:**")
            for f in cur_drive_files:
                st.markdown(f"📥 [{f['name']}]({f['url']})")
        
        new_up = st.file_uploader("➕ Upload file lên Google Drive",
                                   accept_multiple_files=True,
                                   type=["pdf","docx","xlsx","xls","jpg","jpeg","png"],
                                   key=f"up_iqc_{idx}")
        if new_up and st.button("☁️ Upload lên Drive", key=f"btn_upload_iqc_{idx}"):
            new_drive_files = list(cur_drive_files)
            for file in new_up:
                success, msg, file_id = upload_file_to_drive(file.name, file.getvalue())
                if success and file_id:
                    drive_url = get_drive_file_download_url(file_id)
                    new_drive_files.append({"name": file.name, "id": file_id, "url": drive_url})
                    st.success(f"✅ Đã upload {file.name}")
                else:
                    st.error(msg)
            file_names = [f["name"] for f in new_drive_files]
            lst_ref[idx].update({"Files": file_names, "drive_files": new_drive_files})
            set_da_list("iqc_data", lst_ref)
            ghi_log("IQC", "Upload file", f"Upload {len(new_up)} file vào {row.get('Số phiếu','')}")
            st.session_state["last_drive_upload"] = new_drive_files
            st.rerun()
        
        with st.form(f"frm_eiqc_{idx}"):
            c1, c2 = st.columns(2)
            sp = c1.text_input("Số phiếu", value=row.get("Số phiếu",""))
            vt = c2.text_input("Tên vật tư", value=row.get("Tên vật tư",""))
            nc = c1.text_input("Nhà cung cấp", value=row.get("Nhà cung cấp",""))
            lo = c2.text_input("Lô", value=row.get("Lô",""))
            sl = c1.text_input("SL mẫu", value=row.get("SL mẫu",""))
            tt_o = ["Đạt (Pass)", "Không đạt (Failed)"]
            cur_tt = row.get("Trạng thái", "Đạt (Pass)")
            tt = c2.selectbox("Trạng thái", tt_o, index=tt_o.index(cur_tt) if cur_tt in tt_o else 0, key=f"tt_iqc_{idx}")
            un = unames()
            cur_nk = row.get("Người kiểm","")
            nk = c1.selectbox("Người kiểm", un, index=un.index(cur_nk) if cur_nk in un else 0, key=f"nk_iqc_{idx}")
            gc = st.text_area("Ghi chú", value=row.get("Ghi chú",""), height=100)
            if st.form_submit_button("💾 Lưu", use_container_width=True):
                lst_ref[idx].update({
                    "Số phiếu": sp,
                    "Tên vật tư": vt,
                    "Nhà cung cấp": nc,
                    "Lô": lo,
                    "SL mẫu": sl,
                    "Người kiểm": nk,
                    "Trạng thái": tt,
                    "Ghi chú": gc
                })
                set_da_list("iqc_data", lst_ref)
                ghi_log("IQC", "Cập nhật", f"Sửa {sp}")
                st.rerun()
    
    st.write("")
    table_actions(lst, "Số phiếu", "IQC", "iqc_data", edit_iqc)

# ══════════════════════════════════════════════════════════
# IPQC
# ══════════════════════════════════════════════════════════
def form_ipqc():
    require_project(); da_banner()
    st.markdown("## 🧪 Kiểm tra quá trình (IPQC)")
    
    if st.session_state.get("last_drive_upload"):
        st.success("✅ Files đã upload lên Google Drive:")
        for f in st.session_state["last_drive_upload"]:
            st.markdown(f"📥 [{f['name']}]({f['url']})")
        if st.button("Đóng thông báo", key="close_drive_msg_ipqc"):
            st.session_state["last_drive_upload"] = None
            st.rerun()
    
    lst=get_da_list("ipqc_data")
    csv=pd.DataFrame(lst).to_csv(index=False).encode("utf-8-sig") if lst else b""
    st.download_button("📥 CSV",data=csv,file_name=f"IPQC_{AP}.csv",mime="text/csv",key="dl_ipqc",disabled=not lst)
    _show_ipqc = bool(st.session_state.get("last_created_ipqc"))
    with st.expander("➕ Tạo phiếu IPQC mới", expanded=_show_ipqc):
        last_ipqc = st.session_state.get("last_created_ipqc")
        if last_ipqc:
            st.success(f"✅ Đã tạo phiếu **{last_ipqc['sp']}**")
            st.markdown("#### 📎 Upload file đính kèm ngay:")
            up_now_ipqc = st.file_uploader("Chọn file",accept_multiple_files=True,type=["pdf","docx","xlsx","xls","jpg","jpeg","png"],key=f"ipqc_upload_{id(last_ipqc)}")
            c1u,c2u=st.columns(2)
            if up_now_ipqc and c1u.button("☁️ Upload lên Drive",use_container_width=True,key="btn_up_ipqc"):
                drive_files=[]
                for file in up_now_ipqc:
                    success,msg,file_id=upload_file_to_drive(file.name,file.getvalue())
                    if success and file_id:
                        drive_url=get_drive_file_download_url(file_id)
                        drive_files.append({"name":file.name,"id":file_id,"url":drive_url})
                        st.success(f"✅ {file.name}")
                    else: st.error(msg)
                if drive_files:
                    idx=last_ipqc["idx"]; lst[idx]["drive_files"]=list(lst[idx].get("drive_files",[]))+drive_files
                    lst[idx]["Files"]=[f["name"] for f in lst[idx]["drive_files"]]
                    set_da_list("ipqc_data",lst); st.session_state["last_created_ipqc"]=None
                    st.session_state["last_drive_upload"]=drive_files; st.rerun()
            if c2u.button("⏭️ Bỏ qua",use_container_width=True,key="btn_skip_ipqc"):
                st.session_state["last_created_ipqc"]=None; st.rerun()
            if st.button("Đóng thông báo", key="close_ipqc_msg"):
                st.session_state["last_created_ipqc"]=None; st.rerun()
            st.divider()
        with st.form("frm_ipqc_new",clear_on_submit=True):
            c1,c2=st.columns(2)
            sp=c1.text_input("Số phiếu *"); cd=c2.text_input("Tên công đoạn *")
            lo=c1.text_input("Lô sản xuất"); sl=c2.text_input("SL mẫu")
            tt=c1.selectbox("Trạng thái",["Đạt (Pass)","Không đạt (Failed)"])
            un=unames(); nk=c2.selectbox("Người kiểm",un,index=un.index(cu().get("Họ tên","")) if cu().get("Họ tên","") in un else 0)
            ng=c1.date_input("Ngày kiểm",value=date.today()); gi=c2.time_input("Giờ",value=datetime.now().time())
            gc=st.text_area("Ghi chú",height=100)
            if st.form_submit_button("✅ Tạo phiếu",use_container_width=True):
                if sp and cd:
                    lst.append({"Số phiếu":sp,"Tên công đoạn":cd,"Lô":lo or "-","SL mẫu":sl or "-",
                        "Thời gian kiểm":f"{ng.strftime('%d-%m-%Y')} {gi.strftime('%H:%M')}",
                        "Người kiểm":nk,"Files":[],"drive_files":[],
                        "Trạng thái":tt,"Ghi chú":gc or "-","Người tạo":cu().get("Tài khoản","")})
                    set_da_list("ipqc_data",lst)
                    st.session_state["last_created_ipqc"]={"sp":sp,"idx":len(lst)-1}
                    ghi_log("IPQC","Tạo mới",f"Tạo {sp}"); st.rerun()
                else: st.error("Điền Số phiếu và Tên công đoạn")
    def edit_ipqc(idx,row,lst_ref,dk):
        cur_drive_files = list(row.get("drive_files", []))
        if cur_drive_files:
            st.markdown("**📎 Files đã upload:**")
            for f in cur_drive_files:
                st.markdown(f"📥 [{f['name']}]({f['url']})")
        
        new_up = st.file_uploader("➕ Upload file lên Google Drive",
            accept_multiple_files=True,
            type=["pdf","docx","xlsx","xls","jpg","jpeg","png"],
            key=f"up_ipqc_{idx}")
        
        if new_up and st.button("☁️ Upload lên Drive", key=f"btn_upload_ipqc_{idx}"):
            new_drive_files = list(cur_drive_files)
            for file in new_up:
                success, msg, file_id = upload_file_to_drive(file.name, file.getvalue())
                if success and file_id:
                    drive_url = get_drive_file_download_url(file_id)
                    new_drive_files.append({"name": file.name, "id": file_id, "url": drive_url})
                    st.success(f"✅ Đã upload {file.name}")
                else:
                    st.error(msg)
            file_names = [f["name"] for f in new_drive_files]
            lst_ref[idx].update({"Files": file_names, "drive_files": new_drive_files})
            set_da_list("ipqc_data", lst_ref)
            ghi_log("IPQC", "Upload file", f"Upload {len(new_up)} file vào {row.get('Số phiếu','')}")
            st.session_state["last_drive_upload"] = new_drive_files
            st.rerun()
        
        with st.form(f"frm_eipqc_{idx}"):
            c1,c2=st.columns(2)
            sp=c1.text_input("Số phiếu",value=row.get("Số phiếu",""))
            cd=c2.text_input("Tên công đoạn",value=row.get("Tên công đoạn",""))
            lo=c1.text_input("Lô",value=row.get("Lô","")); sl=c2.text_input("SL mẫu",value=row.get("SL mẫu",""))
            tt_o=["Đạt (Pass)","Không đạt (Failed)"]; cur_tt=row.get("Trạng thái","Đạt (Pass)")
            tt=c1.selectbox("Trạng thái",tt_o,index=tt_o.index(cur_tt) if cur_tt in tt_o else 0,key=f"tt_ipqc_{idx}")
            un=unames(); cur_nk=row.get("Người kiểm","")
            nk=c2.selectbox("Người kiểm",un,index=un.index(cur_nk) if cur_nk in un else 0,key=f"nk_ipqc_{idx}")
            gc=st.text_area("Ghi chú",value=row.get("Ghi chú",""),height=100)
            if st.form_submit_button("💾 Lưu",use_container_width=True):
                lst_ref[idx].update({"Số phiếu":sp,"Tên công đoạn":cd,"Lô":lo,"SL mẫu":sl,"Người kiểm":nk,"Trạng thái":tt,"Ghi chú":gc})
                set_da_list("ipqc_data",lst_ref); ghi_log("IPQC","Cập nhật",f"Sửa {sp}"); st.rerun()
    st.write("")
    table_actions(lst,"Số phiếu","IPQC","ipqc_data",edit_ipqc)

# ══════════════════════════════════════════════════════════
# OQC
# ══════════════════════════════════════════════════════════
def form_oqc():
    require_project(); da_banner()
    st.markdown("## 📦 Kiểm tra thành phẩm (OQC)")
    
    if st.session_state.get("last_drive_upload"):
        st.success("✅ Files đã upload lên Google Drive:")
        for f in st.session_state["last_drive_upload"]:
            st.markdown(f"📥 [{f['name']}]({f['url']})")
        if st.button("Đóng thông báo", key="close_drive_msg_oqc"):
            st.session_state["last_drive_upload"] = None
            st.rerun()
    
    lst=get_da_list("oqc_data")
    csv=pd.DataFrame(lst).to_csv(index=False).encode("utf-8-sig") if lst else b""
    st.download_button("📥 CSV",data=csv,file_name=f"OQC_{AP}.csv",mime="text/csv",key="dl_oqc",disabled=not lst)
    _show_oqc = bool(st.session_state.get("last_created_oqc"))
    with st.expander("➕ Tạo phiếu OQC mới", expanded=_show_oqc):
        last_oqc = st.session_state.get("last_created_oqc")
        if last_oqc:
            st.success(f"✅ Đã tạo phiếu **{last_oqc['sp']}**")
            st.markdown("#### 📎 Upload file đính kèm ngay:")
            up_now_oqc = st.file_uploader("Chọn file",accept_multiple_files=True,type=["pdf","docx","xlsx","xls","jpg","jpeg","png"],key="oqc_upload_after")
            c1u,c2u=st.columns(2)
            if up_now_oqc and c1u.button("☁️ Upload lên Drive",use_container_width=True,key="btn_up_oqc"):
                drive_files=[]
                for file in up_now_oqc:
                    success,msg,file_id=upload_file_to_drive(file.name,file.getvalue())
                    if success and file_id:
                        drive_url=get_drive_file_download_url(file_id)
                        drive_files.append({"name":file.name,"id":file_id,"url":drive_url})
                        st.success(f"✅ {file.name}")
                    else: st.error(msg)
                if drive_files:
                    idx=last_oqc["idx"]; lst[idx]["drive_files"]=list(lst[idx].get("drive_files",[]))+drive_files
                    lst[idx]["Files"]=[f["name"] for f in lst[idx]["drive_files"]]
                    set_da_list("oqc_data",lst); st.session_state["last_created_oqc"]=None
                    st.session_state["last_drive_upload"]=drive_files; st.rerun()
            if c2u.button("⏭️ Bỏ qua",use_container_width=True,key="btn_skip_oqc"):
                st.session_state["last_created_oqc"]=None; st.rerun()
            if st.button("Đóng thông báo", key="close_oqc_msg"):
                st.session_state["last_created_oqc"]=None; st.rerun()
            st.divider()
        with st.form("frm_oqc_new",clear_on_submit=True):
            c1,c2=st.columns(2)
            sp=c1.text_input("Số phiếu *"); spn=c2.text_input("Mã/Tên sản phẩm *")
            lo=c1.text_input("Lô thành phẩm"); sl=c2.text_input("SL mẫu")
            tt=c1.selectbox("Trạng thái",["Đạt (Pass)","Không đạt (Failed)"])
            un=unames(); nk=c2.selectbox("Người kiểm",un,index=un.index(cu().get("Họ tên","")) if cu().get("Họ tên","") in un else 0)
            ng=c1.date_input("Ngày kiểm",value=date.today()); gi=c2.time_input("Giờ",value=datetime.now().time())
            gc=st.text_area("Ghi chú",height=100)
            if st.form_submit_button("✅ Tạo phiếu",use_container_width=True):
                if sp and spn:
                    lst.append({"Số phiếu":sp,"Mã/Tên SP":spn,"Lô":lo or "-","SL mẫu":sl or "-",
                        "Thời gian kiểm":f"{ng.strftime('%d-%m-%Y')} {gi.strftime('%H:%M')}",
                        "Người kiểm":nk,"Files":[],"drive_files":[],
                        "Trạng thái":tt,"Ghi chú":gc or "-","Người tạo":cu().get("Tài khoản","")})
                    set_da_list("oqc_data",lst)
                    st.session_state["last_created_oqc"]={"sp":sp,"idx":len(lst)-1}
                    ghi_log("OQC","Tạo mới",f"Tạo {sp}"); st.rerun()
                else: st.error("Điền Số phiếu và Mã/Tên sản phẩm")
    def edit_oqc(idx,row,lst_ref,dk):
        cur_drive_files = list(row.get("drive_files", []))
        if cur_drive_files:
            st.markdown("**📎 Files đã upload:**")
            for f in cur_drive_files:
                st.markdown(f"📥 [{f['name']}]({f['url']})")
        
        new_up = st.file_uploader("➕ Upload file lên Google Drive",
            accept_multiple_files=True,
            type=["pdf","docx","xlsx","xls","jpg","jpeg","png"],
            key=f"up_oqc_{idx}")
        
        if new_up and st.button("☁️ Upload lên Drive", key=f"btn_upload_oqc_{idx}"):
            new_drive_files = list(cur_drive_files)
            for file in new_up:
                success, msg, file_id = upload_file_to_drive(file.name, file.getvalue())
                if success and file_id:
                    drive_url = get_drive_file_download_url(file_id)
                    new_drive_files.append({"name": file.name, "id": file_id, "url": drive_url})
                    st.success(f"✅ Đã upload {file.name}")
                else:
                    st.error(msg)
            file_names = [f["name"] for f in new_drive_files]
            lst_ref[idx].update({"Files": file_names, "drive_files": new_drive_files})
            set_da_list("oqc_data", lst_ref)
            ghi_log("OQC", "Upload file", f"Upload {len(new_up)} file vào {row.get('Số phiếu','')}")
            st.session_state["last_drive_upload"] = new_drive_files
            st.rerun()
        
        with st.form(f"frm_eoqc_{idx}"):
            c1,c2=st.columns(2)
            sp=c1.text_input("Số phiếu",value=row.get("Số phiếu",""))
            spn=c2.text_input("Mã/Tên SP",value=row.get("Mã/Tên SP",""))
            lo=c1.text_input("Lô",value=row.get("Lô","")); sl=c2.text_input("SL mẫu",value=row.get("SL mẫu",""))
            tt_o=["Đạt (Pass)","Không đạt (Failed)"]; cur_tt=row.get("Trạng thái","Đạt (Pass)")
            tt=c1.selectbox("Trạng thái",tt_o,index=tt_o.index(cur_tt) if cur_tt in tt_o else 0,key=f"tt_oqc_{idx}")
            un=unames(); cur_nk=row.get("Người kiểm","")
            nk=c2.selectbox("Người kiểm",un,index=un.index(cur_nk) if cur_nk in un else 0,key=f"nk_oqc_{idx}")
            gc=st.text_area("Ghi chú",value=row.get("Ghi chú",""),height=100)
            if st.form_submit_button("💾 Lưu",use_container_width=True):
                lst_ref[idx].update({"Số phiếu":sp,"Mã/Tên SP":spn,"Lô":lo,"SL mẫu":sl,"Người kiểm":nk,"Trạng thái":tt,"Ghi chú":gc})
                set_da_list("oqc_data",lst_ref); ghi_log("OQC","Cập nhật",f"Sửa {sp}"); st.rerun()
    st.write("")
    table_actions(lst,"Số phiếu","OQC","oqc_data",edit_oqc)

# Dispatch
if   page=="✅ IQC":  form_iqc()
elif page=="🧪 IPQC": form_ipqc()
elif page=="📦 OQC":  form_oqc()

# ══════════════════════════════════════════════════════════
# NCR + CAPA
# ══════════════════════════════════════════════════════════
elif page == "⚠️ NCR + CAPA":
    require_project(); da_banner()
    st.markdown("## ⚠️ NCR & CAPA")
    tab_ncr, tab_capa = st.tabs(["📋 NCR","🔁 CAPA"])

    with tab_ncr:
        if st.session_state.get("last_drive_upload"):
            st.success("✅ Files đã upload lên Google Drive:")
            for f in st.session_state["last_drive_upload"]:
                st.markdown(f"📥 [{f['name']}]({f['url']})")
            if st.button("Đóng thông báo", key="close_drive_msg_ncr"):
                st.session_state["last_drive_upload"] = None
                st.rerun()
        
        lst=get_da_list("ncr_data")
        csv=pd.DataFrame(lst).to_csv(index=False).encode("utf-8-sig") if lst else b""
        st.download_button("📥 CSV",data=csv,file_name=f"NCR_{AP}.csv",mime="text/csv",key="dl_ncr",disabled=not lst)
        _show_ncr = bool(st.session_state.get("last_created_ncr"))
        with st.expander("➕ Tạo NCR mới", expanded=_show_ncr):
            last_ncr = st.session_state.get("last_created_ncr")
            if last_ncr:
                st.success(f"✅ Đã tạo NCR **{last_ncr['sp']}**")
                st.markdown("#### 📎 Upload file đính kèm ngay:")
                up_now_ncr = st.file_uploader("Chọn file",accept_multiple_files=True,type=["pdf","docx","xlsx","xls","jpg","jpeg","png"],key="ncr_upload_after")
                c1u,c2u=st.columns(2)
                if up_now_ncr and c1u.button("☁️ Upload lên Drive",use_container_width=True,key="btn_up_ncr"):
                    drive_files=[]
                    for file in up_now_ncr:
                        success,msg,file_id=upload_file_to_drive(file.name,file.getvalue())
                        if success and file_id:
                            drive_url=get_drive_file_download_url(file_id)
                            drive_files.append({"name":file.name,"id":file_id,"url":drive_url})
                            st.success(f"✅ {file.name}")
                        else: st.error(msg)
                    if drive_files:
                        idx=last_ncr["idx"]; lst[idx]["drive_files"]=list(lst[idx].get("drive_files",[]))+drive_files
                        lst[idx]["Files"]=[f["name"] for f in lst[idx]["drive_files"]]
                        set_da_list("ncr_data",lst); st.session_state["last_created_ncr"]=None
                        st.session_state["last_drive_upload"]=drive_files; st.rerun()
                if c2u.button("⏭️ Bỏ qua",use_container_width=True,key="btn_skip_ncr"):
                    st.session_state["last_created_ncr"]=None; st.rerun()
                if st.button("Đóng thông báo", key="close_ncr_msg"):
                    st.session_state["last_created_ncr"]=None; st.rerun()
                st.divider()
            with st.form("frm_ncr_new",clear_on_submit=True):
                c1,c2=st.columns(2)
                so=c1.text_input("Số NCR *"); ten=c2.text_input("Tên vật tư/SP *")
                lo=c1.text_input("Lô"); sl=c2.text_input("SL phát hiện")
                md=c1.selectbox("Mức độ",["Nhẹ","Vừa","Nghiêm trọng"])
                tt=c2.selectbox("Trạng thái",["Đang điều tra","Mở","Đã xử lý","Đã đóng"])
                un=unames(); ph=c1.selectbox("Người phát hiện",un,index=un.index(cu().get("Họ tên","")) if cu().get("Họ tên","") in un else 0)
                nl=c2.selectbox("Người lập",un,index=un.index(cu().get("Họ tên","")) if cu().get("Họ tên","") in un else 0)
                ng=c1.date_input("Ngày",value=date.today()); gi=c2.time_input("Giờ",value=datetime.now().time())
                gc=st.text_area("Ghi chú",height=100)
                if st.form_submit_button("✅ Tạo NCR",use_container_width=True):
                    if so and ten:
                        lst.append({"Số NCR":so,"Tên vật tư/SP":ten,"Lô":lo or "-","SL phát hiện":sl or "-",
                            "Thời gian":f"{ng.strftime('%d-%m-%Y')} {gi.strftime('%H:%M')}",
                            "Người phát hiện":ph,"Người lập":nl,"Mức độ":md,"Trạng thái":tt,
                            "Files":[],"drive_files":[],"Ghi chú":gc or "-","Người tạo":cu().get("Tài khoản","")})
                        set_da_list("ncr_data",lst)
                        st.session_state["last_created_ncr"]={"sp":so,"idx":len(lst)-1}
                        ghi_log("NCR","Tạo mới",f"Tạo {so}"); st.rerun()
                    else: st.error("Điền Số NCR và Tên vật tư/SP")
        def edit_ncr(idx,row,lst_ref,dk):
            cur_drive_files = list(row.get("drive_files", []))
            if cur_drive_files:
                st.markdown("**📎 Files đã upload:**")
                for f in cur_drive_files:
                    st.markdown(f"📥 [{f['name']}]({f['url']})")
            
            new_up = st.file_uploader("➕ Upload file lên Google Drive",
                accept_multiple_files=True,
                type=["pdf","docx","xlsx","xls","jpg","jpeg","png"],
                key=f"up_ncr_{idx}")
            
            if new_up and st.button("☁️ Upload lên Drive", key=f"btn_upload_ncr_{idx}"):
                new_drive_files = list(cur_drive_files)
                for file in new_up:
                    success, msg, file_id = upload_file_to_drive(file.name, file.getvalue())
                    if success and file_id:
                        drive_url = get_drive_file_download_url(file_id)
                        new_drive_files.append({"name": file.name, "id": file_id, "url": drive_url})
                        st.success(f"✅ Đã upload {file.name}")
                    else:
                        st.error(msg)
                file_names = [f["name"] for f in new_drive_files]
                lst_ref[idx].update({"Files": file_names, "drive_files": new_drive_files})
                set_da_list("ncr_data", lst_ref)
                ghi_log("NCR", "Upload file", f"Upload {len(new_up)} file vào {row.get('Số NCR','')}")
                st.session_state["last_drive_upload"] = new_drive_files
                st.rerun()
            
            with st.form(f"frm_encr_{idx}"):
                c1,c2=st.columns(2)
                so=c1.text_input("Số NCR",value=row.get("Số NCR",""))
                ten=c2.text_input("Tên vật tư/SP",value=row.get("Tên vật tư/SP",""))
                lo=c1.text_input("Lô",value=row.get("Lô","")); sl=c2.text_input("SL phát hiện",value=row.get("SL phát hiện",""))
                md_o=["Nhẹ","Vừa","Nghiêm trọng"]; cur_md=row.get("Mức độ","Vừa")
                md=c1.selectbox("Mức độ",md_o,index=md_o.index(cur_md) if cur_md in md_o else 0,key=f"md_ncr_{idx}")
                tt_o=["Đang điều tra","Mở","Đã xử lý","Đã đóng"]; cur_tt=row.get("Trạng thái","Đang điều tra")
                tt=c2.selectbox("Trạng thái",tt_o,index=tt_o.index(cur_tt) if cur_tt in tt_o else 0,key=f"tt_ncr_{idx}")
                un=unames(); cur_ph=row.get("Người phát hiện",""); cur_nl=row.get("Người lập","")
                ph=c1.selectbox("Người phát hiện",un,index=un.index(cur_ph) if cur_ph in un else 0,key=f"ph_ncr_{idx}")
                nl=c2.selectbox("Người lập",un,index=un.index(cur_nl) if cur_nl in un else 0,key=f"nl_ncr_{idx}")
                gc=st.text_area("Ghi chú",value=row.get("Ghi chú",""),height=100)
                if st.form_submit_button("💾 Lưu",use_container_width=True):
                    lst_ref[idx].update({"Số NCR":so,"Tên vật tư/SP":ten,"Lô":lo,"SL phát hiện":sl,
                        "Mức độ":md,"Trạng thái":tt,"Người phát hiện":ph,"Người lập":nl,"Ghi chú":gc})
                    set_da_list("ncr_data",lst_ref); ghi_log("NCR","Cập nhật",f"Sửa {so}"); st.rerun()
        st.write(""); table_actions(lst,"Số NCR","NCR","ncr_data",edit_ncr)

    with tab_capa:
        if st.session_state.get("last_drive_upload"):
            st.success("✅ Files đã upload lên Google Drive:")
            for f in st.session_state["last_drive_upload"]:
                st.markdown(f"📥 [{f['name']}]({f['url']})")
            if st.button("Đóng thông báo", key="close_drive_msg_capa"):
                st.session_state["last_drive_upload"] = None
                st.rerun()
        
        lst=get_da_list("capa_data")
        csv=pd.DataFrame(lst).to_csv(index=False).encode("utf-8-sig") if lst else b""
        st.download_button("📥 CSV",data=csv,file_name=f"CAPA_{AP}.csv",mime="text/csv",key="dl_capa",disabled=not lst)
        _show_capa = bool(st.session_state.get("last_created_capa"))
        with st.expander("➕ Tạo CAPA mới", expanded=_show_capa):
            last_capa = st.session_state.get("last_created_capa")
            if last_capa:
                st.success(f"✅ Đã tạo CAPA **{last_capa['sp']}**")
                st.markdown("#### 📎 Upload file đính kèm ngay:")
                up_now_capa = st.file_uploader("Chọn file",accept_multiple_files=True,type=["pdf","docx","xlsx","xls","jpg","jpeg","png"],key="capa_upload_after")
                c1u,c2u=st.columns(2)
                if up_now_capa and c1u.button("☁️ Upload lên Drive",use_container_width=True,key="btn_up_capa"):
                    drive_files=[]
                    for file in up_now_capa:
                        success,msg,file_id=upload_file_to_drive(file.name,file.getvalue())
                        if success and file_id:
                            drive_url=get_drive_file_download_url(file_id)
                            drive_files.append({"name":file.name,"id":file_id,"url":drive_url})
                            st.success(f"✅ {file.name}")
                        else: st.error(msg)
                    if drive_files:
                        idx=last_capa["idx"]; lst[idx]["drive_files"]=list(lst[idx].get("drive_files",[]))+drive_files
                        lst[idx]["Files"]=[f["name"] for f in lst[idx]["drive_files"]]
                        set_da_list("capa_data",lst); st.session_state["last_created_capa"]=None
                        st.session_state["last_drive_upload"]=drive_files; st.rerun()
                if c2u.button("⏭️ Bỏ qua",use_container_width=True,key="btn_skip_capa"):
                    st.session_state["last_created_capa"]=None; st.rerun()
                if st.button("Đóng thông báo", key="close_capa_msg"):
                    st.session_state["last_created_capa"]=None; st.rerun()
                st.divider()
            with st.form("frm_capa_new",clear_on_submit=True):
                c1,c2=st.columns(2)
                ma=c1.text_input("Mã CAPA *"); ncr=c2.text_input("Số NCR liên kết")
                bp=c1.text_input("Bộ phận"); th=c2.date_input("Thời hạn",value=date.today())
                tt=c1.selectbox("Trạng thái CAPA",["Đang tiến hành","Hoàn thành","Quá hạn"])
                un=unames(); nl=c2.selectbox("Người lập",un,index=un.index(cu().get("Họ tên","")) if cu().get("Họ tên","") in un else 0)
                nn=st.text_area("Nguyên nhân gốc rễ",height=100)
                kp=st.text_area("Hành động khắc phục",height=100)
                pn=st.text_area("Hành động phòng ngừa",height=100)
                gc=st.text_area("Ghi chú",height=100)
                if st.form_submit_button("✅ Tạo CAPA",use_container_width=True):
                    if ma:
                        lst.append({"Mã CAPA":ma,"Số NCR":ncr or "-","Nguyên nhân":nn or "-",
                            "Khắc phục":kp or "-","Phòng ngừa":pn or "-","Bộ phận":bp or "-",
                            "Thời hạn":th.strftime("%d-%m-%Y"),"Người lập":nl,"Trạng thái CAPA":tt,
                            "Files":[],"drive_files":[],"Ghi chú":gc or "-","Người tạo":cu().get("Tài khoản","")})
                        set_da_list("capa_data",lst)
                        st.session_state["last_created_capa"]={"sp":ma,"idx":len(lst)-1}
                        ghi_log("CAPA","Tạo mới",f"Tạo {ma}"); st.rerun()
                    else: st.error("Điền Mã CAPA")
        def edit_capa(idx,row,lst_ref,dk):
            cur_drive_files = list(row.get("drive_files", []))
            if cur_drive_files:
                st.markdown("**📎 Files đã upload:**")
                for f in cur_drive_files:
                    st.markdown(f"📥 [{f['name']}]({f['url']})")
            
            new_up = st.file_uploader("➕ Upload file lên Google Drive",
                accept_multiple_files=True,
                type=["pdf","docx","xlsx","xls","jpg","jpeg","png"],
                key=f"up_capa_{idx}")
            
            if new_up and st.button("☁️ Upload lên Drive", key=f"btn_upload_capa_{idx}"):
                new_drive_files = list(cur_drive_files)
                for file in new_up:
                    success, msg, file_id = upload_file_to_drive(file.name, file.getvalue())
                    if success and file_id:
                        drive_url = get_drive_file_download_url(file_id)
                        new_drive_files.append({"name": file.name, "id": file_id, "url": drive_url})
                        st.success(f"✅ Đã upload {file.name}")
                    else:
                        st.error(msg)
                file_names = [f["name"] for f in new_drive_files]
                lst_ref[idx].update({"Files": file_names, "drive_files": new_drive_files})
                set_da_list("capa_data", lst_ref)
                ghi_log("CAPA", "Upload file", f"Upload {len(new_up)} file vào {row.get('Mã CAPA','')}")
                st.session_state["last_drive_upload"] = new_drive_files
                st.rerun()
            
            with st.form(f"frm_ecapa_{idx}"):
                c1,c2=st.columns(2)
                ma=c1.text_input("Mã CAPA",value=row.get("Mã CAPA",""))
                ncr=c2.text_input("Số NCR",value=row.get("Số NCR",""))
                bp=c1.text_input("Bộ phận",value=row.get("Bộ phận",""))
                th=c2.text_input("Thời hạn",value=row.get("Thời hạn",""))
                tt_o=["Đang tiến hành","Hoàn thành","Quá hạn"]; cur_tt=row.get("Trạng thái CAPA","Đang tiến hành")
                tt=c1.selectbox("Trạng thái CAPA",tt_o,index=tt_o.index(cur_tt) if cur_tt in tt_o else 0,key=f"tt_capa_{idx}")
                un=unames(); cur_nl=row.get("Người lập","")
                nl=c2.selectbox("Người lập",un,index=un.index(cur_nl) if cur_nl in un else 0,key=f"nl_capa_{idx}")
                nn=st.text_area("Nguyên nhân",value=row.get("Nguyên nhân",""),height=100)
                kp=st.text_area("Khắc phục",value=row.get("Khắc phục",""),height=100)
                gc=st.text_area("Ghi chú",value=row.get("Ghi chú",""),height=100)
                if st.form_submit_button("💾 Lưu",use_container_width=True):
                    lst_ref[idx].update({"Mã CAPA":ma,"Số NCR":ncr,"Bộ phận":bp,"Thời hạn":th,
                        "Trạng thái CAPA":tt,"Nguyên nhân":nn,"Khắc phục":kp,"Người lập":nl,"Ghi chú":gc})
                    set_da_list("capa_data",lst_ref); ghi_log("CAPA","Cập nhật",f"Sửa {ma}"); st.rerun()
        st.write(""); table_actions(lst,"Mã CAPA","CAPA","capa_data",edit_capa,badge_col="Trạng thái CAPA")

# ══════════════════════════════════════════════════════════
# THIẾT BỊ ĐO
# ══════════════════════════════════════════════════════════
elif page == "🔧 Thiết bị đo":
    st.markdown("## 🔧 Thiết bị đo & Hiệu chuẩn")
    st.caption("Thiết bị đo dùng chung cho tất cả dự án")
    dev_lst = list(st.session_state.dev_data.values()) if isinstance(st.session_state.dev_data, dict) else st.session_state.dev_data
    if isinstance(st.session_state.dev_data, dict):
        st.session_state.dev_data = []
    dev_lst = st.session_state.dev_data

    csv=pd.DataFrame(dev_lst).to_csv(index=False).encode("utf-8-sig") if dev_lst else b""
    st.download_button("📥 CSV",data=csv,file_name="ThietBiDo.csv",mime="text/csv",key="dl_tb",disabled=not dev_lst)

    if "show_tb_form" not in st.session_state: st.session_state.show_tb_form=False
    if st.button("➕ Đăng ký thiết bị mới"): st.session_state.show_tb_form=True
    if st.session_state.show_tb_form:
        st.markdown("---")
        with st.form("frm_tb_new",clear_on_submit=True):
            c1,c2=st.columns(2)
            ma=c1.text_input("Mã TB *"); ten=c2.text_input("Tên thiết bị *")
            ser=c1.text_input("Số serie"); vt=c2.text_input("Vị trí")
            ck=c1.selectbox("Chu kỳ HC",["06 tháng","12 tháng"])
            tt=c2.selectbox("Tình trạng",["Sử dụng tốt","Chờ hiệu chuẩn","Hỏng"])
            last=c1.date_input("HC lần cuối",value=date.today()); nxt=c2.date_input("Hạn HC",value=date.today())
            un=unames(); nl=c1.selectbox("Người lập",un,index=un.index(cu().get("Họ tên","")) if cu().get("Họ tên","") in un else 0)
            gc=c2.text_input("Ghi chú")
            b1,b2,_=st.columns([1.5,1.5,6])
            ok=b1.form_submit_button("✅ Đăng ký",use_container_width=True)
            ca=b2.form_submit_button("❌ Hủy",use_container_width=True)
            if ok:
                if ma and ten:
                    dev_lst.append({"Mã TB":ma,"Tên thiết bị":ten,"Số serie":ser or "-","Vị trí":vt or "-",
                        "Chu kỳ HC":ck,"HC lần cuối":last.strftime("%d-%m-%Y"),"Hạn HC":nxt.strftime("%d-%m-%Y"),
                        "Người lập":nl,"Tình trạng":tt,"Ghi chú":gc or "-","Người tạo":cu().get("Tài khoản","")})
                    persist("dev_data"); ghi_log("TB","Đăng ký",f"Đăng ký {ma}")
                    st.session_state.show_tb_form=False; st.rerun()
                else: st.error("Điền Mã TB và Tên thiết bị")
            if ca: st.session_state.show_tb_form=False; st.rerun()
        st.markdown("---")

    def edit_tb(idx,row,lst_ref,dk):
        with st.form(f"frm_etb_{idx}"):
            c1,c2=st.columns(2)
            ma=c1.text_input("Mã TB",value=row.get("Mã TB",""))
            ten=c2.text_input("Tên thiết bị",value=row.get("Tên thiết bị",""))
            ser=c1.text_input("Số serie",value=row.get("Số serie",""))
            vt=c2.text_input("Vị trí",value=row.get("Vị trí",""))
            ck_o=["06 tháng","12 tháng"]; cur_ck=row.get("Chu kỳ HC","12 tháng")
            ck=c1.selectbox("Chu kỳ HC",ck_o,index=ck_o.index(cur_ck) if cur_ck in ck_o else 0,key=f"ck_tb_{idx}")
            tt_o=["Sử dụng tốt","Chờ hiệu chuẩn","Hỏng"]; cur_tt=row.get("Tình trạng","Sử dụng tốt")
            tt=c2.selectbox("Tình trạng",tt_o,index=tt_o.index(cur_tt) if cur_tt in tt_o else 0,key=f"tt_tb_{idx}")
            last=c1.text_input("HC lần cuối",value=row.get("HC lần cuối",""))
            nxt=c2.text_input("Hạn HC",value=row.get("Hạn HC",""))
            un=unames(); cur_nl=row.get("Người lập","")
            nl=c1.selectbox("Người lập",un,index=un.index(cur_nl) if cur_nl in un else 0,key=f"nl_tb_{idx}")
            gc=c2.text_input("Ghi chú",value=row.get("Ghi chú",""))
            if st.form_submit_button("💾 Lưu",use_container_width=True):
                lst_ref[idx].update({"Mã TB":ma,"Tên thiết bị":ten,"Số serie":ser,"Vị trí":vt,
                    "Chu kỳ HC":ck,"HC lần cuối":last,"Hạn HC":nxt,"Người lập":nl,"Tình trạng":tt,"Ghi chú":gc})
                persist("dev_data"); ghi_log("TB","Cập nhật",f"Sửa {ma}"); st.rerun()
    st.write("")
    if dev_lst:
        sc1,sc2=st.columns([4,1])
        kw=sc1.text_input("🔍 Tìm kiếm",placeholder="Nhập từ khóa...",key="srch_TB",label_visibility="collapsed")
        sc2.caption(f"Tổng: **{len(dev_lst)}** TB")
        display=dev_lst if not kw.strip() else [r for r in dev_lst if any(kw.lower() in str(v).lower() for v in r.values())]
        render_df(display,"Tình trạng",c_tinhtrang)
        st.markdown("---")
        for ri,row in enumerate(dev_lst):
            can=co_quyen(row.get("Người tạo",""))
            rid=row.get("Mã TB",f"#{ri}")
            cid,cinfo,cedit,cdel=st.columns([1.2,5.5,0.9,0.9])
            cid.markdown(f"**{rid}**"); cinfo.caption(f"{row.get('Tên thiết bị','')} · {row.get('Tình trạng','')}")
            if can:
                with cedit.popover("✏️ Sửa"): edit_tb(ri,row,dev_lst,"dev_data")
                with cdel.popover("🗑️ Xóa"):
                    st.warning(f"Xóa **{rid}**?")
                    cy,cn=st.columns(2)
                    if cy.button("✅ Xác nhận",key=f"yes_tb_{ri}",use_container_width=True):
                        dev_lst.pop(ri); persist("dev_data"); ghi_log("TB","Xóa",f"Xóa {rid}"); st.rerun()
                    cn.button("❌",key=f"no_tb_{ri}",use_container_width=True)
            else:
                cedit.caption("🔒"); cdel.caption("—")
    else:
        st.info("Chưa có thiết bị đo nào.")

# ══════════════════════════════════════════════════════════
# BÁO CÁO SPC (giữ nguyên)
# ══════════════════════════════════════════════════════════
elif page == "📊 Báo cáo SPC":
    require_project(); da_banner()
    st.markdown("## 📊 Báo cáo thống kê SPC")
    il=get_da_list("iqc_data"); pl=get_da_list("ipqc_data"); ol=get_da_list("oqc_data")
    nl=get_da_list("ncr_data")
    it,ip,if_=pf(il); pt,pp,pf_=pf(pl); ot,op,of_=pf(ol)
    sc1,sc2,sc3=st.columns(3)
    for col,lbl,tot,pas,fail in [(sc1,"IQC",it,ip,if_),(sc2,"OQC",ot,op,of_),(sc3,"IPQC",pt,pp,pf_)]:
        yr_=int(pas/tot*100) if tot else 0
        clr="059669" if yr_>=80 else "dc2626"
        col.markdown(f"""<div style="background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:18px 22px;box-shadow:0 1px 4px rgba(0,0,0,.04)">
          <div style="font-weight:700;font-size:15px;color:#1e293b;margin-bottom:10px">{lbl}</div>
          <div style="display:flex;gap:24px">
            <div><div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase">Tổng</div><div style="font-size:22px;font-weight:800;color:#1e293b">{tot}</div></div>
            <div><div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase">Đạt</div><div style="font-size:22px;font-weight:800;color:#059669">{pas}</div></div>
            <div><div style="font-size:11px;color:#64748b;font-weight:600;text-transform:uppercase">Không đạt</div><div style="font-size:22px;font-weight:800;color:#dc2626">{fail}</div></div>
          </div>
          <div style="margin-top:10px"><span style="background:#{clr}22;color:#{clr};padding:3px 12px;border-radius:20px;font-size:11px;font-weight:700">Tỷ lệ đạt: {yr_}%</span></div>
        </div>""", unsafe_allow_html=True)
    st.write("")
    with st.expander("📂 Import kết quả đo từ factory (Excel/CSV)"):
        up_spc=st.file_uploader("Chọn file",type=["xlsx","xls","csv"],key="spc_up")
        if up_spc:
            try:
                is_csv=up_spc.name.endswith(".csv")
                up_spc.seek(0)
                df_raw=pd.read_csv(up_spc,header=None,dtype=str) if is_csv else pd.read_excel(up_spc,header=None,dtype=str)
                hr=0; bs=-1
                for i in range(min(5,len(df_raw)-1)):
                    ri=df_raw.iloc[i]; rn=df_raw.iloc[i+1]
                    ne=sum(1 for v in ri if str(v).strip() not in ("","nan","None"))
                    nn=sum(1 for v in rn if pd.to_numeric(str(v).strip(),errors="coerce")==pd.to_numeric(str(v).strip(),errors="coerce"))
                    ti=sum(1 for v in ri if str(v).strip() not in ("","nan","None") and pd.to_numeric(str(v).strip(),errors="coerce")!=pd.to_numeric(str(v).strip(),errors="coerce"))
                    sc=ne+nn*2+ti*3
                    if sc>bs and ne>=2: bs=sc; hr=i
                up_spc.seek(0)
                df_imp=pd.read_csv(up_spc,header=hr,keep_default_na=False) if is_csv else pd.read_excel(up_spc,header=hr,keep_default_na=False)
                df_imp=df_imp.dropna(how="all").reset_index(drop=True)
                st.session_state.spc_df=df_imp
                st.success(f"✅ {len(df_imp)} mẫu × {len(df_imp.columns)} cột")
                st.dataframe(df_imp,use_container_width=True,hide_index=True)
            except Exception as e: st.error(f"Lỗi: {e}")
    st.write("")
    dv=[50.05,49.98,50.12,49.91,50.02,50.08,49.95,50.15,50.01,49.99,50.03,49.97,50.07,49.94,50.11]
    dl=[f"M{i+1}" for i in range(len(dv))]
    if st.session_state.spc_df is not None:
        df_r=st.session_state.spc_df
        nc=df_r.select_dtypes(include="number").columns.tolist()
        id_like=[c for c in nc if str(c).strip().upper() in ("ID","STT","NO","#")]
        mc=[c for c in nc if c not in id_like]
        tc=[c for c in df_r.columns if c not in nc]
        if mc:
            sel=st.selectbox("Chọn mẫu phân tích:",[str(r.get(tc[0],f"Mẫu {i+1}")) for i,r in df_r.iterrows()] if tc else [f"Hàng {i+1}" for i in range(len(df_r))],key="spc_row")
            ri=int(sel.split("Hàng ")[-1])-1 if sel.startswith("Hàng") else next((i for i,r in df_r.iterrows() if str(r.get(tc[0],f"Mẫu {i+1}"))==sel),0)
            vals=np.array([float(df_r.loc[ri,c]) for c in mc if pd.to_numeric(df_r.loc[ri,c],errors="coerce")==pd.to_numeric(df_r.loc[ri,c],errors="coerce")])
            labels=[str(c) for c in mc[:len(vals)]]
        else: vals=np.array(dv); labels=dl; st.caption("*(Dữ liệu mẫu)*")
    else: vals=np.array(dv); labels=dl; st.caption("*(Dữ liệu mẫu — import file để dùng số liệu thực tế)*")

    if len(vals)>1:
        mean_v=float(np.mean(vals)); std_v=float(np.std(vals,ddof=1))
        ucl=mean_v+3*std_v; lcl=mean_v-3*std_v
        t1,t2,t3=st.tabs(["📈 X-bar & Histogram","📊 Pareto","📉 Range & Trend"])
        with t1:
            m1,m2,m3,m4,m5=st.columns(5)
            out=int(np.sum((vals>ucl)|(vals<lcl)))
            for col,l,v in [(m1,"Mean",f"{mean_v:.4f}"),(m2,"UCL",f"{ucl:.4f}"),(m3,"LCL",f"{lcl:.4f}"),(m4,"Std Dev",f"{std_v:.4f}"),(m5,"Ngoài giới hạn",out)]:
                col.metric(l,v)
            bc1,bc2=st.columns(2)
            with bc1:
                st.markdown("**X-bar Control Chart**")
                st.line_chart(pd.DataFrame({"Mẫu":labels,"Giá trị đo":vals,"UCL":[ucl]*len(vals),"CL":[mean_v]*len(vals),"LCL":[lcl]*len(vals)}).set_index("Mẫu"),color=["#7c3aed","#dc2626","#059669","#dc2626"])
            with bc2:
                st.markdown("**Histogram**")
                hist,edges=np.histogram(vals,bins=min(8,max(4,len(vals)//3)))
                st.bar_chart(pd.DataFrame({"K":[ f"{edges[i]:.2f}-{edges[i+1]:.2f}" for i in range(len(hist))],"F":hist}).set_index("K"),color="#7c3aed")
        with t2:
            if nl:
                cnt=Counter(x.get("Tên vật tư/SP","-") for x in nl)
                df_par=pd.DataFrame({"Dạng lỗi":list(cnt.keys()),"Số vụ":list(cnt.values())}).sort_values("Số vụ",ascending=False)
            else:
                df_par=pd.DataFrame({"Dạng lỗi":["Trầy xước","Móp méo","Bọt khí","Sai kích thước","Lệch màu"],"Số vụ":[45,28,12,6,3]})
            df_par["%"]=( df_par["Số vụ"]/df_par["Số vụ"].sum()*100).round(1)
            df_par["% tích lũy"]=df_par["%"].cumsum().round(1)
            st.bar_chart(df_par.set_index("Dạng lỗi")["Số vụ"],color="#dc2626")
            st.dataframe(df_par.style.bar(subset=["Số vụ"],color="#fdd5b1").format({"%":"{:.1f}%","% tích lũy":"{:.1f}%"}),use_container_width=True,hide_index=True)
        with t3:
            r=np.abs(np.diff(vals,prepend=vals[0])); r_mean=r.mean(); r_ucl=r_mean*3.267
            wn=min(5,max(2,len(vals)//4)); ma=pd.Series(vals).rolling(wn,min_periods=1).mean().values
            bc1,bc2=st.columns(2)
            with bc1:
                st.markdown("**Range Chart**")
                st.line_chart(pd.DataFrame({"M":labels,"Range":r,"UCL_R":[r_ucl]*len(r),"CL_R":[r_mean]*len(r)}).set_index("M"),color=["#f59f00","#dc2626","#059669"])
            with bc2:
                st.markdown(f"**Moving Average (MA{wn})**")
                st.line_chart(pd.DataFrame({"M":labels,"Giá trị":vals,f"MA({wn})":ma}).set_index("M"),color=["#94a3b8","#7c3aed"])
            cp=(ucl-lcl)/(6*std_v) if std_v>0 else 0
            if cp>=1.33: st.success(f"✅ Cp = {cp:.3f} — Quy trình có năng lực tốt.")
            elif cp>=1.0: st.warning(f"⚠️ Cp = {cp:.3f} — Cần theo dõi chặt.")
            else: st.error(f"❌ Cp = {cp:.3f} < 1.0 — Cần cải thiện ngay.")

# ══════════════════════════════════════════════════════════
# NHẬT KÝ
# ══════════════════════════════════════════════════════════
elif page == "📜 Nhật ký":
    st.markdown("## 📜 Nhật ký hoạt động")
    r=cu().get("Vai trò","")
    if r in ["Quản lý","Trưởng QC"]:
        with st.expander("💾 Sao lưu & Khôi phục"):
            c1,c2=st.columns(2)
            with c1:
                st.markdown("**📦 Backup**")
                bk=backup_all(st.session_state)
                st.download_button("📥 Tải backup",data=bk,
                    file_name=f"ProBackup_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                    mime="application/json",key="btn_bk")
            with c2:
                st.markdown("**🔄 Restore**")
                up_r=st.file_uploader("Chọn file backup",type=["json"],key="up_res")
                if up_r:
                    ok,msg=restore_all(up_r.read(),st.session_state)
                    if ok: st.success(msg); st.rerun()
                    else: st.error(msg)
    else: st.info("🔒 Chức năng này chỉ dành cho Quản lý và Trưởng QC.")
    st.write("")
    df_l=pd.DataFrame(st.session_state.log_list)
    if not df_l.empty:
        st.dataframe(df_l.style.set_properties(**{"font-size":"13px","padding":"8px 12px"})
            .set_table_styles([{"selector":"thead th","props":[("background","#f8fafc"),("font-weight","700"),("font-size","11px"),("color","#64748b"),("text-transform","uppercase"),("padding","10px 12px")]}]),
            use_container_width=True,hide_index=True)
    else: st.info("Nhật ký trống.")

# ══════════════════════════════════════════════════════════
# QUẢN LÝ NGƯỜI DÙNG
# ══════════════════════════════════════════════════════════
elif page == "👤 Người dùng":
    st.markdown("## 👤 Quản lý người dùng")
    role=cu().get("Vai trò","")

    with st.expander("📖 Ma trận phân quyền hệ thống"):
        df_pq = pd.DataFrame({
            "Quyền hạn": ["Tạo TK Quản lý/Trưởng QC","Tạo TK Kiểm tra viên",
                          "Xóa tài khoản bất kỳ","Xóa TK Kiểm tra viên",
                          "Reset pass mọi TK","Tự đổi pass của mình",
                          "Tạo phiếu mới","Sửa/Xóa phiếu của mình",
                          "Sửa/Xóa phiếu của người khác","Xem toàn bộ dữ liệu"],
            "Quản lý (Admin)": ["✅","✅","✅","✅","✅","✅","✅","✅","✅","✅"],
            "Trưởng QC":       ["❌","✅","❌","✅","❌","✅","✅","✅","✅","✅"],
            "Kiểm tra viên":   ["❌","❌","❌","❌","❌","✅","✅","✅","❌","✅ (đọc)"],
        })
        st.dataframe(df_pq, use_container_width=True, hide_index=True)

    st.write("")
    if role in ["Quản lý","Trưởng QC"]:
        with st.expander("➕ Tạo tài khoản mới"):
            with st.form("frm_usr_new",clear_on_submit=True):
                c1,c2=st.columns(2)
                nm=c1.text_input("Họ tên *"); un_=c2.text_input("Tài khoản *")
                pw=c1.text_input("Mật khẩu *",type="password")
                ro_o=["Quản lý","Trưởng QC","Kiểm tra viên"] if role=="Quản lý" else ["Kiểm tra viên"]
                ro=c2.selectbox("Phân quyền",ro_o)
                if st.form_submit_button("💾 Tạo",use_container_width=True):
                    if nm and un_ and pw:
                        if any(u["Tài khoản"]==un_ for u in st.session_state.users_list):
                            st.error("Tài khoản đã tồn tại!")
                        else:
                            st.session_state.users_list.append({"Tài khoản":un_,"Họ tên":nm,"Mật khẩu":pw,"Phân quyền":ro,"Trạng thái":"Hoạt động"})
                            persist("users_list"); ghi_log("Users","Tạo TK",f"Tạo {un_}"); st.success(f"✅ Đã tạo {nm}"); st.rerun()
                    else: st.error("Điền đủ thông tin")

    def c_role(v):
        m={"Quản lý":"background:#fef3c7;color:#92400e;font-weight:700",
           "Trưởng QC":"background:#dcfce7;color:#166534;font-weight:700",
           "Kiểm tra viên":"background:#e0e7ff;color:#3730a3;font-weight:700"}
        return m.get(v,"")
    ud=[{"Họ tên":u["Họ tên"],"Tài khoản":u["Tài khoản"],
         "Mật khẩu":u["Mật khẩu"] if (role=="Quản lý" or u["Tài khoản"]==cu().get("Tài khoản","")) else "••••••",
         "Phân quyền":u["Phân quyền"],"Trạng thái":u.get("Trạng thái","Hoạt động")} for u in st.session_state.users_list]
    st.dataframe(pd.DataFrame(ud).style.map(c_role,subset=["Phân quyền"])
        .set_properties(**{"font-size":"13px","padding":"8px 12px"})
        .set_table_styles([{"selector":"thead th","props":[("background","#f8fafc"),("font-weight","700"),("font-size","11px"),("color","#64748b"),("text-transform","uppercase"),("padding","10px 12px")]}]),
        use_container_width=True,hide_index=True)

    st.write(""); st.markdown("##### ✏️ Thao tác tài khoản")
    for i,u in enumerate(st.session_state.users_list):
        is_self=u["Tài khoản"]==cu().get("Tài khoản","")
        is_adm=u["Tài khoản"]=="admin"
        can_edit=(role=="Quản lý") or is_self
        can_del=(role=="Quản lý" and not is_adm) or (role=="Trưởng QC" and u["Phân quyền"]=="Kiểm tra viên")
        badge="🔓" if (can_edit or can_del) else "🔒"
        with st.expander(f"{badge}  **{u['Họ tên']}** ({u['Tài khoản']}) — {u['Phân quyền']}"):
            if not can_edit and not can_del: st.caption("🔒 Không có quyền"); continue
            ca,cb,cc,_=st.columns([2,2,2,2])
            if can_edit:
                with ca.popover("✏️ Sửa"):
                    with st.form(f"frm_eu_{i}"):
                        nm2=st.text_input("Họ tên",value=u["Họ tên"]); un2=st.text_input("Tài khoản",value=u["Tài khoản"])
                        if role=="Quản lý":
                            ro_o2=["Quản lý","Trưởng QC","Kiểm tra viên"]
                            ro2=st.selectbox("Phân quyền",ro_o2,index=ro_o2.index(u["Phân quyền"]) if u["Phân quyền"] in ro_o2 else 0,key=f"ro_eu_{i}")
                        else: ro2=u["Phân quyền"]; st.caption(f"Phân quyền: {ro2}")
                        tt_o2=["Hoạt động","Tạm khóa"]; cur_tt2=u.get("Trạng thái","Hoạt động")
                        tt2=st.selectbox("Trạng thái",tt_o2,index=tt_o2.index(cur_tt2) if cur_tt2 in tt_o2 else 0,key=f"tt_eu_{i}")
                        if st.form_submit_button("💾 Lưu",use_container_width=True):
                            if un2!=u["Tài khoản"] and any(x["Tài khoản"]==un2 for j,x in enumerate(st.session_state.users_list) if j!=i):
                                st.error("Tài khoản đã tồn tại!")
                            else:
                                st.session_state.users_list[i].update({"Họ tên":nm2,"Tài khoản":un2,"Phân quyền":ro2,"Trạng thái":tt2})
                                if is_self: st.session_state.current_user.update({"Tài khoản":un2,"Họ tên":nm2,"Vai trò":ro2})
                                persist("users_list"); ghi_log("Users","Sửa TK",f"Sửa {u['Tài khoản']}"); st.rerun()
                with cb.popover("🔑 Đổi pass"):
                    with st.form(f"frm_pw2_{i}"):
                        p1=st.text_input("Mật khẩu mới",type="password"); p2=st.text_input("Xác nhận",type="password")
                        if st.form_submit_button("✅ Xác nhận",use_container_width=True):
                            if not p1: st.error("Trống!")
                            elif p1!=p2: st.error("Không khớp!")
                            else:
                                st.session_state.users_list[i]["Mật khẩu"]=p1
                                persist("users_list"); ghi_log("Users","Đổi pass",f"Đổi pass {u['Tài khoản']}"); st.success("✅ Đã đổi!"); st.rerun()
            if can_del:
                with cc.popover("🗑️ Xóa"):
                    st.warning(f"Xóa **{u['Họ tên']}**?")
                    if st.button("✅ Xác nhận",key=f"del_u_{i}"):
                        st.session_state.users_list.pop(i); persist("users_list"); ghi_log("Users","Xóa TK",f"Xóa {u['Tài khoản']}"); st.rerun()