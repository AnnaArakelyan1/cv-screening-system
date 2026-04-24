import React, { useEffect, useState } from 'react';
import API from '../api';
import './UploadCV.css';

const UploadCV = () => {
  const [file, setFile] = useState(null);
  const [jobId, setJobId] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [jobs, setJobs] = useState([]);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    API.get('/jobs/').then(res => {
      const open = res.data.filter(j => j.is_open);
      setJobs(open);
    }).catch(() => {});
  }, []);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file || !jobId) return;
    setLoading(true);
    setStatus('');
    setResult(null);
    setErrorMessage('');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('job_id', jobId);
    if (fullName.trim()) formData.append('full_name', fullName.trim());
    if (email.trim()) formData.append('email', email.trim());

    try {
      const res = await API.post('/candidates/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResult(res.data);
      setStatus('success');
    } catch (err) {
      setStatus('error');
      setErrorMessage(
        err.response?.data?.detail || 'Upload failed. Please try again.'
      );
    }
    setLoading(false);
  };

  return (
    <div className="page">
      <h1>Upload CV</h1>
      <div className="upload-box">
        <form onSubmit={handleUpload}>
          <select
            value={jobId}
            onChange={e => setJobId(e.target.value)}
            required
            className="job-select"
          >
            <option value="">— Select a job position —</option>
            {jobs.map(j => (
              <option key={j.id} value={j.id}>{j.title}</option>
            ))}
          </select>
          <input
            type="text"
            className="job-select"
            placeholder="Full Name (optional)"
            value={fullName}
            onChange={e => setFullName(e.target.value)}
          />
          <input
            type="email"
            className="job-select"
            placeholder="Email Address (optional)"
            value={email}
            onChange={e => setEmail(e.target.value)}
          />
          <input
            id="cv-upload"
            type="file"
            accept=".pdf,.docx"
            onChange={e => setFile(e.target.files[0])}
            required
          />
          <label htmlFor="cv-upload" className={`upload-file-label ${file ? 'has-file' : ''}`}>
            {file ? `✓  ${file.name}` : '📄  Choose a PDF or DOCX file'}
          </label>
          <button type="submit" disabled={loading || !file || !jobId}>
            {loading ? 'Processing...' : 'Upload & Analyze'}
          </button>
        </form>

        {status === 'error' && (
          <p className="error-msg">{errorMessage}</p>
        )}

        {status === 'success' && result && (
          <div className="result">
            <h3>Parsed Successfully</h3>
            <p><strong>Name:</strong> {result.full_name || 'Not detected'}</p>
            <p><strong>Email:</strong> {result.email || 'Not detected'}</p>
            <p><strong>Phone:</strong> {result.phone || 'Not detected'}</p>
            <p><strong>Skills detected:</strong></p>
            <div className="skills">
              {(result.skills || []).map(s => (
                <span key={s} className="skill-tag">{s}</span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default UploadCV;
