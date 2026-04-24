import React, { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import './Apply.css';

const API_BASE = 'http://localhost:8000';

const Apply = () => {
  const { jobId } = useParams();
  const [job, setJob] = useState(null);
  const [file, setFile] = useState(null);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('idle');
  const [errorMsg, setErrorMsg] = useState('');

  useEffect(() => {
    axios.get(`${API_BASE}/jobs/${jobId}/public`)
      .then(res => setJob(res.data))
      .catch(() => setJob(null));
  }, [jobId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!file) return;
    setStatus('loading');
    setErrorMsg('');

    const formData = new FormData();
    formData.append('file', file);
    if (fullName.trim()) formData.append('full_name', fullName.trim());
    if (email.trim()) formData.append('email', email.trim());

    try {
      await axios.post(`${API_BASE}/jobs/${jobId}/apply`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setStatus('success');
    } catch (err) {
      setStatus('error');
      setErrorMsg(err.response?.data?.detail || 'Something went wrong. Please try again.');
    }
  };

  if (!job) return (
    <div className="apply-container">
      <div className="apply-box">
        <p className="apply-not-found">Job not found or no longer available.</p>
      </div>
    </div>
  );

  if (job.is_open === false) return (
    <div className="apply-container">
      <div className="apply-box apply-closed-box">
        <div className="apply-closed-icon">✕</div>
        <h2>Position Closed</h2>
        <p><strong>{job.title}</strong> is no longer accepting applications.</p>
      </div>
    </div>
  );

  if (status === 'success') return (
    <div className="apply-container">
      <div className="apply-box apply-success-box">
        <div className="apply-success-icon">✓</div>
        <h2>Application Received!</h2>
        <p>Thank you for applying for <strong>{job.title}</strong>.</p>
        <p>Our HR team will review your profile and get back to you soon.</p>
      </div>
    </div>
  );

  return (
    <div className="apply-container">
      <div className="apply-box">
        <div className="apply-header">
          <span className="apply-badge">Now Hiring</span>
          <h1>{job.title}</h1>
        </div>

        <div className="apply-description">
          <p>{job.description}</p>
        </div>

        {job.required_skills?.length > 0 && (
          <div className="apply-skills">
            <h4>Required Skills</h4>
            <div className="skills">
              {job.required_skills.map(s => (
                <span key={s} className="skill-tag">{s}</span>
              ))}
            </div>
          </div>
        )}

        {(job.required_experience_years > 0 || job.required_education || job.deadline) && (
          <div className="apply-meta">
            {job.required_experience_years > 0 && (
              <span>Experience: {job.required_experience_years}+ years</span>
            )}
            {job.required_education && (
              <span>Education: {job.required_education}</span>
            )}
            {job.deadline && (
              <span className={job.deadline_passed ? 'apply-deadline-passed' : 'apply-deadline'}>
                Deadline: {new Date(job.deadline).toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' })}
                {job.deadline_passed ? ' (Passed)' : ''}
              </span>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} className="apply-form">
          <h3>Your Details</h3>
          <input
            type="text"
            className="apply-input"
            placeholder="Full Name"
            value={fullName}
            onChange={e => setFullName(e.target.value)}
          />
          <input
            type="email"
            className="apply-input"
            placeholder="Email Address"
            value={email}
            onChange={e => setEmail(e.target.value)}
          />
          <div className="apply-upload-area">
            <input
              type="file"
              accept=".pdf,.docx"
              onChange={e => setFile(e.target.files[0])}
              required
              id="cv-file"
            />
            <label htmlFor="cv-file" className="upload-label">
              {file ? file.name : 'Choose PDF or DOCX file'}
            </label>
          </div>
          {errorMsg && <p className="apply-error">{errorMsg}</p>}
          <button type="submit" disabled={status === 'loading' || !file} className="apply-btn">
            {status === 'loading' ? 'Submitting...' : 'Apply Now'}
          </button>
        </form>
      </div>
    </div>
  );
};

export default Apply;
