"""HTTP API and small browser UI for the first usable application slice."""

from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import shutil
from typing import Any
from uuid import uuid4

from alarm_inspection.domain.points import normalize_point
from alarm_inspection.storage import (
  AppSetting,
    Inspection,
    PointList,
    PointListDecision,
    PointListEventDate,
    SourceFile,
    User,
    UserSession,
    open_store,
)
from alarm_inspection.intake.event_history import parse_xlsx as parse_event_history_xlsx
from alarm_inspection.intake.points_list import parse_xlsx

try:
    from fastapi import Body, FastAPI, File, Form, Query, Request, UploadFile
    from fastapi.responses import HTMLResponse, JSONResponse, Response
except ImportError:  # Allows domain tests to run without web dependencies.
    FastAPI = None


_UPLOAD_ROOT = Path("/tmp/alarm-inspection-uploads")
_SESSION_COOKIE = "inspection_session"
_DEFAULT_PASSWORD_FALLBACK = "password"
_DEFAULT_PASSWORD_SETTING_KEY = "auth.default_password"
_PASSWORD_ITERATIONS = 240_000


def _hash_password(password: str, salt: str) -> str:
  digest = hashlib.pbkdf2_hmac(
    "sha256",
    password.encode("utf-8"),
    salt.encode("utf-8"),
    _PASSWORD_ITERATIONS,
  )
  return digest.hex()


def _password_record(password: str) -> str:
  salt = secrets.token_hex(16)
  return f"{salt}${_hash_password(password, salt)}"


def _verify_password(password: str, record: str) -> bool:
  if "$" not in record:
    return False
  salt, expected_hash = record.split("$", 1)
  actual_hash = _hash_password(password, salt)
  return hmac.compare_digest(actual_hash, expected_hash)


