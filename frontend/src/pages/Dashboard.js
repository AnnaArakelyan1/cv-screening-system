import React, { useEffect, useState } from 'react';
import API from '../api';
import './Dashboard.css';

const Dashboard = () => {
  const [candidates, setCandidates] = useState([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchCandidates = async (skill = '') => {
    setLoading(true);
    try {
      const res = await API.get('/candidates/', {
        params: skill ? { skill } : {}
      });
      setCandidates(res.data);
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  useEffect(() => { fetchCandidates(); }, []);

  const handleSearch = (e) => {
    e.preventDefault();
    fetchCandidates(search);
  };

  return (
    <div className="page">
      <h1>Candidates</h1>
      <form onSubmit={handleSearch} className="search-bar">
        <input
          type="text"
          placeholder="Filter by skill (e.g. python)"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <button type="submit">Search</button>
        <button type="button" onClick={() => { setSearch(''); fetchCandidates(); }}>Clear</button>
      </form>

      {loading ? <p>Loading...</p> : (
        <div className="card-grid">
          {candidates.length === 0 ? (
            <p>No candidates found. Upload some CVs first.</p>
          ) : candidates.map(c => (
            <div className="card" key={c.id}>
              <h3>{c.full_name || 'Unknown'}</h3>
              <p>{c.email || 'No email'}</p>
              <p>{c.phone || 'No phone'}</p>
              <div className="skills">
                {(c.skills || []).map(s => <span key={s} className="skill-tag">{s}</span>)}
              </div>
              {c.cluster_id !== null && (
                <p className="cluster">Cluster: {c.cluster_id}</p>
              )}
              <p className="date">Uploaded: {new Date(c.uploaded_at).toLocaleDateString()}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default Dashboard;