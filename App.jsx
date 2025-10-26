import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

const API_BASE_URL = 'http://localhost:5000';

// Gradient background component
const GradientBackground = () => (
  <div className="fixed inset-0 -z-10 overflow-hidden">
    <div 
      className="absolute inset-0"
      style={{
        background: 'linear-gradient(to bottom right, #B8E0F6, #FFE89F, #E0F0FF)'
      }}
    />
    <div 
      className="absolute top-0 left-1/4 w-96 h-96 rounded-full filter blur-3xl animate-blob"
      style={{
        backgroundColor: '#4A9FD8',
        opacity: 0.7
      }}
    />
    <div 
      className="absolute top-0 right-1/4 w-96 h-96 rounded-full filter blur-3xl animate-blob animation-delay-2000"
      style={{
        backgroundColor: '#FFD966',
        opacity: 0.7
      }}
    />
    <div 
      className="absolute bottom-0 left-1/3 w-96 h-96 rounded-full filter blur-3xl animate-blob animation-delay-4000"
      style={{
        backgroundColor: '#6BB3E0',
        opacity: 0.6
      }}
    />
  </div>
);

// Header Component
const Header = () => (
  <header 
    className="w-full py-6 px-8 backdrop-blur-md shadow-sm"
    style={{ backgroundColor: 'rgba(255, 255, 255, 0.7)' }}
  >
    <div className="max-w-7xl mx-auto flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div 
          className="w-12 h-12 rounded-xl flex items-center justify-center shadow-lg"
          style={{
            background: 'linear-gradient(to bottom right, #4A9FD8, #2E6FA8)'
          }}
        >
          <span className="text-white font-bold text-2xl">C</span>
        </div>
        <div>
          <h1 
            className="text-3xl font-bold"
            style={{
              background: 'linear-gradient(to right, #2E6FA8, #4A9FD8)',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              backgroundClip: 'text'
            }}
          >
            classif.ai
          </h1>
          <p className="text-xs font-medium" style={{ color: '#374151' }}>AI-Powered Proof Grading</p>
        </div>
      </div>
      <div className="flex items-center gap-4">
        <span className="text-sm font-medium" style={{ color: '#374151' }}>Powered by Claude</span>
      </div>
    </div>
  </header>
);

// Upload Zone Component
const UploadZone = ({ onFileSelect, isProcessing }) => {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = React.useRef(null);

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith('image/')) {
      onFileSelect(file);
    }
  };

  const handleFileInput = (e) => {
    const file = e.target.files[0];
    if (file) {
      onFileSelect(file);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-2xl mx-auto"
    >
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isProcessing && fileInputRef.current?.click()}
        className={`relative border-4 border-dashed rounded-3xl p-12 text-center cursor-pointer transition-all duration-300 shadow-xl ${isProcessing ? 'opacity-50 pointer-events-none' : ''}`}
        style={{
          borderColor: isDragging ? '#2E6FA8' : '#4A9FD8',
          backgroundColor: isDragging ? '#D5EDFA' : '#FFFFFF',
          transform: isDragging ? 'scale(1.05)' : 'scale(1)'
        }}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept="image/*"
          onChange={handleFileInput}
          className="hidden"
          disabled={isProcessing}
        />
        
        <div className="flex flex-col items-center gap-4">
          <div 
            className="w-24 h-24 rounded-3xl flex items-center justify-center shadow-2xl"
            style={{
              background: 'linear-gradient(to bottom right, #4A9FD8, #2E6FA8)'
            }}
          >
            <svg className="w-12 h-12 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
            </svg>
          </div>
          
          <div>
            <p className="text-2xl font-bold mb-2" style={{ color: '#111827' }}>
              Drop your proof image here
            </p>
            <p className="text-base font-medium" style={{ color: '#374151' }}>
              or click to browse • PNG, JPG, GIF up to 10MB
            </p>
          </div>
          
          <motion.button
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.95 }}
            className="mt-4 px-10 py-4 text-white text-lg rounded-2xl font-bold shadow-2xl transition-all"
            style={{
              background: 'linear-gradient(to right, #4A9FD8, #2E6FA8)'
            }}
            onClick={(e) => {
              e.stopPropagation();
              fileInputRef.current?.click();
            }}
            disabled={isProcessing}
          >
            Choose File
          </motion.button>
        </div>
      </div>
    </motion.div>
  );
};

