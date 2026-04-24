import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import API from '../api';
import './MatchResults.css';

const downloadCV = async (candidateId, filename) => {
  try {
    const res = await API.get(`/candidates/${candidateId}/cv`, { responseType: 'blob' });
    const url = URL.createObjectURL(res.data);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || `cv_${candidateId}`;
    a.click();
    URL.revokeObjectURL(url);
  } catch {
    alert('CV file not available.');
  }
};

const MatchResults = () => {
  const { id } = useParams();
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(true);
  const [emailModal, setEmailModal] = useState(null);
  const [emailForm, setEmailForm] = useState({ subject: '', body: '' });
  const [sending, setSending] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    const fetchData = async () => {
      try {
        const matchRes = await API.get(`/jobs/${id}/match`);
        setResults(matchRes.data.results);
      } catch (err) {
        console.error(err);
      }
      setLoading(false);
    };
    fetchData();
  }, [id]);

  const handleStatusChange = async (candidateId, status) => {
    try {
      const appsRes = await API.get(`/applications/job/${id}`);
      const application = appsRes.data.find(a => a.candidate_id === candidateId);
      if (!application) return;
      await API.patch(`/applications/${application.id}/status?status=${status}`);
      const res = await API.get(`/jobs/${id}/match`);
      setResults(res.data.results);
    } catch (err) {
      console.error(err);
    }
  };

  const handleUnassign = async (candidateId) => {
    if (!window.confirm('Remove this candidate from the job?')) return;
    try {
      const appsRes = await API.get(`/applications/job/${id}`);
      const application = appsRes.data.find(a => a.candidate_id === candidateId);
      if (!application) return;
      await API.delete(`/applications/${application.id}`);
      const res = await API.get(`/jobs/${id}/match`);
      setResults(res.data.results);
    } catch (err) {
      console.error(err);
    }
  };

  const openEmailModal = (candidate) => {
    setEmailModal(candidate);
    setEmailForm({
      subject: `Regarding your application`,
      body: `Dear ${candidate.full_name || 'Candidate'},\n\nThank you for your application. We would like to inform you that...\n\nBest regards,\nHR Team`
    });
  };

  const handleSendEmail = async () => {
    if (!emailForm.subject || !emailForm.body) return;
    setSending(true);
    try {
      await API.post('/email/send', {
        to_email: emailModal.email,
        subject: emailForm.subject,
        body: emailForm.body
      });
      alert(`Email sent to ${emailModal.email}`);
      setEmailModal(null);
    } catch {
      alert('Failed to send email. Check your email credentials in backend/.env');
    }
    setSending(false);
  };

  const getScoreColor = (score) => {
    if (score >= 70) return '#34d399';
    if (score >= 40) return '#fbbf24';
    return '#f87171';
  };

  const getRankEmoji = (index) => {
    if (index === 0) return { label: '#1', color: '#fbbf24' };
    if (index === 1) return { label: '#2', color: '#a99cf8' };
    if (index === 2) return { label: '#3', color: '#f87171' };
    return { label: `#${index + 1}`, color: '#7880a0' };
  };

  const matchLabel = (val) => {
    if (val === 'exceeds') return { text: '↑', color: '#34d399' };
    if (val === 'meets')   return { text: '✓', color: '#34d399' };
    if (val === 'below')   return { text: '↓', color: '#f87171' };
    return { text: '—', color: '#7880a0' };
  };

  return (
    <div className="page">
      <button className="back-btn" onClick={() => navigate('/jobs')}>← Back to Jobs</button>
      <h1>Candidate Match Results</h1>

      {loading ? (
        <div className="loading-box"><p>Calculating match scores...</p></div>
      ) : results.length === 0 ? (
        <p className="empty-msg">No candidates have applied for this job yet.</p>
      ) : (
        <div className="section">
          <div className="section-header applied-header">
            <span>Applicants</span>
            <span className="count-badge">{results.length}</span>
          </div>
          <div className="results-list">
            {results.map((r, index) => {
              const rank = getRankEmoji(index);
              const expL = matchLabel(r.experience_match);
              const eduL = matchLabel(r.education_match);
              return (
                <div className="result-card" key={r.candidate.id}>
                  <div className="rc-rank" style={{ color: rank.color }}>{rank.label}</div>

                  <div className="rc-info">
                    <div className="rc-name-row">
                      <span className="rc-name">{r.candidate.full_name || 'Unknown'}</span>
                      <span className={`status-badge ${r.application_status}`}>{r.application_status}</span>
                    </div>
                    <div className="rc-email">{r.candidate.email || '—'}</div>
                    <div className="rc-skills">
                      {(r.candidate.skills || []).slice(0, 5).map(s => (
                        <span key={s} className="skill-tag">{s}</span>
                      ))}
                      {(r.candidate.skills || []).length > 5 && (
                        <span className="skill-tag more">+{r.candidate.skills.length - 5}</span>
                      )}
                    </div>
                  </div>

                  <div className="rc-score-col">
                    <div className="score-circle" style={{ borderColor: getScoreColor(r.match_score) }}>
                      <span className="score-number" style={{ color: getScoreColor(r.match_score) }}>{r.match_score}%</span>
                      <span className="score-label">match</span>
                    </div>
                    <div className="rc-breakdown">
                      <span>Exp <span style={{ color: expL.color }}>{expL.text}</span></span>
                      <span>Edu <span style={{ color: eduL.color }}>{eduL.text}</span></span>
                    </div>
                  </div>

                  <div className="rc-detail-col">
                    {r.analysis && <p className="rc-analysis">{r.analysis}</p>}
                    {(r.matched_skills || []).length > 0 && (
                      <div className="rc-chip-row">
                        {r.matched_skills.slice(0, 3).map(s => (
                          <span key={s} className="skill-match-tag matched">{s}</span>
                        ))}
                      </div>
                    )}
                    {(r.missing_skills || []).length > 0 && (
                      <div className="rc-chip-row">
                        {r.missing_skills.slice(0, 2).map(s => (
                          <span key={s} className="skill-match-tag missing">{s}</span>
                        ))}
                      </div>
                    )}
                  </div>

                  <div className="rc-actions">
                    {r.candidate.cv_filename && (
                      <button className="act-sm act-cv" onClick={() => downloadCV(r.candidate.id, r.candidate.cv_filename)}>↓ CV</button>
                    )}
                    <button className="act-sm act-email" onClick={() => openEmailModal(r.candidate)}>✉</button>
                    <button
                      className={`act-sm act-accept ${r.application_status === 'accepted' ? 'active' : ''}`}
                      onClick={() => handleStatusChange(r.candidate.id, 'accepted')}
                      disabled={r.application_status === 'accepted'}
                    >✓</button>
                    <button
                      className={`act-sm act-reject ${r.application_status === 'rejected' ? 'active' : ''}`}
                      onClick={() => handleStatusChange(r.candidate.id, 'rejected')}
                      disabled={r.application_status === 'rejected'}
                    >✕</button>
                    <button className="act-sm act-remove" onClick={() => handleUnassign(r.candidate.id)}>Remove</button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {emailModal && (
        <div className="modal-overlay" onClick={() => setEmailModal(null)}>
          <div className="modal" onClick={e => e.stopPropagation()}>
            <h3>Send Email to {emailModal.full_name || 'Candidate'}</h3>
            <p className="modal-to">To: {emailModal.email}</p>
            <input
              type="text"
              placeholder="Subject"
              value={emailForm.subject}
              onChange={e => setEmailForm({ ...emailForm, subject: e.target.value })}
            />
            <textarea
              placeholder="Message body"
              rows={8}
              value={emailForm.body}
              onChange={e => setEmailForm({ ...emailForm, body: e.target.value })}
            />
            <div className="modal-actions">
              <button className="assign-btn" onClick={handleSendEmail} disabled={sending}>
                {sending ? 'Sending...' : 'Send Email'}
              </button>
              <button className="clear-btn" onClick={() => setEmailModal(null)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default MatchResults;
