import React, { useEffect, useState, useCallback } from 'react';
import API from '../api';
import Toast from '../components/Toast';
import './Dashboard.css';

const Dashboard = () => {
  const [candidates, setCandidates] = useState([]);
  const [allCandidates, setAllCandidates] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState(null);

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
  };

  const fetchCandidates = async () => {
    setLoading(true);
    try {
      const res = await API.get('/candidates/');
      setCandidates(res.data);
      setAllCandidates(res.data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  useEffect(() => { fetchCandidates(); }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    if (!search.trim()) {
      setCandidates(allCandidates);
      return;
    }
    const searchSkills = search.toLowerCase().split(',').map(s => s.trim()).filter(Boolean);
    const filtered = allCandidates.filter(c =>
      searchSkills.every(skill =>
        (c.skills || []).some(s => s.toLowerCase().includes(skill))
      )
    );
    setCandidates(filtered);
  };

  const handleClear = () => {
    setSearch('');
    setCandidates(allCandidates);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this candidate?')) return;
    try {
      await API.delete(`/candidates/${id}`);
      setCandidates(prev => prev.filter(c => c.id !== id));
      setAllCandidates(prev => prev.filter(c => c.id !== id));
      showToast('Candidate deleted successfully.', 'success');
    } catch (err) {
      if (err.response?.status === 403) {
        showToast('You can only delete candidates you uploaded.', 'error');
      } else {
        showToast('Failed to delete candidate.', 'error');
      }
    }
  };

  const highlightSkill = (skill) => {
    if (!search.trim()) return false;
    const searchSkills = search.toLowerCase().split(',').map(s => s.trim());
    return searchSkills.some(s => skill.toLowerCase().includes(s));
  };

  return (
    <div className="page">
      <h1>Candidates</h1>
      <form onSubmit={handleSearch} className="search-bar">
        <input
          type="text"
          placeholder="Filter by skill (e.g. python, docker)"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <button type="submit">Search</button>
        <button type="button" onClick={handleClear}>Clear</button>
      </form>

      {search && (
        <p className="results-count">
          Showing {candidates.length} of {allCandidates.length} candidates
        </p>
      )}

      {loading ? <p>Loading...</p> : (
        <div className="card-grid">
          {candidates.length === 0 ? (
            <p>No candidates found matching "<strong>{search}</strong>".</p>
          ) : candidates.map(c => (
            <div className="card" key={c.id}>
              <h3>{c.full_name || 'Unknown'}</h3>
              <p>{c.email || 'No email'}</p>
              <p>{c.phone || 'No phone'}</p>
              <div className="skills">
                {(c.skills || []).map(s => (
                  <span
                    key={s}
                    className={`skill-tag ${highlightSkill(s) ? 'highlighted' : ''}`}
                  >
                    {s}
                  </span>
                ))}
              </div>
              {c.cluster_id !== null && (
                <p className="cluster">Cluster: {c.cluster_id}</p>
              )}
              <p className="date">Uploaded: {new Date(c.uploaded_at).toLocaleDateString()}</p>
              <button className="delete-btn" onClick={() => handleDelete(c.id)}>Delete</button>
            </div>
          ))}
        </div>
      )}

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
};

export default Dashboard;