import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import API from '../api';
import Toast from '../components/Toast';
import './Jobs.css';

const Jobs = () => {
  const [jobs, setJobs] = useState([]);
  const [form, setForm] = useState({
    title: '', description: '', required_skills: '', required_experience_years: 0, required_education: ''
  });
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const navigate = useNavigate();

  const showToast = (message, type = 'success') => setToast({ message, type });

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
      showToast('Job created successfully!', 'success');
    } catch (err) {
      showToast('Failed to create job.', 'error');
    }
    setLoading(false);
  };

  const handleDelete = async (id) => {
    if (!window.confirm('Are you sure you want to delete this job?')) return;
    try {
      await API.delete(`/jobs/${id}`);
      setJobs(jobs.filter(j => j.id !== id));
      showToast('Job deleted successfully.', 'success');
    } catch (err) {
      if (err.response?.status === 403) {
        showToast('You can only delete your own job postings.', 'error');
      } else {
        showToast('Failed to delete job.', 'error');
      }
    }
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
            <button className="delete-btn" onClick={() => handleDelete(job.id)}>
              Delete
            </button>
          </div>
        ))}
      </div>

      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </div>
  );
};

export default Jobs;