// Processing Status Component
const ProcessingStatus = ({ progress, message }) => (
  <motion.div
    initial={{ opacity: 0, scale: 0.9 }}
    animate={{ opacity: 1, scale: 1 }}
    className="w-full max-w-2xl mx-auto rounded-3xl p-10 shadow-2xl"
    style={{
      backgroundColor: '#FFFFFF',
      border: '2px solid #4A9FD8'
    }}
  >
    <div className="flex items-center gap-6 mb-8">
      <div className="relative">
        <div 
          className="w-20 h-20 rounded-full"
          style={{
            border: '6px solid #D5EDFA'
          }}
        />
        <div 
          className="absolute inset-0 w-20 h-20 rounded-full animate-spin"
          style={{
            border: '6px solid #4A9FD8',
            borderTopColor: 'transparent',
            borderRightColor: 'transparent'
          }}
        />
      </div>
      <div className="flex-1">
        <h3 className="text-2xl font-bold mb-2" style={{ color: '#111827' }}>Processing Your Proof</h3>
        <p className="text-base font-medium" style={{ color: '#374151' }}>{message}</p>
      </div>
    </div>
    
    <div 
      className="w-full rounded-full h-4 overflow-hidden"
      style={{
        backgroundColor: '#D5EDFA',
        border: '2px solid #4A9FD8'
      }}
    >
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${progress}%` }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
        className="h-full rounded-full"
        style={{
          background: 'linear-gradient(to right, #4A9FD8, #6BB3E0)'
        }}
      />
    </div>
    <p className="text-right text-base font-bold mt-3" style={{ color: '#1F2937' }}>{progress}%</p>
  </motion.div>
);

// Results View Component
const ResultsView = ({ results, annotatedImageUrl, onReset }) => {
  const getGradeColor = (grade) => {
    if (grade.startsWith('A')) return 'linear-gradient(to bottom right, #10b981, #059669)';
    if (grade.startsWith('B')) return 'linear-gradient(to bottom right, #4A9FD8, #2E6FA8)';
    if (grade.startsWith('C')) return 'linear-gradient(to bottom right, #FFD966, #FFA500)';
    return 'linear-gradient(to bottom right, #ef4444, #dc2626)';
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="w-full max-w-6xl mx-auto space-y-6"
    >
      {/* Grade Card */}
      <div 
        className="rounded-3xl p-10 shadow-2xl"
        style={{
          backgroundColor: '#FFFFFF',
          border: '2px solid #4A9FD8'
        }}
      >
        <div className="flex items-center justify-between mb-8">
          <h2 className="text-3xl font-bold" style={{ color: '#111827' }}>Grading Results</h2>
          <motion.button
            whileHover={{ scale: 1.08 }}
            whileTap={{ scale: 0.95 }}
            onClick={onReset}
            className="px-8 py-3 text-white text-lg rounded-xl font-bold transition-all shadow-lg"
            style={{
              background: 'linear-gradient(to right, #4A9FD8, #2E6FA8)'
            }}
          >
            Grade Another
          </motion.button>
        </div>
        
        <div className="flex items-center gap-8">
          <div 
            className="w-40 h-40 rounded-3xl flex items-center justify-center shadow-2xl"
            style={{
              background: getGradeColor(results.total_grade),
              border: '4px solid white'
            }}
          >
            <span className="text-6xl font-bold text-white">{results.total_grade}</span>
          </div>
          <div>
            <h3 className="text-2xl font-bold mb-3" style={{ color: '#111827' }}>Overall Grade</h3>
            <p className="text-lg font-medium" style={{ color: '#374151' }}>
              {results.sections.length === 0 
                ? 'Perfect! No errors found.' 
                : `${results.sections.length} issue${results.sections.length !== 1 ? 's' : ''} identified`
              }
            </p>
          </div>
        </div>
      </div>

      {/* Annotated Image */}
      <div 
        className="rounded-3xl p-10 shadow-2xl"
        style={{
          backgroundColor: '#FFFFFF',
          border: '2px solid #FFD966'
        }}
      >
        <h3 className="text-2xl font-bold mb-6" style={{ color: '#111827' }}>Annotated Proof</h3>
        <div 
          className="rounded-2xl overflow-hidden shadow-lg"
          style={{
            border: '4px solid #FFD966'
          }}
        >
          <img 
            src={`${API_BASE_URL}${annotatedImageUrl}`}
            alt="Annotated proof"
            className="w-full h-auto"
          />
        </div>
      </div>

      {/* Errors List */}
      {results.sections.length > 0 && (
        <div 
          className="rounded-3xl p-10 shadow-2xl"
          style={{
            backgroundColor: '#FFFFFF',
            border: '2px solid #f87171'
          }}
        >
          <h3 className="text-2xl font-bold mb-6" style={{ color: '#111827' }}>Identified Issues</h3>
          <div className="space-y-4">
            {results.sections.map((error, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.1 }}
                className="flex gap-4 p-6 rounded-xl shadow-md"
                style={{
                  backgroundColor: '#fee2e2',
                  borderLeft: '8px solid #dc2626'
                }}
              >
                <div 
                  className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center font-bold text-lg text-white shadow-lg"
                  style={{
                    backgroundColor: '#dc2626'
                  }}
                >
                  {error.number}
                </div>
                <div className="flex-1">
                  <p className="font-medium text-lg" style={{ color: '#111827' }}>{error.error}</p>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
};

// Main App Component
export default function App() {
  const [currentStep, setCurrentStep] = useState('upload');
  const [jobId, setJobId] = useState(null);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState('');
  const [results, setResults] = useState(null);

  const handleFileSelect = async (file) => {
    try {
      setCurrentStep('processing');
      setProgress(10);
      setMessage('Uploading your proof...');

      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(`${API_BASE_URL}/api/grade`, {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) throw new Error('Upload failed');
      
      const data = await response.json();
      const { jobId: newJobId } = data;
      setJobId(newJobId);

      pollJobStatus(newJobId);
    } catch (error) {
      console.error('Upload failed:', error);
      alert('Failed to upload file. Please try again.');
      setCurrentStep('upload');
    }
  };

  const pollJobStatus = async (id) => {
    const interval = setInterval(async () => {
      try {
        const statusResponse = await fetch(`${API_BASE_URL}/api/grade/${id}`);
        if (!statusResponse.ok) throw new Error('Status check failed');
        
        const statusData = await statusResponse.json();
        const { status, progress: newProgress, message: newMessage } = statusData;

        setProgress(newProgress);
        setMessage(newMessage);

        if (status === 'done') {
          clearInterval(interval);
          const resultsResponse = await fetch(`${API_BASE_URL}/api/results/${id}`);
          if (!resultsResponse.ok) throw new Error('Results fetch failed');
          
          const resultsData = await resultsResponse.json();
          setResults(resultsData);
          setCurrentStep('results');
        } else if (status === 'failed') {
          clearInterval(interval);
          alert('Processing failed. Please try again.');
          setCurrentStep('upload');
        }
      } catch (error) {
        clearInterval(interval);
        console.error('Status check failed:', error);
        alert('Failed to check status. Please try again.');
        setCurrentStep('upload');
      }
    }, 1000);
  };

  const handleReset = () => {
    setCurrentStep('upload');
    setJobId(null);
    setProgress(0);
    setMessage('');
    setResults(null);
  };

  return (
    <div className="min-h-screen relative">
      <GradientBackground />
      <Header />
      
      <main className="container mx-auto px-4 py-12">
        <AnimatePresence mode="wait">
          {currentStep === 'upload' && (
            <motion.div
              key="upload"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-8"
            >
              <div className="text-center mb-12">
                <h2 className="text-5xl md:text-6xl font-bold mb-4" style={{ color: '#111827' }}>
                  Grade Your Mathematical Proofs
                </h2>
                <p className="text-2xl font-medium" style={{ color: '#1F2937' }}>
                  Upload a proof image and get instant AI-powered feedback
                </p>
              </div>
              <UploadZone onFileSelect={handleFileSelect} isProcessing={false} />
            </motion.div>
          )}

          {currentStep === 'processing' && (
            <motion.div
              key="processing"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <ProcessingStatus progress={progress} message={message} />
            </motion.div>
          )}

          {currentStep === 'results' && results && (
            <motion.div
              key="results"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <ResultsView 
                results={results} 
                annotatedImageUrl={results.pdfAnnotatedUrl} 
                onReset={handleReset} 
              />
            </motion.div>
          )}
        </AnimatePresence>
      </main>
      
      <style jsx>{`
        @keyframes blob {
          0%, 100% { transform: translate(0, 0) scale(1); }
          25% { transform: translate(20px, -50px) scale(1.1); }
          50% { transform: translate(-20px, 20px) scale(0.9); }
          75% { transform: translate(50px, 50px) scale(1.05); }
        }
        .animate-blob {
          animation: blob 7s infinite;
        }
        .animation-delay-2000 {
          animation-delay: 2s;
        }
        .animation-delay-4000 {
          animation-delay: 4s;
        }
      `}</style>
    </div>
  );
}
