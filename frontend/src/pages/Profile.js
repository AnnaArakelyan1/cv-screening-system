import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import API from '../api';
import { useAuth } from '../context/AuthContext';
import Toast from '../components/Toast';
import './Profile.css';

const Profile = () => {
  const [me, setMe] = useState(null);
  const [users, setUsers] = useState([]);
  const [toast, setToast] = useState(null);
  const { logout } = useAuth();
  const navigate = useNavigate();

  const showToast = (message, type = 'success') => setToast({ message, type });

  useEffect(() => {
    const fetchData = async () => {
      try {
        const res = await API.get('/users/me');
        setMe(res.data);
        if (res.data.is_admin) {
          const usersRes = await API.get('/users/');
          setUsers(usersRes.data);
        }
      } catch (err) {
        console.error(err);
      }
    };
    fetchData();
  }, []);

  const handleDeleteSelf = async () => {
    if (!window.confirm('Are you sure you want to delete your account? This cannot be undone.')) return;
    try {
      await API.delete('/users/me');
      logout();
      navigate('/login');
    } catch (err) {
      if (err.response?.data?.detail) {
        showToast(err.response.data.detail, 'error');
      } else {
        showToast('Failed to delete account.', 'error');
      }
    }
  };

  const handleDeleteUser = async (userId, email) => {
    if (!window.confirm(`Delete user ${email}?`)) return;
    try {
      await API.delete(`/users/${userId}`);
      setUsers(users.filter(u => u.id !== userId));
      showToast(`User ${email} deleted.`, 'success');
    } catch (err) {
      showToast('Failed to delete user.', 'error');
    }
  };

  if (!me) return <div className="page"><p>Loading...</p></div>;

  return (
    <div className="page">
      <h1>My Profile</h1>

      <div className="profile-card">
        <div className="profile-info">
          <h2>{me.full_name}</h2>
          <p>{me.email}</p>
          <p>Member since: {new Date(me.created_at).toLocaleDateString()}</p>
          {me.is_admin && <span className="admin-badge">Admin</span>}
        </div>
        {!me.is_admin && (
          <button className="delete-btn" onClick={handleDeleteSelf}>
            Delete My Account
          </button>
        )}
      </div>

      {me.is_admin && (
        <div className="users-section">
          <h2>All HR Users</h2>
          <div className="users-list">
            {users.filter(u => !u.is_admin).length === 0 ? (
              <p>No HR users registered yet.</p>
            ) : (
              users.filter(u => !u.is_admin).map(u => (
                <div className="user-card" key={u.id}>
                  <div className="user-info">
                    <h3>{u.full_name}</h3>
                    <p>{u.email}</p>
                    <p>Joined: {new Date(u.created_at).toLocaleDateString()}</p>
                  </div>
                  <div className="user-actions">
                    <button className="delete-btn" onClick={() => handleDeleteUser(u.id, u.email)}>
                      Delete
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
};

export default Profile;