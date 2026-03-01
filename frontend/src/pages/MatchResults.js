import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import API from '../api';
import './MatchResults.css';

const MatchResults = () => {
  const { id } = useParams();
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const fetch = async () => {
      try {
        const res = await API.get(`/jobs/${id}/match`);
        setResults(res.data);
      } catch (err) {
        console.error(err);
      }
      setLoading(false);
    };
    fetch();
  }, [id]);

  const getScoreColor = (score) => {
    if (score >= 70) return '#27ae60';
    if (score >= 40) return '#f39c12';
    return '#e74c3c';
  };

  return (
    <div className="page">
      <button className="back-btn" onClick={() => navigate('/jobs')}>← Back to Jobs</button>
      <h1>Candidate Match Results</h1>

      {loading ? <p>Calculating matches...</p> : (
        <div className="results-list">
          {results.length === 0 ? (
            <p>No candidates found. Upload CVs first.</p>
          ) : results.map((r, index) => (
            <div className="result-card" key={r.candidate.id}>
              <div className="rank">#{index + 1}</div>
              <div className="candidate-info">
                <h3>{r.candidate.full_name || 'Unknown'}</h3>
                <p>{r.candidate.email || 'No email'}</p>
                <div className="skills">
                  {(r.candidate.skills || []).map(s => (
                    <span key={s} className="skill-tag">{s}</span>
                  ))}
                </div>
              </div>
              <div className="score-box">
                <div className="score" style={{ color: getScoreColor(r.match_score) }}>
                  {r.match_score}%
                </div>
                <div className="score-label">Match Score</div>
                <div className="score-bar">
                  <div
                    className="score-fill"
                    style={{ width: `${r.match_score}%`, background: getScoreColor(r.match_score) }}
                  />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default MatchResults;