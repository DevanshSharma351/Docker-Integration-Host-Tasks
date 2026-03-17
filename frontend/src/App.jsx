import { useState } from 'react';
import { AuthProvider, useAuth } from './context/AuthContext';
import Login from './components/Login';
import Register from './components/Register';
import Dashboard from './components/Dashboard';

function AppContent() {
  const { user, loading } = useAuth();
  const [showRegister, setShowRegister] = useState(false);

  if (loading) {
    return <div className="flex justify-center items-center h-screen">Loading...</div>;
  }

  if (!user) {
    return (
      <div className="min-h-screen bg-gray-100 py-8">
        <div className="text-center mb-4">
          <h1 className="text-3xl font-bold mb-2">Docker Integration Host</h1>
          <p className="text-gray-600">Manage containers across multiple hosts</p>
        </div>
        
        <div className="text-center mb-4">
          <button
            onClick={() => setShowRegister(!showRegister)}
            className="text-blue-500 underline"
          >
            {showRegister ? 'Already have an account? Login' : "Don't have an account? Register"}
          </button>
        </div>

        {showRegister ? <Register /> : <Login />}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <Dashboard />
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
