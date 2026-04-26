import React, { useEffect, useState, useCallback } from 'react';
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
  const [showRejected, setShowRejected] = useState(false);
  const [showShortlisted, setShowShortlisted] = useState(true);
  const [expandedAnalysis, setExpandedAnalysis] = useState({});
  const navigate = useNavigate();

  const fetchData = useCallback(async () => {
    try {
      const res = await API.get(`/jobs/${id}/match`);
      setResults(res.data.results);
      return res.data.results;
    } catch (err) {
      console.error(err);
      return [];
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    let timer;
    const poll = async () => {
      const data = await fetchData();
      if (data.some(r => r.processing)) {
        timer = setTimeout(poll, 5000);
      }
    };
    poll();
    return () => clearTimeout(timer);
  }, [fetchData]);

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

  const anonymizeAnalysis = (analysis, candidate) => {
    if (!analysis) return analysis;
    let text = analysis;
    const name = candidate.full_name;
    if (name && name.trim()) {
      const parts = name.trim().split(/\s+/).filter(p => p.length > 2);
      [name, ...parts].forEach(term => {
        text = text.replace(new RegExp(term, 'gi'), 'This candidate');
      });
    }
    // Replace gendered/singular pronouns, fixing verb agreement too
    text = text.replace(/\b(He|She) is\b/g, 'They are');
    text = text.replace(/\b(he|she) is\b/g, 'they are');
    text = text.replace(/\b(He|She) was\b/g, 'They were');
    text = text.replace(/\b(he|she) was\b/g, 'they were');
    text = text.replace(/\b(He|She) has\b/g, 'They have');
    text = text.replace(/\b(he|she) has\b/g, 'they have');
    text = text.replace(/\b(He|She) does\b/g, 'They do');
    text = text.replace(/\b(he|she) does\b/g, 'they do');
    text = text.replace(/\bHis\b/g, 'Their');
    text = text.replace(/\bHer\b/g, 'Their');
    text = text.replace(/\bhis\b/g, 'their');
    text = text.replace(/\bher\b/g, 'their');
    text = text.replace(/\bHe\b/g, 'They');
    text = text.replace(/\bShe\b/g, 'They');
    text = text.replace(/\bhe\b/g, 'they');
    text = text.replace(/\bshe\b/g, 'they');
    text = text.replace(/\bHim\b/g, 'Them');
    text = text.replace(/\bhim\b/g, 'them');
    return text.replace(/^This candidate\s+this candidate/i, 'This candidate');
  };

  const getScoreColor = (score) => {
    if (score >= 70) return '#34d399';
    if (score >= 40) return '#fbbf24';
    return '#f87171';
  };

  const matchLabel = (val) => {
    if (val === 'exceeds') return { text: '↑', color: '#34d399' };
    if (val === 'meets')   return { text: '✓', color: '#34d399' };
    if (val === 'below')   return { text: '↓', color: '#f87171' };
    return { text: '—', color: '#7880a0' };
  };

  const renderCard = (r, rank) => {
    const status = r.application_status;

    if (r.processing) {
      return (
        <div className="result-card result-card--processing" key={r.candidate.id}>
          <div className="rc-rank" style={{ color: '#7880a0' }}>#{rank}</div>
          <div className="rc-info">
            <div className="rc-name-row">
              <span className="rc-name">{r.candidate.full_name || 'Unknown'}</span>
              <span className={`status-badge ${status}`}>{STATUS_LABELS[status] || status}</span>
            </div>
            <div className="rc-email">{r.candidate.email || '—'}</div>
          </div>
          <div className="rc-score-col">
            <div className="processing-label">Calculating...</div>
          </div>
          <div className="rc-detail-col" />
          <div className="rc-actions">
            {r.candidate.cv_filename && (
              <button className="act-sm act-cv" onClick={() => downloadCV(r.candidate.id, r.candidate.cv_filename)}>↓ CV</button>
            )}
          </div>
        </div>
      );
    }

    const expL = matchLabel(r.experience_match);
    const eduL = matchLabel(r.education_match);

    return (
      <div className={`result-card result-card--${status}`} key={r.candidate.id}>
        <div className="rc-rank" style={{ color: getScoreColor(r.match_score) }}>#{rank}</div>

        <div className="rc-info">
          <div className="rc-name-row">
            <span className="rc-name">{r.candidate.full_name || 'Unknown'}</span>
            <span className={`status-badge ${status}`}>{STATUS_LABELS[status] || status}</span>
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
          {r.analysis && (
            <div>
              <p
                className="rc-analysis"
                style={expandedAnalysis[r.candidate.id] ? { WebkitLineClamp: 'unset', lineClamp: 'unset' } : {}}
              >{anonymizeAnalysis(r.analysis, r.candidate)}</p>
              <button
                className="rc-expand-btn"
                onClick={() => setExpandedAnalysis(prev => ({ ...prev, [r.candidate.id]: !prev[r.candidate.id] }))}
              >{expandedAnalysis[r.candidate.id] ? 'Show less ▲' : 'Read more ▼'}</button>
            </div>
          )}
          {(r.matched_skills || []).length > 0 && (
            <div className="rc-chip-row">
              {r.matched_skills.map(s => (
                <span key={s} className="skill-match-tag matched">{s}</span>
              ))}
            </div>
          )}
          {(r.missing_skills || []).length > 0 && (
            <div className="rc-chip-row">
              {r.missing_skills.map(s => (
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

          {(status === 'applied' || status === 'reviewed') && (<>
            <button className="act-sm act-shortlist" onClick={() => handleStatusChange(r.candidate.id, 'shortlisted')}>
              Interview
            </button>
            <button className="act-sm act-reject" onClick={() => handleStatusChange(r.candidate.id, 'rejected')}>
              Reject
            </button>
          </>)}

          {status === 'shortlisted' && (<>
            <button className="act-sm act-accept" onClick={() => handleStatusChange(r.candidate.id, 'accepted')}>
              Hire
            </button>
            <button className="act-sm act-reject" onClick={() => handleStatusChange(r.candidate.id, 'rejected')}>
              Reject
            </button>
            <button className="act-sm act-restore" onClick={() => handleStatusChange(r.candidate.id, 'applied')}>
              Undo
            </button>
          </>)}

          {(status === 'accepted' || status === 'rejected') && (
            <button className="act-sm act-restore" onClick={() => handleStatusChange(r.candidate.id, 'applied')}>
              Restore
            </button>
          )}

          <button className="act-sm act-remove" onClick={() => handleUnassign(r.candidate.id)}>Remove</button>
        </div>
      </div>
    );
  };

  const STATUS_LABELS = {
    applied: 'Pending',
    reviewed: 'Reviewed',
    shortlisted: 'Interview',
    accepted: 'Hired',
    rejected: 'Rejected',
  };

  const byScore = [...results].sort((a, b) => b.match_score - a.match_score);
  const scoreRank = Object.fromEntries(byScore.map((r, i) => [r.candidate.id, i + 1]));

  const shortlisted = results.filter(r => r.application_status === 'shortlisted');
  const pending     = results.filter(r => ['applied', 'reviewed'].includes(r.application_status));
  const accepted    = results.filter(r => r.application_status === 'accepted');
  const rejected    = results.filter(r => r.application_status === 'rejected');

  return (
    <div className="page">
      <button className="back-btn" onClick={() => navigate('/jobs')}>← Back to Jobs</button>
      <h1>Candidate Match Results</h1>

      {loading ? (
        <div className="loading-box"><p>Calculating match scores...</p></div>
      ) : results.length === 0 ? (
        <p className="empty-msg">No candidates have applied for this job yet.</p>
      ) : (
        <>
          {shortlisted.length > 0 && (
            <div className="section">
              <div
                className="section-header shortlisted-header"
                onClick={() => setShowShortlisted(v => !v)}
                style={{ cursor: 'pointer' }}
              >
                <span>Called for Interview</span>
                <span className="count-badge">{shortlisted.length}</span>
                <span className="toggle-arrow">{showShortlisted ? '▲' : '▼'}</span>
              </div>
              {showShortlisted && (
                <div className="results-list">
                  {shortlisted.map(r => renderCard(r, scoreRank[r.candidate.id]))}
                </div>
              )}
            </div>
          )}

          {accepted.length > 0 && (
            <div className="section">
              <div className="section-header accepted-header">
                <span>Hired</span>
                <span className="count-badge">{accepted.length}</span>
              </div>
              <div className="results-list">
                {accepted.map(r => renderCard(r, scoreRank[r.candidate.id]))}
              </div>
            </div>
          )}

          {pending.length > 0 && (
            <div className="section">
              <div className="section-header pending-header">
                <span>Pending Review</span>
                <span className="count-badge">{pending.length}</span>
              </div>
              <div className="results-list">
                {pending.map(r => renderCard(r, scoreRank[r.candidate.id]))}
              </div>
            </div>
          )}

          {rejected.length > 0 && (
            <div className="section">
              <div
                className="section-header rejected-header"
                onClick={() => setShowRejected(v => !v)}
                style={{ cursor: 'pointer' }}
              >
                <span>Rejected</span>
                <span className="count-badge">{rejected.length}</span>
                <span className="toggle-arrow">{showRejected ? '▲' : '▼'}</span>
              </div>
              {showRejected && (
                <div className="results-list">
                  {rejected.map(r => renderCard(r, scoreRank[r.candidate.id]))}
                </div>
              )}
            </div>
          )}
        </>
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
