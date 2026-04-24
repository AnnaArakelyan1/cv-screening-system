import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import API from '../api';
import { useAuth } from '../context/AuthContext';
import Toast from '../components/Toast';
import './Profile.css';

const Profile = () => {
  const [me, setMe] = useState(null);
  const [stats, setStats] = useState({ candidates: 0, jobs: 0, users: 0 });
  const [toast, setToast] = useState(null);
  const [editOpen, setEditOpen] = useState(false);
  const [editForm, setEditForm] = useState({ full_name: '', email: '', current_password: '', new_password: '', confirm_password: '' });
  const [saving, setSaving] = useState(false);
  const { logout } = useAuth();
  const navigate = useNavigate();

  const showToast = (msg, type = 'success') => setToast({ message: msg, type });

  useEffect(() => {
    const load = async () => {
      try {
        const meRes = await API.get('/users/me');
        setMe(meRes.data);
        const [candidatesRes, jobsRes] = await Promise.all([
          API.get('/candidates/'),
          API.get('/jobs/'),
        ]);
        const s = { candidates: candidatesRes.data.length, jobs: jobsRes.data.length, users: 0 };
        if (meRes.data.is_admin) {
          const usersRes = await API.get('/users/');
          s.users = usersRes.data.length;
        }
        setStats(s);
      } catch {}
    };
    load();
  }, []);

  const openEdit = () => {
    setEditForm({ full_name: me.full_name, email: me.email, current_password: '', new_password: '', confirm_password: '' });
    setEditOpen(true);
  };

  const handleSave = async (e) => {
    e.preventDefault();
    if (editForm.new_password && editForm.new_password !== editForm.confirm_password) {
      showToast('New passwords do not match.', 'error');
      return;
    }
    setSaving(true);
    try {
      const payload = {
        full_name: editForm.full_name.trim() || undefined,
        email: editForm.email.trim() || undefined,
      };
      if (editForm.new_password) {
        payload.current_password = editForm.current_password;
        payload.new_password = editForm.new_password;
      }
      const res = await API.patch('/users/me', payload);
      setMe(res.data);
      setEditOpen(false);
      showToast('Profile updated successfully.');
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to update profile.', 'error');
    }
    setSaving(false);
  };

  const handleDeleteSelf = async () => {
    if (!window.confirm('Delete your account? This cannot be undone.')) return;
    try {
      await API.delete('/users/me');
      logout();
      navigate('/login');
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to delete account.', 'error');
    }
  };

  if (!me) return <div className="page"><p className="loading-msg">Loading profile...</p></div>;

  const initials = me.full_name
    ? me.full_name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : '?';

  return (
    <div className="page">
      <h1>My Profile</h1>

      <div className="profile-layout">
        <div className="profile-sidebar">
          <div className="profile-avatar-wrap">
            <div className="profile-avatar">{initials}</div>
            {me.is_admin && <span className="admin-crown">Admin</span>}
          </div>
          <h2 className="profile-name">{me.full_name}</h2>
          <p className="profile-email">{me.email}</p>
          <p className="profile-since">
            Member since {new Date(me.created_at).toLocaleDateString('en-US', { month: 'long', year: 'numeric' })}
          </p>
          <button className="edit-profile-btn" onClick={openEdit}>Edit Profile</button>
          {!me.is_admin && (
            <button className="delete-account-btn" onClick={handleDeleteSelf}>Delete Account</button>
          )}
        </div>

        <div className="profile-main">
          <div className="profile-stats">
            <div className="profile-stat">
              <span className="pstat-number">{stats.candidates}</span>
              <span className="pstat-label">Total Candidates</span>
            </div>
            <div className="profile-stat">
              <span className="pstat-number">{stats.jobs}</span>
              <span className="pstat-label">Job Postings</span>
            </div>
            {me.is_admin && (
              <div className="profile-stat">
                <span className="pstat-number">{stats.users}</span>
                <span className="pstat-label">HR Users</span>
              </div>
            )}
          </div>

          <div className="profile-details-card">
            <h3>Account Details</h3>
            <div className="detail-row">
              <span className="detail-label">Full Name</span>
              <span className="detail-value">{me.full_name}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Email</span>
              <span className="detail-value">{me.email}</span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Role</span>
              <span className="detail-value">
                <span className={`role-pill ${me.is_admin ? 'role-admin' : 'role-hr'}`}>
                  {me.is_admin ? 'Administrator' : 'HR User'}
                </span>
              </span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Account Status</span>
              <span className="detail-value"><span className="status-active">Active</span></span>
            </div>
            <div className="detail-row">
              <span className="detail-label">Member Since</span>
              <span className="detail-value">
                {new Date(me.created_at).toLocaleDateString('en-US', { day: 'numeric', month: 'long', year: 'numeric' })}
              </span>
            </div>
          </div>
        </div>
      </div>

      {editOpen && (
        <div className="modal-overlay" onClick={() => setEditOpen(false)}>
          <div className="modal edit-profile-modal" onClick={e => e.stopPropagation()}>
            <h3>Edit Profile</h3>
            <form onSubmit={handleSave} className="edit-form">
              <div className="edit-section">
                <div className="pw-field">
                  <label>Full Name</label>
                  <input
                    type="text"
                    value={editForm.full_name}
                    onChange={e => setEditForm({ ...editForm, full_name: e.target.value })}
                  />
                </div>
                <div className="pw-field">
                  <label>Email</label>
                  <input
                    type="email"
                    value={editForm.email}
                    onChange={e => setEditForm({ ...editForm, email: e.target.value })}
                  />
                </div>
              </div>

              <div className="edit-divider">
                <span>Change Password <span className="optional">(optional)</span></span>
              </div>

              <div className="edit-section">
                <div className="pw-field">
                  <label>Current Password</label>
                  <input
                    type="password"
                    placeholder="Required only if changing password"
                    value={editForm.current_password}
                    onChange={e => setEditForm({ ...editForm, current_password: e.target.value })}
                  />
                </div>
                <div className="pw-field">
                  <label>New Password</label>
                  <input
                    type="password"
                    placeholder="At least 6 characters"
                    value={editForm.new_password}
                    onChange={e => setEditForm({ ...editForm, new_password: e.target.value })}
                  />
                </div>
                <div className="pw-field">
                  <label>Confirm New Password</label>
                  <input
                    type="password"
                    placeholder="Repeat new password"
                    value={editForm.confirm_password}
                    onChange={e => setEditForm({ ...editForm, confirm_password: e.target.value })}
                  />
                </div>
              </div>

              <div className="modal-actions">
                <button type="submit" className="pw-submit-btn" disabled={saving}>
                  {saving ? 'Saving...' : 'Save Changes'}
                </button>
                <button type="button" className="cancel-btn" onClick={() => setEditOpen(false)}>
                  Cancel
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
};

export default Profile;
