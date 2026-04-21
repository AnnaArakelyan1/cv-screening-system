import React, { useState, useEffect } from 'react';
import API from '../api';
import './Auth.css';

const Register = () => {
  const [form, setForm] = useState({ full_name: '', email: '', password: '' });
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [users, setUsers] = useState([]);

  const fetchUsers = async () => {
    try {
      const res = await API.get('/users/');
      setUsers(res.data);
    } catch {}
  };

  useEffect(() => { fetchUsers(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');
    try {
      await API.post('/auth/register', form);
      setSuccess(`User "${form.full_name}" created successfully.`);
      setForm({ full_name: '', email: '', password: '' });
      fetchUsers();
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this user?')) return;
    try {
      await API.delete(`/users/${id}`);
      setUsers(users.filter(u => u.id !== id));
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to delete user');
    }
  };

  return (
    <div className="page">
      <h1>Manage Users</h1>

      <div className="job-form-box">
        <h2>Add New User</h2>
        {error && <p className="error">{error}</p>}
        {success && <p className="success">{success}</p>}
        <form onSubmit={handleSubmit}>
          <input type="text" placeholder="Full Name" value={form.full_name}
            onChange={e => setForm({ ...form, full_name: e.target.value })} required />
          <input type="email" placeholder="Email" value={form.email}
            onChange={e => setForm({ ...form, email: e.target.value })} required />
          <input type="password" placeholder="Password" value={form.password}
            onChange={e => setForm({ ...form, password: e.target.value })} required />
          <button type="submit">Create User</button>
        </form>
      </div>

      <div className="users-table-wrap">
        <h2>All Users</h2>
        {users.length === 0 ? <p>No users found.</p> : (
          <table className="users-table">
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Admin</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id}>
                  <td>{u.full_name}</td>
                  <td>{u.email}</td>
                  <td>{u.is_admin ? 'Yes' : 'No'}</td>
                  <td>{new Date(u.created_at).toLocaleDateString()}</td>
                  <td>
                    {!u.is_admin && (
                      <button className="delete-btn" onClick={() => handleDelete(u.id)}>
                        Delete
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};

export default Register;
