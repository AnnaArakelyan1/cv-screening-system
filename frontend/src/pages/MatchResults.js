import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import API from '../api';
import './MatchResults.css';

const MatchResults = () => {
  const { id } = useParams();
  const [results, setResults] = useState([]);
  const [selected, setSelected] = useState([]);
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const matchRes = await API.get(`/jobs/${id}/match`);
        setResults(matchRes.data);
      } catch (err) {
        console.error(err);
      }
      setLoading(false);
    };
    fetchData();
  }, [id]);

  const toggleSelect = (candidateId) => {
    setSelected(prev =>
      prev.includes(candidateId)
        ? prev.filter(i => i !== candidateId)
        : [...prev, candidateId]
    );
  };

  const selectAll = () => {
    const nonApplied = results
      .filter(r => !r.applied)
      .map(r => r.candidate.id);
    setSelected(nonApplied);
  };

  const clearAll = () => setSelected([]);

  const handleAssignSelected = async () => {
    if (selected.length === 0) return;
    setAssigning(true);
    let success = 0;
    for (const candidateId of selected) {
      try {
        await API.post('/applications/', {
          candidate_id: candidateId,
          job_id: parseInt(id)
        });
        success++;
      } catch (err) {}
    }
    const res = await API.get(`/jobs/${id}/match`);
    setResults(res.data);
    setSelected([]);
    setAssigning(false);
    alert(`Successfully assigned ${success} candidate(s).`);
  };

  const handleUnassign = async (candidateId) => {
    if (!window.confirm('Unassign this candidate from the job?')) return;
    try {
      const appsRes = await API.get(`/applications/job/${id}`);
      const application = appsRes.data.find(a => a.candidate_id === candidateId);
      if (!application) return;
      await API.delete(`/applications/${application.id}`);
      const res = await API.get(`/jobs/${id}/match`);
      setResults(res.data);
    } catch (err) {
      console.error(err);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 70) return '#27ae60';
    if (score >= 40) return '#f39c12';
    return '#e74c3c';
  };

  const getRankStyle = (index) => {
    if (index === 0) return { color: '#f1c40f', fontSize: '2rem' };
    if (index === 1) return { color: '#95a5a6', fontSize: '1.8rem' };
    if (index === 2) return { color: '#cd7f32', fontSize: '1.6rem' };
    return { color: '#bdc3c7', fontSize: '1.4rem' };
  };

  const ScoreBox = ({ r, showUnassign }) => (
    <div className="score-box">
      <div className="score-circle" style={{ borderColor: getScoreColor(r.match_score) }}>
        <span className="score-number" style={{ color: getScoreColor(r.match_score) }}>
          {r.match_score}%
        </span>
        <span className="score-label">match</span>
      </div>
      <div className="score-breakdown">
        <div className="breakdown-row">
          <span>Semantic</span>
          <span style={{ color: getScoreColor(r.semantic_score) }}>{r.semantic_score}%</span>
        </div>
        <div className="breakdown-row">
          <span>Experience</span>
          <span style={{ color: getScoreColor(r.experience_score) }}>{r.experience_score}%</span>
        </div>
        <div className="breakdown-row">
          <span>Education</span>
          <span style={{ color: getScoreColor(r.education_score) }}>{r.education_score}%</span>
        </div>
        {r.candidate_years > 0 && (
          <div className="breakdown-years">{r.candidate_years} yrs exp</div>
        )}
      </div>
      {showUnassign && (
        <button className="unassign-btn" onClick={() => handleUnassign(r.candidate.id)}>
          Unassign
        </button>
      )}
    </div>
  );

  const appliedResults = results.filter(r => r.applied);
  const otherResults = results.filter(r => !r.applied);

  return (
    <div className="page">
      <button className="back-btn" onClick={() => navigate('/jobs')}>← Back to Jobs</button>
      <h1>Candidate Match Results</h1>

      <div className="assign-box">
        <div className="assign-box-header">
          <h3>🎯 Assign Candidates to this Job</h3>
          <p>Select candidates from the list below and assign them to this job posting.</p>
        </div>
        <div className="assign-actions">
          <button className="select-btn" onClick={selectAll}>Select All</button>
          <button className="clear-btn" onClick={clearAll}>Clear</button>
          <button
            className="assign-btn"
            onClick={handleAssignSelected}
            disabled={selected.length === 0 || assigning}
          >
            {assigning ? 'Assigning...' : `✓ Assign (${selected.length})`}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="loading-box">
          <p>Calculating match scores...</p>
        </div>
      ) : (
        <>
          {appliedResults.length > 0 && (
            <div className="section">
              <div className="section-header applied-header">
                <span>✅ Applied Candidates</span>
                <span className="count-badge">{appliedResults.length}</span>
              </div>
              <div className="results-list">
                {appliedResults.map((r, index) => (
                  <div className="result-card applied-card" key={r.candidate.id}>
                    <div className="rank-box">
                      <span style={getRankStyle(index)}>#{index + 1}</span>
                    </div>
                    <div className="candidate-info">
                      <div className="name-row">
                        <h3>{r.candidate.full_name || 'Unknown'}</h3>
                        <span className={`status-badge ${r.application_status}`}>
                          {r.application_status}
                        </span>
                      </div>
                      <p className="candidate-email">{r.candidate.email || 'No email'}</p>
                      <div className="skills">
                        {(r.candidate.skills || []).slice(0, 6).map(s => (
                          <span key={s} className="skill-tag">{s}</span>
                        ))}
                        {(r.candidate.skills || []).length > 6 && (
                          <span className="skill-tag more">+{r.candidate.skills.length - 6}</span>
                        )}
                      </div>
                    </div>
                    <ScoreBox r={r} showUnassign={true} />
                  </div>
                ))}
              </div>
            </div>
          )}

          {otherResults.length > 0 && (
            <div className="section">
              <div className="section-header other-header">
                <span>👥 Other Candidates</span>
                <span className="count-badge">{otherResults.length}</span>
              </div>
              <div className="results-list">
                {otherResults.map((r, index) => (
                  <div
                    className={`result-card other-card ${selected.includes(r.candidate.id) ? 'selected-card' : ''}`}
                    key={r.candidate.id}
                    onClick={() => toggleSelect(r.candidate.id)}
                  >
                    <input
                      type="checkbox"
                      className="candidate-checkbox"
                      checked={selected.includes(r.candidate.id)}
                      onChange={() => toggleSelect(r.candidate.id)}
                      onClick={e => e.stopPropagation()}
                    />
                    <div className="rank-box">
                      <span style={getRankStyle(index)}>#{index + 1}</span>
                    </div>
                    <div className="candidate-info">
                      <h3>{r.candidate.full_name || 'Unknown'}</h3>
                      <p className="candidate-email">{r.candidate.email || 'No email'}</p>
                      <div className="skills">
                        {(r.candidate.skills || []).slice(0, 6).map(s => (
                          <span key={s} className="skill-tag">{s}</span>
                        ))}
                        {(r.candidate.skills || []).length > 6 && (
                          <span className="skill-tag more">+{r.candidate.skills.length - 6}</span>
                        )}
                      </div>
                    </div>
                    <ScoreBox r={r} showUnassign={false} />
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default MatchResults;