def _as_bool(value: object, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return value != 0
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off", ""}:
        return False
    return default


def _format_event_date(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%d %H:%M:%S")


def _parse_saved_timestamp(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    for candidate in (text, text.replace(" ", "T", 1)):
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue
    return None


def _parse_date_value(value: object) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _event_history_kind(point_list_id: str | None) -> str:
    if not point_list_id:
        return "event_history"
    # Keep kind within the existing varchar(40) limit in production DB.
    return f"event_history:{point_list_id[:12]}"


def _ensure_inspection_upload_dir(inspection_id: str) -> Path:
    upload_dir = _UPLOAD_ROOT / inspection_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


_HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Alarm Inspection Processor</title>
<style>
:root {
  --bg: radial-gradient(circle at top left, #f8fbff 0%, #eef4fb 45%, #e7eef8 100%);
  --panel: #ffffff;
  --panel-alt: #f8fbff;
  --border: #dfe7f1;
  --text: #17202a;
  --muted: #5b6470;
  --primary: #1769aa;
  --primary-strong: #0f4d7a;
  --ring: rgba(23, 105, 170, 0.2);
  --secondary: #5b6470;
  --success-bg: #e8f5e9;
  --review-bg: #ffebee;
  --danger: #b3261e;
  --shadow: 0 18px 36px rgba(23, 41, 58, 0.1);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  padding: 36px 22px 54px;
  font-family: "IBM Plex Sans", "Avenir Next", "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
}
#app-shell {
  max-width: 1220px;
  margin: 0 auto;
}
h1 {
  margin: 0 0 10px;
  font-size: clamp(2rem, 4vw, 2.65rem);
  letter-spacing: -0.02em;
}
body > p {
  margin: 0 0 16px;
  color: var(--muted);
  font-size: 1.02rem;
}
#user-bar {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}
#avatar-wrap {
  position: relative;
}
#avatar-button {
  width: 42px;
  height: 42px;
  margin: 0;
  padding: 0;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  text-transform: uppercase;
}
#avatar-menu {
  position: absolute;
  right: 0;
  top: 48px;
  min-width: 130px;
  padding: 6px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  box-shadow: var(--shadow);
  z-index: 20;
}
#avatar-menu-option-logout {
  width: 100%;
  margin: 0;
  padding: 9px 10px;
  border-radius: 8px;
  cursor: pointer;
  color: var(--text);
}
#avatar-menu-option-logout:hover {
  background: #edf6ff;
}
.auth-card {
  max-width: 520px;
  margin: 24px auto 0;
}
.admin-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 12px;
}
.checkbox-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 10px;
}
.checkbox-row input[type=checkbox] {
  width: auto;
}
.inline-note {
  color: var(--muted);
  font-size: 0.9rem;
  margin-top: 8px;
}
.admin-list-header {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 12px;
}
.admin-list-header h3 {
  margin: 0;
}
.add-user-row {
  display: flex;
  align-items: flex-end;
  gap: 8px;
}
.add-user-row button {
  width: auto;
  margin: 0;
}
.settings-row {
  margin-top: 12px;
}
.settings-row button {
  width: auto;
}
.user-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.user-actions button {
  width: auto;
  margin: 0;
}
h2, h3 {
  margin: 0 0 14px;
  color: var(--text);
  letter-spacing: -0.01em;
}
label {
  display: block;
  margin: 16px 0 7px;
  font-weight: 600;
  color: var(--text);
}
input, button, select {
  font: inherit;
  border-radius: 10px;
  box-sizing: border-box;
}
input, select {
  width: 100%;
  padding: 11px 13px;
  border: 1px solid var(--border);
  background: #fff;
  color: var(--text);
}
input:focus,
select:focus {
  outline: 2px solid var(--ring);
  outline-offset: 1px;
  border-color: var(--primary);
}
button {
  width: 100%;
  padding: 11px 15px;
  margin-top: 12px;
  background: var(--primary);
  color: #fff;
  border: 1px solid var(--primary);
  border-radius: 10px;
  cursor: pointer;
  font-weight: 600;
  letter-spacing: 0.01em;
  box-shadow: 0 4px 10px rgba(23, 105, 170, 0.2);
  transition: background 120ms ease, transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
}
button:hover {
  background: var(--primary-strong);
  border-color: var(--primary-strong);
  box-shadow: 0 6px 14px rgba(15, 77, 122, 0.24);
}
button:active {
  transform: translateY(1px);
}
.secondary {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}
.secondary:hover {
  background: var(--primary-strong);
  border-color: var(--primary-strong);
}
.ghost {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}
.ghost:hover {
  background: var(--primary-strong);
  border-color: var(--primary-strong);
}
.danger {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}
.danger:hover {
  background: var(--primary-strong);
  border-color: var(--primary-strong);
}
.card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: 24px 22px;
  margin-top: 20px;
  box-shadow: var(--shadow);
}
.hidden { display: none !important; }
.row,
.nav,
.inline-form,
.create-actions,
.delete-actions,
.toolbar,
.toolbar-group,
.upload-row,
.action-row {
  display: flex;
  gap: 14px;
  align-items: center;
  flex-wrap: wrap;
}
.row {
  align-items: stretch;
}
.row > * {
  flex: 1 1 0;
}
.row button,
.nav button,
.inline-form button,
.create-actions button,
.delete-actions button,
.toolbar button,
.toolbar-group button,
.action-row button {
  width: auto;
  margin-top: 0;
  flex: 0 0 auto;
}
.nav {
  justify-content: space-between;
  margin-bottom: 18px;
}
.toolbar {
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 12px 14px;
  background: var(--panel-alt);
  border: 1px solid var(--border);
  border-radius: 14px;
}
.toolbar-group {
  justify-content: flex-start;
}
.action-row {
  justify-content: flex-end;
}
.inline-form {
  width: 100%;
  flex: 1 1 auto;
  padding: 18px;
  background: var(--panel-alt);
  border: 1px solid var(--border);
  border-radius: 14px;
}
.inline-form label {
  display: none;
}
.inline-form input[type=file] {
  min-width: 240px;
  flex: 1 1 auto;
  border-style: dashed;
  background: #fff;
}
.visually-hidden-text {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
.visually-hidden-file {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
.file-trigger {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 40px;
  padding: 9px 13px;
  margin: 0;
  border-radius: 10px;
  background: var(--primary);
  border: 1px solid var(--primary);
  color: #fff;
  font-weight: 600;
  letter-spacing: 0.01em;
  box-shadow: 0 4px 10px rgba(23, 105, 170, 0.2);
  cursor: pointer;
  transition: background 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
}
.file-trigger:hover {
  background: var(--primary-strong);
  border-color: var(--primary-strong);
  box-shadow: 0 6px 14px rgba(15, 77, 122, 0.24);
}
.file-name {
  min-width: 280px;
  max-width: 440px;
  padding: 8px 10px;
  border: 1px dashed var(--border);
  border-radius: 10px;
  background: #fff;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.upload-row {
  width: 100%;
  display: flex;
  gap: 14px;
  align-items: center;
  justify-content: flex-start;
}
.upload-row > * {
  flex: 0 0 auto;
}
.upload-row .file-control {
  display: flex;
  align-items: center;
  gap: 12px;
  justify-content: space-between;
  flex: 1 1 auto;
  width: 100%;
}
.upload-row .file-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1 1 auto;
  min-width: 0;
}
.upload-row .upload-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  margin-left: auto;
}
#event-history-form {
  width: 100%;
}
#event-history-form .upload-row {
  padding: 0;
}
.inspection-details {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 12px;
  padding: 12px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--panel-alt);
}
.details-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  .admin-list-header,
  .add-user-row {
    align-items: stretch;
    flex-direction: column;
  }
}
.compact-field label {
  margin: 0 0 4px;
  font-size: 0.82rem;
  font-weight: 600;
  color: var(--muted);
}
.compact-field input,
.compact-field select {
  margin: 0;
  padding: 8px 10px;
}
#inspection-store-number {
  background: #f2f7fd;
}
.inspection-actions-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  align-items: end;
  margin-bottom: 10px;
}
.inspection-actions-row .inline-form {
  padding: 10px 12px;
}
.points-list-picker label {
  margin-top: 0;
}
.accepted-header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 8px;
}
.accepted-header-row h3 {
  margin: 0;
}
.accepted-header-row button {
  width: auto;
  margin: 0;
}
.create-actions,
.delete-actions {
  justify-content: flex-end;
  margin-top: 16px;
}
#point-lists {
  display: flex;
  flex-direction: column;
  gap: 14px;
  margin-top: 12px;
}
.point-list {
  display: grid;
  grid-template-columns: minmax(150px, 180px) minmax(220px, 1fr) auto;
  gap: 14px;
  align-items: center;
  padding: 14px;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--panel-alt);
}
.point-list select,
.point-list input {
  margin: 0;
  min-width: 0;
}
.point-list .remove-point-list {
  width: auto;
  margin: 0;
  justify-self: end;
}
.table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 18px;
  min-width: 520px;
}
.table th,
.table td {
  border: 1px solid var(--border);
  padding: 11px 13px;
  text-align: left;
  vertical-align: top;
}
.table th {
  background: #edf2f7;
  font-weight: 700;
}
.table tbody tr:nth-child(even) {
  background: #fafcff;
}
#message,
#inspection-message,
#home-message {
  margin-top: 16px;
  color: var(--muted);
  white-space: pre-wrap;
}
.modal {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(17, 24, 39, 0.7);
  align-items: center;
  justify-content: center;
  padding: 20px;
  z-index: 10;
}
.modal.open {
  display: flex;
}
.modal-card {
  width: min(1040px, 92vw);
  max-height: 85vh;
  overflow: auto;
  background: #fff;
  border-radius: 18px;
  padding: 24px 22px;
  box-shadow: var(--shadow);
}
.close {
  float: right;
  width: auto;
  margin: 0;
  background: var(--secondary);
}
.accepted-row { background: var(--success-bg); }
.review-row { background: var(--review-bg); }
.accepted { color: #176b3a; font-weight: 600; }
.review { color: #a33b00; font-weight: 600; }
.status-toggle {
  width: auto;
  margin: 0;
  padding: 6px 12px;
  background: #fff;
  border: 1px solid currentColor;
  color: inherit;
}
.location-input {
  width: 100%;
  min-width: 120px;
  padding: 9px 11px;
  border: 1px solid var(--border);
  border-radius: 10px;
  box-sizing: border-box;
}
#inspection-point-list-selector {
  margin-bottom: 0;
}
#inspection-screen .nav:first-of-type {
  justify-content: flex-start;
}
#inspection-meta {
  margin: 0 0 14px;
  color: var(--muted);
}
@media (max-width: 700px) {
  body { padding: 22px 12px 42px; }
  .card, .modal-card { padding: 18px 15px; }
  .row,
  .nav,
  .inline-form,
  .create-actions,
  .delete-actions {
    display: grid;
    grid-template-columns: 1fr;
  }
  .point-list {
    grid-template-columns: 1fr;
  }
  .point-list .remove-point-list {
    justify-self: stretch;
  }
  .table {
    min-width: 440px;
  }
  .details-row,
  .inspection-actions-row {
    grid-template-columns: 1fr;
  }
  .admin-grid {
    grid-template-columns: 1fr;
  }
  .accepted-header-row {
    flex-direction: column;
    align-items: stretch;
  }
  .upload-row {
    align-items: stretch;
  }
  .upload-row .file-control,
  .upload-row .file-left,
  .upload-row .upload-actions {
    width: 100%;
  }
  .upload-row .file-control {
    flex-direction: column;
    align-items: stretch;
  }
  .upload-row .file-left {
    flex-wrap: wrap;
  }
  .file-name {
    min-width: 0;
    max-width: none;
    width: 100%;
  }
}
</style></head>
<body><h1>Home Page</h1><p>Choose an existing inspection or create a new one.</p>

