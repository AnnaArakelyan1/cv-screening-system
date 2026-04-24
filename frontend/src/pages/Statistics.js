import React, { useEffect, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
  PieChart, Pie, Cell, LabelList,
} from 'recharts';
import API from '../api';
import './Statistics.css';

const COLORS = ['#27ae60', '#f39c12', '#e74c3c'];

const StatCard = ({ label, value, sub }) => (
  <div className="stat-card">
    <div className="stat-value">{value}</div>
    <div className="stat-label">{label}</div>
    {sub && <div className="stat-sub">{sub}</div>}
  </div>
);

const Statistics = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    API.get('/stats/').then(res => {
      setData(res.data);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, []);

  if (loading) return <div className="page"><p className="loading-text">Loading statistics...</p></div>;
  if (!data)   return <div className="page"><p>Failed to load statistics.</p></div>;

  return (
    <div className="page stats-page">
      <h1>Statistics</h1>

      <div className="stat-cards-row">
        <StatCard label="Total Candidates" value={data.total_candidates} />
        <StatCard label="Total Jobs" value={data.total_jobs} sub={`${data.open_jobs} open`} />
        <StatCard label="Applications" value={data.total_applications} />
        <StatCard
          label="Acceptance Rate"
          value={
            data.total_applications > 0
              ? `${Math.round((data.applications_by_status[0].count / data.total_applications) * 100)}%`
              : '—'
          }
        />
      </div>

      <div className="charts-grid">

        <div className="chart-card wide">
          <h3>Applicants per Job</h3>
          {data.candidates_per_job.length === 0 ? <p className="empty">No data yet.</p> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.candidates_per_job} margin={{ top: 10, right: 20, left: 0, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" />
                <XAxis dataKey="title" tick={{ fill: '#a0a0b0', fontSize: 12 }} angle={-30} textAnchor="end" interval={0} />
                <YAxis tick={{ fill: '#a0a0b0' }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: '#1e1e2e', border: '1px solid #2a2a3a', borderRadius: 8 }}
                  labelStyle={{ color: '#fff' }}
                  formatter={(value, name) => [value, name]}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.full_title || ''}
                />
                <Legend wrapperStyle={{ color: '#a0a0b0', paddingTop: 12 }} />
                <Bar dataKey="accepted" name="Accepted" stackId="a" fill="#27ae60" />
                <Bar dataKey="pending"  name="Pending"  stackId="a" fill="#f39c12" />
                <Bar dataKey="rejected" name="Rejected" stackId="a" fill="#e74c3c" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="chart-card">
          <h3>Application Status</h3>
          {data.total_applications === 0 ? <p className="empty">No applications yet.</p> : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie
                  data={data.applications_by_status}
                  dataKey="count"
                  nameKey="status"
                  cx="50%"
                  cy="50%"
                  outerRadius={90}
                  innerRadius={45}
                >
                  {data.applications_by_status.map((entry, i) => (
                    <Cell key={i} fill={COLORS[i]} />
                  ))}
                  <LabelList dataKey="count" position="outside" fill="#ccc" fontSize={13} />
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#1e1e2e', border: '1px solid #2a2a3a', borderRadius: 8 }}
                  formatter={(value, name) => [value, name]}
                />
                <Legend wrapperStyle={{ color: '#a0a0b0' }} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="chart-card">
          <h3>Match Score Distribution</h3>
          {data.score_distribution.every(b => b.count === 0) ? <p className="empty">No scores yet.</p> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.score_distribution} margin={{ top: 10, right: 10, left: 0, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" />
                <XAxis dataKey="range" tick={{ fill: '#a0a0b0', fontSize: 12 }} />
                <YAxis tick={{ fill: '#a0a0b0' }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: '#1e1e2e', border: '1px solid #2a2a3a', borderRadius: 8 }}
                  labelStyle={{ color: '#fff' }}
                />
                <Bar dataKey="count" name="Candidates" radius={[4, 4, 0, 0]}>
                  {data.score_distribution.map((entry, i) => {
                    const colors = ['#e74c3c', '#e67e22', '#f39c12', '#2ecc71', '#27ae60'];
                    return <Cell key={i} fill={colors[i]} />;
                  })}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="chart-card wide">
          <h3>Top Skills Across Candidates</h3>
          {data.top_skills.length === 0 ? <p className="empty">No skills data yet.</p> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart
                data={data.top_skills}
                layout="vertical"
                margin={{ top: 5, right: 30, left: 60, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" />
                <XAxis type="number" tick={{ fill: '#a0a0b0' }} allowDecimals={false} />
                <YAxis type="category" dataKey="skill" tick={{ fill: '#a0a0b0', fontSize: 12 }} width={80} />
                <Tooltip
                  contentStyle={{ background: '#1e1e2e', border: '1px solid #2a2a3a', borderRadius: 8 }}
                  labelStyle={{ color: '#fff' }}
                />
                <Bar dataKey="count" name="Candidates" fill="#6c63ff" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        <div className="chart-card">
          <h3>Avg Match Score per Job</h3>
          {data.candidates_per_job.length === 0 ? <p className="empty">No data yet.</p> : (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={data.candidates_per_job} margin={{ top: 10, right: 10, left: 0, bottom: 60 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a2a3a" />
                <XAxis dataKey="title" tick={{ fill: '#a0a0b0', fontSize: 12 }} angle={-30} textAnchor="end" interval={0} />
                <YAxis tick={{ fill: '#a0a0b0' }} domain={[0, 100]} />
                <Tooltip
                  contentStyle={{ background: '#1e1e2e', border: '1px solid #2a2a3a', borderRadius: 8 }}
                  labelStyle={{ color: '#fff' }}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.full_title || ''}
                />
                <Bar dataKey="avg_score" name="Avg Score" fill="#6c63ff" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

      </div>
    </div>
  );
};

export default Statistics;
