import React, { useState, useEffect } from 'react';
import API from '../api';
import Toast from '../components/Toast';
import './Users.css';

const Users = () => {
  const [form, setForm] = useState({ full_name: '', email: '', password: '' });
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);

  const showToast = (message, type = 'success') => setToast({ message, type });

  const fetchUsers = async () => {
    try {
      const res = await API.get('/users/');
      setUsers(res.data);
    } catch {}
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await API.post('/auth/register', form);
      showToast(`User "${form.full_name}" created successfully.`);
      setForm({ full_name: '', email: '', password: '' });
      fetchUsers();
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to create user.', 'error');
    }
    setLoading(false);
  };

  const handleDelete = async (id, name) => {
    if (!window.confirm(`Delete user "${name}"?`)) return;
    try {
      await API.delete(`/users/${id}`);
      setUsers(prev => prev.filter(u => u.id !== id));
      showToast(`User "${name}" deleted.`);
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to delete user.', 'error');
    }
  };

  const handleToggleActive = async (id, isActive, name) => {
    try {
      await API.patch(`/users/${id}/toggle-active`);
      setUsers(prev => prev.map(u => u.id === id ? { ...u, is_active: !isActive } : u));
      showToast(`User "${name}" ${isActive ? 'deactivated' : 'activated'}.`);
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to update user.', 'error');
    }
  };

  const hrUsers = users.filter(u => !u.is_admin);
  const adminUsers = users.filter(u => u.is_admin);

  return (
    <div className="page">
      <h1>User Management</h1>

      <div className="users-stats">
        <div className="users-stat-card">
          <span className="stat-number">{users.length}</span>
          <span className="stat-label">Total Users</span>
        </div>
        <div className="users-stat-card">
          <span className="stat-number">{hrUsers.length}</span>
          <span className="stat-label">HR Users</span>
        </div>
        <div className="users-stat-card">
          <span className="stat-number">{adminUsers.length}</span>
          <span className="stat-label">Admins</span>
        </div>
      </div>

      <div className="users-layout">
        <div className="add-user-panel">
          <h2>Add New User</h2>
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label>Full Name</label>
              <input
                type="text"
                placeholder="Jane Smith"
                value={form.full_name}
                onChange={e => setForm({ ...form, full_name: e.target.value })}
                required
              />
            </div>
            <div className="field">
              <label>Email</label>
              <input
                type="email"
                placeholder="jane@company.com"
                value={form.email}
                onChange={e => setForm({ ...form, email: e.target.value })}
                required
              />
            </div>
            <div className="field">
              <label>Password</label>
              <input
                type="password"
                placeholder="••••••••"
                value={form.password}
                onChange={e => setForm({ ...form, password: e.target.value })}
                required
              />
            </div>
            <button type="submit" className="create-btn" disabled={loading}>
              {loading ? 'Creating...' : 'Create User'}
            </button>
          </form>
        </div>

        <div className="users-list-panel">
          <h2>All Users <span className="users-count">{users.length}</span></h2>
          {users.length === 0 ? (
            <p className="empty-msg">No users yet.</p>
          ) : (
            <div className="users-table-wrap">
              <table className="users-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    <th>Joined</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {users.map(u => (
                    <tr key={u.id} className={!u.is_active ? 'user-inactive' : ''}>
                      <td>
                        <div className="user-cell">
                          <div className="user-avatar-sm">
                            {(u.full_name || 'U')[0].toUpperCase()}
                          </div>
                          {u.full_name}
                        </div>
                      </td>
                      <td className="muted">{u.email}</td>
                      <td>
                        <span className={`role-badge ${u.is_admin ? 'role-admin' : 'role-hr'}`}>
                          {u.is_admin ? 'Admin' : 'HR'}
                        </span>
                      </td>
                      <td>
                        <span className={`active-badge ${u.is_active ? 'active' : 'inactive'}`}>
                          {u.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="muted">{new Date(u.created_at).toLocaleDateString()}</td>
                      <td>
                        {!u.is_admin && (
                          <div className="user-actions">
                            <button
                              className={`toggle-btn ${u.is_active ? 'deactivate' : 'activate'}`}
                              onClick={() => handleToggleActive(u.id, u.is_active, u.full_name)}
                            >
                              {u.is_active ? 'Deactivate' : 'Activate'}
                            </button>
                            <button className="delete-btn" onClick={() => handleDelete(u.id, u.full_name)}>
                              Delete
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
};

export default Users;
