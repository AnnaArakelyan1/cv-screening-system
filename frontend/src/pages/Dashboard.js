import React, { useEffect, useState } from 'react';
import API from '../api';
import Toast from '../components/Toast';
import { useAuth } from '../context/AuthContext';
import './Dashboard.css';

const PAGE_SIZE = 25;

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

const SortIcon = ({ col, sortCol, sortDir }) =>
  sortCol !== col
    ? <span className="sort-icon sort-inactive">↕</span>
    : <span className="sort-icon">{sortDir === 'asc' ? '↑' : '↓'}</span>;

const SEARCH_OPTIONS = [
  { value: 'all',   label: 'All fields' },
  { value: 'name',  label: 'Name' },
  { value: 'email', label: 'Email' },
  { value: 'skill', label: 'Skill' },
];

const Dashboard = () => {
  const [allCandidates, setAllCandidates] = useState([]);
  const [filtered, setFiltered]           = useState([]);
  const [jobMap, setJobMap]               = useState({});   // candidateId -> [jobTitle, ...]
  const [search, setSearch]               = useState('');
  const [searchBy, setSearchBy]           = useState('all');
  const [loading, setLoading]             = useState(true);
  const [toast, setToast]                 = useState(null);
  const [stats, setStats]                 = useState({ total: 0, openJobs: 0, newThisWeek: 0 });
  const [page, setPage]                   = useState(1);
  const [sortCol, setSortCol]             = useState('uploaded_at');
  const [sortDir, setSortDir]             = useState('desc');
  const [expandedSkills, setExpandedSkills] = useState(new Set());

  const { user } = useAuth();
  const showToast = (msg, type = 'success') => setToast({ message: msg, type });

  useEffect(() => {
    const load = async () => {
      try {
        const [cRes, jRes, appRes] = await Promise.all([
          API.get('/candidates/'),
          API.get('/jobs/'),
          API.get('/applications/'),
        ]);
        const all  = cRes.data;
        const jobs = jRes.data;
        const apps = appRes.data;

        // Build candidateId -> [job titles]
        const jById = Object.fromEntries(jobs.map(j => [j.id, j.title]));
        const map = {};
        apps.forEach(a => {
          if (!map[a.candidate_id]) map[a.candidate_id] = [];
          if (jById[a.job_id]) map[a.candidate_id].push(jById[a.job_id]);
        });

        setAllCandidates(all);
        setFiltered(all);
        setJobMap(map);

        const weekAgo = new Date(); weekAgo.setDate(weekAgo.getDate() - 7);
        setStats({
          total: all.length,
          openJobs: jobs.filter(j => j.is_open).length,
          newThisWeek: all.filter(c => new Date(c.uploaded_at) >= weekAgo).length,
        });
      } catch (err) { console.error(err); }
      setLoading(false);
    };
    load();
  }, []);

  useEffect(() => {
    if (!search.trim()) { setFiltered(allCandidates); setPage(1); return; }
    const terms = search.toLowerCase().split(',').map(s => s.trim()).filter(Boolean);
    setFiltered(allCandidates.filter(c => {
      const name  = (c.full_name || '').toLowerCase().trim();
      const email = (c.email || '').toLowerCase().trim();
      const skills = (c.skills || []);
      if (searchBy === 'name')  return terms.some(t => name.includes(t));
      if (searchBy === 'email') return terms.some(t => email.includes(t));
      if (searchBy === 'skill') return terms.every(t => skills.some(s => s.toLowerCase().includes(t)));
      return terms.some(t =>
        name.includes(t) ||
        email.includes(t) ||
        skills.some(s => s.toLowerCase().includes(t))
      );
    }));
    setPage(1);
  }, [search, searchBy, allCandidates]);

  const handleClear = () => { setSearch(''); setPage(1); };

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this candidate?')) return;
    try {
      await API.delete(`/candidates/${id}`);
      const next = allCandidates.filter(c => c.id !== id);
      setAllCandidates(next);
      showToast('Candidate deleted.');
    } catch (err) {
      showToast(err.response?.status === 403 ? 'You can only delete candidates you uploaded.' : 'Failed to delete.', 'error');
    }
  };

  const handleSort = (col) => {
    setSortDir(sortCol === col ? (sortDir === 'asc' ? 'desc' : 'asc') : 'asc');
    setSortCol(col);
    setPage(1);
  };

  const sorted = [...filtered].sort((a, b) => {
    let av, bv;
    if (sortCol === 'uploaded_at') { av = new Date(a.uploaded_at); bv = new Date(b.uploaded_at); }
    else if (sortCol === 'skills') { av = (a.skills || []).length; bv = (b.skills || []).length; }
    else { av = String(a[sortCol] ?? '').toLowerCase(); bv = String(b[sortCol] ?? '').toLowerCase(); }
    return av < bv ? (sortDir === 'asc' ? -1 : 1) : av > bv ? (sortDir === 'asc' ? 1 : -1) : 0;
  });

  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));
  const rows = sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  const isSearchActive = search.trim().length > 0;

  const highlightTerms = search.toLowerCase().split(',').map(t => t.trim()).filter(Boolean);
  const isHighlighted = (val) =>
    isSearchActive && (searchBy === 'skill' || searchBy === 'all') &&
    highlightTerms.some(t => val.toLowerCase().includes(t));

  return (
    <div className="page">
      <h1>Candidates</h1>

      <div className="stats-row">
        <div className="stat-card stat-card--blue">
          <div className="stat-value">{stats.total}</div>
          <div className="stat-label">Total Candidates</div>
        </div>
        <div className="stat-card stat-card--green">
          <div className="stat-value">{stats.openJobs}</div>
          <div className="stat-label">Open Jobs</div>
        </div>
        <div className="stat-card stat-card--purple">
          <div className="stat-value">{stats.newThisWeek}</div>
          <div className="stat-label">New This Week</div>
        </div>
      </div>

      <div className="table-toolbar">
        <div className="search-bar">
          <select
            value={searchBy}
            onChange={e => setSearchBy(e.target.value)}
            className="search-select"
          >
            {SEARCH_OPTIONS.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
          <input
            type="text"
            placeholder={
              searchBy === 'name'  ? 'Search by name…' :
              searchBy === 'email' ? 'Search by email…' :
              searchBy === 'skill' ? 'Search by skill (comma-separated)…' :
              'Search candidates…'
            }
            value={search}
            onChange={e => setSearch(e.target.value)}
            autoComplete="off"
          />
          {isSearchActive && <button type="button" onClick={handleClear}>Clear</button>}
        </div>
      </div>

      {loading ? <p>Loading...</p> : sorted.length === 0 ? (
        <p className="empty-msg">No candidates found{isSearchActive ? ` for "${search}"` : ''}.</p>
      ) : (
        <>
          <div className="table-wrap">
            <table className="candidates-table">
              <thead>
                <tr>
                  <th className="sortable" onClick={() => handleSort('full_name')}>
                    Name <SortIcon col="full_name" sortCol={sortCol} sortDir={sortDir} />
                  </th>
                  <th className="sortable" onClick={() => handleSort('email')}>
                    Email <SortIcon col="email" sortCol={sortCol} sortDir={sortDir} />
                  </th>
                  <th>Phone</th>
                  <th className="sortable" onClick={() => handleSort('skills')}>
                    Skills <SortIcon col="skills" sortCol={sortCol} sortDir={sortDir} />
                  </th>
                  <th>Applied For</th>
                  <th className="sortable" onClick={() => handleSort('uploaded_at')}>
                    Uploaded <SortIcon col="uploaded_at" sortCol={sortCol} sortDir={sortDir} />
                  </th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {rows.map(c => (
                  <tr key={c.id}>
                    <td className="td-name">{c.full_name || <span className="unknown">Unknown</span>}</td>
                    <td className="td-muted">{c.email || '—'}</td>
                    <td className="td-muted">{c.phone || '—'}</td>
                    <td>
                      <div className="skills-cell">
                        {(expandedSkills.has(c.id) ? (c.skills || []) : (c.skills || []).slice(0, 4)).map(s => (
                          <span key={s} className={`skill-tag${isHighlighted(s) ? ' highlighted' : ''}`}>{s}</span>
                        ))}
                        {(c.skills || []).length > 4 && (
                          <span
                            className="skill-tag more"
                            onClick={() => setExpandedSkills(prev => {
                              const next = new Set(prev);
                              next.has(c.id) ? next.delete(c.id) : next.add(c.id);
                              return next;
                            })}
                          >
                            {expandedSkills.has(c.id) ? '▲ less' : `+${c.skills.length - 4}`}
                          </span>
                        )}
                      </div>
                    </td>
                    <td>
                      <div className="applied-for-cell">
                        {(jobMap[c.id] || []).length === 0
                          ? <span className="td-muted">—</span>
                          : (jobMap[c.id] || []).map((title, i) => (
                              <span key={i} className="job-pill">{title}</span>
                            ))
                        }
                      </div>
                    </td>
                    <td className="td-muted td-date">{new Date(c.uploaded_at).toLocaleDateString()}</td>
                    <td>
                      <div className="row-actions">
                        {c.cv_filename && (
                          <button className="act-btn act-download" onClick={() => downloadCV(c.id, c.cv_filename)}>↓ CV</button>
                        )}
                        {user?.is_admin && (
                          <button className="act-btn act-delete" onClick={() => handleDelete(c.id)}>Delete</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="pagination">
              <button onClick={() => setPage(p => p - 1)} disabled={page === 1}>← Prev</button>
              <span>{page} / {totalPages}</span>
              <button onClick={() => setPage(p => p + 1)} disabled={page === totalPages}>Next →</button>
            </div>
          )}
        </>
      )}

      {toast && <Toast message={toast.message} type={toast.type} onClose={() => setToast(null)} />}
    </div>
  );
};

export default Dashboard;
