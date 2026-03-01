import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import API from '../api';
import './Jobs.css';

const Jobs = () => {
  const [jobs, setJobs] = useState([]);
  const [form, setForm] = useState({
    title: '', description: '', required_skills: '', required_experience_years: 0, required_education: ''
  });
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const fetchJobs = async () => {
    const res = await API.get('/jobs/');
    setJobs(res.data);
  };

  useEffect(() => { fetchJobs(); }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      await API.post('/jobs/', {
        ...form,
        required_skills: form.required_skills.split(',').map(s => s.trim()).filter(Boolean),
        required_experience_years: parseInt(form.required_experience_years)
      });
      setForm({ title: '', description: '', required_skills: '', required_experience_years: 0, required_education: '' });
      fetchJobs();
    } catch (err) {
      console.error(err);
    }
    setLoading(false);
  };

  return (
    <div className="page">
      <h1>Job Postings</h1>

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
          <button type="submit" disabled={loading}>{loading ? 'Creating...' : 'Create Job'}</button>
        </form>
      </div>

      <div className="job-list">
        {jobs.map(job => (
          <div className="job-card" key={job.id}>
            <h3>{job.title}</h3>
            <p>{job.description}</p>
            <div className="skills">
              {(job.required_skills || []).map(s => <span key={s} className="skill-tag">{s}</span>)}
            </div>
            <button onClick={() => navigate(`/jobs/${job.id}/match`)}>
              View Matched Candidates
            </button>
          </div>
        ))}
      </div>
    </div>
  );
};

export default Jobs;