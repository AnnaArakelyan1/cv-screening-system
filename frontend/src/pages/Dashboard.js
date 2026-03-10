import React, { useEffect, useState } from 'react';
import API from '../api';
import './Dashboard.css';

const Dashboard = () => {
  const [candidates, setCandidates] = useState([]);
  const [allCandidates, setAllCandidates] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

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
    // Support multiple skills separated by comma
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
      const updated = candidates.filter(c => c.id !== id);
      setCandidates(updated);
      setAllCandidates(allCandidates.filter(c => c.id !== id));
    } catch (err) {
      console.error(err);
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
    </div>
  );
};

export default Dashboard;