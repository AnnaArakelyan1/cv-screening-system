import React, { useState } from 'react';
import API from '../api';
import './UploadCV.css';

const UploadCV = () => {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    setStatus('');
    setResult(null);
    setErrorMessage('');

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await API.post('/candidates/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setResult(res.data);
      setStatus('success');
    } catch (err) {
      setStatus('error');
      if (err.response?.status === 409) {
        setErrorMessage(err.response.data.detail);
      } else if (err.response?.status === 400) {
        setErrorMessage(err.response.data.detail);
      } else {
        setErrorMessage('Upload failed. Please try again.');
      }
    }
    setLoading(false);
  };

  return (
    <div className="page">
      <h1>Upload CV</h1>
      <div className="upload-box">
        <form onSubmit={handleUpload}>
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={e => setFile(e.target.files[0])}
            required
          />
          <button type="submit" disabled={loading}>
            {loading ? 'Processing...' : 'Upload & Analyze'}
          </button>
        </form>

        {status === 'error' && (
          <p className="error-msg">{errorMessage}</p>
        )}

        {status === 'success' && result && (
          <div className="result">
            <h3>✅ Parsed Successfully!</h3>
            <p><strong>Name:</strong> {result.full_name || 'Not detected'}</p>
            <p><strong>Email:</strong> {result.email || 'Not detected'}</p>
            <p><strong>Phone:</strong> {result.phone || 'Not detected'}</p>
            <p><strong>Skills:</strong></p>
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