<div id="user-bar" class="hidden"><span id="active-user-label"></span><div id="avatar-wrap"><button type="button" id="avatar-button" class="secondary" title="Account menu">JP</button><div id="avatar-menu" class="hidden"><div id="avatar-menu-option-logout" role="menuitem" tabindex="0">Logout</div></div></div></div>

<div id="login-screen" class="card auth-card">
<h2>Login</h2>
<form id="login-form">
<label for="login-email">Email</label><input id="login-email" type="email" autocomplete="username" required>
<label for="login-password">Password</label><input id="login-password" type="password" autocomplete="current-password" required>
<button type="submit">Sign In</button>
</form>
<form id="password-reset-form" class="hidden">
<label for="reset-current-password">Current password</label><input id="reset-current-password" type="password" autocomplete="current-password" required>
<label for="reset-new-password">New password</label><input id="reset-new-password" type="password" autocomplete="new-password" required>
<button type="submit">Reset Password</button>
</form>
<div id="login-message"></div>
</div>

<div id="home-screen" class="card hidden">
<h2>Start</h2>
<label for="inspection-picker">Existing inspections</label>
<div class="row"><select id="inspection-picker"></select><button type="button" id="open-inspection" class="ghost">Open Inspection</button></div>
<button type="button" id="refresh-inspections" class="secondary">Refresh List</button>
<button type="button" id="start-create">Create New Inspection</button>
<button type="button" id="open-admin" class="secondary hidden">Administration</button>
<button type="button" id="delete-inspection" class="danger">Delete Inspection</button>
<div id="home-message"></div>
</div>

<div id="admin-screen" class="card hidden">
<div class="nav"><button type="button" id="back-home-from-admin" class="secondary">Back to Home</button></div>
<h2>Administration</h2>
<div class="admin-grid">
<div class="admin-list-header"><h3>User List</h3><form id="admin-create-user-form" class="add-user-row"><label for="admin-new-user-email">Add User</label><input id="admin-new-user-email" type="email" placeholder="user@example.com" required><button type="submit">Add User</button></form></div>
<table class="table"><thead><tr><th>Email</th><th>Admin</th><th>Force Reset</th><th>Actions</th></tr></thead><tbody id="admin-users-body"></tbody></table>
<div class="settings-row"><label for="admin-default-password">Default Password</label><input id="admin-default-password" type="text" required><button type="button" id="save-admin-settings">Save Default Password</button><div class="inline-note">This default password is global and is used for new users and reset actions.</div></div>
</div>
<div id="admin-message"></div>
</div>

<div id="create-screen" class="card hidden">
<div class="nav"><button type="button" id="back-home-from-create" class="secondary">Back to Home</button></div>
<h2>Create New Inspection</h2>
<form id="inspection-form">
<label for="store_number">Store number</label><input id="store_number" required>
<label for="address">Address</label><input id="address" required>
<label>Points Lists by security panel</label><div id="point-lists"><div class="point-list"><select name="point_list_category" required><option>Combo</option><option>Fire</option><option>Burglar</option><option>Gas Station</option></select><input name="points_files" type="file" accept=".xls,.xlsx,.pdf" required><button type="button" class="remove-point-list danger">Delete List</button></div></div><div class="create-actions"><button type="button" id="add-list">Add another Points List</button><button type="button" id="preview-list">Preview Points Lists</button></div><div id="preview"></div>
<input type="hidden" name="point_decisions" id="point-decisions" value="[]"></form><div id="message"></div></div>

