import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import API from '../api';
import Toast from '../components/Toast';
import { useAuth } from '../context/AuthContext';
import './Jobs.css';

const Jobs = () => {
  const [jobs, setJobs]       = useState([]);
  const [filtered, setFiltered] = useState([]);
  const [search, setSearch]   = useState('');
  const [searchBy, setSearchBy] = useState('all');
  const [statusFilter, setStatusFilter] = useState('all');
  const [form, setForm]       = useState({
    title: '', description: '', required_skills: '',
    required_experience_years: 0, required_education: '', deadline: ''
  });
  const [deadlineEdit, setDeadlineEdit] = useState(null);
  const [loading, setLoading] = useState(false);
  const [toast, setToast]     = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [expandedSkills, setExpandedSkills] = useState(new Set());
  const [reportModal, setReportModal] = useState(null);
  const navigate = useNavigate();

  const { user } = useAuth();
  const showToast = (msg, type = 'success') => setToast({ message: msg, type });

  const fetchJobs = async () => {
    try {
      const res = await API.get('/jobs/');
      setJobs(res.data);
      setFiltered(res.data);
    } catch (err) {
      if (err.code !== 'ERR_CANCELED') showToast('Failed to load jobs.', 'error');
    }
  };

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 15000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    let out = jobs;
    if (statusFilter !== 'all') out = out.filter(j => statusFilter === 'open' ? j.is_open : !j.is_open);
    if (search.trim()) {
      const terms = search.toLowerCase().split(',').map(s => s.trim()).filter(Boolean);
      out = out.filter(j => {
        const title = j.title.toLowerCase();
        const skills = j.required_skills || [];
        const desc = (j.description || '').toLowerCase();
        if (searchBy === 'title') return terms.some(t => title.includes(t));
        if (searchBy === 'skill') return terms.every(t => skills.some(s => s.toLowerCase().includes(t)));
        return terms.some(t => title.includes(t) || desc.includes(t) || skills.some(s => s.toLowerCase().includes(t)));
      });
    }
    setFiltered(out);
  }, [search, searchBy, statusFilter, jobs]);

  const copyLink = (jobId) => {
    navigator.clipboard.writeText(`${window.location.origin}/apply/${jobId}`);
    setCopiedId(jobId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await API.post('/jobs/', {
        ...form,
        required_skills: form.required_skills.split(',').map(s => s.trim()).filter(Boolean),
        required_experience_years: parseInt(form.required_experience_years) || 0,
        deadline: form.deadline ? new Date(form.deadline).toISOString() : null,
      });
      setForm({ title: '', description: '', required_skills: '', required_experience_years: 0, required_education: '', deadline: '' });
      setShowForm(false);
      await fetchJobs();
      showToast('Job created successfully!');
    } catch {
      showToast('Failed to create job.', 'error');
    }
    setLoading(false);
  };

  const handleToggle = async (id) => {
    try {
      const res = await API.patch(`/jobs/${id}/toggle`);
      const next = jobs.map(j => j.id === id ? { ...j, is_open: res.data.is_open } : j);
      setJobs(next);
    } catch {
      showToast('Failed to update job status.', 'error');
    }
  };

  const handleDeadlineSave = async (job) => {
    try {
      await API.patch(`/jobs/${job.id}`, {
        deadline: deadlineEdit.value ? new Date(deadlineEdit.value).toISOString() : null
      });
      await fetchJobs();
      setDeadlineEdit(null);
    } catch {
      showToast('Failed to update deadline.', 'error');
    }
  };

  const fetchReport = async (job) => {
    try {
      const res = await API.get(`/jobs/${job.id}/report`);
      setReportModal({ job, ...res.data });
    } catch {
      showToast('No report available for this job.', 'error');
    }
  };

  const downloadReportPDF = async (job) => {
    try {
      const res = await API.get(`/jobs/${job.id}/report/pdf`, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `report_${job.title.replace(/\s+/g, '_')}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      showToast('Failed to download report.', 'error');
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this job posting?')) return;
    try {
      await API.delete(`/jobs/${id}`);
      const next = jobs.filter(j => j.id !== id);
      setJobs(next);
      showToast('Job deleted.');
    } catch (err) {
      showToast(err.response?.status === 403 ? 'You can only delete your own job postings.' : 'Failed to delete.', 'error');
    }
  };

  return (
    <div className="page">
      <h1>Job Postings</h1>

      <div className="jobs-toolbar">
        <div className="jobs-search-row">
          <select
            className="jobs-status-select"
            value={searchBy}
            onChange={e => setSearchBy(e.target.value)}
          >
            <option value="all">All fields</option>
            <option value="title">Title</option>
            <option value="skill">Skill</option>
          </select>
          <input
            type="text"
            className="jobs-search-input"
            placeholder={
              searchBy === 'title' ? 'Search by title…' :
              searchBy === 'skill' ? 'Search by skill (comma-separated)…' :
              'Search jobs…'
            }
            value={search}
            onChange={e => setSearch(e.target.value)}
            autoComplete="off"
          />
          <select
            className="jobs-status-select"
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
          >
            <option value="all">All statuses</option>
            <option value="open">Open</option>
            <option value="closed">Closed</option>
          </select>
        </div>
        <button className="new-job-btn" onClick={() => setShowForm(v => !v)}>
          {showForm ? '✕ Cancel' : '+ New Job'}
        </button>
      </div>

      {showForm && (
        <div className="job-form-box">
          <h2>Create New Job</h2>
          <form onSubmit={handleSubmit}>
            <input type="text" placeholder="Job Title" value={form.title}
              onChange={e => setForm({ ...form, title: e.target.value })} required />
            <textarea placeholder="Job Description" value={form.description}
              onChange={e => setForm({ ...form, description: e.target.value })} required />
            <input type="text" placeholder="Required Skills (comma separated)" value={form.required_skills}
              onChange={e => setForm({ ...form, required_skills: e.target.value })} />
            <input type="number" placeholder="Required Experience (years)" value={form.required_experience_years}
              onChange={e => setForm({ ...form, required_experience_years: e.target.value })} />
            <input type="text" placeholder="Required Education" value={form.required_education}
              onChange={e => setForm({ ...form, required_education: e.target.value })} />
            <label style={{ fontSize: '0.82rem', color: 'var(--muted)', marginBottom: '-0.5rem' }}>
              Application Deadline (optional)
            </label>
            <input type="datetime-local" value={form.deadline}
              onChange={e => setForm({ ...form, deadline: e.target.value })} />
            <button type="submit" disabled={loading}>{loading ? 'Creating…' : 'Create Job'}</button>
          </form>
        </div>
      )}

      {filtered.length === 0 ? (
        <p className="empty-msg">No jobs found{search ? ` for "${search}"` : ''}.</p>
      ) : (
        <div className="table-wrap">
          <table className="jobs-table">
            <thead>
              <tr>
                <th>Title</th>
                <th>Required Skills</th>
                <th>Exp.</th>
                <th>Education</th>
                <th>Deadline</th>
                <th>Status</th>
                <th>Apply Link</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(job => (
                <tr key={job.id}>
                  <td className="td-name">{job.title}</td>
                  <td>
                    <div className="skills-cell">
                      {(expandedSkills.has(job.id) ? (job.required_skills || []) : (job.required_skills || []).slice(0, 4)).map(s => (
                        <span key={s} className="skill-tag">{s}</span>
                      ))}
                      {(job.required_skills || []).length > 4 && (
                        <span
                          className="skill-tag more"
                          onClick={() => setExpandedSkills(prev => {
                            const next = new Set(prev);
                            next.has(job.id) ? next.delete(job.id) : next.add(job.id);
                            return next;
                          })}
                        >
                          {expandedSkills.has(job.id) ? '▲ less' : '+' + (job.required_skills.length - 4)}
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="td-muted td-center">
                    {job.required_experience_years ? `${job.required_experience_years}y` : '—'}
                  </td>
                  <td className="td-muted">{job.required_education || '—'}</td>
                  <td className="td-deadline">
                    {deadlineEdit?.id === job.id ? (
                      <div className="deadline-edit">
                        <input
                          type="datetime-local"
                          value={deadlineEdit.value}
                          onChange={e => setDeadlineEdit({ ...deadlineEdit, value: e.target.value })}
                          className="deadline-input"
                        />
                        <div className="deadline-edit-actions">
                          <button className="act-btn act-open" onClick={() => handleDeadlineSave(job)}>Save</button>
                          <button className="act-btn" style={{background:'#f1f5f9',color:'var(--muted)',border:'1.5px solid var(--border)'}} onClick={() => setDeadlineEdit(null)}>Cancel</button>
                        </div>
                      </div>
                    ) : (
                      <div className="deadline-display" onClick={() => setDeadlineEdit({ id: job.id, value: job.deadline ? new Date(job.deadline).toISOString().slice(0,16) : '' })}>
                        {job.deadline
                          ? <span className={new Date(job.deadline) < new Date() ? 'deadline-passed' : 'deadline-active'}>
                              {new Date(job.deadline).toLocaleDateString()}
                            </span>
                          : <span className="deadline-none">Set deadline</span>
                        }
                      </div>
                    )}
                  </td>
                  <td>
                    {(() => {
                      const expired = !job.is_open && job.deadline && new Date(job.deadline) < new Date();
                      return (
                        <span className={`job-status ${job.is_open ? 'open' : expired ? 'expired' : 'closed'}`}>
                          {job.is_open ? 'Open' : expired ? 'Expired' : 'Closed'}
                        </span>
                      );
                    })()}
                  </td>
                  <td>
                    <button className="copy-btn" onClick={() => copyLink(job.id)}>
                      {copiedId === job.id ? '✓ Copied' : 'Copy Link'}
                    </button>
                  </td>
                  <td>
                    <div className="row-actions">
                      <button className="act-btn act-match" onClick={() => navigate(`/jobs/${job.id}/match`)}>
                        Matches
                      </button>
                      <button
                        className={`act-btn ${job.is_open ? 'act-close' : 'act-open'}`}
                        onClick={() => handleToggle(job.id)}
                      >
                        {job.is_open ? 'Close' : 'Reopen'}
                      </button>
                      {!job.is_open && (
                        <button className="act-btn act-report" onClick={() => fetchReport(job)}>
                          Report
                        </button>
                      )}
                      {user?.is_admin && (
                        <button className="act-btn act-delete" onClick={() => handleDelete(job.id)}>
                          Delete
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {reportModal && (() => {
        const rd = reportModal.data;
        const sd = rd.score_distribution || {};
        const EXP_LABELS = { exceeds: 'Exceeds', meets: 'Meets', below: 'Below', unknown: '—' };
        const STATUS_LABELS = { applied: 'Pending', reviewed: 'Pending', shortlisted: 'Interview', accepted: 'Hired', rejected: 'Rejected' };
        const renderCandidate = (c, i) => (
          <div key={i} className="report-candidate">
            <div style={{ flex: 1 }}>
              <div className="report-cand-name">{c.name}</div>
              <div className="report-cand-email">{[c.email, c.phone].filter(Boolean).join(' · ') || '—'}</div>
              <div className="report-cand-meta">
                Exp: {EXP_LABELS[c.experience_match] || '—'} · Edu: {EXP_LABELS[c.education_match] || '—'}
              </div>
              {c.matched_skills?.length > 0 && (
                <div className="skills-cell" style={{ marginTop: '0.3rem' }}>
                  {c.matched_skills.map(s => <span key={s} className="skill-tag">{s}</span>)}
                </div>
              )}
              {c.missing_skills?.length > 0 && (
                <div className="report-missing">Missing: {c.missing_skills.join(', ')}</div>
              )}
              {c.analysis && <div className="report-analysis">{c.analysis}</div>}
            </div>
            {c.score != null && <div className="report-cand-score">{c.score}%</div>}
          </div>
        );
        return (
          <div className="modal-overlay" onClick={() => setReportModal(null)}>
            <div className="modal report-modal" onClick={e => e.stopPropagation()}>
              <h3>{rd.job_title}</h3>
              <p className="report-generated">
                Report generated {new Date(reportModal.generated_at).toLocaleDateString('en-US', { day: 'numeric', month: 'long', year: 'numeric' })}
              </p>

              <div className="report-stats">
                {[
                  { num: rd.total_applicants, label: 'Total' },
                  { num: rd.by_status.accepted, label: 'Hired' },
                  { num: rd.by_status.shortlisted, label: 'Shortlisted' },
                  { num: rd.by_status.rejected, label: 'Rejected' },
                  { num: rd.by_status.pending, label: 'Pending' },
                  { num: rd.avg_score != null ? `${rd.avg_score}%` : '—', label: 'Avg Score' },
                ].map(({ num, label }) => (
                  <div key={label} className="report-stat">
                    <div className="report-stat-num">{num}</div>
                    <div className="report-stat-label">{label}</div>
                  </div>
                ))}
              </div>

              {(sd.strong || sd.good || sd.moderate || sd.weak) ? (
                <div className="report-section">
                  <h4>Score Distribution</h4>
                  <div className="report-dist">
                    {[['Strong 80+', sd.strong, '#34d399'], ['Good 60+', sd.good, '#60a5fa'], ['Moderate 40+', sd.moderate, '#fbbf24'], ['Weak', sd.weak, '#f87171']].map(([lbl, val, col]) => (
                      <div key={lbl} className="report-dist-item">
                        <span className="report-dist-num" style={{ color: col }}>{val || 0}</span>
                        <span className="report-dist-label">{lbl}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              {rd.top_missing_skills?.length > 0 && (
                <div className="report-section">
                  <h4>Most Missing Skills</h4>
                  <div className="skills-cell">
                    {rd.top_missing_skills.map(s => <span key={s} className="skill-tag">{s}</span>)}
                  </div>
                </div>
              )}

              {rd.hired?.length > 0 && (
                <div className="report-section">
                  <h4>Hired ({rd.hired.length})</h4>
                  {rd.hired.map(renderCandidate)}
                </div>
              )}

              {rd.shortlisted?.length > 0 && (
                <div className="report-section">
                  <h4>Shortlisted — Not Hired ({rd.shortlisted.length})</h4>
                  {rd.shortlisted.map(renderCandidate)}
                </div>
              )}

              {rd.all_candidates?.length > 0 && (
                <div className="report-section">
                  <h4>All Candidates ({rd.all_candidates.length})</h4>
                  <table className="report-table">
                    <thead>
                      <tr><th>#</th><th>Name</th><th>Score</th><th>Status</th><th>Exp</th><th>Edu</th></tr>
                    </thead>
                    <tbody>
                      {rd.all_candidates.map((c, i) => (
                        <tr key={i}>
                          <td className="report-td-muted">{i + 1}</td>
                          <td>
                            <div>{c.name}</div>
                            <div className="report-td-sub">{c.email || ''}</div>
                          </td>
                          <td className="report-td-score">{c.score != null ? `${c.score}%` : '—'}</td>
                          <td><span className={`report-status-badge ${c.status}`}>{STATUS_LABELS[c.status] || c.status}</span></td>
                          <td className="report-td-muted">{EXP_LABELS[c.experience_match] || '—'}</td>
                          <td className="report-td-muted">{EXP_LABELS[c.education_match] || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {rd.required_skills?.length > 0 && (
                <div className="report-section">
                  <h4>Required Skills</h4>
                  <div className="skills-cell">
                    {rd.required_skills.map(s => <span key={s} className="skill-tag">{s}</span>)}
                  </div>
                </div>
              )}

              <div className="modal-actions" style={{ marginTop: '1.5rem' }}>
                <button className="act-btn act-match" onClick={() => downloadReportPDF(reportModal.job)}>Download PDF</button>
                <button className="cancel-btn" onClick={() => setReportModal(null)}>Close</button>
              </div>
            </div>
          </div>
        );
      })()}

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
};

export default Jobs;