<div id="inspection-screen" class="card hidden">
<div class="toolbar">
  <div class="toolbar-group">
    <button type="button" id="back-home-from-inspection" class="secondary">Back to Home</button>
    <button type="button" id="clear-event-dates" class="secondary">Clear Dates</button>
  </div>
  <div class="toolbar-group">
    <button type="button" id="refresh-inspection" class="ghost">Refresh</button>
    <button type="button" id="toggle-missing-points" class="ghost">Show Missing Points Only</button>
  </div>
</div>

<div class="inspection-details">
  <div class="details-row">
    <div class="compact-field">
      <label for="inspection-store-number">Store Number</label>
      <input id="inspection-store-number" type="text" readonly>
    </div>
    <div class="compact-field">
      <label for="inspection-store-type">Store Type</label>
      <select id="inspection-store-type">
         <option>Walmart - Supercenter</option>
        <option>Walmart - Neighborhood Market</option>
        <option>Sam's Club</option>
      </select>
    </div>
    <div class="compact-field">
      <label for="inspection-address">Address</label>
      <input id="inspection-address" type="text" placeholder="Enter address">
    </div>
  </div>
  <div class="details-row">
    <div class="compact-field">
      <label for="inspection-inspector">Inspector</label>
      <input id="inspection-inspector" type="text" placeholder="Enter inspector name">
    </div>
    <div class="compact-field">
      <label for="inspection-start-date">Start Date</label>
      <input id="inspection-start-date" type="date">
    </div>
    <div class="compact-field">
      <label for="inspection-end-date">End Date</label>
      <input id="inspection-end-date" type="date">
    </div>
  </div>
</div>

<div class="inspection-actions-row">
  <div class="compact-field points-list-picker">
    <label for="inspection-point-list-selector">Points List</label>
    <select id="inspection-point-list-selector"></select>
  </div>

  <form id="event-history-form" class="inline-form">
    <div class="upload-row">
      <label for="event-file" class="visually-hidden-text">Event History file</label>
      <div class="file-control">
        <div class="file-left">
          <input id="event-file" class="visually-hidden-file" type="file" accept=".xls,.xlsx,.pdf" required>
          <button type="button" id="choose-event-file" class="file-trigger">Upload Events</button>
          <span id="event-file-name" class="file-name">No file selected</span>
        </div>
      </div>
    </div>
  </form>
</div>

<div class="accepted-header-row"><h3>Accepted Points</h3><div class="user-actions"><button type="button" id="edit-table" class="ghost">Edit</button><button type="button" id="save-table" class="ghost">Save</button><button type="button" id="save-event-dates" class="ghost">Accept Results</button></div></div>
<table class="table"><thead><tr><th>Device Type</th><th>Address</th><th>Location</th><th>Test Result</th></tr></thead><tbody id="accepted-points-body"></tbody></table>
<div id="inspection-message"></div>
</div>

<div id="delete-inspection-modal" class="modal"><div class="modal-card"><button class="close" id="close-delete-inspection">Close</button><h2>Delete Inspection</h2><label for="delete-inspection-selector">Select inspection</label><select id="delete-inspection-selector"></select><div class="delete-actions"><button type="button" id="confirm-delete-inspection" class="danger">Delete</button><button type="button" id="cancel-delete-inspection" class="secondary">Cancel</button></div></div></div>

<div id="review-confirm-modal" class="modal"><div class="modal-card"><button class="close" id="close-review-confirm">Close</button><h2>Confirm Review</h2><p id="review-confirm-summary">This will commit all reviewed decisions and create the inspection.</p><div class="delete-actions"><button type="button" id="confirm-finish-review" class="primary">Confirm and Create Inspection</button><button type="button" id="cancel-finish-review" class="secondary">Cancel</button></div></div></div>

<div id="preview-modal" class="modal"><div class="modal-card"><button class="close" id="close-preview">Close</button><h2>Points List Review</h2><label for="preview-list-selector">Points List</label><select id="preview-list-selector"></select><p id="preview-summary"></p><p>Edit descriptions and use each row's status button to toggle Accept or Review. Rows remain visible until you delete them.</p><div class="nav"><button type="button" class="delete-review-action">Delete all Review rows</button><button type="button" class="save-review-action">Save review decisions</button><button type="button" class="finish-review-action">Finish Review</button></div><table class="table"><thead><tr><th>Point</th><th>Description</th><th>Status</th></tr></thead><tbody id="preview-body"></tbody></table><div class="nav"><button type="button" class="delete-review-action">Delete all Review rows</button><button type="button" class="save-review-action">Save review decisions</button><button type="button" class="finish-review-action">Finish Review</button></div></div></div>
<script src="/review.js"></script>
</body></html>"""


def create_app():
    if FastAPI is None:
        raise RuntimeError("Install the 'web' optional dependencies to run the API")
    app = FastAPI(title="Alarm Inspection Processor", version="0.1.0")
    store = open_store()

    def serialize_user(user: User) -> dict[str, Any]:
      return {
        "id": user.id,
        "email": user.email,
        "is_admin": bool(user.is_admin),
        "force_password_reset": bool(user.force_password_reset),
      }

    def get_default_password(session) -> str:
      setting = session.get(AppSetting, _DEFAULT_PASSWORD_SETTING_KEY)
      if setting is None or not setting.value:
        return _DEFAULT_PASSWORD_FALLBACK
      return setting.value

    def set_default_password(session, value: str) -> str:
      clean_value = value.strip() or _DEFAULT_PASSWORD_FALLBACK
      setting = session.get(AppSetting, _DEFAULT_PASSWORD_SETTING_KEY)
      now = datetime.now(timezone.utc)
      if setting is None:
        setting = AppSetting(
          key=_DEFAULT_PASSWORD_SETTING_KEY,
          value=clean_value,
          updated_at=now,
        )
        session.add(setting)
      else:
        setting.value = clean_value
        setting.updated_at = now
      return clean_value

    def seed_initial_admin() -> None:
      admin_email = "john.porter@securitybuildingcontrols.com"
      with store.begin() as session:
        default_password = get_default_password(session)
        set_default_password(session, default_password)
        existing = session.query(User).filter(User.email == admin_email).first()
        if existing is not None:
          return
        session.add(User(
          id=str(uuid4()),
          email=admin_email,
          password_hash=_password_record(default_password),
          is_admin=True,
          force_password_reset=True,
          is_active=True,
          created_at=datetime.now(timezone.utc),
        ))

    def get_user_from_request(request: Request) -> User | None:
      token = request.cookies.get(_SESSION_COOKIE)
      if not token:
        return None
      now = datetime.now(timezone.utc)
      with store() as session:
        session_row = (
          session.query(UserSession)
          .filter(UserSession.session_token == token, UserSession.expires_at >= now)
          .first()
        )
        if session_row is None:
          return None
        user = session.get(User, session_row.user_id)
        if user is None or not user.is_active:
          return None
        return user

    def require_admin(request: Request) -> User:
      user = getattr(request.state, "current_user", None)
      if user is None or not bool(user.is_admin):
        raise PermissionError("Admin privileges are required.")
      return user

    seed_initial_admin()

    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
      path = request.url.path
      if not path.startswith("/api/"):
        return await call_next(request)
      if path in {
        "/api/auth/login",
        "/api/auth/logout",
        "/api/auth/me",
        "/api/auth/reset-password",
      }:
        return await call_next(request)

      user = get_user_from_request(request)
      if user is None:
        return JSONResponse(status_code=401, content={"error": "Authentication required."})
      if user.force_password_reset:
        return JSONResponse(status_code=403, content={"error": "Password reset is required before continuing."})
      request.state.current_user = user
      return await call_next(request)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/auth/login")
    def login(payload: dict = Body(default={})) -> Response:
      email = str(payload.get("email") or "").strip().lower()
      password = str(payload.get("password") or "")
      if not email or not password:
        return JSONResponse(status_code=400, content={"error": "Email and password are required."})

      with store.begin() as session:
        user = session.query(User).filter(User.email == email).first()
        if user is None or not user.is_active or not _verify_password(password, user.password_hash):
          return JSONResponse(status_code=401, content={"error": "Invalid credentials."})

        token = secrets.token_urlsafe(36)
        now = datetime.now(timezone.utc)
        session.add(UserSession(
          id=str(uuid4()),
          user_id=user.id,
          session_token=token,
          created_at=now,
          expires_at=now.replace(hour=23, minute=59, second=59, microsecond=0),
        ))
        response = JSONResponse(content={"user": serialize_user(user)})
        response.set_cookie(
          key=_SESSION_COOKIE,
          value=token,
          httponly=True,
          samesite="lax",
          secure=False,
          max_age=60 * 60 * 24,
        )
        return response

    @app.get("/api/auth/me")
    def auth_me(request: Request) -> dict[str, Any]:
      user = get_user_from_request(request)
      if user is None:
        return {"authenticated": False}
      return {"authenticated": True, "user": serialize_user(user)}

    @app.post("/api/auth/logout")
    def logout(request: Request) -> Response:
      token = request.cookies.get(_SESSION_COOKIE)
      if token:
        with store.begin() as session:
          session.query(UserSession).filter(UserSession.session_token == token).delete(synchronize_session=False)
      response = JSONResponse(content={"status": "logged_out"})
      response.delete_cookie(_SESSION_COOKIE)
      return response

    @app.post("/api/auth/reset-password")
    def reset_password(request: Request, payload: dict = Body(default={})) -> Response:
      user = get_user_from_request(request)
      if user is None:
        return JSONResponse(status_code=401, content={"error": "Authentication required."})

      current_password = str(payload.get("current_password") or "")
      new_password = str(payload.get("new_password") or "")
      if not current_password or not new_password:
        return JSONResponse(status_code=400, content={"error": "Current and new passwords are required."})
      if len(new_password) < 8:
        return JSONResponse(status_code=400, content={"error": "New password must be at least 8 characters."})

      with store.begin() as session:
        db_user = session.get(User, user.id)
        if db_user is None or not _verify_password(current_password, db_user.password_hash):
          return JSONResponse(status_code=400, content={"error": "Current password is incorrect."})
        db_user.password_hash = _password_record(new_password)
        db_user.force_password_reset = False
        return JSONResponse(content={"status": "password_reset", "user": serialize_user(db_user)})

    @app.get("/api/admin/users")
    def admin_list_users(request: Request) -> Response:
      try:
        require_admin(request)
      except PermissionError as exc:
        return JSONResponse(status_code=403, content={"error": str(exc)})
      with store() as session:
        users = session.query(User).order_by(User.email.asc()).all()
        return JSONResponse(content={
          "users": [
            {
              "id": user.id,
              "email": user.email,
              "is_admin": bool(user.is_admin),
              "force_password_reset": bool(user.force_password_reset),
              "is_active": bool(user.is_active),
            }
            for user in users
          ]
        })

    @app.get("/api/admin/settings")
    def admin_get_settings(request: Request) -> Response:
      try:
        require_admin(request)
      except PermissionError as exc:
        return JSONResponse(status_code=403, content={"error": str(exc)})
      with store.begin() as session:
        default_password = get_default_password(session)
        set_default_password(session, default_password)
        return JSONResponse(content={"default_password": default_password})

    @app.patch("/api/admin/settings")
    def admin_update_settings(request: Request, payload: dict = Body(default={})) -> Response:
      try:
        require_admin(request)
      except PermissionError as exc:
        return JSONResponse(status_code=403, content={"error": str(exc)})
      candidate = str(payload.get("default_password") or "").strip()
      if len(candidate) < 4:
        return JSONResponse(status_code=400, content={"error": "Default password must be at least 4 characters."})
      with store.begin() as session:
        updated = set_default_password(session, candidate)
        return JSONResponse(content={"status": "updated", "default_password": updated})

    @app.post("/api/admin/users")
    def admin_add_user(request: Request, payload: dict = Body(default={})) -> Response:
      try:
        require_admin(request)
      except PermissionError as exc:
        return JSONResponse(status_code=403, content={"error": str(exc)})

      email = str(payload.get("email") or "").strip().lower()
      is_admin = _as_bool(payload.get("is_admin"), default=False)
      if not email:
        return JSONResponse(status_code=400, content={"error": "Email is required."})

      with store.begin() as session:
        existing = session.query(User).filter(User.email == email).first()
        if existing is not None:
          return JSONResponse(status_code=400, content={"error": "User already exists."})
        default_password = get_default_password(session)
        new_user = User(
          id=str(uuid4()),
          email=email,
          password_hash=_password_record(default_password),
          is_admin=is_admin,
          force_password_reset=True,
          is_active=True,
          created_at=datetime.now(timezone.utc),
        )
        session.add(new_user)
        return JSONResponse(content={"status": "created", "user": serialize_user(new_user)})

    @app.patch("/api/admin/users/{user_id}")
    def admin_update_user(user_id: str, request: Request, payload: dict = Body(default={})) -> Response:
      try:
        admin_user = require_admin(request)
      except PermissionError as exc:
        return JSONResponse(status_code=403, content={"error": str(exc)})

      with store.begin() as session:
        target = session.get(User, user_id)
        if target is None:
          return JSONResponse(status_code=404, content={"error": "User not found."})
        if "is_admin" in payload:
          target.is_admin = _as_bool(payload.get("is_admin"), default=bool(target.is_admin))
        if "force_password_reset" in payload:
          target.force_password_reset = _as_bool(
            payload.get("force_password_reset"),
            default=bool(target.force_password_reset),
          )
        if _as_bool(payload.get("reset_password"), default=False):
          default_password = get_default_password(session)
          target.password_hash = _password_record(default_password)
          target.force_password_reset = True
        if user_id == admin_user.id and not target.is_admin:
          return JSONResponse(status_code=400, content={"error": "You cannot remove your own admin access."})
        return JSONResponse(content={"status": "updated", "user": serialize_user(target)})

    @app.delete("/api/admin/users/{user_id}")
    def admin_delete_user(user_id: str, request: Request) -> Response:
      try:
        admin_user = require_admin(request)
      except PermissionError as exc:
        return JSONResponse(status_code=403, content={"error": str(exc)})
      if user_id == admin_user.id:
        return JSONResponse(status_code=400, content={"error": "You cannot delete your own account."})

      with store.begin() as session:
        target = session.get(User, user_id)
        if target is None:
          return JSONResponse(status_code=404, content={"error": "User not found."})
        session.query(UserSession).filter(UserSession.user_id == user_id).delete(synchronize_session=False)
        session.delete(target)
        return JSONResponse(content={"status": "deleted", "user_id": user_id})

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return _HTML

    @app.get("/review.js")
    def review_script() -> Response:
        script = Path(__file__).with_name("review.js").read_text(encoding="utf-8")
        return Response(content=script, media_type="application/javascript")

    @app.post("/api/inspections")
    async def create_inspection(
        store_number: str = Form(...),
        address: str = Form(...),
        point_list_categories: list[str] = Form(...),
        points_files: list[UploadFile] = File(...),
        point_decisions: str = Form("[]"),
    ) -> dict:
        inspection_id = str(uuid4())
        target = _UPLOAD_ROOT / inspection_id
        target.mkdir(parents=True, exist_ok=True)
        files = []
        point_file_names = []
        for upload in points_files:
            filename = Path(upload.filename or "upload.bin").name
            destination = target / filename
            destination.write_bytes(await upload.read())
            files.append(filename)
            point_file_names.append(filename)
        created_at = datetime.now(timezone.utc)
        inferred_date = date.today()

        decisions_to_store = json.loads(point_decisions)
        if not isinstance(decisions_to_store, list) or not decisions_to_store:
            return {"error": "Review decisions are required before creating an inspection."}
        if any(_as_bool(item.get("accepted"), default=False) is False and _as_bool(item.get("deleted"), default=False) is False for item in decisions_to_store):
            return {"error": "All Review rows must be accepted or deleted before finishing the review."}

        with store.begin() as session:
            session.add(Inspection(id=inspection_id, store_number=store_number, address=address,
                                   store_type="Walmart - Supercenter", inspector_name="",
                                   start_date=inferred_date, completion_date=inferred_date,
                                   status="pending_event_history", created_at=created_at))
            for filename in files:
                session.add(SourceFile(id=str(uuid4()), inspection_id=inspection_id,
                                       filename=filename, path=str(target / filename),
                                       kind="points_list"))
            point_list_ids_by_filename: dict[str, str] = {}
            for filename, list_category in zip(point_file_names, point_list_categories, strict=False):
                point_list_id = str(uuid4())
                session.add(PointList(id=point_list_id, inspection_id=inspection_id,
                                      category=list_category, filename=filename,
                                      path=str(target / filename), accepted_at=created_at))
                point_list_ids_by_filename[filename] = point_list_id

            default_list_id = point_list_ids_by_filename.get(point_file_names[0], "") if point_file_names else ""
            for decision in decisions_to_store:
                source_filename = str(decision.get("source_filename") or "")
                point_list_id = point_list_ids_by_filename.get(source_filename, default_list_id)
                if point_list_id:
                    session.add(PointListDecision(
                        id=str(uuid4()),
                        inspection_id=inspection_id,
                        point_list_id=point_list_id,
                        address=decision.get("address"),
                        text=decision.get("text", ""),
                        accepted=_as_bool(decision.get("accepted"), default=False),
                        deleted=_as_bool(decision.get("deleted"), default=False),
                        reason=decision.get("reason", "technician review"),
                    ))
        return {
            "id": inspection_id,
            "status": "pending_event_history",
            "files": files,
            "accepted_points": sum(1 for d in decisions_to_store if _as_bool(d.get("accepted"), default=False)),
        }

    @app.get("/api/inspections")
    def list_inspections() -> list[dict]:
        with store() as session:
            rows = session.query(Inspection).order_by(Inspection.created_at.desc()).all()
            return [{"id": row.id, "store_number": row.store_number, "address": row.address,
                     "start_date": row.start_date.isoformat(),
                     "completion_date": row.completion_date.isoformat(),
                     "status": row.status, "created_at": row.created_at.isoformat()} for row in rows]

    @app.delete("/api/inspections/{inspection_id}")
    def delete_inspection(inspection_id: str) -> dict:
        upload_path = _UPLOAD_ROOT / inspection_id
        with store.begin() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}

            session.query(PointListEventDate).filter(
                PointListEventDate.inspection_id == inspection_id
            ).delete(synchronize_session=False)
            session.query(PointListDecision).filter(
                PointListDecision.inspection_id == inspection_id
            ).delete(synchronize_session=False)
            session.query(PointList).filter(
                PointList.inspection_id == inspection_id
            ).delete(synchronize_session=False)
            session.query(SourceFile).filter(
                SourceFile.inspection_id == inspection_id
            ).delete(synchronize_session=False)
            session.delete(inspection)

        shutil.rmtree(upload_path, ignore_errors=True)
        return {"id": inspection_id, "status": "deleted"}

    @app.get("/api/inspections/{inspection_id}")
    def get_inspection(inspection_id: str, point_list_id: str | None = Query(default=None)) -> dict:
        with store() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}

            point_lists = (
                session.query(PointList)
                .filter(PointList.inspection_id == inspection_id)
                .order_by(PointList.accepted_at.asc(), PointList.filename.asc())
                .all()
            )
            selected_point_list_id = point_list_id or (point_lists[0].id if point_lists else None)

            scoped_points = (
                session.query(PointListDecision)
                .filter(
                    PointListDecision.inspection_id == inspection_id,
                    PointListDecision.point_list_id == selected_point_list_id,
                    PointListDecision.accepted.is_(True),
                    PointListDecision.deleted.is_(False),
                )
                .order_by(PointListDecision.address.asc(), PointListDecision.text.asc())
                .all()
            )
            points = scoped_points

            selected_kind = _event_history_kind(selected_point_list_id)
            event_history_files = (
                session.query(SourceFile)
                .filter(SourceFile.inspection_id == inspection_id, SourceFile.kind == selected_kind)
                .order_by(SourceFile.filename.asc())
                .all()
            )
            saved_event_dates = (
                session.query(PointListEventDate)
                .filter(
                    PointListEventDate.inspection_id == inspection_id,
                    PointListEventDate.point_list_id == selected_point_list_id,
                )
                .order_by(PointListEventDate.point_address.asc())
                .all()
            )
            mapped_dates = {item.point_address: item.event_timestamp for item in saved_event_dates}
            return {
                "id": inspection.id,
                "store_number": inspection.store_number,
                "store_type": inspection.store_type,
                "address": inspection.address,
                "inspector_name": inspection.inspector_name,
                "start_date": inspection.start_date.isoformat(),
                "completion_date": inspection.completion_date.isoformat(),
                "status": inspection.status,
                "accepted_points": [
                    {
                        "address": point.address,
                        "text": point.text,
                        "event_date": _format_event_date(
                            mapped_dates.get(point.address) if point.address is not None else None
                        ),
                    }
                    for point in points
                ],
                "point_lists": [
                    {"id": item.id, "category": item.category, "filename": item.filename}
                    for item in point_lists
                ],
                "selected_point_list_id": selected_point_list_id,
                "event_history_files": [file.filename for file in event_history_files],
            }

    @app.patch("/api/inspections/{inspection_id}")
    def update_inspection_details(inspection_id: str, payload: dict = Body(default={})) -> dict:
        with store.begin() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}

            store_number = str(payload.get("store_number") or "").strip()
            store_type = str(payload.get("store_type") or "").strip()
            address = str(payload.get("address") or "").strip()
            inspector_name = str(payload.get("inspector_name") or "").strip()
            start_date = _parse_date_value(payload.get("start_date"))
            completion_date = _parse_date_value(payload.get("completion_date"))

            if store_number:
                inspection.store_number = store_number
            if store_type:
                inspection.store_type = store_type
            if address:
                inspection.address = address
            inspection.inspector_name = inspector_name
            if start_date is not None:
                inspection.start_date = start_date
            if completion_date is not None:
                inspection.completion_date = completion_date

            return {
                "id": inspection.id,
                "store_number": inspection.store_number,
                "store_type": inspection.store_type,
                "address": inspection.address,
                "inspector_name": inspection.inspector_name,
                "start_date": inspection.start_date.isoformat(),
                "completion_date": inspection.completion_date.isoformat(),
                "status": inspection.status,
            }

    @app.post("/api/inspections/{inspection_id}/event-history")
    async def add_event_history(
        inspection_id: str,
        point_list_id: str = Form(...),
        event_file: UploadFile = File(...),
    ) -> dict:
        with store() as session:
            inspection = session.get(Inspection, inspection_id)
            if inspection is None:
                return {"error": "inspection not found"}

            point_list = (
                session.query(PointList)
                .filter(PointList.inspection_id == inspection_id, PointList.id == point_list_id)
                .first()
            )
            if point_list is None:
                return {"error": "Selected Points List was not found for this inspection."}

        target = _ensure_inspection_upload_dir(inspection_id)

        filename = Path(event_file.filename or "event-history.bin").name
        if not filename.lower().endswith(".xlsx"):
            return {"error": "Event History processing currently supports XLSX files."}
        destination = target / filename
        destination.write_bytes(await event_file.read())
        try:
            extracted = parse_event_history_xlsx(destination)
        except ValueError as exc:
            destination.unlink(missing_ok=True)
            return {"error": f"{filename}: {exc}"}

        with store() as session:
            existing = (
                session.query(PointListEventDate)
                .filter(
                    PointListEventDate.inspection_id == inspection_id,
                    PointListEventDate.point_list_id == point_list_id,
                )
                .all()
            )
        existing_points = {item.point_address for item in existing}

        pending_matches = [
            {"point": point, "timestamp": _format_event_date(timestamp)}
            for point, timestamp in sorted(extracted.items())
            if point not in existing_points
        ]

        with store.begin() as session:
            session.add(SourceFile(id=str(uuid4()), inspection_id=inspection_id,
                                   filename=filename, path=str(destination),
                                   kind=_event_history_kind(point_list_id)))
        return {
            "inspection_id": inspection_id,
            "point_list_id": point_list_id,
            "filename": filename,
            "status": "matched",
            "matched_points": len(extracted),
            "pending_matches": pending_matches,
            "ignored_existing": len(extracted) - len(pending_matches),
        }

    @app.post("/api/inspections/{inspection_id}/event-dates/save")
    def save_event_dates(inspection_id: str, payload: dict = Body(default={})) -> dict:
        matches = payload.get("matches", [])
        point_list_id = str(payload.get("point_list_id") or "").strip()
        if not isinstance(matches, list):
            return {"error": "matches must be a list"}
        if not point_list_id:
            return {"error": "point_list_id is required"}

        saved = 0
        ignored_existing = 0
        ignored_invalid = 0

        with store.begin() as session:
            point_list = (
                session.query(PointList)
                .filter(PointList.inspection_id == inspection_id, PointList.id == point_list_id)
                .first()
            )
            if point_list is None:
                return {"error": "Selected Points List was not found for this inspection."}

            existing_rows = (
                session.query(PointListEventDate)
                .filter(
                    PointListEventDate.inspection_id == inspection_id,
                    PointListEventDate.point_list_id == point_list_id,
                )
                .all()
            )
            existing_points = {item.point_address for item in existing_rows}

            accepted_points = (
                session.query(PointListDecision)
                .filter(
                    PointListDecision.inspection_id == inspection_id,
                    PointListDecision.point_list_id == point_list_id,
                    PointListDecision.accepted.is_(True),
                    PointListDecision.deleted.is_(False),
                    PointListDecision.address.is_not(None),
                )
                .all()
            )
            allowed_points = {int(item.address) for item in accepted_points if item.address is not None}

            for item in matches:
                if not isinstance(item, dict):
                    ignored_invalid += 1
                    continue
                point = normalize_point(item.get("point"))
                timestamp = _parse_saved_timestamp(item.get("timestamp"))
                source_filename = str(item.get("source_filename") or "")

                if point is None or timestamp is None or point not in allowed_points:
                    ignored_invalid += 1
                    continue
                if point in existing_points:
                    ignored_existing += 1
                    continue

                session.add(
                    PointListEventDate(
                        id=str(uuid4()),
                        inspection_id=inspection_id,
                        point_list_id=point_list_id,
                        point_address=point,
                        event_timestamp=timestamp,
                        source_filename=source_filename,
                    )
                )
                existing_points.add(point)
                saved += 1

        return {
            "inspection_id": inspection_id,
            "point_list_id": point_list_id,
            "status": "saved",
            "saved": saved,
            "ignored_existing": ignored_existing,
            "ignored_invalid": ignored_invalid,
        }

    @app.post("/api/inspections/{inspection_id}/event-dates/clear")
    def clear_event_dates(inspection_id: str, payload: dict = Body(default={})) -> dict:
        point_list_id = str(payload.get("point_list_id") or "").strip()
        if not point_list_id:
            return {"error": "point_list_id is required"}
        with store.begin() as session:
            cleared = (
                session.query(PointListEventDate)
                .filter(
                    PointListEventDate.inspection_id == inspection_id,
                    PointListEventDate.point_list_id == point_list_id,
                )
                .delete(synchronize_session=False)
            )
        return {
            "inspection_id": inspection_id,
            "point_list_id": point_list_id,
            "status": "cleared",
            "cleared": int(cleared),
        }

    @app.post("/api/point-lists/preview")
    async def preview_points_list(
        points_files: list[UploadFile] = File(...),
        point_list_categories: list[str] = Form(default=[]),
    ) -> dict:
        if point_list_categories and len(point_list_categories) != len(points_files):
            return {"error": "Each Points List must have a matching security-panel category."}

        previews = []
        for index, points_file in enumerate(points_files):
            filename = Path(points_file.filename or f"points-{index + 1}.xlsx").name
            if not filename.lower().endswith(".xlsx"):
                return {"error": "The first parser supports XLSX files; PDF and legacy XLS need a separate adapter."}
            preview_path = _UPLOAD_ROOT / f"preview-{uuid4()}-{filename}"
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            preview_path.write_bytes(await points_file.read())
            try:
                rows = parse_xlsx(preview_path)
            except ValueError as exc:
                return {"error": f"{filename}: {exc}"}
            previews.append({
                "filename": filename,
                "category": point_list_categories[index] if point_list_categories else "",
                "accepted": sum(row["accepted"] for row in rows),
                "rejected": sum(not row["accepted"] for row in rows),
                "rows": rows,
            })

        accepted = sum(item["accepted"] for item in previews)
        rejected = sum(item["rejected"] for item in previews)
        first = previews[0] if len(previews) == 1 else None
        return {
            "filename": first["filename"] if first else None,
            "accepted": accepted,
            "rejected": rejected,
            "rows": first["rows"] if first else [],
            "lists": previews,
        }

    return app


app = create_app() if FastAPI is not None else None
